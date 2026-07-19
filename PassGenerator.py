import sys
import time
import gzip
import json
from tqdm import tqdm
from itertools import product
import argparse
import os
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Combination estimate above which a heads-up is printed before generating
LARGE_COMBINATION_WARNING = 5_000_000

def open_output(filename, use_gzip):
    """Open the output file, gzip-compressed when requested or when it ends in .gz."""
    if use_gzip or filename.endswith('.gz'):
        return gzip.open(filename, 'wt', encoding='utf-8')
    return open(filename, 'w', encoding='utf-8')

def load_config(path):
    """Load a JSON config file whose keys mirror the command-line options
    (words, output, min_length, max_length, AB, Ab, ba, Ba, BA, L337,
    word_start, word_end, gzip). Command-line arguments override it."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def leet_convert(word):
    leet_dict = {
        'a': '4', 'A': '4',
        'b': '8', 'B': '8',
        'e': '3', 'E': '3',
        'g': '6', 'G': '6',
        'i': '1', 'I': '1',
        'l': '1', 'L': '1',
        'o': '0', 'O': '0',
        's': '5', 'S': '5',
        't': '7', 'T': '7',
        'z': '2', 'Z': '2'
    }
    return ''.join(leet_dict.get(char, char) for char in word)

def max_token_count(words, max_length):
    """How many tokens to combine.

    When ``max_length`` (a character length) is given, allow enough tokens to
    reach it: each token contributes at least the shortest word's length, so
    ``max_length // shortest_word`` tokens can still fit. When it is not given,
    fall back to the number of input words (the tool's legacy default).
    """
    if max_length:
        shortest = min((len(w) for w in words), default=1) or 1
        return max(1, max_length // shortest)
    return len(words)

def calculate_total_combinations(words, min_length, max_length, modifiers):
    """Estimate the number of combinations (drives the progress bar only)."""
    word_count = len(words)
    max_tokens = max_token_count(words, max_length)
    base_combinations = sum(word_count ** i for i in range(1, max_tokens + 1))

    # Calculate modifier multiplier
    modifier_multiplier = 1
    if modifiers.get('uppercase'):
        modifier_multiplier += 1
    if modifiers.get('capitalize'):
        modifier_multiplier += 1
    if modifiers.get('reverse'):
        modifier_multiplier += 1
    if modifiers.get('reverse_capitalize'):
        modifier_multiplier += 1
    if modifiers.get('reverse_upper'):
        modifier_multiplier += 1
    if modifiers.get('leet'):
        modifier_multiplier *= 2

    return base_combinations * modifier_multiplier

def generate_base_combinations(words, min_length, max_length, word_start=None, word_end=None):
    """Generator for base word combinations.

    ``min_length``/``max_length`` bound the *character length* of each combined
    string; the token count is bounded by :func:`max_token_count`.
    """
    max_tokens = max_token_count(words, max_length)
    for length in range(1, max_tokens + 1):
        for combo in product(words, repeat=length):
            combined = ''.join(combo)
            if len(combined) >= min_length and (not max_length or len(combined) <= max_length):
                if word_start:
                    combined = word_start + combined
                if word_end:
                    combined = combined + word_end
                yield combined

def apply_modifications(word, modifiers):
    """Apply modifications in a specific order"""
    results = [word]  # Start with original word
    modified = []

    # First apply case modifications
    if modifiers.get('uppercase'):
        modified.append(word.upper())
    if modifiers.get('capitalize'):
        modified.append(word.capitalize())
    results.extend(modified)

    # Then apply reverse modifications
    if any([modifiers.get('reverse'), modifiers.get('reverse_capitalize'), modifiers.get('reverse_upper')]):
        reversed_word = word[::-1]
        reverse_results = [reversed_word]
        if modifiers.get('reverse_capitalize'):
            reverse_results.append(reversed_word.capitalize())
        if modifiers.get('reverse_upper'):
            reverse_results.append(reversed_word.upper())
        results.extend(reverse_results)

    # Finally apply leet speak
    if modifiers.get('leet'):
        leet_results = [leet_convert(w) for w in results]
        results.extend(leet_results)

    return results

def write_unique(file, word, seen):
    """Write word to file if not seen before"""
    if word not in seen:
        seen.add(word)
        file.write(word + '\n')
        return True
    return False

def generate_and_save_combinations(lst, filename, min_length=1, max_length=None, uppercase=False, capitalize=False,
                                 reverse=False, reverse_capitalize=False, reverse_upper=False, leet=False,
                                 word_start=None, word_end=None, use_gzip=False):
    try:
        # Create modifiers dictionary
        modifiers = {
            'uppercase': uppercase,
            'capitalize': capitalize,
            'reverse': reverse,
            'reverse_capitalize': reverse_capitalize,
            'reverse_upper': reverse_upper,
            'leet': leet
        }

        # Calculate total combinations
        total_combinations = calculate_total_combinations(lst, min_length, max_length, modifiers)

        # Warn before a very large run
        if total_combinations > LARGE_COMBINATION_WARNING:
            print(f"{Fore.YELLOW}Warning: about {total_combinations:,} combinations estimated; "
                  f"this may take a while and use significant disk space.{Style.RESET_ALL}")

        with open_output(filename, use_gzip) as file:
            progress_bar = tqdm(total=total_combinations,
                              desc=f'{Fore.CYAN}Processing{Style.RESET_ALL}',
                              unit=f' {Fore.GREEN}combinations{Style.RESET_ALL}',
                              dynamic_ncols=True,
                              position=0,
                              leave=True,
                              ncols=150,
                              bar_format='{desc}: {percentage:.2f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}] {percentage:.2f}%',
                              miniters=1,
                              mininterval=0.1,
                              smoothing=0.3)
            
            start_time = time.time()
            seen = set()
            
            # Generate and process combinations
            for base_word in generate_base_combinations(lst, min_length, max_length, word_start, word_end):
                # Write original word
                if write_unique(file, base_word, seen):
                    progress_bar.update(1)
                
                # Apply modifications and write
                for modified_word in apply_modifications(base_word, modifiers):
                    if write_unique(file, modified_word, seen):
                        progress_bar.update(1)
            
            # Update progress bar to 100% if needed
            if progress_bar.n < total_combinations:
                progress_bar.update(total_combinations - progress_bar.n)
            
            progress_bar.close()
            end_time = time.time()
            elapsed_time = end_time - start_time

            # Print statistics
            print(f"\n{Fore.GREEN}Combinations saved successfully.{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Total combinations generated:{Style.RESET_ALL} {Fore.YELLOW}{len(seen):,}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Processing time:{Style.RESET_ALL} {Fore.YELLOW}{elapsed_time:.2f}{Style.RESET_ALL} seconds")
            print(f"{Fore.CYAN}Memory usage:{Style.RESET_ALL} {Fore.YELLOW}{sys.getsizeof(seen) / (1024*1024):.2f}{Style.RESET_ALL} MB")
            print(f"{Fore.CYAN}File location:{Style.RESET_ALL} {Fore.YELLOW}{os.path.abspath(filename)}{Style.RESET_ALL}")
            
    except PermissionError:
        print(f"{Fore.RED}Error: No write permission for file '{filename}'.{Style.RESET_ALL}")
    except IOError as e:
        print(f"{Fore.RED}File operation error: {e}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")

def print_usage_examples():
    print(f"\n{Fore.GREEN}=== Password Combination Generator ==={Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}Usage Examples:{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}1. Basic usage:{Style.RESET_ALL}")
    print("     python PassGenerator.py -w a b c")
    print("     This command generates all possible combinations of characters a, b, c")
    print(f"\n  {Fore.YELLOW}2. With custom output file:{Style.RESET_ALL}")
    print("     python PassGenerator.py -w a b c -o output.txt")
    print("     Saves combinations to 'output.txt'")
    print(f"\n  {Fore.YELLOW}3. With minimum and maximum length:{Style.RESET_ALL}")
    print("     python PassGenerator.py -w a b c -m 2 -M 4")
    print("     Generates combinations with length between 2 and 4")
    print(f"\n  {Fore.YELLOW}4. Case modifiers:{Style.RESET_ALL}")
    print("     python PassGenerator.py -w test -AB")
    print("     Generates uppercase version (TEST)")
    print("     python PassGenerator.py -w test -Ab")
    print("     Generates capitalized version (Test)")
    print("     python PassGenerator.py -w test -ba")
    print("     Generates reversed version (tset)")
    print("     python PassGenerator.py -w test -Ba")
    print("     Generates reversed and capitalized version (Tset)")
    print("     python PassGenerator.py -w test -BA")
    print("     Generates reversed uppercase version (TSET)")
    print(f"\n  {Fore.YELLOW}5. Leet mode:{Style.RESET_ALL}")
    print("     python PassGenerator.py -w test -L337")
    print("     Generates leet speak version (7357)")
    print(f"\n  {Fore.YELLOW}6. Word boundaries:{Style.RESET_ALL}")
    print("     python PassGenerator.py -w test -ws admin_ -we _2023")
    print("     Adds prefix and suffix to words (admin_test_2023)")
    print(f"\n  {Fore.YELLOW}7. With all parameters:{Style.RESET_ALL}")
    print("     python PassGenerator.py -w a b c -o output.txt -m 2 -M 4 -AB -L337 -ws pre_ -we _post")
    print(f"\n{Fore.CYAN}Note: Use quotes for characters containing spaces:{Style.RESET_ALL}")
    print('     python PassGenerator.py -w "123" "abc" "@#$"')

def main():
    # Pre-parse --config so it can supply defaults for the real parser
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument('-c', '--config')
    pre_args, _ = pre_parser.parse_known_args()
    config = {}
    if pre_args.config:
        try:
            config = load_config(pre_args.config)
        except Exception as e:
            print(f"{Fore.RED}Error loading config: {e}{Style.RESET_ALL}")
            return

    parser = argparse.ArgumentParser(
        description=f'{Fore.GREEN}Password Combination Generator{Style.RESET_ALL}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Run without parameters for detailed information.')

    parser.add_argument('-c', '--config',
                      help='Load options from a JSON config file (CLI args override it)')
    parser.add_argument('-w', '--words', nargs='+', required='words' not in config,
                      help='Characters to generate combinations from')
    parser.add_argument('-o', '--output', default='combinations.txt',
                      help='Output file name (default: combinations.txt)')
    parser.add_argument('-M', '--max-length', type=int,
                      help='Maximum combination length')
    parser.add_argument('-m', '--min-length', type=int, default=1,
                      help='Minimum combination length (default: 1)')
    
    # Case modifier arguments
    parser.add_argument('-AB', action='store_true',
                      help='Convert words to uppercase')
    parser.add_argument('-Ab', action='store_true',
                      help='Capitalize words')
    parser.add_argument('-ba', action='store_true',
                      help='Reverse words')
    parser.add_argument('-Ba', action='store_true',
                      help='Reverse and capitalize words')
    parser.add_argument('-BA', action='store_true',
                      help='Reverse and convert words to uppercase')
    parser.add_argument('-L337', action='store_true',
                      help='Convert letters to leet speak (e.g., LEET -> L337)')
    
    # Word boundary arguments
    parser.add_argument('-ws', '--word-start',
                      help='Add prefix to each word')
    parser.add_argument('-we', '--word-end',
                      help='Add suffix to each word')

    # Output arguments
    parser.add_argument('-z', '--gzip', action='store_true',
                      help='Write gzip-compressed output (.gz)')

    # Config values become defaults; explicit CLI arguments still override them
    parser.set_defaults(**config)

    # If no parameters are provided
    if len(sys.argv) == 1:
        print(f"\n{Fore.GREEN}=== Password Combination Generator ==={Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}This program generates all possible combinations of given characters.{Style.RESET_ALL}")
        print_usage_examples()
        return

    try:
        args = parser.parse_args()
        
        if not args.words:
            print(f"{Fore.RED}Error: You must specify at least one character.{Style.RESET_ALL}")
            return
            
        if args.max_length is not None and args.max_length < 1:
            print(f"{Fore.RED}Error: Maximum length cannot be less than 1.{Style.RESET_ALL}")
            return

        if args.min_length < 1:
            print(f"{Fore.RED}Error: Minimum length cannot be less than 1.{Style.RESET_ALL}")
            return

        if args.max_length is not None and args.min_length > args.max_length:
            print(f"{Fore.RED}Error: Minimum length cannot be greater than maximum length.{Style.RESET_ALL}")
            return

        # Resolve the output name: append .gz when compressing without the suffix
        use_gzip = args.gzip or args.output.endswith('.gz')
        output = args.output
        if use_gzip and not output.endswith('.gz'):
            output += '.gz'

        generate_and_save_combinations(
            args.words,
            output,
            args.min_length,
            args.max_length,
            uppercase=args.AB,
            capitalize=args.Ab,
            reverse=args.ba,
            reverse_capitalize=args.Ba,
            reverse_upper=args.BA,
            leet=args.L337,
            word_start=args.word_start,
            word_end=args.word_end,
            use_gzip=use_gzip
        )
        
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Run without parameters for help: python PassGenerator.py{Style.RESET_ALL}")

if __name__ == '__main__':
    main()

