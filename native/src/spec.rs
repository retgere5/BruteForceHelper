//! The job format.
//!
//! A caller writes one `key value...` line per option to stdin and closes the
//! job with `go`. Text travels as hex-encoded UTF-8, `-` stands for an option
//! that is not set:
//!
//! ```text
//! BFH1 generate
//! words <hex>...
//! min <n>
//! max <n|->
//! start <hex|->
//! end <hex|->
//! mods <7 x 0/1>      uppercase capitalize reverse reverse_capitalize reverse_upper leet turkish
//! dedup memory|none
//! limit <n|->
//! maxmem <bytes|->
//! gzip 0|1
//! newline <hex>
//! threads <n>         0 = one per CPU core
//! char <hex char> <hex upper> <hex lower> <hex title>
//! line <hex>          (variants command)
//! go
//! ```

use std::io::BufRead;

use crate::text::{Entry, Table};

pub const PROTOCOL: &str = "BFH1";

/// The variation switches, in the order PassGenerator keeps them.
#[derive(Clone, Copy, Default, Debug, PartialEq, Eq)]
pub struct Mods {
    pub uppercase: bool,
    pub capitalize: bool,
    pub reverse: bool,
    pub reverse_capitalize: bool,
    pub reverse_upper: bool,
    pub leet: bool,
    pub turkish: bool,
}

pub struct Spec {
    pub command: String,
    pub words: Vec<String>,
    pub min: u64,
    pub max: Option<u64>,
    pub start: String,
    pub end: String,
    pub mods: Mods,
    pub dedup: bool,
    pub limit: Option<u64>,
    pub maxmem: Option<u64>,
    pub gzip: bool,
    pub newline: Vec<u8>,
    pub threads: usize,
    pub table: Table,
    pub lines: Vec<String>,
}

impl Spec {
    /// Reads a job up to its `go` line.
    pub fn read(input: &mut impl BufRead) -> Result<Spec, String> {
        let mut spec = Spec {
            command: String::new(),
            words: Vec::new(),
            min: 0,
            max: None,
            start: String::new(),
            end: String::new(),
            mods: Mods::default(),
            dedup: true,
            limit: None,
            maxmem: None,
            gzip: false,
            newline: vec![b'\n'],
            threads: 0,
            table: Table::new(),
            lines: Vec::new(),
        };
        let mut line = String::new();
        if !next_line(input, &mut line)? {
            return Err("empty job".into());
        }
        match line.split_once(' ') {
            Some((PROTOCOL, command)) => spec.command = command.to_string(),
            _ => {
                return Err(format!(
                    "this build speaks {PROTOCOL}, the job starts with: {line}"
                ))
            }
        }
        while next_line(input, &mut line)? {
            let (key, value) = line.split_once(' ').unwrap_or((&line, ""));
            match key {
                "go" => return Ok(spec),
                "words" => spec.words = fields(value).map(text).collect::<Result<_, _>>()?,
                "min" => spec.min = number(value)?,
                "max" => spec.max = optional(value, number)?,
                "start" => spec.start = optional(value, text)?.unwrap_or_default(),
                "end" => spec.end = optional(value, text)?.unwrap_or_default(),
                "mods" => spec.mods = mods(value)?,
                "dedup" => spec.dedup = choice(value, "memory", "none")?,
                "limit" => spec.limit = optional(value, number)?,
                "maxmem" => spec.maxmem = optional(value, number)?,
                "gzip" => spec.gzip = choice(value, "1", "0")?,
                "newline" => spec.newline = unhex(value)?,
                "threads" => spec.threads = number(value)? as usize,
                "char" => {
                    let (c, entry) = char_row(value)?;
                    spec.table.add(c, entry);
                }
                "line" => spec.lines.push(text(value)?),
                _ => return Err(format!("unknown job line: {key}")),
            }
        }
        Err("the job ended before `go`".into())
    }
}

/// Reads the next line without its line ending; false at the end of the input.
fn next_line(input: &mut impl BufRead, line: &mut String) -> Result<bool, String> {
    line.clear();
    match input.read_line(line) {
        Ok(0) => Ok(false),
        Ok(_) => {
            while line.ends_with(['\n', '\r']) {
                line.pop();
            }
            Ok(true)
        }
        Err(error) => Err(format!("cannot read the job: {error}")),
    }
}

fn fields(value: &str) -> impl Iterator<Item = &str> {
    value.split(' ').filter(|field| !field.is_empty())
}

fn number(value: &str) -> Result<u64, String> {
    value.parse().map_err(|_| format!("not a number: {value}"))
}

fn optional<T>(
    value: &str,
    parse: impl Fn(&str) -> Result<T, String>,
) -> Result<Option<T>, String> {
    if value == "-" {
        Ok(None)
    } else {
        parse(value).map(Some)
    }
}

fn choice(value: &str, yes: &str, no: &str) -> Result<bool, String> {
    if value == yes {
        Ok(true)
    } else if value == no {
        Ok(false)
    } else {
        Err(format!("expected {yes} or {no}, got: {value}"))
    }
}

fn mods(value: &str) -> Result<Mods, String> {
    let bits: Vec<bool> = value.bytes().map(|bit| bit == b'1').collect();
    if bits.len() != 7 || value.bytes().any(|bit| bit != b'0' && bit != b'1') {
        return Err(format!("mods takes seven 0/1 digits, got: {value}"));
    }
    Ok(Mods {
        uppercase: bits[0],
        capitalize: bits[1],
        reverse: bits[2],
        reverse_capitalize: bits[3],
        reverse_upper: bits[4],
        leet: bits[5],
        turkish: bits[6],
    })
}

fn char_row(value: &str) -> Result<(char, Entry), String> {
    let parts: Vec<&str> = fields(value).collect();
    if parts.len() != 4 {
        return Err(format!("malformed char line: {value}"));
    }
    let key = text(parts[0])?;
    let mut chars = key.chars();
    let c = match (chars.next(), chars.next()) {
        (Some(c), None) => c,
        _ => return Err(format!("char line needs one character: {value}")),
    };
    Ok((
        c,
        Entry {
            upper: text(parts[1])?,
            lower: text(parts[2])?,
            title: text(parts[3])?,
        },
    ))
}

fn text(value: &str) -> Result<String, String> {
    String::from_utf8(unhex(value)?).map_err(|_| format!("not UTF-8: {value}"))
}

pub fn unhex(value: &str) -> Result<Vec<u8>, String> {
    fn digit(byte: u8) -> Option<u8> {
        match byte {
            b'0'..=b'9' => Some(byte - b'0'),
            b'a'..=b'f' => Some(byte - b'a' + 10),
            b'A'..=b'F' => Some(byte - b'A' + 10),
            _ => None,
        }
    }
    let bytes = value.as_bytes();
    if bytes.len() % 2 != 0 {
        return Err(format!("not hex: {value}"));
    }
    bytes
        .chunks_exact(2)
        .map(|pair| Some(digit(pair[0])? << 4 | digit(pair[1])?))
        .collect::<Option<Vec<u8>>>()
        .ok_or_else(|| format!("not hex: {value}"))
}

pub fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(DIGITS[(byte >> 4) as usize] as char);
        out.push(DIGITS[(byte & 15) as usize] as char);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn read(job: &str) -> Result<Spec, String> {
        Spec::read(&mut job.as_bytes())
    }

    #[test]
    fn hex_round_trip() {
        assert_eq!(hex("aç!".as_bytes()), "61c3a721");
        assert_eq!(unhex("61C3a721").unwrap(), "aç!".as_bytes());
        assert!(unhex("6").is_err());
        assert!(unhex("zz").is_err());
    }

    #[test]
    fn reads_every_option() {
        let spec = read(
            "BFH1 generate\nwords 6162 c3a7\nmin 2\nmax 5\nstart 78\nend -\nmods 1000011\n\
             dedup none\nlimit 10\nmaxmem -\ngzip 1\nnewline 0d0a\nthreads 3\n\
             char c3a7 c387 c3a7 c387\ngo\nstop\n",
        )
        .unwrap();
        assert_eq!(spec.command, "generate");
        assert_eq!(spec.words, ["ab", "ç"]);
        assert_eq!((spec.min, spec.max), (2, Some(5)));
        assert_eq!((spec.start.as_str(), spec.end.as_str()), ("x", ""));
        assert_eq!(
            spec.mods,
            Mods {
                uppercase: true,
                leet: true,
                turkish: true,
                ..Mods::default()
            }
        );
        assert!(!spec.dedup && spec.gzip);
        assert_eq!((spec.limit, spec.maxmem), (Some(10), None));
        assert_eq!(spec.newline, b"\r\n");
        assert_eq!(spec.threads, 3);
        let entry = spec.table.entry('ç').unwrap();
        assert_eq!((entry.upper.as_str(), entry.lower.as_str()), ("Ç", "ç"));
    }

    #[test]
    fn accepts_windows_line_endings_and_empty_lists() {
        let spec = read("BFH1 variants\r\nwords\r\nline 61\r\ngo\r\n").unwrap();
        assert!(spec.words.is_empty());
        assert_eq!(spec.lines, ["a"]);
    }

    #[test]
    fn refuses_what_it_does_not_understand() {
        let refusal = |job| read(job).err().unwrap();
        assert!(refusal("BFH0 generate\ngo\n").contains("BFH1"));
        assert!(refusal("BFH1 generate\ncolour 1\ngo\n").contains("colour"));
        assert!(refusal("BFH1 generate\nwords 61\n").contains("go"));
        assert!(read("BFH1 generate\nmods 10\ngo\n").is_err());
        assert!(read("BFH1 generate\nmin x\ngo\n").is_err());
        assert!(read("BFH1 generate\nchar c3a7 c387 c3a7\ngo\n").is_err());
        assert!(read("BFH1 generate\nchar c3a7c3a7 c387 c3a7 c387\ngo\n").is_err());
        assert!(read("").is_err());
    }
}
