//! Case, reversal and leet, done the way Python does them.
//!
//! Nothing here asks Rust how a character behaves. ASCII is fixed, and every
//! other character comes with its upper, lower and title forms in the job
//! (`char` lines), as the calling Python sees them. A different
//! Unicode version on either side therefore cannot change the output.

use std::collections::HashMap;

use crate::spec::Mods;

/// What Python knows about one non-ASCII character.
pub struct Entry {
    pub upper: String,
    pub lower: String,
    pub title: String,
}

/// Code points below this are looked up by index (covers Latin, Greek,
/// Cyrillic, Hebrew and Arabic), the rest through a map.
const DIRECT: usize = 0x800;

pub struct Table {
    direct: Vec<u16>,
    others: HashMap<char, u16>,
    entries: Vec<Entry>,
}

impl Table {
    pub fn new() -> Table {
        Table {
            direct: vec![0; DIRECT],
            others: HashMap::new(),
            entries: Vec::new(),
        }
    }

    pub fn add(&mut self, c: char, entry: Entry) {
        self.entries.push(entry);
        let slot = self.entries.len() as u16;
        match self.direct.get_mut(c as usize) {
            Some(direct) => *direct = slot,
            None => {
                self.others.insert(c, slot);
            }
        }
    }

    pub fn entry(&self, c: char) -> Option<&Entry> {
        let slot = match self.direct.get(c as usize) {
            Some(&slot) => slot,
            None => self.others.get(&c).copied().unwrap_or(0),
        };
        self.entries.get((slot as usize).wrapping_sub(1))
    }

    fn known(&self, c: char) -> Result<&Entry, String> {
        self.entry(c)
            .ok_or_else(|| format!("no case data for U+{:04X}", c as u32))
    }

    fn push_upper(&self, c: char, out: &mut String) -> Result<(), String> {
        if c.is_ascii() {
            out.push(c.to_ascii_uppercase());
        } else {
            out.push_str(&self.known(c)?.upper);
        }
        Ok(())
    }

    fn push_lower(&self, c: char, out: &mut String) -> Result<(), String> {
        if c.is_ascii() {
            out.push(c.to_ascii_lowercase());
        } else {
            out.push_str(&self.known(c)?.lower);
        }
        Ok(())
    }

    fn push_title(&self, c: char, out: &mut String) -> Result<(), String> {
        if c.is_ascii() {
            out.push(c.to_ascii_uppercase());
        } else {
            out.push_str(&self.known(c)?.title);
        }
        Ok(())
    }

    /// str.upper()
    pub fn upper(&self, text: &str) -> Result<String, String> {
        let mut out = String::with_capacity(text.len());
        text.chars()
            .try_for_each(|c| self.push_upper(c, &mut out))?;
        Ok(out)
    }

    /// str.lower(). Greek capital sigma is the one letter whose lowercase
    /// depends on its neighbours; the caller keeps such input in Python.
    pub fn lower(&self, text: &str) -> Result<String, String> {
        let mut out = String::with_capacity(text.len());
        text.chars()
            .try_for_each(|c| self.push_lower(c, &mut out))?;
        Ok(out)
    }

    /// str.capitalize(): the first character in title case, the rest lowered.
    pub fn capitalize(&self, text: &str) -> Result<String, String> {
        let mut out = String::with_capacity(text.len());
        let mut chars = text.chars();
        if let Some(first) = chars.next() {
            self.push_title(first, &mut out)?;
            chars.try_for_each(|c| self.push_lower(c, &mut out))?;
        }
        Ok(out)
    }

    /// PassGenerator.tr_upper(): ali -> ALİ
    pub fn tr_upper(&self, text: &str) -> Result<String, String> {
        let mut out = String::with_capacity(text.len());
        text.chars()
            .try_for_each(|c| self.push_upper(dotted_upper(c), &mut out))?;
        Ok(out)
    }

    /// PassGenerator.tr_lower(): IRMAK -> ırmak
    pub fn tr_lower(&self, text: &str) -> Result<String, String> {
        let mut out = String::with_capacity(text.len());
        text.chars()
            .try_for_each(|c| self.push_lower(dotted_lower(c), &mut out))?;
        Ok(out)
    }

    /// PassGenerator.tr_capitalize(): istanbul -> İstanbul, ALİ -> Ali
    pub fn tr_capitalize(&self, text: &str) -> Result<String, String> {
        let mut out = String::with_capacity(text.len());
        let mut chars = text.chars();
        if let Some(first) = chars.next() {
            self.push_title(dotted_upper(first), &mut out)?;
            chars.try_for_each(|c| self.push_lower(dotted_lower(c), &mut out))?;
        }
        Ok(out)
    }
}

// Turkish keeps the dot: i <-> İ and ı <-> I
fn dotted_upper(c: char) -> char {
    match c {
        'i' => 'İ',
        'ı' => 'I',
        other => other,
    }
}

fn dotted_lower(c: char) -> char {
    match c {
        'I' => 'ı',
        'İ' => 'i',
        other => other,
    }
}

/// text[::-1]: reversed character by character.
pub fn reversed(text: &str) -> String {
    text.chars().rev().collect()
}

/// PassGenerator.leet_convert()
pub fn leet(text: &str) -> String {
    text.chars()
        .map(|c| match c {
            'a' | 'A' => '4',
            'b' | 'B' => '8',
            'e' | 'E' => '3',
            'g' | 'G' => '6',
            'i' | 'I' | 'l' | 'L' => '1',
            'o' | 'O' => '0',
            's' | 'S' => '5',
            't' | 'T' => '7',
            'z' | 'Z' => '2',
            other => other,
        })
        .collect()
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Case {
    Plain,
    Upper,
    TrUpper,
    Capital,
    TrCapital,
}

/// One of the lines a word turns into.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Variant {
    pub reversed: bool,
    pub case: Case,
    pub leet: bool,
}

/// The variations these switches make, in the order apply_flags() lists them.
pub fn variants(mods: &Mods) -> Vec<Variant> {
    let plain = |reversed, case| Variant {
        reversed,
        case,
        leet: false,
    };
    let mut list = vec![plain(false, Case::Plain)];
    if mods.uppercase {
        list.push(plain(false, Case::Upper));
        if mods.turkish {
            list.push(plain(false, Case::TrUpper));
        }
    }
    if mods.capitalize {
        list.push(plain(false, Case::Capital));
        if mods.turkish {
            list.push(plain(false, Case::TrCapital));
        }
    }
    if mods.reverse || mods.reverse_capitalize || mods.reverse_upper {
        list.push(plain(true, Case::Plain));
        if mods.reverse_capitalize {
            list.push(plain(true, Case::Capital));
            if mods.turkish {
                list.push(plain(true, Case::TrCapital));
            }
        }
        if mods.reverse_upper {
            list.push(plain(true, Case::Upper));
            if mods.turkish {
                list.push(plain(true, Case::TrUpper));
            }
        }
    }
    if mods.leet {
        let leeted: Vec<Variant> = list
            .iter()
            .map(|variant| Variant {
                leet: true,
                ..*variant
            })
            .collect();
        list.extend(leeted);
    }
    list
}

impl Variant {
    /// A line is its pieces (prefix, words, suffix) one after another, and every
    /// operation here works character by character. So a variation of the line
    /// is the same variation of each piece, joined in line order (backwards for
    /// a reversed variation). Only capitalizing tells the pieces apart: the
    /// piece that opens the line takes `first`, all others `rest`.
    pub fn first(&self, table: &Table, piece: &str) -> Result<String, String> {
        let piece = self.turned(piece);
        let cased = match self.case {
            Case::Plain => piece,
            Case::Upper => table.upper(&piece)?,
            Case::TrUpper => table.tr_upper(&piece)?,
            Case::Capital => table.capitalize(&piece)?,
            Case::TrCapital => table.tr_capitalize(&piece)?,
        };
        Ok(self.leeted(cased))
    }

    pub fn rest(&self, table: &Table, piece: &str) -> Result<String, String> {
        let piece = self.turned(piece);
        let cased = match self.case {
            Case::Plain => piece,
            Case::Upper => table.upper(&piece)?,
            Case::TrUpper => table.tr_upper(&piece)?,
            Case::Capital => table.lower(&piece)?,
            Case::TrCapital => table.tr_lower(&piece)?,
        };
        Ok(self.leeted(cased))
    }

    /// Whether `first` and `rest` can differ.
    pub fn capitalizes(&self) -> bool {
        matches!(self.case, Case::Capital | Case::TrCapital)
    }

    fn turned(&self, piece: &str) -> String {
        if self.reversed {
            reversed(piece)
        } else {
            piece.to_string()
        }
    }

    fn leeted(&self, piece: String) -> String {
        if self.leet {
            leet(&piece)
        } else {
            piece
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn turkish() -> Table {
        let mut table = Table::new();
        let mut add = |c: char, upper: &str, lower: &str, title: &str| {
            let entry = Entry {
                upper: upper.into(),
                lower: lower.into(),
                title: title.into(),
            };
            table.add(c, entry);
        };
        add('İ', "İ", "i\u{307}", "İ");
        add('ı', "I", "ı", "I");
        add('ş', "Ş", "ş", "Ş");
        add('Ş', "Ş", "ş", "Ş");
        add('ß', "SS", "ß", "Ss");
        add('\u{307}', "\u{307}", "\u{307}", "\u{307}");
        add('\u{1F600}', "\u{1F600}", "\u{1F600}", "\u{1F600}");
        table
    }

    #[test]
    fn python_case_rules() {
        let table = turkish();
        assert_eq!(table.upper("ali ış ß").unwrap(), "ALI IŞ SS");
        assert_eq!(table.lower("AİŞ").unwrap(), "ai\u{307}ş");
        assert_eq!(table.capitalize("ßA").unwrap(), "Ssa");
        assert_eq!(table.capitalize("").unwrap(), "");
    }

    #[test]
    fn turkish_case_rules() {
        let table = turkish();
        assert_eq!(table.tr_upper("ali ış").unwrap(), "ALİ IŞ");
        assert_eq!(table.tr_lower("AİIŞ").unwrap(), "aiış");
        assert_eq!(table.tr_capitalize("istanbul").unwrap(), "İstanbul");
        assert_eq!(table.tr_capitalize("ALİ").unwrap(), "Ali");
        assert_eq!(table.tr_capitalize("IŞIK").unwrap(), "Işık");
    }

    #[test]
    fn characters_outside_the_table_are_an_error() {
        let table = turkish();
        assert_eq!(table.upper("aç").unwrap_err(), "no case data for U+00E7");
        // characters past the directly indexed range are found too
        assert_eq!(table.upper("\u{1F600}").unwrap(), "\u{1F600}");
        assert!(table.entry('\u{1F601}').is_none());
    }

    #[test]
    fn reversal_and_leet() {
        assert_eq!(reversed("aşk1"), "1kşa");
        assert_eq!(leet("Test Leet zigzag"), "7357 1337 216246");
    }

    #[test]
    fn variation_order_follows_apply_flags() {
        let all = Mods {
            uppercase: true,
            capitalize: true,
            reverse: false,
            reverse_capitalize: true,
            reverse_upper: true,
            leet: true,
            turkish: true,
        };
        let list = variants(&all);
        assert_eq!(list.len(), 20);
        let table = turkish();
        let lines: Vec<String> = list
            .iter()
            .map(|variant| variant.first(&table, "ali").unwrap())
            .collect();
        assert_eq!(
            lines,
            [
                "ali", "ALI", "ALİ", "Ali", "Ali", "ila", "Ila", "İla", "ILA", "İLA", "411", "411",
                "41İ", "411", "411", "114", "114", "İ14", "114", "İ14"
            ]
        );
        assert_eq!(variants(&Mods::default()).len(), 1);
        assert_eq!(
            variants(&Mods {
                turkish: true,
                ..Mods::default()
            })
            .len(),
            1
        );
    }

    #[test]
    fn only_the_opening_piece_is_capitalized() {
        let table = turkish();
        let capital = Variant {
            reversed: false,
            case: Case::Capital,
            leet: false,
        };
        assert_eq!(capital.first(&table, "aLi").unwrap(), "Ali");
        assert_eq!(capital.rest(&table, "aLi").unwrap(), "ali");
        let turned = Variant {
            reversed: true,
            case: Case::TrCapital,
            leet: true,
        };
        assert_eq!(turned.first(&table, "kIi").unwrap(), "İık");
        assert_eq!(turned.rest(&table, "kIi").unwrap(), "1ık");
        assert!(
            capital.capitalizes()
                && !Variant {
                    case: Case::Upper,
                    ..capital
                }
                .capitalizes()
        );
    }
}
