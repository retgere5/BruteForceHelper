//! The word tree.
//!
//! A line is a sequence of words. Round k holds the lines made of k words, and
//! inside a round the sequences come in the order itertools.product() gives
//! them; only those whose joined length fits the bounds are built. `Splitter`
//! cuts that tree into tasks and `Walker` turns a task into lines, both in
//! exactly this order, so putting the tasks back in sequence gives the file a
//! single thread would have written.

use std::ops::Range;

use crate::dedup::hash;
use crate::spec::Spec;
use crate::text::{self, Variant};

/// Lines one task aims for, and the bytes they should stay under.
const TASK_LINES: u64 = 1 << 16;
const TASK_BYTES: u64 = 1 << 20;

/// Most cells the completion counts may take (rounds x lengths).
const WAYS_LIMIT: u64 = 1 << 24;

/// What stays fixed while a job runs.
pub struct Plan {
    lens: Vec<u64>,
    shortest: u64,
    longest: u64,
    floor: u64,
    max: Option<u64>,
    rounds: u64,
    sizes: Vec<(u64, u64)>,
    pub shapes: Vec<Shape>,
    /// Bytes of the line ending.
    pub newline: usize,
}

impl Plan {
    pub fn new(spec: &Spec) -> Result<Plan, String> {
        if spec.words.is_empty() || spec.words.iter().any(String::is_empty) {
            return Err("the core needs words, none of them empty".into());
        }
        if spec.newline.last() != Some(&b'\n') {
            return Err("the line ending has to end in a line feed".into());
        }
        if spec
            .words
            .iter()
            .chain([&spec.start, &spec.end])
            .any(|piece| piece.contains('\n'))
        {
            return Err("a line break inside a word".into());
        }
        let lens: Vec<u64> = spec
            .words
            .iter()
            .map(|word| word.chars().count() as u64)
            .collect();
        let shortest = lens.iter().copied().min().unwrap_or(1);
        let longest = lens.iter().copied().max().unwrap_or(1);
        let max = spec.max.filter(|&max| max > 0);
        // with a maximum, as many words as can still fit; without one, as many as were given
        let rounds = match max {
            Some(max) => (max / shortest).max(1),
            None => lens.len() as u64,
        };
        if max.is_some_and(|max| (max + 1).saturating_mul(rounds) > WAYS_LIMIT) {
            return Err("the length bounds are too wide for the core".into());
        }
        let mut sorted = lens.clone();
        sorted.sort_unstable();
        let mut sizes: Vec<(u64, u64)> = Vec::new();
        for len in sorted {
            match sizes.last_mut() {
                Some((size, words)) if *size == len => *words += 1,
                _ => sizes.push((len, 1)),
            }
        }
        let shapes = text::variants(&spec.mods)
            .iter()
            .map(|variant| Shape::new(variant, spec))
            .collect::<Result<Vec<Shape>, String>>()?;
        Ok(Plan {
            lens,
            shortest,
            longest,
            floor: spec.min,
            max,
            rounds,
            sizes,
            shapes,
            newline: spec.newline.len(),
        })
    }

    /// Whether `left` more words can still bring `total` characters inside the bounds.
    fn fits(&self, total: u64, left: u64) -> bool {
        let least = total.saturating_add(left.saturating_mul(self.shortest));
        let most = total.saturating_add(left.saturating_mul(self.longest));
        most >= self.floor && !self.max.is_some_and(|max| least > max)
    }

    /// Whether a finished line of `total` characters is inside the bounds.
    fn inside(&self, total: u64) -> bool {
        total >= self.floor && !self.max.is_some_and(|max| total > max)
    }

    /// Word sequences one task may hold: about TASK_LINES lines or TASK_BYTES bytes.
    pub fn budget(&self) -> u64 {
        let chars = self.max.unwrap_or(self.floor.max(self.longest));
        let widest = self
            .shapes
            .iter()
            .map(|shape| shape.width(chars))
            .max()
            .unwrap_or(1) as u64;
        let lines = TASK_LINES.min(TASK_BYTES / widest.max(1)).max(1);
        (lines / self.shapes.len() as u64).max(1)
    }

    /// How many lines the job looks at, counted no further than `cap`.
    pub fn lines(&self, cap: u64) -> u64 {
        let mut ways = Ways { levels: Vec::new() };
        let mut total = 0u64;
        for round in 1..=self.rounds {
            let lines = ways
                .get(self, round, 0)
                .saturating_mul(self.shapes.len() as u64);
            total = total.saturating_add(lines);
            if total >= cap {
                return cap;
            }
        }
        total
    }
}

/// How one variation of a line is put together from its pieces.
///
/// Forward: `head` (the prefix), the words, `tail` (the suffix and the line
/// ending). Reversed: `head` is the turned suffix, then the words last to
/// first, and `tail` holds the turned prefix. When capitalizing, the piece
/// that opens the line is cased differently from the others (see
/// text::Variant), so a word that can open a line has two forms.
pub struct Shape {
    reversed: bool,
    bytes: Vec<u8>,
    rest: Vec<(u32, u32)>,
    first: Vec<(u32, u32)>,
    head: Vec<u8>,
    tail: Vec<u8>,
    /// The longest form a word takes, in bytes.
    widest: usize,
    /// Bytes per character of the words, rounded up.
    density: usize,
}

impl Shape {
    fn new(variant: &Variant, spec: &Spec) -> Result<Shape, String> {
        let table = &spec.table;
        let (opening, closing) = if variant.reversed {
            (&spec.end, &spec.start)
        } else {
            (&spec.start, &spec.end)
        };
        let head = variant.first(table, opening)?.into_bytes();
        let mut tail = variant.rest(table, closing)?.into_bytes();
        tail.extend_from_slice(&spec.newline);

        let mut bytes = Vec::new();
        let mut keep = |form: String| -> Result<(u32, u32), String> {
            let at = bytes.len();
            bytes.extend_from_slice(form.as_bytes());
            match (u32::try_from(at), u32::try_from(form.len())) {
                (Ok(at), Ok(len)) => Ok((at, len)),
                _ => Err("the words are too long for the core".to_string()),
            }
        };
        let mut rest = Vec::with_capacity(spec.words.len());
        for word in &spec.words {
            rest.push(keep(variant.rest(table, word)?)?);
        }
        // only a word that can open the line needs its opening form
        let mut first = Vec::new();
        if opening.is_empty() && variant.capitalizes() {
            for word in &spec.words {
                first.push(keep(variant.first(table, word)?)?);
            }
        }
        let widest = rest
            .iter()
            .chain(&first)
            .map(|&(_, len)| len as usize)
            .max()
            .unwrap_or(0);
        let chars: usize = spec.words.iter().map(|word| word.chars().count()).sum();
        let rest_bytes: usize = rest.iter().map(|&(_, len)| len as usize).sum();
        let density = rest_bytes.div_ceil(chars.max(1)).max(1);
        Ok(Shape {
            reversed: variant.reversed,
            bytes,
            rest,
            first,
            head,
            tail,
            widest,
            density,
        })
    }

    /// The bytes of a word; `opening` when it is the piece that opens the line.
    fn form(&self, word: usize, opening: bool) -> &[u8] {
        let (at, len) = if opening && !self.first.is_empty() {
            self.first[word]
        } else {
            self.rest[word]
        };
        &self.bytes[at as usize..at as usize + len as usize]
    }

    /// About how many bytes a line of `chars` characters takes.
    fn width(&self, chars: u64) -> usize {
        self.head.len() + self.tail.len() + (chars as usize).saturating_mul(self.density)
    }
}

/// How many word sequences complete a line: `get(left, used)` counts the ways
/// to add `left` more words to `used` characters and end inside the bounds.
/// Counts stop at u64::MAX, far beyond what a run ever reaches.
struct Ways {
    levels: Vec<Vec<u64>>,
}

impl Ways {
    fn get(&mut self, plan: &Plan, left: u64, used: u64) -> u64 {
        let Some(column) = column(plan, used) else {
            return 0;
        };
        while self.levels.len() as u64 <= left {
            self.grow(plan);
        }
        self.levels[left as usize][column]
    }

    fn grow(&mut self, plan: &Plan) {
        let width = plan.max.unwrap_or(plan.floor) + 1;
        let level = match self.levels.last() {
            None => (0..width)
                .map(|used| u64::from(used >= plan.floor))
                .collect(),
            Some(below) => (0..width)
                .map(|used| {
                    plan.sizes.iter().fold(0u64, |ways, &(len, words)| {
                        match column(plan, used + len) {
                            Some(column) => {
                                ways.saturating_add(words.saturating_mul(below[column]))
                            }
                            None => ways,
                        }
                    })
                })
                .collect(),
        };
        self.levels.push(level);
    }
}

/// Where a length sits in a level of the counts; None when it is past the
/// maximum. Without a maximum every length from the minimum on counts alike.
fn column(plan: &Plan, used: u64) -> Option<usize> {
    match plan.max {
        Some(max) => (used <= max).then_some(used as usize),
        None => Some(used.min(plan.floor) as usize),
    }
}

/// A piece of the tree: in round `round`, under the words `prefix`, the
/// subtrees of the words `lo..hi`.
pub struct Task {
    pub seq: u64,
    pub round: u64,
    pub prefix: Vec<u32>,
    pub lo: usize,
    pub hi: usize,
}

/// Hands out the tree as tasks of at most `budget` sequences, in order.
pub struct Splitter {
    ways: Ways,
    budget: u64,
    round: u64,
    path: Vec<u32>,
    used: Vec<u64>,
    next: Vec<usize>,
    seq: u64,
}

impl Splitter {
    pub fn new(budget: u64) -> Splitter {
        Splitter {
            ways: Ways { levels: Vec::new() },
            budget,
            round: 0,
            path: Vec::new(),
            used: Vec::new(),
            next: Vec::new(),
            seq: 0,
        }
    }

    pub fn next(&mut self, plan: &Plan) -> Option<Task> {
        let words = plan.lens.len();
        loop {
            if self.next.is_empty() {
                // between rounds: move on to the next one that holds a line
                loop {
                    if self.round >= plan.rounds {
                        return None;
                    }
                    self.round += 1;
                    if self.ways.get(plan, self.round, 0) > 0 {
                        break;
                    }
                }
                self.used.push(0);
                self.next.push(0);
            }
            let depth = self.path.len();
            let left = self.round - depth as u64;
            let used = self.used[depth];
            let from = self.next[depth];
            if from >= words {
                self.path.pop();
                self.used.pop();
                self.next.pop();
                continue;
            }
            if left == 1 {
                // the words here finish their lines: hand them out in runs
                let to = words.min(from.saturating_add(self.budget as usize));
                self.next[depth] = to;
                return Some(self.task(from, to));
            }
            // words that lead small subtrees go out together
            let mut to = from;
            let mut total = 0u64;
            while to < words {
                let below = self.ways.get(plan, left - 1, used + plan.lens[to]);
                if below > self.budget || (total > 0 && total + below > self.budget) {
                    break;
                }
                total += below;
                to += 1;
            }
            if to > from {
                self.next[depth] = to;
                if total > 0 {
                    return Some(self.task(from, to));
                }
                continue;
            }
            // this word leads more than one task can hold: split below it
            self.next[depth] = from + 1;
            self.path.push(from as u32);
            self.used.push(used + plan.lens[from]);
            self.next.push(0);
        }
    }

    fn task(&mut self, lo: usize, hi: usize) -> Task {
        let task = Task {
            seq: self.seq,
            round: self.round,
            prefix: self.path.clone(),
            lo,
            hi,
        };
        self.seq += 1;
        task
    }
}

/// The lines of one task, in order.
#[derive(Default)]
pub struct Block {
    pub seq: u64,
    /// The lines, each with its line ending.
    pub bytes: Vec<u8>,
    pub lines: u64,
    /// When deduplicating: where each line ends, and its hash.
    pub ends: Vec<u32>,
    pub hashes: Vec<u64>,
}

impl Block {
    pub fn clear(&mut self) {
        self.bytes.clear();
        self.lines = 0;
        self.ends.clear();
        self.hashes.clear();
    }
}

/// Builds the lines of tasks. One per thread.
pub struct Walker<'a> {
    plan: &'a Plan,
    hashing: bool,
    /// Per variation, the part of the line the words so far have settled: for a
    /// forward one the start of the line, for a reversed one its end, kept at
    /// the back of the buffer from `begins` on.
    parts: Vec<Vec<u8>>,
    begins: Vec<usize>,
    used: Vec<u64>,
    next: Vec<usize>,
    saved: Vec<usize>,
}

impl<'a> Walker<'a> {
    pub fn new(plan: &'a Plan, hashing: bool) -> Walker<'a> {
        let parts = plan
            .shapes
            .iter()
            .map(|shape| {
                if shape.reversed {
                    shape.tail.clone()
                } else {
                    shape.head.clone()
                }
            })
            .collect();
        Walker {
            plan,
            hashing,
            parts,
            begins: vec![0; plan.shapes.len()],
            used: vec![0],
            next: vec![0],
            saved: Vec::new(),
        }
    }

    /// Appends the lines of `task` to `block`.
    pub fn fill(&mut self, task: &Task, block: &mut Block) {
        let plan = self.plan;
        let round = usize::try_from(task.round).expect("more words per line than fit in memory");
        self.reset(round);
        for (depth, &word) in task.prefix.iter().enumerate() {
            self.push(depth, word as usize);
        }
        let top = task.prefix.len();
        let mut depth = top;
        self.next[depth] = task.lo;
        loop {
            let end = if depth == top {
                task.hi
            } else {
                plan.lens.len()
            };
            if round - depth == 1 {
                self.leaves(depth, self.next[depth]..end, block);
            } else if self.next[depth] < end {
                let word = self.next[depth];
                self.next[depth] += 1;
                let total = self.used[depth] + plan.lens[word];
                if plan.fits(total, (round - depth - 1) as u64) {
                    self.push(depth, word);
                    depth += 1;
                    self.next[depth] = 0;
                }
                continue;
            }
            if depth == top {
                break;
            }
            depth -= 1;
            self.pop(depth);
        }
    }

    /// Back to the state before any word, with room for `round` of them.
    fn reset(&mut self, round: usize) {
        let shapes = self.plan.shapes.len();
        if self.used.len() <= round {
            self.used.resize(round + 1, 0);
            self.next.resize(round + 1, 0);
        }
        if self.saved.len() < round * shapes {
            self.saved.resize(round * shapes, 0);
        }
        for ((shape, part), begin) in self
            .plan
            .shapes
            .iter()
            .zip(&mut self.parts)
            .zip(&mut self.begins)
        {
            if shape.reversed {
                // all words but the last go in front of the tail
                let need = shape.tail.len() + (round - 1).saturating_mul(shape.widest);
                if part.len() < need {
                    *part = vec![0; need];
                    let at = need - shape.tail.len();
                    part[at..].copy_from_slice(&shape.tail);
                }
                *begin = part.len() - shape.tail.len();
            } else {
                part.truncate(shape.head.len());
            }
        }
    }

    /// Adds `word` as the word number `depth` of the line.
    fn push(&mut self, depth: usize, word: usize) {
        let plan = self.plan;
        let saved = &mut self.saved[depth * plan.shapes.len()..];
        for (v, shape) in plan.shapes.iter().enumerate() {
            let part = &mut self.parts[v];
            if shape.reversed {
                saved[v] = self.begins[v];
                let form = shape.form(word, false);
                self.begins[v] -= form.len();
                part[self.begins[v]..saved[v]].copy_from_slice(form);
            } else {
                saved[v] = part.len();
                part.extend_from_slice(shape.form(word, depth == 0));
            }
        }
        self.used[depth + 1] = self.used[depth] + plan.lens[word];
    }

    /// Takes the word number `depth` off again.
    fn pop(&mut self, depth: usize) {
        let shapes = self.plan.shapes.len();
        let saved = &self.saved[depth * shapes..];
        for (v, shape) in self.plan.shapes.iter().enumerate() {
            if shape.reversed {
                self.begins[v] = saved[v];
            } else {
                self.parts[v].truncate(saved[v]);
            }
        }
    }

    /// The lines that end with one of `words` as their word number `depth`:
    /// every variation of each, as apply_flags() orders them.
    fn leaves(&mut self, depth: usize, words: Range<usize>, block: &mut Block) {
        let plan = self.plan;
        let used = self.used[depth];
        for word in words {
            if !plan.inside(used + plan.lens[word]) {
                continue;
            }
            for (v, shape) in plan.shapes.iter().enumerate() {
                let start = block.bytes.len();
                if shape.reversed {
                    block.bytes.extend_from_slice(&shape.head);
                    block.bytes.extend_from_slice(shape.form(word, true));
                    block
                        .bytes
                        .extend_from_slice(&self.parts[v][self.begins[v]..]);
                } else {
                    block.bytes.extend_from_slice(&self.parts[v]);
                    block.bytes.extend_from_slice(shape.form(word, depth == 0));
                    block.bytes.extend_from_slice(&shape.tail);
                }
                if self.hashing {
                    let end = block.bytes.len();
                    block
                        .hashes
                        .push(hash(&block.bytes[start..end - plan.newline]));
                    block
                        .ends
                        .push(u32::try_from(end).expect("a block of lines past 4 GB"));
                }
            }
            block.lines += plan.shapes.len() as u64;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::spec::Mods;
    use crate::text::Table;

    fn spec(words: &[&str], min: u64, max: Option<u64>) -> Spec {
        Spec {
            command: "generate".into(),
            words: words.iter().map(|word| word.to_string()).collect(),
            min,
            max,
            start: String::new(),
            end: String::new(),
            mods: Mods::default(),
            dedup: true,
            limit: None,
            maxmem: None,
            gzip: false,
            newline: vec![b'\n'],
            threads: 1,
            table: Table::new(),
            lines: Vec::new(),
        }
    }

    /// Every line of a job, through tasks of at most `budget` sequences.
    fn lines(spec: &Spec, budget: u64) -> Vec<String> {
        let plan = Plan::new(spec).unwrap();
        let mut splitter = Splitter::new(budget);
        let mut walker = Walker::new(&plan, false);
        let mut block = Block::default();
        let mut expected = 0;
        while let Some(task) = splitter.next(&plan) {
            assert_eq!(task.seq, expected);
            expected += 1;
            let before = block.lines;
            walker.fill(&task, &mut block);
            assert!(
                block.lines - before <= budget * plan.shapes.len() as u64,
                "a task over its budget"
            );
        }
        String::from_utf8(block.bytes)
            .unwrap()
            .lines()
            .map(str::to_string)
            .collect()
    }

    /// The same lines the slow way: every product of the words, filtered by length.
    fn reference(words: &[&str], min: u64, max: Option<u64>) -> Vec<String> {
        let shortest = words
            .iter()
            .map(|word| word.chars().count() as u64)
            .min()
            .unwrap();
        let rounds = match max {
            Some(max) => (max / shortest).max(1),
            None => words.len() as u64,
        };
        let mut out = Vec::new();
        for round in 1..=rounds {
            let mut choice = vec![0usize; round as usize];
            'product: loop {
                let line: String = choice.iter().map(|&word| words[word]).collect();
                let len = line.chars().count() as u64;
                if len >= min && max.map_or(true, |max| len <= max) {
                    out.push(line);
                }
                for place in (0..choice.len()).rev() {
                    choice[place] += 1;
                    if choice[place] < words.len() {
                        continue 'product;
                    }
                    choice[place] = 0;
                }
                break;
            }
        }
        out
    }

    #[test]
    fn tasks_of_any_size_give_the_lines_in_product_order() {
        let cases: [(&[&str], u64, Option<u64>); 8] = [
            (&["a", "b", "c"], 1, Some(4)),
            (&["a", "bb", "ccc"], 1, Some(6)),
            (&["ab", "c"], 2, Some(5)),
            (&["x", "yy"], 3, None),
            (&["admin", "root", "2024"], 6, Some(12)),
            (&["a", "a", "bc"], 2, Some(4)),
            (&["abc"], 7, Some(8)),
            (&["1", "22", "333", "4444"], 5, Some(9)),
        ];
        for (words, min, max) in cases {
            let expected = reference(words, min, max);
            for budget in [1, 2, 3, 7, 50, 1 << 16] {
                assert_eq!(
                    lines(&spec(words, min, max), budget),
                    expected,
                    "{words:?} {min} {max:?} budget {budget}"
                );
            }
        }
    }

    #[test]
    fn completion_counts_match_the_lines() {
        let job = spec(&["a", "bb", "ccc"], 2, Some(7));
        let plan = Plan::new(&job).unwrap();
        let mut ways = Ways { levels: Vec::new() };
        let total: u64 = (1..=plan.rounds)
            .map(|round| ways.get(&plan, round, 0))
            .sum();
        assert_eq!(
            total as usize,
            reference(&["a", "bb", "ccc"], 2, Some(7)).len()
        );
        // without a maximum every sequence of three words counts once it is long enough
        let open = Plan::new(&spec(&["a", "bb", "ccc"], 1, None)).unwrap();
        let mut ways = Ways { levels: Vec::new() };
        assert_eq!(
            (1..=3)
                .map(|round| ways.get(&open, round, 0))
                .collect::<Vec<_>>(),
            [3, 9, 27]
        );
    }

    #[test]
    fn counts_stop_at_the_largest_number() {
        let words: Vec<String> = (0..300).map(|n| format!("w{n}")).collect();
        let words: Vec<&str> = words.iter().map(String::as_str).collect();
        let plan = Plan::new(&spec(&words, 1, None)).unwrap();
        let mut ways = Ways { levels: Vec::new() };
        assert_eq!(ways.get(&plan, 2, 0), 90_000);
        assert_eq!(ways.get(&plan, 40, 0), u64::MAX);
    }

    #[test]
    fn prefix_suffix_and_variations_shape_each_line() {
        let mut job = spec(&["ab", "c"], 1, Some(3));
        job.start = "x".into();
        job.end = "yz".into();
        job.mods = Mods {
            capitalize: true,
            reverse_capitalize: true,
            ..Mods::default()
        };
        let got = lines(&job, 2);
        // per sequence: the line, capitalized, reversed, reversed and capitalized
        assert_eq!(
            &got[..8],
            ["xabyz", "Xabyz", "zybax", "Zybax", "xcyz", "Xcyz", "zycx", "Zycx"]
        );
        assert_eq!(&got[8..12], ["xabcyz", "Xabcyz", "zycbax", "Zycbax"]);

        // without a prefix or suffix the first word (or, reversed, the last) opens the line
        let mut bare = spec(&["ab", "Cd"], 1, Some(4));
        bare.mods = job.mods;
        let got = lines(&bare, 1);
        assert_eq!(&got[8..12], ["abab", "Abab", "baba", "Baba"]);
        assert_eq!(&got[12..16], ["abCd", "Abcd", "dCba", "Dcba"]);
    }

    #[test]
    fn refuses_jobs_it_cannot_do() {
        assert!(Plan::new(&spec(&[], 1, None)).is_err());
        assert!(Plan::new(&spec(&["a", ""], 1, None)).is_err());
        assert!(Plan::new(&spec(&["a\nb"], 1, None)).is_err());
        assert!(Plan::new(&spec(&["a"], 1, Some(1 << 20))).is_err());
        let mut odd = spec(&["a"], 1, None);
        odd.newline = b"\r".to_vec();
        assert!(Plan::new(&odd).is_err());
    }
}
