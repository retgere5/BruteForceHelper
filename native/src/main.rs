//! bfh-core: the generation loop of BruteForce Helper's PassGenerator.
//!
//! PassGenerator.py starts this program, writes a job to its stdin (see
//! spec.rs) and reads progress from its stderr; the generated lines leave
//! through stdout, which the caller points at the output file.

#![forbid(unsafe_code)]

mod dedup;
mod gz;
mod run;
mod sardinas;
mod spec;
mod text;
mod walk;

use std::io::{self, BufWriter, Write};
use std::process::ExitCode;

use spec::{hex, Spec, PROTOCOL};

/// Why a job was not done.
enum Failure {
    /// The job is the problem (another protocol, an unknown option, missing
    /// case data): nothing was written and the caller should run it itself.
    Job(String),
    /// Reading or writing failed on the way.
    Io(io::Error),
}

impl From<io::Error> for Failure {
    fn from(error: io::Error) -> Failure {
        Failure::Io(error)
    }
}

impl From<String> for Failure {
    fn from(message: String) -> Failure {
        Failure::Job(message)
    }
}

fn main() -> ExitCode {
    if std::env::args().nth(1).as_deref() == Some("--protocol") {
        println!("{PROTOCOL}");
        return ExitCode::SUCCESS;
    }
    let (kind, message, code) = match serve() {
        Ok(()) => return ExitCode::SUCCESS,
        Err(Failure::Job(message)) => ("job", message, 2),
        Err(Failure::Io(error)) => ("io", error.to_string(), 1),
    };
    let _ = writeln!(io::stderr(), "E {kind} {message}");
    ExitCode::from(code)
}

/// Reads the job on stdin and does it.
fn serve() -> Result<(), Failure> {
    let spec = Spec::read(&mut io::stdin().lock())?;
    match spec.command.as_str() {
        "generate" => run::generate(&spec),
        "variants" => variants(&spec),
        other => Err(Failure::Job(format!("unknown command: {other}"))),
    }
}

/// For each `line` of the job, every variation of it (hex, space separated):
/// what apply_flags() returns in Python. Lets the tests compare the two.
fn variants(spec: &Spec) -> Result<(), Failure> {
    let list = text::variants(&spec.mods);
    let mut out = BufWriter::new(io::stdout().lock());
    for line in &spec.lines {
        let mut row = Vec::with_capacity(list.len());
        for variant in &list {
            row.push(hex(variant.first(&spec.table, line)?.as_bytes()));
        }
        writeln!(out, "{}", row.join(" "))?;
    }
    out.flush()?;
    Ok(())
}
