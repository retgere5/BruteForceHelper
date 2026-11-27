//! Running a job: the tree goes out as tasks, each task comes back as a block
//! of lines, and the blocks are written in order.
//!
//! While it runs the program reports on stderr, one line at a time:
//!
//! ```text
//! P <lines looked at> <lines written> <bytes the dedup set holds>     about ten times a second
//! R {"written":..,"processed":..,"stopped_by":..,"memory":..,"dedup":..,"threads":..}   at the end
//! E job|io <message>                                                  instead of R, when it fails
//! ```
//!
//! A `stop` line on stdin ends the run early; what was written stays, and it
//! is always a whole number of lines from the start of the full output.

use std::collections::HashMap;
use std::fs::File;
use std::io::{self, BufRead, BufWriter, Write};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::Duration;

use crate::dedup::Seen;
use crate::sardinas::spells_each_line_once;
use crate::spec::Spec;
use crate::walk::{Block, Plan, Splitter, Task, Walker};
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

    let threads = match spec.threads {
        0 => thread::available_parallelism().map_or(1, |count| count.get()),
        count => count,
    };
    // without variations, words that spell every line one way cannot repeat a line
    let words: Vec<&[u8]> = spec.words.iter().map(String::as_bytes).collect();
    let dedup = if !spec.dedup {
        "none"
    } else if plan.shapes.len() == 1 && spells_each_line_once(&words) {
        "unneeded"
    } else {
        "memory"
    };
    let mut sink = Sink::new(
        BufWriter::with_capacity(1 << 20, output()?),
        spec,
        &plan,
        Arc::clone(&meter),
        dedup == "memory",
        threads,
    );
    let finished = run(&plan, &stop, &mut sink, threads)?;
    sink.out.flush()?;

    reporter.finish();
    let stopped_by = match sink.ended {
        Some(reason) => format!("\"{reason}\""),
        None if !finished => "\"user\"".to_string(),
        None => "null".to_string(),
    };
    let summary = format!(
        "R {{\"written\":{},\"processed\":{},\"stopped_by\":{stopped_by},\"memory\":{},\
         \"dedup\":\"{dedup}\",\"threads\":{threads}}}\n",
        sink.written,
        sink.processed,
        sink.memory(),
    );
    io::stderr().write_all(summary.as_bytes())?;
    Ok(())
}

/// Does the job on `threads` threads. True when the whole tree was done,
/// false when a stop request cut it short.
fn run(
    plan: &Plan,
    stop: &AtomicBool,
    sink: &mut Sink<impl Write>,
    threads: usize,
) -> io::Result<bool> {
    if threads > 1 {
        return run_in_parallel(plan, stop, sink, threads);
    }
    let mut splitter = Splitter::new(plan.budget());
    let mut walker = Walker::new(plan, sink.remembers());
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
        block = sink.take(block)?;
    }
    Ok(true)
}

/// Tasks a thread may have out before the oldest one is written.
const WINDOW_PER_THREAD: usize = 4;

/// The tasks, shared by the threads that build them.
///
/// Blocks are written in task order, so a block that is ready early has to
/// wait for the ones before it. No more than `window` tasks are out at a time
/// (handed out, not yet written): that bounds the memory waiting blocks take,
/// however uneven the tasks are.
struct Feed {
    state: Mutex<FeedState>,
    room: Condvar,
    window: usize,
}

struct FeedState {
    splitter: Splitter,
    out: usize,
    closed: bool,
    exhausted: bool,
}

impl Feed {
    /// The next task, once there is room for it; None when no more should start.
    fn next(&self, plan: &Plan, stop: &AtomicBool) -> Option<Task> {
        let mut state = self.state.lock().unwrap();
        loop {
            if state.closed || stop.load(Ordering::Relaxed) {
                return None;
            }
            if state.out < self.window {
                break;
            }
            state = self.room.wait(state).unwrap();
        }
        let task = state.splitter.next(plan);
        match task {
            Some(_) => state.out += 1,
            None => state.exhausted = true,
        }
        task
    }

    /// A task's block has been dealt with; `close` when no more are wanted.
    fn done(&self, close: bool) {
        let mut state = self.state.lock().unwrap();
        state.out -= 1;
        state.closed |= close;
        self.room.notify_all();
    }
}

fn run_in_parallel(
    plan: &Plan,
    stop: &AtomicBool,
    sink: &mut Sink<impl Write>,
    threads: usize,
) -> io::Result<bool> {
    let hashing = sink.remembers();
    let feed = Feed {
        state: Mutex::new(FeedState {
            splitter: Splitter::new(plan.budget()),
            out: 0,
            closed: false,
            exhausted: false,
        }),
        room: Condvar::new(),
        window: threads * WINDOW_PER_THREAD,
    };
    // written blocks go back to the threads, so their buffers are reused
    let spare = Mutex::new(Vec::<Block>::new());
    let (ready, blocks) = mpsc::channel::<Block>();
    let mut failure = None;
    thread::scope(|scope| {
        for _ in 0..threads {
            let ready = ready.clone();
            let (feed, spare) = (&feed, &spare);
            scope.spawn(move || {
                let mut walker = Walker::new(plan, hashing);
                while let Some(task) = feed.next(plan, stop) {
                    let mut block = spare.lock().unwrap().pop().unwrap_or_default();
                    block.clear();
                    block.seq = task.seq;
                    walker.fill(&task, &mut block);
                    if ready.send(block).is_err() {
                        return;
                    }
                }
            });
        }
        drop(ready);
        // this thread puts the blocks back in order and writes them
        let mut early: HashMap<u64, Block> = HashMap::new();
        let mut turn = 0;
        for block in blocks {
            early.insert(block.seq, block);
            while let Some(block) = early.remove(&turn) {
                turn += 1;
                let used = if failure.is_none() && sink.ended.is_none() {
                    sink.take(block)
                } else {
                    Ok(block)
                };
                match used {
                    Ok(block) => spare.lock().unwrap().push(block),
                    Err(error) => failure = Some(error),
                }
                feed.done(failure.is_some() || sink.ended.is_some());
            }
        }
    });
    match failure {
        Some(error) => Err(error),
        None => Ok(feed.state.into_inner().unwrap().exhausted || sink.ended.is_some()),
    }
}

/// How a run keeps repeats out of its output.
enum Dedup {
    /// It does not: the job asked for none, or no line can repeat.
    Off,
    /// One set, looked up by the thread that writes.
    Here(Seen, Finder),
    /// One set per thread; a line belongs to the set its hash picks.
    Shards(Shards),
}

/// Most lines the sets are sized for at the start (64 MB of table); past
/// that they grow.
const SIZED_FOR: u64 = 4 << 20;
/// Most threads that look lines up at once.
const MOST_SHARDS: usize = 8;
/// Lines looked up together.
const BATCH: usize = 32;

/// Scratch space of one thread that looks lines up.
#[derive(Default)]
struct Finder {
    mine: Vec<u32>,
    slots: Vec<u64>,
}

impl Finder {
    /// Looks up the lines of `block` whose hash picks set number `me` of
    /// `sets`, adds the new ones to `seen` and lists the others in `repeats`.
    fn find(
        &mut self,
        seen: &mut Seen,
        block: &Block,
        newline: usize,
        (me, sets): (usize, usize),
        repeats: &mut Vec<u32>,
    ) {
        self.mine.clear();
        for (line, &hash) in block.hashes.iter().enumerate() {
            if set_of(hash, sets) == me {
                self.mine.push(line as u32);
            }
        }
        self.slots.resize(BATCH, 0);
        for batch in self.mine.chunks(BATCH) {
            // A lookup misses the cache twice: at its slot, and at the line the
            // slot points to. Both are read for the whole batch before any line is
            // looked up, so the misses overlap instead of being waited out in turn.
            for (slot, &line) in self.slots.iter_mut().zip(batch) {
                *slot = seen.peek(block.hashes[line as usize]);
            }
            let glanced = self.slots.iter().zip(batch).fold(0, |all, (&slot, &line)| {
                all ^ seen.glance(block.hashes[line as usize], slot)
            });
            std::hint::black_box(glanced);
            for &line in batch {
                let at = line as usize;
                let start = if at == 0 {
                    0
                } else {
                    block.ends[at - 1] as usize
                };
                let end = block.ends[at] as usize - newline;
                if !seen.insert(block.hashes[at], &block.bytes[start..end]) {
                    repeats.push(line);
                }
            }
        }
    }
}

/// The set a hash belongs to. Uses bits the sets themselves do not: they
/// take their slot from the low bits and their tag from the top 24.
fn set_of(hash: u64, sets: usize) -> usize {
    (((hash >> 32) & 0xff) as usize * sets) >> 8
}

/// The threads that look lines up, each with its own set.
///
/// Every thread gets the whole block and a list to fill with the repeats it
/// finds among its own lines. (Marking them in one shared array instead makes
/// the threads fight over the same cache lines.)
struct Shards {
    work: Vec<mpsc::Sender<(Arc<Block>, Vec<u32>)>>,
    done: mpsc::Receiver<Vec<u32>>,
    memory: Arc<Vec<AtomicU64>>,
    lists: Vec<Vec<u32>>,
}

impl Shards {
    fn start(count: usize, room: u64, newline: usize) -> Shards {
        let memory: Arc<Vec<AtomicU64>> = Arc::new((0..count).map(|_| AtomicU64::new(0)).collect());
        let (finished, done) = mpsc::channel();
        let work = (0..count)
            .map(|me| {
                let (send, blocks) = mpsc::channel::<(Arc<Block>, Vec<u32>)>();
                let (finished, memory) = (finished.clone(), Arc::clone(&memory));
                thread::spawn(move || {
                    let mut seen = Seen::with_room(room / count as u64);
                    let mut finder = Finder::default();
                    memory[me].store(seen.memory(), Ordering::Relaxed);
                    for (block, mut repeats) in blocks {
                        repeats.clear();
                        finder.find(&mut seen, &block, newline, (me, count), &mut repeats);
                        memory[me].store(seen.memory(), Ordering::Relaxed);
                        drop(block);
                        if finished.send(repeats).is_err() {
                            return;
                        }
                    }
                });
                send
            })
            .collect();
        Shards {
            work,
            done,
            memory,
            lists: vec![Vec::new(); count],
        }
    }

    /// Looks the block's lines up on all threads and marks the repeats.
    fn find(&mut self, block: Block, repeats: &mut [bool]) -> Block {
        let block = Arc::new(block);
        for (work, list) in self.work.iter().zip(self.lists.drain(..)) {
            work.send((Arc::clone(&block), list))
                .expect("a dedup thread ended early");
        }
        for _ in &self.work {
            let list = self.done.recv().expect("a dedup thread ended early");
            for &line in &list {
                repeats[line as usize] = true;
            }
            self.lists.push(list);
        }
        Arc::try_unwrap(block)
            .ok()
            .expect("a dedup thread kept its block")
    }

    fn memory(&self) -> u64 {
        self.memory
            .iter()
            .map(|bytes| bytes.load(Ordering::Relaxed))
            .sum()
    }
}

/// Where the blocks end up: drops repeats, stops at the limit, writes the rest.
struct Sink<W: Write> {
    out: W,
    dedup: Dedup,
    /// Per line of the block at hand: whether it repeats an earlier line.
    repeats: Vec<bool>,
    list: Vec<u32>,
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
    /// `remember` turns deduplication on; with more than one thread the
    /// lookups are spread over threads too.
    fn new(
        out: W,
        spec: &Spec,
        plan: &Plan,
        meter: Arc<Meter>,
        remember: bool,
        threads: usize,
    ) -> Sink<W> {
        let limit = spec.limit.filter(|&limit| limit > 0);
        let maxmem = spec.maxmem.filter(|&bytes| bytes > 0);
        let dedup = if !remember {
            Dedup::Off
        } else {
            // no more lines than the job has or the limit lets through, and a
            // table well inside the memory cap
            let room = plan
                .lines(SIZED_FOR)
                .min(limit.unwrap_or(u64::MAX))
                .min(maxmem.map_or(u64::MAX, |bytes| bytes / 64));
            if threads > 1 {
                Dedup::Shards(Shards::start(threads.min(MOST_SHARDS), room, plan.newline))
            } else {
                Dedup::Here(Seen::with_room(room), Finder::default())
            }
        };
        let sink = Sink {
            out,
            dedup,
            repeats: Vec::new(),
            list: Vec::new(),
            limit,
            maxmem,
            newline: plan.newline,
            written: 0,
            processed: 0,
            ended: None,
            meter,
        };
        sink.meter.memory.store(sink.memory(), Ordering::Relaxed);
        sink
    }

    fn remembers(&self) -> bool {
        !matches!(self.dedup, Dedup::Off)
    }

    fn memory(&self) -> u64 {
        match &self.dedup {
            Dedup::Off => 0,
            Dedup::Here(seen, _) => seen.memory(),
            Dedup::Shards(shards) => shards.memory(),
        }
    }

    /// Takes the next block of the output, and gives it back to be used again.
    fn take(&mut self, mut block: Block) -> io::Result<Block> {
        // lines that may still be written before the limit
        let room = self.limit.map_or(u64::MAX, |limit| limit - self.written);
        let mut looked_at = block.lines;
        let mut kept = block.lines;
        if !self.remembers() {
            if block.lines >= room {
                self.out
                    .write_all(&block.bytes[..end_of_line(&block.bytes, room)])?;
                looked_at = room;
                kept = room;
                self.ended = Some("limit");
            } else {
                self.out.write_all(&block.bytes)?;
            }
        } else {
            self.repeats.clear();
            self.repeats.resize(block.ends.len(), false);
            block = match &mut self.dedup {
                Dedup::Here(seen, finder) => {
                    self.list.clear();
                    finder.find(seen, &block, self.newline, (0, 1), &mut self.list);
                    for &line in &self.list {
                        self.repeats[line as usize] = true;
                    }
                    block
                }
                Dedup::Shards(shards) => shards.find(block, &mut self.repeats),
                Dedup::Off => block,
            };
            kept = 0;
            let mut start = 0; // of the line at hand
            let mut pending = 0; // start of the kept lines not written yet
            for (index, (&end, &repeat)) in block.ends.iter().zip(&self.repeats).enumerate() {
                let end = end as usize;
                if repeat {
                    self.out.write_all(&block.bytes[pending..start])?;
                    pending = end;
                } else {
                    kept += 1;
                    if kept == room {
                        looked_at = index as u64 + 1;
                        self.ended = Some("limit");
                        start = end;
                        break;
                    }
                }
                start = end;
            }
            self.out.write_all(&block.bytes[pending..start])?;
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
        Ok(block)
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
    /// Every job is done on one thread and on three, which have to agree.
    fn outcome(spec: &Spec) -> (String, u64, u64, Option<&'static str>) {
        let plan = Plan::new(spec).unwrap();
        let on = |threads| {
            let mut sink = Sink::new(
                Vec::new(),
                spec,
                &plan,
                Arc::new(Meter::default()),
                spec.dedup,
                threads,
            );
            assert!(run(&plan, &AtomicBool::new(false), &mut sink, threads).unwrap());
            (
                String::from_utf8(sink.out).unwrap(),
                sink.written,
                sink.processed,
                sink.ended,
            )
        };
        let single = on(1);
        assert_eq!(on(3), single);
        single
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
        for threads in [1, 3] {
            let meter = Arc::new(Meter::default());
            let mut sink = Sink::new(Vec::new(), &job, &plan, meter, true, threads);
            assert!(!run(&plan, &AtomicBool::new(true), &mut sink, threads).unwrap());
            assert_eq!(sink.written, 0);
        }
    }

    #[test]
    fn line_ends_are_found_by_count() {
        assert_eq!(end_of_line(b"a\r\nbb\r\nc\r\n", 1), 3);
        assert_eq!(end_of_line(b"a\r\nbb\r\nc\r\n", 2), 7);
        assert_eq!(end_of_line(b"a\r\nbb\r\nc\r\n", 3), 10);
    }
}
