# BruteForce Helper Tools

A collection of tools to help with password analysis and wordlist optimization. For educational purposes only.

## Tools

### 1. PassGenerator
Generate password combinations based on given characters.

Features:
- Custom character set input
- Progress bar with real-time statistics
- Checkpoint system for large operations
- Multi-threaded processing

### 2. WordlistOptimizer
Optimize and clean wordlists by applying various filters.

Features:
- Multiple filtering options
- Real-time statistics
- Checkpoint system
- Multi-processing support
- Smart filter recommendations
- Progress tracking with detailed statistics

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/BruteForceHelper.git

# Navigate to directory
cd BruteForceHelper

# Install required packages
pip install -r requirements.txt
```

## Usage

### PassGenerator

```bash
python PassGenerator.py -w [characters] [-o output_file] [-m max_length]
```

Example:
```bash
python PassGenerator.py -w a b c -o wordlist.txt -m 4
```

### WordlistOptimizer

```bash
python WordlistOptimizer.py
```
Follow the interactive prompts to:
1. Select input/output files
2. Choose filtering options
3. Configure optimization settings

## Disclaimer

This tool is for educational purposes only. Users are responsible for ensuring they have permission to test any systems they use this tool against.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 