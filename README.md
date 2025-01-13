# 🛠️ BruteForce Helper Tools

<div align="center">

![GitHub](https://img.shields.io/github/license/retgere5/BruteForceHelper)
![Python](https://img.shields.io/badge/python-3.6+-blue.svg)
![Version](https://img.shields.io/badge/version-1.0.0-green)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/retgere5/BruteForceHelper/graphs/commit-activity)

A powerful collection of tools for password analysis and wordlist optimization. 
*For educational purposes only.*

</div>

## 📋 Table of Contents
- [Features](#-features)
- [Installation](#-installation)
- [Tools](#-tools)
  - [PassGenerator](#-passgenerator)
  - [WordlistOptimizer](#-wordlistoptimizer)
- [Usage Examples](#-usage-examples)
- [Disclaimer](#-disclaimer)
- [License](#-license)

## ✨ Features

### 🔐 PassGenerator
- ⚡ High-speed combination generation
- 📊 Real-time progress tracking
- 💾 Checkpoint system for large operations
- 🚀 Multi-threaded processing
- 📝 Custom character set support

### 🔍 WordlistOptimizer
- 🎯 Multiple filtering options
- 📈 Real-time statistics
- ⏸️ Checkpoint system
- 💪 Multi-processing support
- 🧠 Smart filter recommendations
- 📊 Detailed progress tracking

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/retgere5/BruteForceHelper.git

# Navigate to directory
cd BruteForceHelper

# Install required packages
pip install -r requirements.txt
```

## 🛠️ Tools

### 🔑 PassGenerator

Generate all possible password combinations from given characters.

```bash
python PassGenerator.py -w [characters] [-o output_file] [-m max_length]
```

#### Examples:
```bash
# Basic usage
python PassGenerator.py -w a b c

# With custom output file
python PassGenerator.py -w a b c -o wordlist.txt

# With maximum length
python PassGenerator.py -w a b c -m 4

# With special characters
python PassGenerator.py -w "123" "abc" "@#$" -o output.txt -m 3
```

### 🔍 WordlistOptimizer

Clean and optimize your wordlists with advanced filtering options.

```bash
python WordlistOptimizer.py
```

#### Interactive Setup:
1. 📁 Select input/output files
2. ⚙️ Choose filtering options:
   - Length filters
   - Pattern filters
   - Character type filters
   - Common word filters
3. 🎯 Configure optimization settings
4. 📊 View real-time statistics

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
- Remove common patterns
- Filter by length
- Remove sequential characters
- Eliminate keyboard patterns
- Remove single character types
</details>

## ⚠️ Disclaimer

This tool is for **educational purposes only**. Users are responsible for ensuring they have permission to test any systems they use this tool against. The creators are not responsible for any misuse or damage caused by this program.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
<div align="center">
Made with ❤️ by <a href="https://github.com/retgere5">retgere5</a>
</div> 