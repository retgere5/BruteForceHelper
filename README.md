# 🛠️ BruteForce Helper Tools

![GitHub Python Version](https://img.shields.io/badge/python-3.6%2B-blue)
![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)

A powerful collection of tools for password analysis and wordlist optimization. _For educational purposes only._

## 📋 Table of Contents

* [Features](#-features)
* [Installation](#-installation)
* [Tools](#-tools)
  * [PassGenerator](#-passgenerator)
  * [WordlistOptimizer](#-wordlistoptimizer)
* [Usage Examples](#-usage-examples)
* [Upcoming Features](#-upcoming-features)
* [Disclaimer](#-disclaimer)
* [License](#-license)

## ✨ Features

### 🔐 PassGenerator

* ⚡ High-speed combination generation
* 📊 Real-time progress tracking with colored output
* 💾 Efficient memory management
* 🔄 Case modifiers:
  * `-AB`: Convert to uppercase (test -> TEST)
  * `-Ab`: Capitalize first letter (test -> Test)
  * `-ba`: Reverse text (test -> tset)
  * `-Ba`: Reverse and capitalize (test -> Tset)
  * `-BA`: Reverse and uppercase (test -> TSET)
* 🔢 Length control:
  * `-m`: Minimum length
  * `-M`: Maximum length
* 🎯 Word boundaries:
  * `-ws`: Add prefix to words
  * `-we`: Add suffix to words
* 🔠 Leet speak conversion (`-L337`)
* 🎨 Colorful interactive UI
* 🚫 Duplicate prevention
* 📝 UTF-8 encoding support

### �� WordlistOptimizer

* 🎯 Multiple filtering options
* 📈 Real-time statistics
* ⏸️ Checkpoint system
* 💪 Multi-processing support
* 🧠 Smart filter recommendations
* 📊 Detailed progress tracking
* 🌈 Colorful interactive UI
* 🌍 Multi-language support (English/Turkish)
* 💡 Smart filter suggestions based on wordlist size
* 🔄 Session saving and loading
* 📊 Advanced statistics and reporting
* ⚡ Performance optimizations

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/retgere5/BruteForceHelper.git

# Navigate to directory
cd BruteForceHelper

# Install required packages
pip install -r requirements.txt
```

### 🧪 Running Tests

```bash
# Install development dependencies (adds pytest)
pip install -r requirements-dev.txt

# Run the test suite
pytest
```

> WordlistOptimizer's interactive `q`/`c` stop/checkpoint keys use `msvcrt` and are Windows-only; the rest of the tool (including filtering and multi-processing) runs on Linux and macOS as well.

## 🛠️ Tools

### 🔑 PassGenerator

Generate all possible password combinations with advanced features.

```bash
python PassGenerator.py -w [words/chars] [options]
```

#### Options:

* `-w, --words`: Words or characters to generate combinations from (required)
* `-o, --output`: Output file name (default: combinations.txt)
* `-m, --min-length`: Minimum combination length (default: 1)
* `-M, --max-length`: Maximum combination length
* `-AB`: Convert to uppercase
* `-Ab`: Capitalize first letter
* `-ba`: Reverse text
* `-Ba`: Reverse and capitalize
* `-BA`: Reverse and uppercase
* `-L337`: Convert to leet speak
* `-ws, --word-start`: Add prefix to words
* `-we, --word-end`: Add suffix to words
* `-z, --gzip`: Write gzip-compressed output (`.gz`)
* `-c, --config`: Load options from a JSON config file (CLI arguments override it)

#### Examples:

```bash
# Basic usage with case modifiers
python PassGenerator.py -w test -AB -Ab
# Output: test, TEST, Test

# With length control
python PassGenerator.py -w a b c -m 2 -M 4
# Output: aa, aaa, aaaa, ab, aba, ...

# With word boundaries
python PassGenerator.py -w test -ws admin_ -we _2023
# Output: admin_test_2023

# Complex combinations
python PassGenerator.py -w test user -m 4 -M 8 -AB -L337
# Output: test, TEST, T3ST, user, USER, U53R, testuser, ...

# Multiple features
python PassGenerator.py -w retgere 5 Prophet -m 6 -M 12 -AB -ba -Ab -Ba
# Output: retgere, RETGERE, eregter, Retgere, retgere5, Prophet, ...

# Compressed output (.gz)
python PassGenerator.py -w test -AB -z -o wordlist.txt
# Writes wordlist.txt.gz

# From a JSON config file (CLI args still override individual values)
python PassGenerator.py -c config.json
```

Example `config.json` for PassGenerator:

```json
{
  "words": ["test", "admin"],
  "min_length": 4,
  "max_length": 12,
  "AB": true,
  "L337": true,
  "output": "wordlist.txt",
  "gzip": true
}
```

### 🔍 WordlistOptimizer

Clean and optimize your wordlists with advanced filtering options.

```bash
# Interactive
python WordlistFixer.py

# Non-interactive, from a JSON config
python WordlistFixer.py --config config.json --lang en
```

Example `config.json` for WordlistOptimizer (missing filter keys default to off; `input` is required):

```json
{
  "input": "rockyou.txt",
  "output": "cleaned.txt.gz",
  "min_length_filter": true,
  "repetitive_chars": true,
  "keep_stats": true
}
```

#### Interactive Setup:

1. 🌍 Select your language (English/Turkish)
2. 📁 Select input/output files (use a `.gz` name for gzip-compressed input or output)
3. ⚙️ Choose filtering options:
   * Length filters
   * Pattern filters
   * Character type filters
   * Common word filters
4. 🎯 Configure optimization settings
5. 📊 View real-time statistics and filter effectiveness

#### Filter Groups:

* **Basic Security**
  * Minimum length filter
  * Repetitive character filter
  * Pattern repetition filter

* **Character Based**
  * Numbers only filter
  * Letters only filter
  * Single character type filter

* **Pattern Based**
  * Sequential characters filter
  * Keyboard pattern filter
  * Special pattern filter

* **Format Based**
  * Year pattern filter
  * Date pattern filter
  * Phone number filter

* **Word Based**
  * Common words filter
  * Leet speak filter

## 💡 Usage Examples

<details>
<summary>Click to expand usage examples</summary>

### PassGenerator

```bash
# Generate all combinations of numbers 0-9
python PassGenerator.py -w 0 1 2 3 4 5 6 7 8 9 -m 4

# Generate combinations of special characters
python PassGenerator.py -w "@" "#" "$" "%" -o special_chars.txt
```

### WordlistOptimizer

* Remove common patterns
* Filter by length
* Remove sequential characters
* Eliminate keyboard patterns
* Remove single character types
* Language-specific filtering
* Smart recommendations based on wordlist size
* Real-time filter effectiveness tracking
</details>

## 🔜 Upcoming Features

### 🆕 Planned Improvements

* 🚀 Performance optimizations:
  * Optimized memory usage
  * Streaming / disk-based deduplication for very large runs
* 💾 File handling:
  * PassGenerator resume capability
  * Disk space checks
* 📊 Enhanced progress tracking:
  * Memory usage indicator
  * Wordlist statistics
* 🛡️ Error handling:
  * Memory overflow protection
* ⚙️ Configuration:
  * Combination limit settings

## ⚠️ Disclaimer

This tool is for **educational purposes only**. Users are responsible for ensuring they have permission to test any systems they use this tool against. The creators are not responsible for any misuse or damage caused by this program.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Made with ❤️ by retgere5 