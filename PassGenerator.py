import sys
import time
import gzip
import json
import shutil
import hashlib
import sqlite3
from tqdm import tqdm
from itertools import product
from types import SimpleNamespace
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

# Output lines buffered before a single bulk write
WRITE_BATCH = 2_000

# Combinations counted before a single progress-bar update
PROGRESS_UPDATE_BATCH = 1_000

# How often (in written combinations) to measure dedup memory for the warning/cap
MEMORY_CHECK_INTERVAL = 10_000

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

def generation_signature(words, min_length, max_length, modifiers, word_start, word_end, use_gzip,
                         filters=None):
    """Stable fingerprint of the generation parameters, used to validate a resume."""
    fields = {
        'words': list(words), 'min': min_length, 'max': max_length,
        'modifiers': modifiers, 'ws': word_start, 'we': word_end, 'gzip': bool(use_gzip),
    }
    if filters:
        # only present when rules are on, so older checkpoints keep matching
        fields['filters'] = sorted(set(filters))
        # rules now skip whole branches, which changes what a saved position counts:
        # checkpoints written before that must not match
        fields['skips_branches'] = True
    payload = json.dumps(fields, sort_keys=True)
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def filter_rule_names():
    """WordlistOptimizer's cleaning rules, usable with --filters (loaded on demand,
    so runs without rules never import the cleaner)."""
    from modules.settings_manager import Settings
    return tuple(Settings.DEFAULT_FILTERS)


def make_rule_check(filters):
    """(check, stats) for the given rule names, where check(line) is True for lines
    to keep and stats.stats counts removals per rule; None when no rules are on."""
    names = set(filters or ())
    if not names:
        return None
    known = filter_rule_names()
    unknown = sorted(names.difference(known))
    if unknown:
        raise ValueError(f"unknown rule(s): {', '.join(unknown)} (choose from: {', '.join(known)})")
    from modules.filters import PasswordFilter, FilterStats
    options = _rule_options(names)
    password_filter = PasswordFilter()
    stats = FilterStats()

    def check(line):
        return password_filter.is_valid_password(line, options, stats)
    return check, stats


def _rule_options(names):
    """The options namespace PasswordFilter reads, with exactly ``names`` turned on."""
    return SimpleNamespace(**{name: name in names for name in filter_rule_names()})


class _Pruner:
    """Skips word sequences whose every line a substring rule would drop anyway.

    Rules such as pattern_repetition look for a piece inside the line. Once the
    words chosen so far put such a piece into every variation of the line, all
    lines on that branch get dropped whatever words follow, so the generator skips
    the branch instead of building them. ``lines`` counts the lines skipped this
    way, ``by_rule`` splits them by the rule that cut each branch."""

    def __init__(self, rules, variants):
        self.rules = rules        # [(name, check)] in PasswordFilter's order
        self.variants = variants  # one per line apply_flags() makes, see _prefix_variants()
        self.reset()

    def reset(self):
        self.lines = 0
        self.by_rule = {}


def make_pruner(filters, modifiers, words, word_start=None, word_end=None):
    """A _Pruner for the substring rules among ``filters``, or None when none of
    them is on or the input is one the shortcut cannot reason about: an empty word
    (a line could end right after any prefix) or Greek capital sigma (its lowercase
    depends on the letter after it)."""
    names = set(filters or ())
    if not names:
        return None
    if '' in words or any('Σ' in text for text in (*words, word_start or '', word_end or '')):
        return None
    from modules.filters import PasswordFilter
    rules = PasswordFilter().substring_rules(_rule_options(names))
    if not rules:
        return None
    return _Pruner(rules, _prefix_variants(compile_modifiers(modifiers)))


def _reversed_text(text):
    return text[::-1]


def _reversed_lower(text):
    return text[::-1].lower()


def _reversed_upper(text):
    return text[::-1].upper()


def _leet_of(variant):
    return lambda text: leet_convert(variant(text))


def _prefix_variants(flags):
    """For each line apply_flags() makes (same order), a function from the first
    characters of a line to text that line is sure to contain, as long as at
    least one more word follows them."""
    uppercase, capitalize, reverse, reverse_capitalize, reverse_upper, leet = flags
    variants = [str]  # the line itself
    if uppercase:
        variants.append(str.upper)
    if capitalize:
        variants.append(str.capitalize)
    if reverse or reverse_capitalize or reverse_upper:
        variants.append(_reversed_text)
        if reverse_capitalize:
            # reversed, the line starts with a later word, so these characters end up lowercased
            variants.append(_reversed_lower)
        if reverse_upper:
            variants.append(_reversed_upper)
    if leet:
        variants.extend([_leet_of(variant) for variant in variants])
    return variants

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

def _bounded_totals(words, min_length, max_length):
    """(sequences, their total UTF-8 bytes) over every 1..max_token_count() word
    sequence whose joined length lies inside the bounds."""
    if not words:
        return 0, 0
    floor = min_length or 0
    groups = {}  # word length -> [words of that length, their bytes together]
    for word in words:
        group = groups.setdefault(len(word), [0, 0])
        group[0] += 1
        group[1] += len(word.encode('utf-8'))
    # ways[length] = (sequences of the current token count with that joined length,
    # their bytes). Without a max length only "reached the floor or not" matters
    # past the floor, so those lengths share one bucket.
    ways = {0: (1, 0)}
    sequences = size = 0
    for _ in range(max_token_count(words, max_length)):
        grown = {}
        for length, (count, total) in ways.items():
            for chars, (n, group_bytes) in groups.items():
                new = length + chars
                if max_length:
                    if new > max_length:
                        continue
                elif new > floor:
                    new = floor
                old_count, old_total = grown.get(new, (0, 0))
                grown[new] = (old_count + count * n, old_total + total * n + count * group_bytes)
        ways = grown
        if not ways:
            break
        for length, (count, total) in ways.items():
            if length >= floor:
                sequences += count
                size += total
    return sequences, size


def count_base_combinations(words, min_length, max_length):
    """Exact number of word sequences generate_base_combinations() yields, counted
    before dedup (a prefix/suffix does not change the count)."""
    return _bounded_totals(words, min_length, max_length)[0]


def variation_multiplier(modifiers):
    """Lines each base word turns into with these variations, before dedup (the
    same count apply_flags() returns)."""
    uppercase, capitalize, reverse, reverse_capitalize, reverse_upper, leet = compile_modifiers(modifiers)
    # any reversed variant also brings the plain reversed word with it
    multiplier = (1 + uppercase + capitalize + (reverse or reverse_capitalize or reverse_upper)
                  + reverse_capitalize + reverse_upper)
    return multiplier * 2 if leet else multiplier


def calculate_total_combinations(words, min_length, max_length, modifiers):
    """Lines the run will consider: the exact base count times one per variation
    (an upper bound for the written count, since duplicates are dropped)."""
    return count_base_combinations(words, min_length, max_length) * variation_multiplier(modifiers)


def estimate_output_bytes(words, min_length, max_length, modifiers, word_start=None, word_end=None):
    """Size of the output before dedup: every line inside the bounds with its
    prefix, suffix and line ending, once per variation."""
    sequences, size = _bounded_totals(words, min_length, max_length)
    extra = len((word_start or '').encode('utf-8')) + len((word_end or '').encode('utf-8')) + len(os.linesep)
    return (size + sequences * extra) * variation_multiplier(modifiers)

def _until_set(iterable, stop_event, every=4096):
    """Yield from `iterable` until `stop_event.is_set()` (checked every `every` items)."""
    for i, item in enumerate(iterable):
        if not i % every and stop_event.is_set():
            return
        yield item

def generate_base_combinations(words, min_length, max_length, word_start=None, word_end=None, stop_event=None,
                               prune=None):
    """Generator for base word combinations.

    ``min_length``/``max_length`` bound the *character length* of each combined
    string; the token count is bounded by :func:`max_token_count`. Generation
    ends early once ``stop_event`` (anything with ``is_set()``) is set. With
    ``prune`` (see :func:`make_pruner`) branches whose every line its rules would
    drop are skipped, and counted in it.
    """
    if not words:
        return
    max_tokens = max_token_count(words, max_length)
    lengths = [len(w) for w in words]
    shortest, longest = min(lengths), max(lengths)
    floor = min_length or 0
    for count in range(1, max_tokens + 1):
        # Too few tokens to ever reach min_length: skip the whole round
        if count * longest < floor:
            continue
        if prune is not None and count > 1:
            # (one word per line leaves no prefix to cut early)
            combos = _pruned_products(words, lengths, count, floor, max_length, shortest, longest,
                                      word_start or '', prune)
        elif (not max_length or count * longest <= max_length) and count * shortest >= floor:
            # every sequence of this many words fits: plain product(), no length checks
            combos = (''.join(combo) for combo in product(words, repeat=count))
        else:
            combos = _bounded_products(words, lengths, count, floor, max_length, shortest, longest)
        if stop_event is not None:
            combos = _until_set(combos, stop_event)
        for combined in combos:
            if word_start:
                combined = word_start + combined
            if word_end:
                combined = combined + word_end
            yield combined
        if stop_event is not None and stop_event.is_set():
            return


def _bounded_products(words, lengths, count, floor, max_length, shortest, longest):
    """The ``count``-word sequences whose joined length fits the bounds, in the same
    order product() would give them, without walking prefixes that can no longer fit
    (short words otherwise make product() visit billions of sequences for nothing)."""
    def extend(prefix, used, rest):
        for word, size in zip(words, lengths):
            total, left = used + size, rest - 1
            if (max_length and total + left * shortest > max_length) or total + left * longest < floor:
                continue
            if not left:
                yield prefix + word
            elif (not max_length or total + left * longest <= max_length) and total + left * shortest >= floor:
                # nothing below this prefix can leave the bounds
                for tail in product(words, repeat=left):
                    yield prefix + word + ''.join(tail)
            else:
                yield from extend(prefix + word, total, left)
    return extend('', 0, count)


def _completion_counter(lengths, floor, max_length, shortest, longest):
    """below(left, used): how many sequences the walk yields under a prefix of
    ``used`` characters that still needs ``left`` more words."""
    groups = {}
    for size in lengths:
        groups[size] = groups.get(size, 0) + 1
    memo = {}

    def below(left, used):
        if not left:
            return 1
        key = (left, used)
        if key not in memo:
            rest, total = left - 1, 0
            for size, n in groups.items():
                new = used + size
                if (max_length and new + rest * shortest > max_length) or new + rest * longest < floor:
                    continue
                total += n * below(rest, new)
            memo[key] = total
        return memo[key]
    return below


def _pruned_products(words, lengths, count, floor, max_length, shortest, longest, word_start, pruner):
    """_bounded_products() that also skips each branch whose lines the pruner's
    rules would all drop. Whatever it does yield comes in the same order."""
    rules, variants = pruner.rules, pruner.variants
    plain = len(variants) == 1  # no variations: check the line itself
    below = _completion_counter(lengths, floor, max_length, shortest, longest)

    def cut_by(text):
        for name, matches in rules:
            if matches(text):
                return name
        return None

    def skip(names, sequences):
        pruner.lines += sequences * len(names)
        for name in names:
            pruner.by_rule[name] = pruner.by_rule.get(name, 0) + sequences

    # Only prefixes with more words to come are checked: a finished line goes to the
    # full rule check anyway, so cutting there would save nothing.
    def extend(prefix, used, rest, verdicts):
        for word, size in zip(words, lengths):
            total, left = used + size, rest - 1
            if (max_length and total + left * shortest > max_length) or total + left * longest < floor:
                continue
            line = prefix + word
            if not left:
                yield line
                continue
            text = word_start + line if word_start else line
            if plain:
                name = cut_by(text)
                if name is not None:
                    skip((name,), below(left, total))
                    continue
                yield from extend(line, total, left, verdicts)
            else:
                # a variation stays cut once it is; the branch goes when all of them are
                now = [verdict or cut_by(variant(text)) for verdict, variant in zip(verdicts, variants)]
                if all(now):
                    skip(now, below(left, total))
                    continue
                yield from extend(line, total, left, now)
    return extend('', 0, count, [None] * len(variants))

def compile_modifiers(modifiers):
    """Precompute modifier flags once so the hot loop avoids per-word dict lookups."""
    return (
        bool(modifiers.get('uppercase')),
        bool(modifiers.get('capitalize')),
        bool(modifiers.get('reverse')),
        bool(modifiers.get('reverse_capitalize')),
        bool(modifiers.get('reverse_upper')),
        bool(modifiers.get('leet')),
    )

def apply_flags(word, flags):
    """Apply modifications from precompiled flags. Produces the same list (and order)
    as :func:`apply_modifications`, but without per-call dictionary lookups."""
    uppercase, capitalize, reverse, reverse_capitalize, reverse_upper, leet = flags
    results = [word]
    # Case modifications
    if uppercase:
        results.append(word.upper())
    if capitalize:
        results.append(word.capitalize())
    # Reverse modifications
    if reverse or reverse_capitalize or reverse_upper:
        reversed_word = word[::-1]
        results.append(reversed_word)
        if reverse_capitalize:
            results.append(reversed_word.capitalize())
        if reverse_upper:
            results.append(reversed_word.upper())
    # Leet speak (applied to everything produced so far)
    if leet:
        results.extend([leet_convert(w) for w in results])
    return results

def apply_modifications(word, modifiers):
    """Apply modifications in a specific order (thin wrapper over the fast path)."""
    return apply_flags(word, compile_modifiers(modifiers))

class _Deadline:
    """Event-like time budget: is_set() turns true once `seconds` have passed."""
    def __init__(self, seconds):
        self._end = time.monotonic() + seconds

    def is_set(self):
        return time.monotonic() >= self._end

def preview_combinations(words, min_length=1, max_length=None, modifiers=None, word_start=None,
                         word_end=None, count=40, dedup=True, time_budget=0.25, filters=None):
    """The first `count` lines a run with these options would write, in the same
    order. Capped at `time_budget` seconds so it stays cheap enough to call on
    every keystroke."""
    flags = compile_modifiers(modifiers or {})
    has_modifiers = any(flags)
    rule = make_rule_check(filters)
    keep = rule[0] if rule else None
    seen = set()
    sample = []
    bases = generate_base_combinations(words, min_length, max_length, word_start, word_end,
                                       _Deadline(time_budget),
                                       make_pruner(filters, modifiers or {}, words, word_start, word_end))
    for base_word in bases:
        for word in (apply_flags(base_word, flags) if has_modifiers else (base_word,)):
            if keep is not None and not keep(word):
                continue
            if dedup:
                if word in seen:
                    continue
                seen.add(word)
            sample.append(word)
            if len(sample) >= count:
                return sample
    return sample

def _silent(*_args, **_kwargs):
    pass

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
                                 dedup=True, resume=False, disk_dedup=False,
                                 quiet=False, progress=None, stop_event=None, filters=None, live=None):
    """Generate every combination and write them to `filename`.

    ``filters`` names WordlistOptimizer rules: a line any of them matches is dropped
    before it is written (and before dedup, so it costs no memory either). Rules
    that look for a piece inside the line also cut whole branches while the words
    are combined, so most lines they drop are never built (the result's ``skipped``).

    For programmatic callers such as the web UI: ``quiet`` turns off all console
    output and lets errors propagate instead of printing them,
    ``progress(written, estimated_total)`` is called as lines are written,
    ``live`` (a dict) is kept up to date with ``processed`` (candidate lines seen)
    and ``filtered_total`` at the same moments, and ``stop_event`` (anything with
    ``is_set()``) ends the run early while keeping what was already written.
    Returns a summary dict, or None when the run was interrupted or failed.
    """
    say = _silent if quiet else print
    disk_conn = None
    db_path = None
    try:
        if disk_dedup and resume:
            if quiet:
                raise ValueError("resume is not supported with disk dedup")
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
        rule = make_rule_check(filters)
        keep = rule[0] if rule else None
        pruner = make_pruner(filters, modifiers, lst, word_start, word_end)

        # Calculate total combinations
        total_combinations = calculate_total_combinations(lst, min_length, max_length, modifiers)
        if limit:
            total_combinations = min(total_combinations, limit)

        # Warn before a very large run
        if total_combinations > LARGE_COMBINATION_WARNING:
            say(f"{Fore.YELLOW}Warning: about {total_combinations:,} combinations estimated; "
                f"this may take a while and use significant disk space.{Style.RESET_ALL}")

        # Warn if the output location is low on free disk space
        free = check_disk_space(filename)
        if free is not None and free < MIN_FREE_DISK_BYTES:
            say(f"{Fore.YELLOW}Warning: low free disk space "
                f"({free / (1024 * 1024):.0f} MB) on the output location.{Style.RESET_ALL}")

        # Resume support: restore state from a matching checkpoint
        checkpoint_file = filename + '.pgckpt'
        signature = generation_signature(lst, min_length, max_length, modifiers, word_start, word_end, use_gzip,
                                         filters)
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
                                seen_bytes += 49 + len(existing_word)
                    written = len(seen)
                else:
                    written = checkpoint['written']
                say(f"{Fore.CYAN}Resuming from {written:,} combinations.{Style.RESET_ALL}")

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
                              smoothing=0.3,
                              disable=quiet)

            start_time = time.time()
            memory_warned = False
            stop = False
            stopped_by = None
            base_index = 0
            pending = 0
            max_memory_bytes = max_memory_mb * 1024 * 1024 if max_memory_mb else None

            # Precompute the modifier plan and dedup mode once (kept out of the hot loop)
            mod_flags = compile_modifiers(modifiers)
            has_modifiers = any(mod_flags)
            in_memory_dedup = dedup and not disk_dedup

            out_buffer = []
            processed = 0
            removed = 0
            shown_skipped = 0

            def flush_buffer():
                if out_buffer:
                    file.write('\n'.join(out_buffer) + '\n')
                    out_buffer.clear()

            def skipped():
                # lines the rules dropped by cutting a branch, never built or checked
                return pruner.lines if pruner is not None else 0

            def new_skipped():
                nonlocal shown_skipped
                delta, shown_skipped = skipped() - shown_skipped, skipped()
                return delta

            def report():
                if live is not None:
                    live['processed'] = processed + skipped()
                    live['filtered_total'] = removed + skipped()
                if progress is not None:
                    progress(written, total_combinations)

            try:
                # Generate and process combinations
                for base_word in generate_base_combinations(lst, min_length, max_length, word_start, word_end,
                                                            stop_event, pruner):
                    if base_index < skip_count:
                        base_index += 1
                        if base_index == skip_count and pruner is not None:
                            pruner.reset()  # what was cut before the resume point is not this run's
                        continue

                    # apply_flags() yields the original word first, then its variants
                    words = apply_flags(base_word, mod_flags) if has_modifiers else (base_word,)
                    for word in words:
                        processed += 1
                        if keep is not None:
                            # with rules on, the bar follows candidates (written lags behind),
                            # skipped branches included
                            pending += 1
                            if pending >= PROGRESS_UPDATE_BATCH:
                                progress_bar.update(pending + new_skipped())
                                pending = 0
                                report()
                            if not keep(word):
                                removed += 1
                                continue

                        if disk_dedup:
                            disk_cur.execute("INSERT OR IGNORE INTO words(w) VALUES(?)", (word,))
                            if disk_cur.rowcount != 1:
                                continue
                        elif in_memory_dedup:
                            if word in seen:
                                continue
                            seen.add(word)
                            seen_bytes += 49 + len(word)  # cheap CPython string-size estimate

                        # Buffered write (bulk-flushed to cut per-line overhead)
                        out_buffer.append(word)
                        if len(out_buffer) >= WRITE_BATCH:
                            flush_buffer()

                        written += 1
                        if keep is None:
                            pending += 1
                            if pending >= PROGRESS_UPDATE_BATCH:
                                progress_bar.update(pending)
                                pending = 0
                                report()

                        if limit and written >= limit:
                            stop = True
                            stopped_by = 'limit'
                            break

                        if disk_dedup:
                            if written % DISK_DEDUP_COMMIT_INTERVAL == 0:
                                disk_conn.commit()
                        elif in_memory_dedup:
                            # Live memory indicator (periodic)
                            if written % MEMORY_INDICATOR_INTERVAL == 0:
                                progress_bar.set_postfix_str(
                                    f"mem ~{(sys.getsizeof(seen) + seen_bytes) / (1024*1024):.0f}MB")

                            # Memory warning / hard cap, measured only periodically so the
                            # per-item cost stays off large runs.
                            if (max_memory_bytes or not memory_warned) and written % MEMORY_CHECK_INTERVAL == 0:
                                used_bytes = sys.getsizeof(seen) + seen_bytes
                                if not memory_warned and used_bytes >= MEMORY_WARNING_BYTES:
                                    memory_warned = True
                                    progress_bar.clear()
                                    say(f"{Fore.YELLOW}Warning: the dedup set is holding ~"
                                        f"{used_bytes / (1024*1024):.0f} MB in memory.{Style.RESET_ALL}")
                                if max_memory_bytes and used_bytes >= max_memory_bytes:
                                    stop = True
                                    stopped_by = 'memory'
                                    progress_bar.clear()
                                    say(f"{Fore.YELLOW}Memory limit reached (~"
                                        f"{used_bytes / (1024*1024):.0f} MB); stopping generation.{Style.RESET_ALL}")
                                    break

                    base_index += 1
                    if stop:
                        break

                    # Persist a resume checkpoint periodically
                    if resume and base_index % CHECKPOINT_INTERVAL == 0:
                        flush_buffer()
                        file.flush()
                        save_checkpoint(checkpoint_file, signature, base_index, written)

            except KeyboardInterrupt:
                if resume:
                    flush_buffer()
                    file.flush()
                    save_checkpoint(checkpoint_file, signature, base_index, written)
                    if pending:
                        progress_bar.update(pending)
                    progress_bar.close()
                    say(f"\n{Fore.YELLOW}Interrupted; checkpoint saved. "
                        f"Re-run with --resume to continue.{Style.RESET_ALL}")
                    return
                raise
            finally:
                # Ensure buffered output is written on every exit path
                flush_buffer()

            if stopped_by is None and stop_event is not None and stop_event.is_set():
                stopped_by = 'user'
            report()

            progress_bar.update(pending + new_skipped())

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
            say(f"\n{Fore.GREEN}Combinations saved successfully.{Style.RESET_ALL}")
            say(f"{Fore.CYAN}Total combinations generated:{Style.RESET_ALL} {Fore.YELLOW}{written:,}{Style.RESET_ALL}")
            filtered = {name: n for name, n in rule[1].stats.items() if n} if rule else {}
            for name, n in (pruner.by_rule.items() if pruner is not None else ()):
                filtered[name] = filtered.get(name, 0) + n
            removed_total = removed + skipped()
            if rule:
                never_built = (f" ({skipped():,} of them were never generated)" if skipped() else '')
                say(f"{Fore.CYAN}Removed by rules:{Style.RESET_ALL} {Fore.YELLOW}{removed_total:,}{Style.RESET_ALL}"
                    + never_built
                    + ''.join(f"\n  {name}: {n:,}" for name, n in sorted(filtered.items(), key=lambda kv: -kv[1])))
            say(f"{Fore.CYAN}Processing time:{Style.RESET_ALL} {Fore.YELLOW}{elapsed_time:.2f}{Style.RESET_ALL} seconds")
            say(f"{Fore.CYAN}Memory usage:{Style.RESET_ALL} {Fore.YELLOW}{(sys.getsizeof(seen) + seen_bytes) / (1024*1024):.2f}{Style.RESET_ALL} MB")
            say(f"{Fore.CYAN}File location:{Style.RESET_ALL} {Fore.YELLOW}{os.path.abspath(filename)}{Style.RESET_ALL}")

            return {
                'written': written,
                'elapsed': elapsed_time,
                'path': os.path.abspath(filename),
                'stopped_by': stopped_by,
                'filtered': filtered,
                'filtered_total': removed_total,
                'skipped': skipped(),
            }

    except PermissionError:
        if quiet:
            raise
        print(f"{Fore.RED}Error: No write permission for file '{filename}'.{Style.RESET_ALL}")
    except IOError as e:
        if quiet:
            raise
        print(f"{Fore.RED}File operation error: {e}{Style.RESET_ALL}")
    except Exception as e:
        if quiet:
            raise
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
    print(f"\n  {Fore.YELLOW}8. Web interface:{Style.RESET_ALL}")
    print("     python PassGenerator.py --webui")
    print("     Opens the tools in your browser (runs only on this computer)")
    print(f"\n{Fore.CYAN}Note: Use quotes for characters containing spaces:{Style.RESET_ALL}")
    print('     python PassGenerator.py -w "123" "abc" "@#$"')
    print(f"\n{Fore.CYAN}Run with -h for all options (compression, config, limits, resume, disk-dedup).{Style.RESET_ALL}")

def main():
    # Pre-parse --config (and --webui) before the real parser, which may require -w
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument('-c', '--config')
    pre_parser.add_argument('--webui', action='store_true')
    pre_parser.add_argument('--port', type=int)
    pre_parser.add_argument('--no-browser', action='store_true', dest='no_browser')
    pre_args, _ = pre_parser.parse_known_args()

    if pre_args.webui:
        from webui.server import run
        run(port=pre_args.port, open_browser=not pre_args.no_browser, start_tab='generate')
        return

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
    parser.add_argument('--filters', nargs='+', metavar='RULE',
                      help='Drop lines with WordlistOptimizer rules before they are written '
                           '(names separated by spaces or commas, or "all"). '
                           'Smaller file, slower run.')

    # Web interface
    parser.add_argument('--webui', action='store_true',
                      help='Open the web interface in your browser (local only)')
    parser.add_argument('--port', type=int,
                      help='Port for --webui (default: 8765)')
    parser.add_argument('--no-browser', action='store_true', dest='no_browser',
                      help='With --webui, only print the link instead of opening a browser')

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

        filters = None
        if args.filters:
            known = filter_rule_names()
            names = [name for item in args.filters for name in str(item).split(',') if name]
            filters = list(known) if 'all' in names else names
            unknown = [name for name in filters if name not in known]
            if unknown:
                parser.error(f"unknown rule: {', '.join(unknown)} (choose from: all, {', '.join(known)})")

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
            disk_dedup=args.disk_dedup,
            filters=filters
        )
        
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Run without parameters for help: python PassGenerator.py{Style.RESET_ALL}")

if __name__ == '__main__':
    main()

