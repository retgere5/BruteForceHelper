//! gzip output, compressed on several threads.
//!
//! The output is cut into chunks of about a megabyte; each becomes a gzip
//! member of its own on whichever thread is free, and the members are written
//! in order. A file of several members unpacks to the bytes that went in, the
//! same as one long member would (gzip -d, zcat and Python's gzip module read
//! them through), and the compressor no longer holds the whole run back.

use std::collections::HashMap;
use std::io::{self, Write};
use std::sync::mpsc::{self, TryRecvError};
use std::sync::{Arc, Mutex};
use std::thread;

use flate2::write::GzEncoder;
use flate2::Compression;

const CHUNK: usize = 1 << 20;
const LEVEL: u32 = 6;
/// Chunks a thread may have out before the oldest one is written.
const WINDOW_PER_THREAD: u64 = 2;

pub struct Gz<W: Write> {
    out: W,
    chunk: Vec<u8>,
    /// Where chunks go to be compressed; gone once the output is finished.
    work: Option<mpsc::Sender<(u64, Vec<u8>)>>,
    done: mpsc::Receiver<(u64, Vec<u8>)>,
    threads: Vec<thread::JoinHandle<()>>,
    /// Members that are ready before their turn.
    early: HashMap<u64, Vec<u8>>,
    /// Chunks handed out so far, and members written so far.
    sent: u64,
    written: u64,
    window: u64,
}

impl<W: Write> Gz<W> {
    pub fn new(out: W, threads: usize) -> Gz<W> {
        let threads = threads.max(1);
        let (work, chunks) = mpsc::channel::<(u64, Vec<u8>)>();
        let (ready, done) = mpsc::channel();
        let chunks = Arc::new(Mutex::new(chunks));
        let threads = (0..threads)
            .map(|_| {
                let (chunks, ready) = (Arc::clone(&chunks), ready.clone());
                thread::spawn(move || loop {
                    let next = chunks.lock().unwrap().recv();
                    let Ok((number, chunk)) = next else { return };
                    if ready.send((number, member(&chunk))).is_err() {
                        return;
                    }
                })
            })
            .collect::<Vec<_>>();
        let window = threads.len() as u64 * WINDOW_PER_THREAD;
        Gz {
            out,
            chunk: Vec::with_capacity(CHUNK),
            work: Some(work),
            done,
            threads,
            early: HashMap::new(),
            sent: 0,
            written: 0,
            window,
        }
    }

    /// Compresses what is left and writes the last members.
    pub fn finish(&mut self) -> io::Result<()> {
        if self.work.is_none() {
            return Ok(());
        }
        // an empty output still is a gzip file: one member with nothing in it
        if !self.chunk.is_empty() || self.sent == 0 {
            self.send();
        }
        self.collect(true)?;
        self.work = None;
        for thread in self.threads.drain(..) {
            let _ = thread.join();
        }
        self.out.flush()
    }

    #[cfg(test)]
    fn into_inner(self) -> W {
        self.out
    }

    fn send(&mut self) {
        let chunk = std::mem::replace(&mut self.chunk, Vec::with_capacity(CHUNK));
        let work = self.work.as_ref().expect("output after it was finished");
        work.send((self.sent, chunk))
            .expect("the compressing threads ended early");
        self.sent += 1;
    }

    /// Writes the members whose turn has come. Waits for them when `all` are
    /// wanted, or when too many chunks are out.
    fn collect(&mut self, all: bool) -> io::Result<()> {
        while self.written < self.sent {
            if let Some(member) = self.early.remove(&self.written) {
                self.out.write_all(&member)?;
                self.written += 1;
                continue;
            }
            let (number, member) = if all || self.sent - self.written >= self.window {
                self.done
                    .recv()
                    .expect("the compressing threads ended early")
            } else {
                match self.done.try_recv() {
                    Ok(ready) => ready,
                    Err(TryRecvError::Empty) => break,
                    Err(TryRecvError::Disconnected) => {
                        panic!("the compressing threads ended early")
                    }
                }
            };
            self.early.insert(number, member);
        }
        Ok(())
    }
}

impl<W: Write> Write for Gz<W> {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.chunk.extend_from_slice(bytes);
        if self.chunk.len() >= CHUNK {
            self.send();
            self.collect(false)?;
        }
        Ok(bytes.len())
    }

    /// Nothing is held back that could be written before finish().
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

/// One chunk as a gzip member.
fn member(chunk: &[u8]) -> Vec<u8> {
    let mut encoder = GzEncoder::new(
        Vec::with_capacity(chunk.len() / 3 + 64),
        Compression::new(LEVEL),
    );
    encoder
        .write_all(chunk)
        .expect("writing to memory cannot fail");
    encoder.finish().expect("writing to memory cannot fail")
}

#[cfg(test)]
mod tests {
    use super::*;
    use flate2::read::MultiGzDecoder;
    use std::io::Read;

    fn unpack(packed: &[u8]) -> Vec<u8> {
        let mut out = Vec::new();
        MultiGzDecoder::new(packed).read_to_end(&mut out).unwrap();
        out
    }

    /// About `megabytes` of numbered lines.
    fn lines(megabytes: usize) -> Vec<u8> {
        let mut text = Vec::new();
        let mut number = 0u32;
        while text.len() < megabytes << 20 {
            text.extend_from_slice(format!("line {number} şifre\r\n").as_bytes());
            number += 1;
        }
        text
    }

    #[test]
    fn members_come_out_in_the_order_the_bytes_went_in() {
        let text = lines(9);
        for threads in [1, 4] {
            let mut gz = Gz::new(Vec::new(), threads);
            // written in uneven pieces, as the blocks of a run are
            for piece in text.chunks(300_001) {
                gz.write_all(piece).unwrap();
            }
            gz.finish().unwrap();
            let packed = gz.into_inner();
            assert!(packed.len() < text.len() / 2);
            assert_eq!(unpack(&packed), text, "{threads} threads");
        }
    }

    #[test]
    fn short_output_is_one_member() {
        let mut gz = Gz::new(Vec::new(), 3);
        gz.write_all(b"a\nb\n").unwrap();
        gz.finish().unwrap();
        gz.finish().unwrap(); // a second call has nothing left to do
        let packed = gz.into_inner();
        assert_eq!(unpack(&packed), b"a\nb\n");
        assert_eq!(&packed[..2], [0x1f, 0x8b]);
    }

    #[test]
    fn no_output_is_still_a_gzip_file() {
        let mut gz = Gz::new(Vec::new(), 2);
        gz.finish().unwrap();
        let packed = gz.into_inner();
        assert_eq!(&packed[..2], [0x1f, 0x8b]);
        assert_eq!(unpack(&packed), b"");
    }

    #[test]
    fn the_same_input_packs_to_the_same_bytes() {
        let text = lines(3);
        let pack = |threads| {
            let mut gz = Gz::new(Vec::new(), threads);
            gz.write_all(&text).unwrap();
            gz.finish().unwrap();
            gz.into_inner()
        };
        assert_eq!(pack(1), pack(5));
    }
}
