<div align="center">

<img src="webui/static/favicon.svg" width="76" alt="">

# BruteForce Helper

**Build password wordlists from your own words, and clean the ones you already have.**

[![tests](https://github.com/retgere5/BruteForceHelper/actions/workflows/tests.yml/badge.svg)](https://github.com/retgere5/BruteForceHelper/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.9%2B-3776ab)
![license](https://img.shields.io/badge/license-MIT-2ea44f)

**English** · [Türkçe](README.tr.md)

</div>

---

Two command-line tools for password wordlists, plus a web interface for both.

| Tool | What it does |
|---|---|
| **PassGenerator** | Builds a wordlist from the words you give it: every combination, with optional case, reverse and leet variations |
| **WordlistOptimizer** | Cleans a wordlist you already have with 14 rules, or tells you what is in it |
| **Web interface** | Both tools in the browser, running only on your computer |

> **Important:** for learning and authorized security testing only. Use it on systems you own or have permission to test.

**Contents:** [Install](#install) · [PassGenerator](#passgenerator) · [WordlistOptimizer](#wordlistoptimizer) · [Web interface](#web-interface) · [Under the hood](#under-the-hood) · [Development](#development) · [License](#responsible-use-and-license)

## Install

You need Python 3.9 or newer. It runs on Windows, Linux and macOS (tested on Windows and Linux).

```bash
git clone https://github.com/retgere5/BruteForceHelper.git
cd BruteForceHelper
pip install -r requirements.txt
```

Then pick where to start:

```bash
python PassGenerator.py -w admin 2024    # build a wordlist
python WordlistFixer.py                  # clean or analyze one
python PassGenerator.py --webui          # do both in the browser
```

## PassGenerator

Give it a few words and it writes every way of joining them, one per line, to `combinations.txt`.

```bash
python PassGenerator.py -w admin root 2024
# admin, root, 2024, adminadmin, adminroot, admin2024, ...   39 lines

python PassGenerator.py -w admin root 2024 -M 9 -Ab
# admin, Admin, root, Root, 2024, adminroot, Adminroot, ...   18 lines

python PassGenerator.py -w password -AB -L337
# password, PASSWORD, p455w0rd, P455W0RD
```

Without `-M`, a line is made of at most as many words as you gave (three in the first example).

### Options

| Option | What it does | Example |
|---|---|---|
| `-w WORD ...` | Words or characters to combine (required) | `-w admin 2024 !` |
| `-m N`, `-M N` | Shortest and longest line, in characters | `-m 8 -M 12` |
| `-o FILE` | Output file | `-o mylist.txt` |
| `-AB` | Uppercase | `test` → `TEST` |
| `-Ab` | Capitalized | `test` → `Test` |
| `-ba` | Reversed | `test` → `tset` |
| `-Ba`, `-BA` | Reversed, then capitalized or uppercase | `test` → `Tset`, `TSET` |
| `-L337` | Leet: `a→4 b→8 e→3 g→6 i→1 l→1 o→0 s→5 t→7 z→2` | `password` → `p455w0rd` |
| `-TR` | Adds the Turkish form of each case variation | `ali` → `ALI`, `ALİ` |
| `-ws`, `-we` | Text before and after every line | `-ws x_ -we _23` → `x_admin_23` |

Run `python PassGenerator.py` with no options for more examples, or with `-h` for the full list.

<details>
<summary><b>Large runs</b>: gzip, limits, memory, resume, config file</summary>
<br>

| Option | What it does |
|---|---|
| `-z` | Write gzip (`.gz`). A file name ending in `.gz` does the same |
| `--limit N` | Stop after N lines |
| `--filters RULE ...` | Drop weak lines while generating, using the [cleaning rules](#rules). `all` turns every rule on |
| `--no-dedup` | Do not remove repeated lines: memory stays constant |
| `--max-memory MB` | Stop when the memory used for removing repeats reaches this size |
| `--disk-dedup` | Remove repeats on disk (SQLite): bounded memory, slower |
| `--resume` | Save progress while running. After an interruption, run the same command again to continue |
| `-c FILE` | Read the options from a JSON file. Options on the command line win |

```json
{ "words": ["admin", "root"], "min_length": 6, "AB": true, "L337": true }
```

With `--filters`, rules that look for something inside a line (repeats, runs, years and so on) skip whole groups of lines before they are built. The file gets smaller and the run gets faster.

</details>

### Faster with Rust (optional)

The generation loop also exists as a small Rust program in `native/`. It uses every CPU core and writes exactly the same file, byte for byte.

| 9 words, 8 to 12 characters | Python | With Rust |
|---|---|---|
| 5 million lines | 8.8 s | 0.08 s |
| 40 million candidate lines (`-AB -Ab -L337`) | 47 s | 0.5 s |
| 11 million lines, gzip | 15.5 s | 0.5 s |

<sub>Measured on a 6-core Ryzen 5 5600.</sub>

Build it once with [Rust](https://rustup.rs) 1.74 or newer:

```bash
cargo build --release --manifest-path native/Cargo.toml
```

PassGenerator finds the program by itself, on the command line and in the web interface. Without it everything runs in Python as before. Runs with `--filters`, `--resume` or `--disk-dedup` always use Python, and `BFH_NATIVE=0` turns the Rust program off.

## WordlistOptimizer

Cleans a wordlist: you choose the rules, it removes the lines that match and writes the rest to `optimized.txt`.

```bash
python WordlistFixer.py
```

It asks for the language, the files and the rules, then shows live statistics while it works. Two more ways to run it:

```bash
# only look at a list: how many lines, how long, which characters
python WordlistFixer.py --analyze rockyou.txt --lang en

# no questions: the settings come from a file
python WordlistFixer.py --config clean.json --lang en
```

```json
{
  "input": "rockyou.txt",
  "output": "cleaned.txt",
  "min_length": 8,
  "max_length": 16,
  "repetitive_chars": true,
  "sequential_chars": true,
  "keyboard_patterns": true,
  "common_words": true
}
```

<details>
<summary><a id="rules"></a><b>The 14 rules</b></summary>
<br>

| Rule | Removes a line that | Example |
|---|---|---|
| `min_length_filter` | is shorter than 4 characters | `abc` |
| `repetitive_chars` | has the same character 4 times in a row | `aaaa12` |
| `pattern_repetition` | repeats a piece of 2 or more characters straight away | `abab`, `1a21a2` |
| `number_only` | is digits only, 6 or more of them | `482913` |
| `letter_only` | is letters only, 6 or more of them | `sunshine` |
| `single_char_type` | is made of one kind of character: all digits, all letters or all symbols | `hello` |
| `sequential_chars` | has 4 neighbours of the alphabet or the digits in a row, in either direction | `abcd`, `4321` |
| `keyboard_patterns` | contains `qwerty`, `asdfgh`, `zxcvbn`, `qwertz` or `azerty` | `qwerty7` |
| `special_patterns` | contains `!@#` | `pass!@#` |
| `year_patterns` | contains a year from 1900 to 2099 | `ali1998` |
| `date_patterns` | contains a date, or 8 digits in a row | `01.02.2024` |
| `phone_patterns` | contains a Turkish mobile number | `05321234567` |
| `common_words` | contains `password`, `admin`, `123456`, `qwerty`, `letmein`, `welcome`, `monkey`, `dragon`, `master` or `football` | `admin42` |
| `leet_speak` | has a letter together with its leet stand-in, such as `a` with `4` or `s` with `5` | `pa5sword` |

</details>

Good to know:

- `.gz` files work as input and as output.
- Lists with broken UTF-8 (rockyou has some) are read without errors, and those lines are written back unchanged.
- Large lists are filtered on every CPU core. The order of the lines does not change.
- Messages are Turkish by default. `--lang en` switches `--config` and `--analyze` to English.
- While it runs, `q` stops and `c` saves a checkpoint and stops. These two keys work on Windows only.

## Web interface

```bash
python PassGenerator.py --webui
```

The browser opens at `http://127.0.0.1:8765` with three tools: **Generate**, **Clean** and **Analyze**. The first lines of the list appear while you type, a wordlist can be dropped onto the page, and each screen shows the command line that does the same job.

- It runs only on your computer. Nothing is sent anywhere, and the page loads nothing from the internet.
- Results go to the `output/` folder.
- `--port 9000` picks another port. `--no-browser` only prints the link.
- `python WordlistFixer.py --webui` opens it on the Clean tab.
- The page is in English and Turkish.

## Under the hood

- The number of lines and the size of the file are worked out from the word lengths before anything is written. The web interface shows them while you type.
- The generator only follows word sequences that can still fit between `-m` and `-M`. With `--filters` it also skips whole branches a rule would remove: with one rule on, 2.0 of the 2.2 million removed lines of the 9-word example are never built.
- The Rust core has to write the same bytes as the Python loop. Tests run both on fixed and random jobs and compare the files.
- Repeated lines are tracked in about 20 bytes per line in Rust, on disk, or not at all, and long runs can be resumed.
- The web interface needs nothing but Python's standard library: no build step, no external request. It listens on 127.0.0.1 only, checks a per-launch token and where each request comes from, and sends a strict content security policy.
- More than 250 Python tests and about 40 Rust tests run on Windows and Linux with Python 3.9 and 3.12.

## Development

```bash
pip install -r requirements-dev.txt
pytest                                          # Python tests
cargo test --manifest-path native/Cargo.toml    # Rust tests
```

## Responsible use and license

This project is for education and authorized security testing. Making sure you have permission to test a system is your responsibility. The author is not responsible for misuse.

Released under the [MIT License](LICENSE).

---

<div align="center">

Made with ❤️ by [retgere5](https://github.com/retgere5)

</div>
