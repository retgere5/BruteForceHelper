import sys
import time
import gzip
import json
import shutil
import hashlib
import sqlite3
from tqdm import tqdm
from itertools import product
import argparse
import os
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Combination estimate above which a heads-up is printed before generating
LARGE_COMBINATION_WARNING = 5_000_000

# Warn when the output location has less free space than this
MIN_FREE_DISK_BYTES = 100 * 1024 * 1024  # 100 MB

# Warn once when the in-memory dedup set grows past this size
MEMORY_WARNING_BYTES = 512 * 1024 * 1024  # 512 MB

# How often (in written combinations) to refresh the live memory indicator
MEMORY_INDICATOR_INTERVAL = 100_000

# How often (in base words) to persist a resume checkpoint
CHECKPOINT_INTERVAL = 10_000

# How often (in written combinations) to commit the on-disk dedup database
DISK_DEDUP_COMMIT_INTERVAL = 50_000

def check_disk_space(path):
    """Free bytes on the filesystem that holds `path`'s directory, or None if unknown."""
    try:
        target = os.path.dirname(os.path.abspath(path)) or '.'
        return shutil.disk_usage(target).free
    except Exception:
        return None

def open_output(filename, use_gzip, append=False):
    """Open the output file for writing (append optional), gzip-compressed when
    requested or when it ends in .gz."""
    if use_gzip or filename.endswith('.gz'):
        return gzip.open(filename, 'at' if append else 'wt', encoding='utf-8')
    return open(filename, 'a' if append else 'w', encoding='utf-8')

def open_input(filename):
    """Open a text file for reading, gzip-decompressed when it ends in .gz."""
    if filename.endswith('.gz'):
        return gzip.open(filename, 'rt', encoding='utf-8')
    return open(filename, 'r', encoding='utf-8')

def load_config(path):
    """Load a JSON config file whose keys mirror the command-line options
    (words, output, min_length, max_length, AB, Ab, ba, Ba, BA, L337,
    word_start, word_end, gzip). Command-line arguments override it."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generation_signature(words, min_length, max_length, modifiers, word_start, word_end, use_gzip):
    """Stable fingerprint of the generation parameters, used to validate a resume."""
    payload = json.dumps({
        'words': list(words), 'min': min_length, 'max': max_length,
        'modifiers': modifiers, 'ws': word_start, 'we': word_end, 'gzip': bool(use_gzip),
    }, sort_keys=True)
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()

def save_checkpoint(path, signature, position, written):
    """Atomically persist resume state (position = base words fully processed)."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'signature': signature, 'position': position, 'written': written}, f)
    os.replace(tmp, path)

def load_checkpoint(path, signature):
    """Return the checkpoint dict if it exists and matches the signature, else None."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if data.get('signature') == signature:
        return data
    return None

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
                                 word_start=None, word_end=None, use_gzip=False, limit=None, max_memory_mb=None,
                                 dedup=True, resume=False, disk_dedup=False):
    disk_conn = None
    db_path = None
    try:
        if disk_dedup and resume:
            print(f"{Fore.RED}Error: --resume is not supported with --disk-dedup.{Style.RESET_ALL}")
            return

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
        if limit:
            total_combinations = min(total_combinations, limit)

        # Warn before a very large run
        if total_combinations > LARGE_COMBINATION_WARNING:
            print(f"{Fore.YELLOW}Warning: about {total_combinations:,} combinations estimated; "
                  f"this may take a while and use significant disk space.{Style.RESET_ALL}")

        # Warn if the output location is low on free disk space
        free = check_disk_space(filename)
        if free is not None and free < MIN_FREE_DISK_BYTES:
            print(f"{Fore.YELLOW}Warning: low free disk space "
                  f"({free / (1024 * 1024):.0f} MB) on the output location.{Style.RESET_ALL}")

        # Resume support: restore state from a matching checkpoint
        checkpoint_file = filename + '.pgckpt'
        signature = generation_signature(lst, min_length, max_length, modifiers, word_start, word_end, use_gzip)
        seen = set()
        seen_bytes = 0
        written = 0
        skip_count = 0
        resuming = False
        if resume:
            checkpoint = load_checkpoint(checkpoint_file, signature)
            if checkpoint:
                skip_count = checkpoint['position']
                resuming = True
                if dedup:
                    # Rebuild the dedup set from what was already written
                    with open_input(filename) as existing:
                        for line in existing:
                            existing_word = line.rstrip('\n')
                            if existing_word and existing_word not in seen:
                                seen.add(existing_word)
                                seen_bytes += sys.getsizeof(existing_word)
                    written = len(seen)
                else:
                    written = checkpoint['written']
                print(f"{Fore.CYAN}Resuming from {written:,} combinations.{Style.RESET_ALL}")

        # On-disk dedup: use a temporary SQLite index instead of an in-memory set
        if disk_dedup:
            db_path = filename + '.dedup.sqlite'
            if os.path.exists(db_path):
                os.remove(db_path)
            disk_conn = sqlite3.connect(db_path)
            disk_conn.execute("PRAGMA journal_mode = OFF")
            disk_conn.execute("PRAGMA synchronous = OFF")
            disk_conn.execute("CREATE TABLE words (w TEXT PRIMARY KEY)")
            disk_cur = disk_conn.cursor()

        with open_output(filename, use_gzip, append=resuming) as file:
            progress_bar = tqdm(total=total_combinations,
                              initial=written,
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
            memory_warned = False
            stop = False
            base_index = 0
            max_memory_bytes = max_memory_mb * 1024 * 1024 if max_memory_mb else None

            try:
                # Generate and process combinations
                for base_word in generate_base_combinations(lst, min_length, max_length, word_start, word_end):
                    if base_index < skip_count:
                        base_index += 1
                        continue

                    # apply_modifications() yields the original word first, then its variants
                    for word in apply_modifications(base_word, modifiers):
                        if disk_dedup:
                            disk_cur.execute("INSERT OR IGNORE INTO words(w) VALUES(?)", (word,))
                            is_new = disk_cur.rowcount == 1
                            if is_new:
                                file.write(word + '\n')
                        elif dedup:
                            is_new = write_unique(file, word, seen)
                        else:
                            # Constant-memory streaming: write everything, keep no set
                            file.write(word + '\n')
                            is_new = True
                        if not is_new:
                            continue

                        written += 1
                        progress_bar.update(1)

                        if limit and written >= limit:
                            stop = True
                            break

                        if disk_dedup:
                            if written % DISK_DEDUP_COMMIT_INTERVAL == 0:
                                disk_conn.commit()
                        elif dedup:
                            seen_bytes += sys.getsizeof(word)

                            # Live memory indicator in the progress bar (cheap: periodic)
                            if written % MEMORY_INDICATOR_INTERVAL == 0:
                                progress_bar.set_postfix_str(
                                    f"mem ~{(sys.getsizeof(seen) + seen_bytes) / (1024*1024):.0f}MB")

                            # Total dedup memory = set container + stored strings. Only
                            # measured while it can still change an outcome, to keep the
                            # per-item cost off large unbounded runs.
                            if max_memory_bytes or not memory_warned:
                                used_bytes = sys.getsizeof(seen) + seen_bytes
                                if not memory_warned and used_bytes >= MEMORY_WARNING_BYTES:
                                    memory_warned = True
                                    progress_bar.clear()
                                    print(f"{Fore.YELLOW}Warning: the dedup set is holding ~"
                                          f"{used_bytes / (1024*1024):.0f} MB in memory.{Style.RESET_ALL}")
                                if max_memory_bytes and used_bytes >= max_memory_bytes:
                                    stop = True
                                    progress_bar.clear()
                                    print(f"{Fore.YELLOW}Memory limit reached (~"
                                          f"{used_bytes / (1024*1024):.0f} MB); stopping generation.{Style.RESET_ALL}")
                                    break

                    base_index += 1
                    if stop:
                        break

                    # Persist a resume checkpoint periodically
                    if resume and base_index % CHECKPOINT_INTERVAL == 0:
                        file.flush()
                        save_checkpoint(checkpoint_file, signature, base_index, written)

            except KeyboardInterrupt:
                if resume:
                    file.flush()
                    save_checkpoint(checkpoint_file, signature, base_index, written)
                    progress_bar.close()
                    print(f"\n{Fore.YELLOW}Interrupted; checkpoint saved. "
                          f"Re-run with --resume to continue.{Style.RESET_ALL}")
                    return
                raise

            # Update progress bar to 100% if needed
            if progress_bar.n < total_combinations:
                progress_bar.update(total_combinations - progress_bar.n)

            progress_bar.close()
            end_time = time.time()
            elapsed_time = end_time - start_time

            # A completed run has no checkpoint to keep
            if resume and os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)

            # Print statistics
            print(f"\n{Fore.GREEN}Combinations saved successfully.{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Total combinations generated:{Style.RESET_ALL} {Fore.YELLOW}{written:,}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Processing time:{Style.RESET_ALL} {Fore.YELLOW}{elapsed_time:.2f}{Style.RESET_ALL} seconds")
            print(f"{Fore.CYAN}Memory usage:{Style.RESET_ALL} {Fore.YELLOW}{(sys.getsizeof(seen) + seen_bytes) / (1024*1024):.2f}{Style.RESET_ALL} MB")
            print(f"{Fore.CYAN}File location:{Style.RESET_ALL} {Fore.YELLOW}{os.path.abspath(filename)}{Style.RESET_ALL}")
            
    except PermissionError:
        print(f"{Fore.RED}Error: No write permission for file '{filename}'.{Style.RESET_ALL}")
    except IOError as e:
        print(f"{Fore.RED}File operation error: {e}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")
    finally:
        # Always tear down the temporary on-disk dedup database
        if disk_conn is not None:
            try:
                disk_conn.commit()
                disk_conn.close()
            except Exception:
                pass
        if db_path and os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass

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
    parser.add_argument('--limit', type=int,
                      help='Stop after generating this many unique combinations')
    parser.add_argument('--max-memory', type=int, dest='max_memory',
                      help='Stop when the in-memory dedup set exceeds this many MB')
    dedup_group = parser.add_mutually_exclusive_group()
    dedup_group.add_argument('--no-dedup', action='store_true', dest='no_dedup',
                      help='Do not remove duplicates (constant memory, may repeat lines)')
    dedup_group.add_argument('--disk-dedup', action='store_true', dest='disk_dedup',
                      help='Deduplicate on disk via SQLite (bounded memory, slower)')
    parser.add_argument('--resume', action='store_true',
                      help='Checkpoint the run and resume it if interrupted')

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

        if args.limit is not None and args.limit < 1:
            print(f"{Fore.RED}Error: Limit cannot be less than 1.{Style.RESET_ALL}")
            return

        if args.max_memory is not None and args.max_memory < 1:
            print(f"{Fore.RED}Error: Max memory cannot be less than 1 MB.{Style.RESET_ALL}")
            return

        if args.disk_dedup and args.resume:
            print(f"{Fore.RED}Error: --resume cannot be combined with --disk-dedup.{Style.RESET_ALL}")
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
            use_gzip=use_gzip,
            limit=args.limit,
            max_memory_mb=args.max_memory,
            dedup=not args.no_dedup,
            resume=args.resume,
            disk_dedup=args.disk_dedup
        )
        
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Run without parameters for help: python PassGenerator.py{Style.RESET_ALL}")

if __name__ == '__main__':
    main()

