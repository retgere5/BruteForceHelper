//! Can two different word sequences spell the same line?
//!
//! If not, a run without variations cannot write a line twice and needs no
//! memory of what it wrote. The words are then a uniquely decodable code,
//! which the Sardinas-Patterson test decides: it follows the "dangling
//! suffixes" left over when one word starts another, and the code is ambiguous
//! exactly when such a leftover is itself a word.

use std::collections::HashSet;

/// Word lists above this size, and searches longer than this many steps, are
/// given up on: the answer is then "maybe", and the run keeps its dedup.
const LARGEST_INPUT: usize = 8 << 20;
const MOST_STEPS: usize = 50_000_000;

/// True when no line can be put together from the words in two ways.
/// False also when that could not be settled.
pub fn spells_each_line_once(words: &[&[u8]]) -> bool {
    let size: usize = words.iter().map(|word| word.len()).sum();
    if words.is_empty() || size > LARGEST_INPUT {
        return false;
    }
    let mut code: HashSet<&[u8]> = HashSet::with_capacity(words.len());
    for &word in words {
        // an empty word, or the same word twice, already spells a line two ways
        if word.is_empty() || !code.insert(word) {
            return false;
        }
    }
    let mut sorted = words.to_vec();
    sorted.sort_unstable();

    let mut steps = size;
    let mut seen: HashSet<&[u8]> = HashSet::new();
    let mut pending: Vec<&[u8]> = Vec::new();
    // what is left of a word when another word begins it
    for &word in words {
        for cut in 1..word.len() {
            if code.contains(&word[..cut]) && seen.insert(&word[cut..]) {
                pending.push(&word[cut..]);
            }
        }
    }
    while let Some(left) = pending.pop() {
        if code.contains(left) {
            return false;
        }
        // a word begins the leftover: what follows that word is left over next
        for cut in 1..left.len() {
            if code.contains(&left[..cut]) && seen.insert(&left[cut..]) {
                pending.push(&left[cut..]);
            }
        }
        // the leftover begins a word: so is the rest of that word
        let from = sorted.partition_point(|&word| word < left);
        for &word in sorted[from..]
            .iter()
            .take_while(|word| word.starts_with(left))
        {
            if seen.insert(&word[left.len()..]) {
                pending.push(&word[left.len()..]);
            }
            steps += 1;
        }
        steps += left.len();
        if steps > MOST_STEPS {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn once(words: &[&str]) -> bool {
        let words: Vec<&[u8]> = words.iter().map(|word| word.as_bytes()).collect();
        spells_each_line_once(&words)
    }

    #[test]
    fn words_that_never_start_each_other_are_safe() {
        assert!(once(&["00", "01", "1"]));
        assert!(once(&["admin", "root", "2024"]));
        assert!(once(&[
            "muhammed", "gunuc", "63", "34", "!", "@", "prophet", "retgere", "5"
        ]));
        assert!(once(&["a"]));
    }

    #[test]
    fn a_word_spelled_by_others_is_ambiguous() {
        assert!(!once(&["a", "ab", "b"])); // ab = a + b
        assert!(!once(&["ab", "abab"])); // abab = ab + ab
        assert!(!once(&["a", "aa"]));
    }

    #[test]
    fn ambiguity_can_take_several_words_to_show() {
        assert!(!once(&["0", "01", "10"])); // 010 = 0 + 10 = 01 + 0
        assert!(!once(&["a", "ab", "bcd", "cde", "e"])); // abcde = a + bcd + e = ab + cde
        assert!(!once(&["011", "01110", "1110", "10011"])); // 011 + 10011 = 01110 + 011
    }

    #[test]
    fn a_word_may_start_another_without_ambiguity() {
        assert!(once(&["0", "01", "011"])); // read from the back, every line splits one way
        assert!(once(&["ab", "abc", "cb"]));
        assert!(once(&["a", "ba"]));
    }

    #[test]
    fn repeated_or_empty_words_are_ambiguous() {
        assert!(!once(&["a", "b", "a"]));
        assert!(!once(&["a", ""]));
        assert!(!once(&[]));
    }

    #[test]
    fn works_on_the_bytes_of_any_text() {
        assert!(once(&["ş", "ğü", "i"]));
        assert!(!once(&["ş", "şş"]));
    }
}
