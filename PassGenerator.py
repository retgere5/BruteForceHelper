import sys
import time
from tqdm import tqdm
from itertools import product
import argparse
import os

def generate_and_save_combinations(lst, filename, max_length=None):
    try:
        total_combinations = 0
        # Calculate total combinations for progress bar
        for length in range(1, len(lst) + 1 if not max_length else min(max_length + 1, len(lst) + 1)):
            total_combinations += len(lst) ** length

        with open(filename, 'w') as file:
            progress_bar = tqdm(total=total_combinations,
                              desc='Processing',
                              unit=' combinations',
                              dynamic_ncols=True,
                              position=0,
                              leave=True,
                              ncols=150,
                              bar_format='{desc}: {percentage:.2f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}] {percentage:.2f}%',
                              miniters=1,
                              mininterval=0.1,
                              smoothing=0.3)
            
            start_time = time.time()
            
            # Generate and write combinations one by one to save memory
            for length in range(1, len(lst) + 1 if not max_length else min(max_length + 1, len(lst) + 1)):
                for combination in product(lst, repeat=length):
                    file.write(''.join(combination) + '\n')
                    progress_bar.update(1)
            
            progress_bar.close()
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"\nCombinations saved successfully.")
            print(f"Total combinations generated: {total_combinations:,}")
            print(f"Processing time: {elapsed_time:.2f} seconds")
            print(f"File location: {os.path.abspath(filename)}")
            
    except PermissionError:
        print(f"Error: No write permission for file '{filename}'.")
    except IOError as e:
        print(f"File operation error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def print_usage_examples():
    print("\nUsage Examples:")
    print("  1. Basic usage:")
    print("     python PassGenerator.py -w a b c")
    print("     This command generates all possible combinations of characters a, b, c")
    print("\n  2. With custom output file:")
    print("     python PassGenerator.py -w a b c -o output.txt")
    print("     Saves combinations to 'output.txt'")
    print("\n  3. With maximum length:")
    print("     python PassGenerator.py -w a b c -m 2")
    print("     Generates combinations with length 1 and 2 only")
    print("\n  4. With all parameters:")
    print("     python PassGenerator.py -w a b c -o output.txt -m 2")
    print("\nNote: Use quotes for characters containing spaces:")
    print('     python PassGenerator.py -w "123" "abc" "@#$"')

def main():
    parser = argparse.ArgumentParser(
        description='Password Combination Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Run without parameters for detailed information.')
    
    parser.add_argument('-w', '--words', nargs='+', required=True,
                      help='Characters to generate combinations from')
    parser.add_argument('-o', '--output', default='combinations.txt',
                      help='Output file name (default: combinations.txt)')
    parser.add_argument('-m', '--max-length', type=int,
                      help='Maximum combination length')
    
    # If no parameters are provided
    if len(sys.argv) == 1:
        print("\n=== Password Combination Generator ===")
        print("\nThis program generates all possible combinations of given characters.")
        print_usage_examples()
        return

    try:
        args = parser.parse_args()
        
        if not args.words:
            print("Error: You must specify at least one character.")
            return
            
        if args.max_length is not None and args.max_length < 1:
            print("Error: Maximum length cannot be less than 1.")
            return
            
        generate_and_save_combinations(args.words, args.output, args.max_length)
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nRun without parameters for help: python PassGenerator.py")

if __name__ == '__main__':
    main()

