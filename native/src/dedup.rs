//! The set of lines already written.
//!
//! Lines sit back to back in large chunks and are found through an open
//! addressing table of 64-bit slots: 40 bits say where a line is, 24 bits are
//! a piece of its hash, so a lookup reads the line itself only when it is
//! almost certainly the one asked for. A 12-character line costs about 25
//! bytes this way, a few times less than in a Python set of strings.

const CHUNK_BITS: u32 = 20;
const CHUNK: usize = 1 << CHUNK_BITS;
const PLACE_BITS: u32 = 40;
const PLACE: u64 = (1 << PLACE_BITS) - 1;

pub struct Seen {
    slots: Vec<u64>,
    filled: usize,
    chunks: Vec<Vec<u8>>,
}

impl Seen {
    /// A set with a table sized for about `lines` lines, so that a run of
    /// known size does not have to grow it on the way.
    pub fn with_room(lines: u64) -> Seen {
        let slots = (lines.saturating_mul(4) / 3 + 1).clamp(1 << 10, 1 << 32);
        Seen {
            slots: vec![0; slots.next_power_of_two() as usize],
            filled: 0,
            chunks: Vec::new(),
        }
    }

    /// Reads the slot a lookup of `hash` starts at. Doing this for a batch of
    /// lines before looking them up lets their cache misses overlap.
    pub fn peek(&self, hash: u64) -> u64 {
        self.slots[hash as usize & (self.slots.len() - 1)]
    }

    /// For a slot peek() returned: reads the start of the line it points to,
    /// if that line may be the one `hash` belongs to. The second half of
    /// warming a lookup up; the value itself means nothing.
    pub fn glance(&self, hash: u64, slot: u64) -> u8 {
        if slot != 0 && slot >> PLACE_BITS == hash >> PLACE_BITS {
            self.line(slot & PLACE).first().copied().unwrap_or(0)
        } else {
            0
        }
    }

    /// Adds a line whose hash() is `hash`; false when it was already there.
    pub fn insert(&mut self, hash: u64, line: &[u8]) -> bool {
        let mask = self.slots.len() - 1;
        let tag = hash >> PLACE_BITS;
        let mut at = hash as usize & mask;
        loop {
            let slot = self.slots[at];
            if slot == 0 {
                break;
            }
            if slot >> PLACE_BITS == tag && self.line(slot & PLACE) == line {
                return false;
            }
            at = (at + 1) & mask;
        }
        self.slots[at] = tag << PLACE_BITS | self.store(line);
        self.filled += 1;
        if self.filled * 4 > self.slots.len() * 3 {
            self.grow();
        }
        true
    }

    /// Bytes held by the lines and the table.
    pub fn memory(&self) -> u64 {
        let lines: usize = self.chunks.iter().map(Vec::len).sum();
        (lines + self.slots.len() * 8) as u64
    }

    /// Appends a line to the chunks and returns its place (never zero).
    fn store(&mut self, line: &[u8]) -> u64 {
        let need = line.len() + 5;
        assert!(
            need <= CHUNK,
            "a line of {} bytes is too long to remember",
            line.len()
        );
        if self
            .chunks
            .last()
            .map_or(true, |chunk| chunk.len() + need > CHUNK)
        {
            self.chunks.push(Vec::with_capacity(CHUNK));
        }
        let index = self.chunks.len() - 1;
        let chunk = &mut self.chunks[index];
        let offset = chunk.len();
        let mut len = line.len();
        while len >= 0x80 {
            chunk.push(len as u8 | 0x80);
            len >>= 7;
        }
        chunk.push(len as u8);
        chunk.extend_from_slice(line);
        place(index, offset)
    }

    fn line(&self, place: u64) -> &[u8] {
        let position = (place - 1) as usize;
        entry(&self.chunks[position >> CHUNK_BITS], position & (CHUNK - 1)).0
    }

    /// Doubles the table. The slots do not hold whole hashes, so every line is
    /// hashed again; the old table is let go first to keep the peak low.
    fn grow(&mut self) {
        let size = self.slots.len() * 2;
        self.slots = Vec::new();
        self.slots = vec![0; size];
        let mask = size - 1;
        // (where the lookup starts, what the slot will hold), a batch at a time
        let mut batch = [(0usize, 0u64); 32];
        let mut ready = 0;
        for (index, chunk) in self.chunks.iter().enumerate() {
            let mut offset = 0;
            while offset < chunk.len() {
                let (line, next) = entry(chunk, offset);
                let hash = hash(line);
                let slot = (hash >> PLACE_BITS) << PLACE_BITS | place(index, offset);
                batch[ready] = (hash as usize & mask, slot);
                ready += 1;
                if ready == batch.len() {
                    settle(&mut self.slots, &batch);
                    ready = 0;
                }
                offset = next;
            }
        }
        settle(&mut self.slots, &batch[..ready]);
    }
}

/// Puts a batch of slots into a table that has room for them. Every start is
/// read before any slot is placed, so the cache misses of a batch overlap
/// instead of being waited out one after another.
fn settle(slots: &mut [u64], batch: &[(usize, u64)]) {
    let mask = slots.len() - 1;
    let touched = batch.iter().fold(0, |all, &(at, _)| all ^ slots[at]);
    std::hint::black_box(touched);
    for &(mut at, slot) in batch {
        while slots[at] != 0 {
            at = (at + 1) & mask;
        }
        slots[at] = slot;
    }
}

fn place(chunk: usize, offset: usize) -> u64 {
    let position = (chunk as u64) << CHUNK_BITS | offset as u64;
    assert!(position < PLACE, "too many lines to remember");
    position + 1
}

/// The line stored at `offset` of a chunk, and where the next one starts.
fn entry(chunk: &[u8], mut offset: usize) -> (&[u8], usize) {
    let mut len = 0;
    let mut shift = 0;
    loop {
        let byte = chunk[offset];
        offset += 1;
        len |= ((byte & 0x7f) as usize) << shift;
        if byte < 0x80 {
            break;
        }
        shift += 7;
    }
    (&chunk[offset..offset + len], offset + len)
}

/// A 64-bit hash for short byte strings (multiply-and-fold, after wyhash).
pub fn hash(bytes: &[u8]) -> u64 {
    const A: u64 = 0x9e37_79b9_7f4a_7c15;
    const B: u64 = 0xc2b2_ae3d_27d4_eb4f;
    fn fold(a: u64, b: u64) -> (u64, u64) {
        let wide = u128::from(a) * u128::from(b);
        (wide as u64, (wide >> 64) as u64)
    }
    fn word(bytes: &[u8], at: usize) -> u64 {
        let mut word = [0; 8];
        word.copy_from_slice(&bytes[at..at + 8]);
        u64::from_le_bytes(word)
    }
    fn half(bytes: &[u8], at: usize) -> u64 {
        let mut half = [0; 4];
        half.copy_from_slice(&bytes[at..at + 4]);
        u64::from(u32::from_le_bytes(half))
    }
    let len = bytes.len();
    let mut state = A ^ (len as u64).wrapping_mul(B);
    let (first, last) = if len >= 16 {
        let mut at = 0;
        while at + 16 < len {
            let (low, high) = fold(word(bytes, at) ^ B, word(bytes, at + 8) ^ state);
            state = low ^ high;
            at += 16;
        }
        (word(bytes, len - 16), word(bytes, len - 8))
    } else if len >= 8 {
        (word(bytes, 0), word(bytes, len - 8))
    } else if len >= 4 {
        (half(bytes, 0) << 32 | half(bytes, len - 4), 0)
    } else if len > 0 {
        (
            u64::from(bytes[0]) << 16 | u64::from(bytes[len / 2]) << 8 | u64::from(bytes[len - 1]),
            0,
        )
    } else {
        (0, 0)
    };
    let (low, high) = fold(first ^ B, last ^ state);
    let (low, high) = fold(low ^ A, high ^ B);
    low ^ high
}

#[cfg(test)]
mod tests {
    use super::*;

    fn add(seen: &mut Seen, line: &[u8]) -> bool {
        seen.insert(hash(line), line)
    }

    #[test]
    fn a_line_is_new_only_once() {
        let mut seen = Seen::with_room(0);
        assert!(add(&mut seen, b"abc"));
        assert!(add(&mut seen, b"abd"));
        assert!(add(&mut seen, b""));
        assert!(!add(&mut seen, b"abc"));
        assert!(!add(&mut seen, b""));
        assert!(add(&mut seen, b"ab"));
    }

    #[test]
    fn remembers_everything_while_the_table_grows() {
        let mut seen = Seen::with_room(0);
        let line = |n: u32| format!("line-{n}").into_bytes();
        for n in 0..200_000 {
            assert!(add(&mut seen, &line(n)), "{n} was new");
        }
        for n in 0..200_000 {
            assert!(!add(&mut seen, &line(n)), "{n} was known");
        }
        assert!(add(&mut seen, &line(200_000)));
        assert!(seen.memory() > 200_000 * 12);
    }

    #[test]
    fn lines_of_every_length_come_back_whole() {
        let mut seen = Seen::with_room(0);
        let text: Vec<u8> = (0..20_000).map(|n| (n % 251) as u8).collect();
        for len in (0..300).chain([1000, 16_383, 16_384, 20_000]) {
            assert!(add(&mut seen, &text[..len]), "{len} bytes were new");
        }
        for len in (0..300).chain([1000, 16_383, 16_384, 20_000]) {
            assert!(!add(&mut seen, &text[..len]), "{len} bytes were known");
        }
    }

    #[test]
    fn a_set_sized_for_its_lines_does_not_grow_its_table() {
        assert_eq!(Seen::with_room(0).slots.len(), 1 << 10);
        let mut seen = Seen::with_room(100_000);
        assert_eq!(seen.slots.len(), 1 << 18);
        for n in 0..100_000u32 {
            assert!(add(&mut seen, format!("{n}").as_bytes()));
        }
        assert_eq!(seen.slots.len(), 1 << 18);
    }

    #[test]
    fn a_lookup_can_be_warmed_up() {
        let mut seen = Seen::with_room(0);
        let known = hash(b"hello");
        assert_eq!((seen.peek(known), seen.glance(known, 0)), (0, 0));
        assert!(seen.insert(known, b"hello"));
        let slot = seen.peek(known);
        assert_ne!(slot, 0);
        assert_eq!(seen.glance(known, slot), b'h');
        // a slot that holds another hash's line is not followed
        assert_eq!(seen.glance(!known, slot), 0);
    }

    #[test]
    fn lines_with_the_same_hash_stay_apart() {
        let mut seen = Seen::with_room(0);
        assert!(seen.insert(7, b"one"));
        assert!(seen.insert(7, b"two"));
        assert!(!seen.insert(7, b"one"));
        assert!(!seen.insert(7, b"two"));
    }

    #[test]
    fn hash_tells_short_strings_apart() {
        let mut hashes = std::collections::HashSet::new();
        for len in 0..40usize {
            for fill in [0u8, 1, 0x61, 0xff] {
                let bytes = vec![fill; len];
                hashes.insert(hash(&bytes));
                if len > 0 {
                    for at in [0, len / 2, len - 1] {
                        let mut other = bytes.clone();
                        other[at] ^= 0x20;
                        hashes.insert(hash(&other));
                    }
                }
            }
        }
        // the empty string, then 4 fills per length with one changed byte in up to three places
        assert_eq!(hashes.len(), 1 + 8 + 12 + 37 * 16);
    }
}
