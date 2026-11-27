//! Running a job: the tree goes out as tasks, each task comes back as a block
//! of lines, and the blocks are written in order.
//!
//! While it runs the program reports on stderr, one line at a time:
//!
//! ```text
//! P <lines looked at> <lines written> <bytes the dedup set holds>     about ten times a second
//! R {"written":..,"processed":..,"stopped_by":..,"memory":..,"dedup":..}   once, at the end
//! E job|io <message>                                                  instead of R, when it fails
//! ```
//!
//! A `stop` line on stdin ends the run early; what was written stays, and it
//! is always a whole number of lines from the start of the full output.

use std::fs::File;
use std::io::{self, BufRead, BufWriter, Write};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::dedup::Seen;
use crate::spec::Spec;
use crate::walk::{Block, Plan, Splitter, Walker};
use crate::Failure;

const REPORT_EVERY: Duration = Duration::from_millis(100);

/// The numbers a progress line carries.
#[derive(Default)]
struct Meter {
    processed: AtomicU64,
    written: AtomicU64,
    memory: AtomicU64,
}

pub fn generate(spec: &Spec) -> Result<(), Failure> {
    if spec.gzip {
        return Err(Failure::Job("gzip output is not done here".into()));
    }
    let plan = Plan::new(spec)?;
    let stop = Arc::new(AtomicBool::new(false));
    watch_stdin(Arc::clone(&stop));
    let meter = Arc::new(Meter::default());
    let reporter = Reporter::start(Arc::clone(&meter), Arc::clone(&stop));

    let mut sink = Sink::new(
        BufWriter::with_capacity(1 << 20, output()?),
        spec,
        &plan,
        Arc::clone(&meter),
    );
    let finished = run(&plan, &stop, &mut sink)?;
    sink.out.flush()?;

    reporter.finish();
    let stopped_by = match sink.ended {
        Some(reason) => format!("\"{reason}\""),
        None if !finished => "\"user\"".to_string(),
        None => "null".to_string(),
    };
    let summary =
        format!(
        "R {{\"written\":{},\"processed\":{},\"stopped_by\":{},\"memory\":{},\"dedup\":\"{}\"}}\n",
        sink.written,
        sink.processed,
        stopped_by,
        sink.memory(),
        if sink.seen.is_some() { "memory" } else { "none" },
    );
    io::stderr().write_all(summary.as_bytes())?;
    Ok(())
}

/// Does the tasks one after another. True when the whole tree was done.
fn run(plan: &Plan, stop: &AtomicBool, sink: &mut Sink<impl Write>) -> io::Result<bool> {
    let mut splitter = Splitter::new(plan.budget());
    let mut walker = Walker::new(plan, sink.seen.is_some());
    let mut block = Block::default();
    while sink.ended.is_none() {
        if stop.load(Ordering::Relaxed) {
            return Ok(false);
        }
        let Some(task) = splitter.next(plan) else {
            return Ok(true);
        };
        block.clear();
        walker.fill(&task, &mut block);
        sink.take(&block)?;
    }
    Ok(true)
}

/// Where the blocks end up: drops repeats, stops at the limit, writes the rest.
struct Sink<W: Write> {
    out: W,
    seen: Option<Seen>,
    limit: Option<u64>,
    maxmem: Option<u64>,
    newline: usize,
    written: u64,
    processed: u64,
    /// Why the run should end here, once it should: "limit" or "memory".
    ended: Option<&'static str>,
    meter: Arc<Meter>,
}

impl<W: Write> Sink<W> {
    fn new(out: W, spec: &Spec, plan: &Plan, meter: Arc<Meter>) -> Sink<W> {
        Sink {
            out,
            seen: spec.dedup.then(Seen::new),
            limit: spec.limit.filter(|&limit| limit > 0),
            maxmem: spec.maxmem.filter(|&bytes| bytes > 0),
            newline: plan.newline,
            written: 0,
            processed: 0,
            ended: None,
            meter,
        }
    }

    fn memory(&self) -> u64 {
        self.seen.as_ref().map_or(0, Seen::memory)
    }

    /// Takes the next block of the output.
    fn take(&mut self, block: &Block) -> io::Result<()> {
        // lines that may still be written before the limit
        let room = self.limit.map_or(u64::MAX, |limit| limit - self.written);
        let mut looked_at = block.lines;
        let mut kept = block.lines;
        match &mut self.seen {
            None if block.lines >= room => {
                self.out
                    .write_all(&block.bytes[..end_of_line(&block.bytes, room)])?;
                looked_at = room;
                kept = room;
                self.ended = Some("limit");
            }
            None => self.out.write_all(&block.bytes)?,
            Some(seen) => {
                kept = 0;
                let mut start = 0; // of the line at hand
                let mut pending = 0; // start of the kept lines not written yet
                for (index, (&end, &hash)) in block.ends.iter().zip(&block.hashes).enumerate() {
                    let end = end as usize;
                    if seen.insert(hash, &block.bytes[start..end - self.newline]) {
                        kept += 1;
                        if kept == room {
                            looked_at = index as u64 + 1;
                            self.ended = Some("limit");
                            start = end;
                            break;
                        }
                    } else {
                        self.out.write_all(&block.bytes[pending..start])?;
                        pending = end;
                    }
                    start = end;
                }
                self.out.write_all(&block.bytes[pending..start])?;
            }
        }
        self.written += kept;
        self.processed += looked_at;
        let memory = self.memory();
        if self.ended.is_none() && self.maxmem.is_some_and(|most| memory >= most) {
            self.ended = Some("memory");
        }
        self.meter
            .processed
            .store(self.processed, Ordering::Relaxed);
        self.meter.written.store(self.written, Ordering::Relaxed);
        self.meter.memory.store(memory, Ordering::Relaxed);
        Ok(())
    }
}

/// Where line number `count` (from one) ends. No line holds a line feed of its own.
fn end_of_line(bytes: &[u8], count: u64) -> usize {
    let mut left = count;
    for (at, &byte) in bytes.iter().enumerate() {
        if byte == b'\n' {
            left -= 1;
            if left == 0 {
                return at + 1;
            }
        }
    }
    bytes.len()
}

/// Writes the progress lines until told to finish.
struct Reporter {
    done: mpsc::Sender<()>,
    thread: thread::JoinHandle<()>,
}

impl Reporter {
    fn start(meter: Arc<Meter>, stop: Arc<AtomicBool>) -> Reporter {
        let (done, wait) = mpsc::channel::<()>();
        let thread = thread::spawn(move || loop {
            let line = format!(
                "P {} {} {}\n",
                meter.processed.load(Ordering::Relaxed),
                meter.written.load(Ordering::Relaxed),
                meter.memory.load(Ordering::Relaxed),
            );
            if io::stderr().write_all(line.as_bytes()).is_err() {
                // nobody is listening any more: wind the run down
                stop.store(true, Ordering::Relaxed);
                return;
            }
            if wait.recv_timeout(REPORT_EVERY) != Err(RecvTimeoutError::Timeout) {
                return;
            }
        });
        Reporter { done, thread }
    }

    fn finish(self) {
        drop(self.done);
        let _ = self.thread.join();
    }
}

/// Sets `stop` when a `stop` line arrives on stdin.
fn watch_stdin(stop: Arc<AtomicBool>) {
    thread::spawn(move || {
        let mut line = String::new();
        loop {
            line.clear();
            match io::stdin().lock().read_line(&mut line) {
                Ok(0) | Err(_) => return,
                Ok(_) if line.trim() == "stop" => {
                    stop.store(true, Ordering::Relaxed);
                    return;
                }
                Ok(_) => {}
            }
        }
    });
}

/// Standard output as a plain file: the caller points it at the output file.
#[cfg(windows)]
fn output() -> io::Result<File> {
    use std::os::windows::io::AsHandle;
    Ok(File::from(io::stdout().as_handle().try_clone_to_owned()?))
}

#[cfg(not(windows))]
fn output() -> io::Result<File> {
    use std::os::fd::AsFd;
    Ok(File::from(io::stdout().as_fd().try_clone_to_owned()?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spec::Mods;
    use crate::text::Table;

    fn spec(words: &[&str], max: u64) -> Spec {
        Spec {
            command: "generate".into(),
            words: words.iter().map(|word| word.to_string()).collect(),
            min: 1,
            max: Some(max),
            start: String::new(),
            end: String::new(),
            mods: Mods::default(),
            dedup: true,
            limit: None,
            maxmem: None,
            gzip: false,
            newline: b"\r\n".to_vec(),
            threads: 1,
            table: Table::new(),
            lines: Vec::new(),
        }
    }

    /// Runs a job into memory: (output, written, processed, why it ended).
    fn outcome(spec: &Spec) -> (String, u64, u64, Option<&'static str>) {
        let plan = Plan::new(spec).unwrap();
        let mut sink = Sink::new(Vec::new(), spec, &plan, Arc::new(Meter::default()));
        assert!(run(&plan, &AtomicBool::new(false), &mut sink).unwrap());
        (
            String::from_utf8(sink.out).unwrap(),
            sink.written,
            sink.processed,
            sink.ended,
        )
    }

    #[test]
    fn repeats_are_written_once() {
        let (out, written, processed, ended) = outcome(&spec(&["a", "a", "b"], 2));
        assert_eq!(out, "a\r\nb\r\naa\r\nab\r\nba\r\nbb\r\n");
        assert_eq!((written, processed, ended), (6, 12, None));
    }

    #[test]
    fn repeats_stay_without_dedup() {
        let mut job = spec(&["a", "a"], 2);
        job.dedup = false;
        let (out, written, processed, _) = outcome(&job);
        assert_eq!(out, "a\r\na\r\naa\r\naa\r\naa\r\naa\r\n");
        assert_eq!((written, processed), (6, 6));
    }

    #[test]
    fn the_limit_counts_written_lines() {
        let mut job = spec(&["a", "a", "b"], 2);
        job.limit = Some(4);
        // a, (a), b, aa, (aa), ab: the fourth new line is the sixth one looked at
        let (out, written, processed, ended) = outcome(&job);
        assert_eq!(out, "a\r\nb\r\naa\r\nab\r\n");
        assert_eq!((written, processed, ended), (4, 6, Some("limit")));

        job.dedup = false;
        let (out, written, processed, ended) = outcome(&job);
        assert_eq!(out, "a\r\na\r\nb\r\naa\r\n");
        assert_eq!((written, processed, ended), (4, 4, Some("limit")));
    }

    #[test]
    fn a_limit_on_the_last_line_still_counts_as_the_reason() {
        let mut job = spec(&["a", "b"], 1);
        job.limit = Some(2);
        assert_eq!(outcome(&job).3, Some("limit"));
        job.limit = Some(3);
        assert_eq!(outcome(&job).3, None);
    }

    #[test]
    fn the_memory_cap_ends_the_run() {
        let mut job = spec(&["a", "b", "c", "d"], 9);
        job.maxmem = Some(64 * 1024);
        let (out, written, _, ended) = outcome(&job);
        assert_eq!(ended, Some("memory"));
        assert_eq!(out.lines().count() as u64, written);
        assert!(written < 4 + 16 + 64 + 256 + 1024 + 4096 + 16384 + 65536 + 262_144);
    }

    #[test]
    fn stop_ends_the_run_between_tasks() {
        let job = spec(&["a", "b"], 3);
        let plan = Plan::new(&job).unwrap();
        let mut sink = Sink::new(Vec::new(), &job, &plan, Arc::new(Meter::default()));
        assert!(!run(&plan, &AtomicBool::new(true), &mut sink).unwrap());
        assert_eq!(sink.written, 0);
    }

    #[test]
    fn line_ends_are_found_by_count() {
        assert_eq!(end_of_line(b"a\r\nbb\r\nc\r\n", 1), 3);
        assert_eq!(end_of_line(b"a\r\nbb\r\nc\r\n", 2), 7);
        assert_eq!(end_of_line(b"a\r\nbb\r\nc\r\n", 3), 10);
    }
}
