import sys
import time
from tqdm import tqdm
from itertools import product
import argparse
import os
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

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
    leet_word = ''
    for char in word:
        leet_word += leet_dict.get(char, char)
    return leet_word

def apply_case_modifiers(word, uppercase=False, capitalize=False, reverse=False, reverse_capitalize=False, reverse_upper=False, leet=False):
    results = []  # Don't include original word as it's already written
    
    if reverse or reverse_capitalize or reverse_upper:
        reversed_word = word[::-1]
        if reverse:
            results.append(reversed_word)
        if reverse_capitalize:
            results.append(reversed_word.capitalize())
        if reverse_upper:
            results.append(reversed_word.upper())
    
    if uppercase:
        results.append(word.upper())
    if capitalize:
        results.append(word.capitalize())
    
    # Apply leet mode if requested
    if leet:
        results.append(leet_convert(word))
        # Apply leet to all modified versions
        modified_results = results.copy()
        for modified_word in modified_results:
            results.append(leet_convert(modified_word))
    
    return list(dict.fromkeys(results))  # Remove duplicates while preserving order

def generate_and_save_combinations(lst, filename, min_length=1, max_length=None, uppercase=False, capitalize=False, 
                                 reverse=False, reverse_capitalize=False, reverse_upper=False, leet=False,
                                 word_start=None, word_end=None):
    try:
        # First, generate combinations of whole words
        words = lst.copy()
        total_combinations = 0
        
        # Calculate combinations for whole words and their combinations
        word_combinations = []
        for length in range(1, len(lst) + 1):
            for combo in product(words, repeat=length):
                combined = ''.join(combo)
                if len(combined) >= min_length and (max_length is None or len(combined) <= max_length):
                    # Apply word start/end if specified
                    modified_word = combined
                    if word_start:
                        modified_word = word_start + modified_word
                    if word_end:
                        modified_word = modified_word + word_end
                    word_combinations.append(modified_word)
        
        # Calculate total combinations including case modifications
        total_combinations = len(word_combinations)
        if uppercase or capitalize or reverse or reverse_capitalize or reverse_upper or leet:
            total_combinations *= 2  # At least double for each modifier

        with open(filename, 'w', encoding='utf-8') as file:
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
            
            # Process all word combinations
            seen = set()  # To avoid duplicates
            for word in word_combinations:
                # Always write the original word first
                if word not in seen:
                    seen.add(word)
                    file.write(word + '\n')
                    progress_bar.update(1)
                
                # Then apply case modifiers
                modified_words = apply_case_modifiers(word, uppercase, capitalize, reverse, 
                                                   reverse_capitalize, reverse_upper, leet)
                for mword in modified_words:
                    if mword not in seen:  # Avoid duplicates
                        seen.add(mword)
                        file.write(mword + '\n')
                        progress_bar.update(1)
            
            progress_bar.close()
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"\n{Fore.GREEN}Combinations saved successfully.{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Total combinations generated:{Style.RESET_ALL} {Fore.YELLOW}{len(seen):,}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Processing time:{Style.RESET_ALL} {Fore.YELLOW}{elapsed_time:.2f}{Style.RESET_ALL} seconds")
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
    parser = argparse.ArgumentParser(
        description=f'{Fore.GREEN}Password Combination Generator{Style.RESET_ALL}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Run without parameters for detailed information.')
    
    parser.add_argument('-w', '--words', nargs='+', required=True,
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
            
        generate_and_save_combinations(
            args.words, 
            args.output, 
            args.min_length, 
            args.max_length,
            uppercase=args.AB,
            capitalize=args.Ab,
            reverse=args.ba,
            reverse_capitalize=args.Ba,
            reverse_upper=args.BA,
            leet=args.L337,
            word_start=args.word_start,
            word_end=args.word_end
        )
        
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Run without parameters for help: python PassGenerator.py{Style.RESET_ALL}")

if __name__ == '__main__':
    main()

