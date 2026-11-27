"""Tests for the standalone PassGenerator tool."""
import gzip
import json
import os
import sys

import PassGenerator as pg


def _interrupt_after(monkeypatch, n):
    """Patch generate_base_combinations to raise KeyboardInterrupt after n base words."""
    real = pg.generate_base_combinations

    def fake(*args, **kwargs):
        for i, base_word in enumerate(real(*args, **kwargs)):
            if i >= n:
                raise KeyboardInterrupt
            yield base_word

    monkeypatch.setattr(pg, "generate_base_combinations", fake)


def _mods(**over):
    base = {
        'uppercase': False, 'capitalize': False, 'reverse': False,
        'reverse_capitalize': False, 'reverse_upper': False, 'leet': False,
    }
    base.update(over)
    return base


def test_leet_convert():
    assert pg.leet_convert("test") == "7357"
    assert pg.leet_convert("LEET") == "1337"
    assert pg.leet_convert("xyz") == "xy2"  # only z is mapped


def test_apply_modifications_original_only():
    assert pg.apply_modifications("test", _mods()) == ["test"]


def test_apply_modifications_case():
    res = pg.apply_modifications("test", _mods(uppercase=True, capitalize=True))
    assert "test" in res and "TEST" in res and "Test" in res


def test_apply_modifications_reverse_variants():
    res = pg.apply_modifications(
        "test", _mods(reverse=True, reverse_capitalize=True, reverse_upper=True)
    )
    assert "tset" in res   # reversed
    assert "Tset" in res   # reversed + capitalize
    assert "TSET" in res   # reversed + upper


def test_apply_modifications_leet_applies_to_all_prior():
    res = pg.apply_modifications("test", _mods(uppercase=True, leet=True))
    assert "7357" in res   # leet of "test" (and of "TEST")


def test_generate_base_combinations_lengths():
    combos = list(pg.generate_base_combinations(["a", "b"], 1, None))
    assert set(combos) == {"a", "b", "aa", "ab", "ba", "bb"}


def test_generate_base_combinations_min_length():
    combos = list(pg.generate_base_combinations(["a", "b"], 2, None))
    assert "a" not in combos
    assert "aa" in combos


def test_generate_base_combinations_prefix_suffix():
    combos = list(
        pg.generate_base_combinations(["x"], 1, None, word_start="pre_", word_end="_suf")
    )
    assert combos == ["pre_x_suf"]


def test_write_unique_dedup(tmp_path):
    out = tmp_path / "o.txt"
    seen = set()
    with open(out, "w", encoding="utf-8") as fh:
        assert pg.write_unique(fh, "a", seen) is True
        assert pg.write_unique(fh, "a", seen) is False
    assert out.read_text(encoding="utf-8").count("a") == 1


def test_generate_and_save_dedup(tmp_path):
    out = tmp_path / "combos.txt"
    # duplicate input word must not produce duplicate output lines
    pg.generate_and_save_combinations(["a", "a"], str(out), min_length=1, max_length=None)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert lines == sorted(set(lines), key=lines.index)  # no duplicates
    assert "a" in lines and "aa" in lines


def test_calculate_total_combinations_is_positive():
    total = pg.calculate_total_combinations(["a", "b", "c"], 1, 2, _mods(uppercase=True, leet=True))
    assert isinstance(total, int) and total > 0


def test_max_token_count_uses_max_length():
    # single-char words: token count follows max_length, not word count
    assert pg.max_token_count(["a", "b", "c"], 4) == 4
    # multi-char words: bounded by the shortest word length
    assert pg.max_token_count(["test", "user"], 8) == 2
    # no max_length: legacy fallback to number of words
    assert pg.max_token_count(["a", "b", "c"], None) == 3


def test_max_length_allows_more_tokens_than_words():
    # Regression: -M was capped at len(words) tokens, so long single-char
    # combinations never appeared. One word "a" with max_length 4 -> a..aaaa.
    assert list(pg.generate_base_combinations(["a"], 1, 4)) == ["a", "aa", "aaa", "aaaa"]


def test_readme_example_produces_length_four():
    # README: `-w a b c -m 2 -M 4` should include "aaaa" (4 chars).
    combos = list(pg.generate_base_combinations(["a", "b", "c"], 2, 4))
    assert "aaaa" in combos
    assert all(2 <= len(c) <= 4 for c in combos)


def test_max_length_is_a_character_bound():
    combos = list(pg.generate_base_combinations(["ab", "c"], 1, 3))
    assert all(len(c) <= 3 for c in combos)
    assert "abab" not in combos  # 4 chars, excluded


def test_gzip_output_roundtrip(tmp_path):
    out = tmp_path / "combos.txt.gz"
    pg.generate_and_save_combinations(["a", "b"], str(out), min_length=1, max_length=None, use_gzip=True)
    with gzip.open(out, "rt", encoding="utf-8") as fh:
        lines = [ln for ln in fh.read().splitlines() if ln]
    assert set(lines) == {"a", "b", "aa", "ab", "ba", "bb"}


def test_gzip_autodetected_by_extension(tmp_path):
    out = tmp_path / "combos.gz"  # no use_gzip flag, detected from .gz suffix
    pg.generate_and_save_combinations(["x"], str(out), min_length=1, max_length=None)
    with gzip.open(out, "rt", encoding="utf-8") as fh:
        assert "x" in fh.read()


def test_large_combination_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pg, "LARGE_COMBINATION_WARNING", 5)
    pg.generate_and_save_combinations(["a", "b", "c"], str(tmp_path / "o.txt"), min_length=1, max_length=None)
    assert "Warning" in capsys.readouterr().out


def test_config_file_supplies_options(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"words": ["a", "b"], "min_length": 1, "output": str(out)}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["PassGenerator.py", "-c", str(cfg)])
    pg.main()
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert set(lines) == {"a", "b", "aa", "ab", "ba", "bb"}


def test_cli_overrides_config(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    unused = tmp_path / "unused.txt"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"words": ["a"], "output": str(unused)}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["PassGenerator.py", "-c", str(cfg), "-o", str(out)])
    pg.main()
    assert out.exists()
    assert not unused.exists()


def test_limit_caps_unique_output(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(["a", "b", "c"], str(out), min_length=1, max_length=None, limit=4)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 4


def test_limit_via_cli(tmp_path, monkeypatch):
    out = tmp_path / "o.txt"
    monkeypatch.setattr(sys, "argv", ["PassGenerator.py", "-w", "a", "b", "c", "--limit", "3", "-o", str(out)])
    pg.main()
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 3


def test_low_disk_space_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pg, "check_disk_space", lambda path: 1024)  # pretend 1 KB free
    pg.generate_and_save_combinations(["a"], str(tmp_path / "o.txt"), min_length=1, max_length=None)
    assert "low free disk space" in capsys.readouterr().out.lower()


def test_memory_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pg, "MEMORY_WARNING_BYTES", 5)  # trip almost immediately
    monkeypatch.setattr(pg, "MEMORY_CHECK_INTERVAL", 1)  # measure every combination
    pg.generate_and_save_combinations(["a", "b"], str(tmp_path / "o.txt"), min_length=1, max_length=None)
    assert "holding" in capsys.readouterr().out.lower()


def test_max_memory_stops_early(tmp_path):
    words = [chr(ord('a') + i) for i in range(30)]  # unbounded: 30 + 900 + 27000 combos
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(words, str(out), min_length=1, max_length=None, max_memory_mb=1)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert 0 < len(lines) < 27930  # a 1 MB cap must stop before exhausting the space


def test_dedup_default_removes_duplicates(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(["a", "a"], str(out), min_length=1, max_length=None)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == len(set(lines))


def test_no_dedup_keeps_duplicates(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(["a", "a"], str(out), min_length=1, max_length=None, dedup=False)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert lines.count("a") > 1
    assert len(lines) > len(set(lines))


def test_no_dedup_via_cli(tmp_path, monkeypatch):
    out = tmp_path / "o.txt"
    monkeypatch.setattr(sys, "argv", ["PassGenerator.py", "-w", "a", "a", "--no-dedup", "-o", str(out)])
    pg.main()
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) > len(set(lines))


def test_live_memory_indicator_runs(tmp_path, monkeypatch):
    # A tiny refresh interval trips the indicator; generation must still succeed.
    monkeypatch.setattr(pg, "MEMORY_INDICATOR_INTERVAL", 2)
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(["a", "b", "c"], str(out), min_length=1, max_length=None)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) > 0 and len(lines) == len(set(lines))


def test_resume_no_checkpoint_runs_normally(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(["a", "b"], str(out), min_length=1, max_length=None, resume=True)
    lines = sorted(ln for ln in out.read_text(encoding="utf-8").splitlines() if ln)
    assert lines == sorted({"a", "b", "aa", "ab", "ba", "bb"})
    assert not os.path.exists(str(out) + ".pgckpt")  # removed on completion


def test_resume_saves_checkpoint_on_interrupt(tmp_path, monkeypatch):
    out = tmp_path / "o.txt"
    _interrupt_after(monkeypatch, 2)
    pg.generate_and_save_combinations(["a", "b", "c", "d"], str(out), min_length=1, max_length=None, resume=True)
    assert os.path.exists(str(out) + ".pgckpt")


def test_resume_completes_after_interrupt(tmp_path, monkeypatch):
    words = ["a", "b", "c", "d"]
    full = tmp_path / "full.txt"
    pg.generate_and_save_combinations(words, str(full), min_length=1, max_length=None)
    expected = sorted(ln for ln in full.read_text(encoding="utf-8").splitlines() if ln)

    out = tmp_path / "o.txt"
    _interrupt_after(monkeypatch, 2)
    pg.generate_and_save_combinations(words, str(out), min_length=1, max_length=None, resume=True)
    assert os.path.exists(str(out) + ".pgckpt")

    monkeypatch.undo()  # restore apply_modifications, then resume to completion
    pg.generate_and_save_combinations(words, str(out), min_length=1, max_length=None, resume=True)
    resumed = sorted(ln for ln in out.read_text(encoding="utf-8").splitlines() if ln)
    assert resumed == expected
    assert not os.path.exists(str(out) + ".pgckpt")


def test_disk_dedup_matches_in_memory(tmp_path):
    words = ["a", "a", "b", "c"]  # duplicate input forces dedup work
    mem = tmp_path / "mem.txt"
    disk = tmp_path / "disk.txt"
    pg.generate_and_save_combinations(words, str(mem), min_length=1, max_length=None)
    pg.generate_and_save_combinations(words, str(disk), min_length=1, max_length=None, disk_dedup=True)
    assert disk.read_text(encoding="utf-8").splitlines() == mem.read_text(encoding="utf-8").splitlines()
    assert not os.path.exists(str(disk) + ".dedup.sqlite")  # temp db cleaned up


def test_disk_dedup_no_duplicates(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(["a", "a", "b"], str(out), min_length=1, max_length=None, disk_dedup=True)
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == len(set(lines))


def test_disk_dedup_and_resume_conflict_is_refused(tmp_path, capsys):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(["a"], str(out), min_length=1, max_length=None, disk_dedup=True, resume=True)
    assert "not supported" in capsys.readouterr().out.lower()
    assert not out.exists()


# --- exact estimate -------------------------------------------------------------

USER_WORDS = ['muhammed', 'gunuc', '63', '34', '!', '@', 'prophet', 'retgere', '5']


def test_estimate_counts_only_lines_inside_length_bounds():
    # 1-character words allow 12 words per line, but only 5,061,474 sequences fit 8-12 characters
    assert pg.count_base_combinations(USER_WORDS, 8, 12) == 5_061_474
    assert pg.calculate_total_combinations(USER_WORDS, 8, 12, _mods()) == 5_061_474


def test_estimate_matches_generated_count():
    cases = [(['a', 'bb', 'ccc'], 1, 6), (['ab', 'c'], 2, 5), (['x', 'yy'], 3, None),
             (['admin', 'root', '2024'], 6, 12), (['a', 'a', 'bc'], 2, 4)]
    for words, mn, mx in cases:
        produced = sum(1 for _ in pg.generate_base_combinations(words, mn, mx))
        assert pg.count_base_combinations(words, mn, mx) == produced, (words, mn, mx)


def test_estimate_without_max_length_keeps_old_formula():
    assert pg.count_base_combinations(['a', 'bb', 'ccc'], 1, None) == 3 + 9 + 27


def test_estimate_unreachable_min_is_zero():
    assert pg.count_base_combinations(['a'], 5, 4) == 0
    assert pg.count_base_combinations(['abc'], 7, 8) == 0


def test_estimate_scales_with_variations():
    base = pg.count_base_combinations(['ab', 'c'], 2, 5)
    assert pg.calculate_total_combinations(['ab', 'c'], 2, 5, _mods(capitalize=True, leet=True)) == base * 4


def test_variation_count_matches_the_lines_each_word_turns_into():
    # -Ba / -BA alone also bring the plain reversed word with them
    from itertools import product
    keys = ['uppercase', 'capitalize', 'reverse', 'reverse_capitalize', 'reverse_upper', 'leet']
    for values in product([False, True], repeat=len(keys)):
        mods = dict(zip(keys, values))
        assert pg.variation_multiplier(mods) == len(pg.apply_modifications('abc', mods)), mods


# --- length-pruned generation -----------------------------------------------------

def _reference_combinations(words, mn, mx, ws=None, we=None):
    """The original algorithm: every product per token count, filtered by length."""
    from itertools import product
    out = []
    for k in range(1, pg.max_token_count(words, mx) + 1):
        for combo in product(words, repeat=k):
            joined = ''.join(combo)
            if len(joined) >= mn and (not mx or len(joined) <= mx):
                out.append((ws or '') + joined + (we or ''))
    return out


def test_pruned_generation_matches_product_reference():
    cases = [
        (['a', 'bb', 'ccc'], 1, 6, None, None),
        (['ab', 'c'], 2, 5, '<', '>'),
        (['x', 'yy'], 3, None, None, None),
        (['admin', 'root', '2024'], 6, 12, None, '!'),
        (['a', 'a', 'bc'], 2, 4, None, None),
        (['abc'], 7, 8, None, None),
        (['1', '22', '333', '4444'], 5, 9, 'p', None),
    ]
    for words, mn, mx, ws, we in cases:
        got = list(pg.generate_base_combinations(words, mn, mx, ws, we))
        assert got == _reference_combinations(words, mn, mx, ws, we), (words, mn, mx)


def test_generation_skips_infeasible_space_quickly():
    # a 1-character word allows 20 words per line: 5**20 products, yet only a few
    # thousand sequences fit in 20 characters
    import time
    words = ['!', 'aaaaaaaaaa', 'bbbbbbbbbb', 'cccccccccc', 'dddddddddd']
    start = time.perf_counter()
    produced = sum(1 for _ in pg.generate_base_combinations(words, 1, 20))
    assert produced == pg.count_base_combinations(words, 1, 20)
    assert time.perf_counter() - start < 10


# --- cleaning rules while generating ------------------------------------------------

def _lines(path):
    return path.read_text(encoding='utf-8').split()


def test_rules_drop_lines_before_writing(tmp_path):
    out = tmp_path / "o.txt"
    result = pg.generate_and_save_combinations(['a', 'b'], str(out), 4, 4, quiet=True,
                                               filters=['repetitive_chars'])
    lines = _lines(out)
    assert 'aaaa' not in lines and 'bbbb' not in lines
    assert len(lines) == 14 and result['written'] == 14
    assert result['filtered_total'] == 2
    assert result['filtered'] == {'repetitive_chars': 2}


def test_no_rules_output_unchanged(tmp_path):
    out = tmp_path / "o.txt"
    result = pg.generate_and_save_combinations(['a', 'b'], str(out), 4, 4, quiet=True)
    assert len(_lines(out)) == 16
    assert result['filtered_total'] == 0 and result['filtered'] == {}


def test_rules_see_prefix_and_suffix(tmp_path):
    out = tmp_path / "o.txt"
    result = pg.generate_and_save_combinations(['a'], str(out), 2, 2, word_start='aa', quiet=True,
                                               filters=['repetitive_chars'])
    assert result['written'] == 0 and result['filtered_total'] == 1


def test_limit_counts_kept_lines(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(['a', 'b'], str(out), 4, 4, limit=5, quiet=True,
                                      filters=['repetitive_chars'])
    assert _lines(out) == ['aaab', 'aaba', 'aabb', 'abaa', 'abab']


def test_live_counters_follow_the_run(tmp_path):
    live = {}
    pg.generate_and_save_combinations(['a', 'b'], str(tmp_path / "o.txt"), 4, 4, quiet=True,
                                      filters=['repetitive_chars'], live=live)
    assert live == {'processed': 16, 'filtered_total': 2}


def test_resume_refuses_changed_rules(tmp_path, monkeypatch, capsys):
    out = str(tmp_path / "o.txt")
    words = ['a', 'b', 'c']
    _interrupt_after(monkeypatch, 3)
    pg.generate_and_save_combinations(words, out, 1, 3, resume=True, filters=['repetitive_chars'])
    monkeypatch.undo()
    capsys.readouterr()
    pg.generate_and_save_combinations(words, out, 1, 3, resume=True, filters=['sequential_chars'])
    assert 'Resuming' not in capsys.readouterr().out


def test_preview_applies_rules():
    sample = pg.preview_combinations(['a', 'b'], 4, 4, filters=['repetitive_chars'], count=40)
    assert 'aaaa' not in sample and 'bbbb' not in sample and len(sample) == 14


def test_unknown_rule_is_refused(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        pg.generate_and_save_combinations(['a'], str(tmp_path / "o.txt"), quiet=True, filters=['nope'])


def test_cli_unknown_rule_errors(monkeypatch, capsys):
    import pytest
    monkeypatch.setattr(sys, 'argv', ['PassGenerator.py', '-w', 'a', '--filters', 'nope'])
    with pytest.raises(SystemExit):
        pg.main()
    assert 'nope' in capsys.readouterr().err


def test_cli_filters_all(tmp_path, monkeypatch):
    out = tmp_path / "o.txt"
    monkeypatch.setattr(sys, 'argv', ['PassGenerator.py', '-w', 'a', '1', '!', '-m', '4', '-M', '4',
                                      '-o', str(out), '--filters', 'all'])
    pg.main()
    lines = _lines(out)
    # every rule on: 72 of the 81 mixed lines survive; runs like '!!!!' do not
    assert len(lines) == 72 and '!!!!' not in lines and 'a1a1' not in lines


def _reference_run(words, mn, mx, mods, rules, ws=None, we=None):
    """Lines and drop count of a run built line by line, with no branch skipped:
    every combination, every variation, the rules, then dedup."""
    keep = pg.make_rule_check(rules)[0]
    seen, lines, dropped = set(), [], 0
    for base in _reference_combinations(words, mn, mx, ws, we):
        for line in pg.apply_modifications(base, mods):
            if not keep(line):
                dropped += 1
            elif line not in seen:
                seen.add(line)
                lines.append(line)
    return lines, dropped


PRUNE_WORDS = ['ab', 'a', '1', '!']
PRUNE_CASES = [
    # words, min, max, modifiers, rules, prefix, suffix
    (PRUNE_WORDS, 4, 8, {}, ['pattern_repetition'], None, None),
    (PRUNE_WORDS, 4, 8, {}, 'all', None, None),
    (PRUNE_WORDS, 3, 7, {'uppercase': True, 'capitalize': True}, ['pattern_repetition', 'sequential_chars'],
     None, None),
    (['Ab', 'c', '12', '3'], 2, 7, {'reverse_capitalize': True}, ['pattern_repetition', 'repetitive_chars'],
     None, None),
    (['ab', 'c', '9', '1'], 2, 6, {'reverse': True, 'reverse_upper': True, 'leet': True}, 'all', '<', '>'),
    (['es', 'l', '7', 't'], 2, 6, {'leet': True}, ['leet_speak', 'pattern_repetition'], None, None),
    (['qw', 'er', 'ty', 'a'], 2, 8, {'uppercase': True}, ['keyboard_patterns', 'common_words'], 'x', None),
    (['19', '9', '0', '5'], 4, 10, {}, ['year_patterns', 'date_patterns', 'phone_patterns'], None, '!'),
    (['a', 'a', 'b'], 1, 6, {}, ['pattern_repetition'], None, None),
    (['ab', 'c'], 1, None, {'capitalize': True}, ['pattern_repetition'], 'ab', None),
    (['ab', '', 'a'], 1, 5, {'reverse_capitalize': True}, ['pattern_repetition'], None, None),
    (['ΣΣ', 'σ', 'a'], 1, 6, {'capitalize': True, 'reverse_capitalize': True}, ['pattern_repetition'], None, None),
]


def test_rules_skip_branches_without_changing_the_output(tmp_path):
    for i, (words, mn, mx, mods, rules, ws, we) in enumerate(PRUNE_CASES):
        rules = list(pg.filter_rule_names()) if rules == 'all' else rules
        out = tmp_path / f"o{i}.txt"
        result = pg.generate_and_save_combinations(words, str(out), mn, mx, word_start=ws, word_end=we,
                                                   quiet=True, filters=rules, **mods)
        expected, dropped = _reference_run(words, mn, mx, _mods(**mods), rules, ws, we)
        assert out.read_text(encoding='utf-8').splitlines() == expected, i
        assert result['filtered_total'] == dropped, i


def test_limit_with_skipped_branches_keeps_the_first_lines(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(PRUNE_WORDS, str(out), 4, 8, limit=500, quiet=True,
                                      filters=['pattern_repetition'])
    expected, _ = _reference_run(PRUNE_WORDS, 4, 8, _mods(), ['pattern_repetition'])
    assert out.read_text(encoding='utf-8').splitlines() == expected[:500]


def test_rules_skip_lines_without_building_them(tmp_path):
    result = pg.generate_and_save_combinations(PRUNE_WORDS, str(tmp_path / "o.txt"), 4, 8, quiet=True,
                                               filters=['pattern_repetition'])
    assert 0 < result['skipped'] <= result['filtered_total']


def test_skipped_branches_account_for_every_missing_line():
    mods = _mods(uppercase=True, reverse=True)
    pruner = pg.make_pruner(['pattern_repetition'], mods, PRUNE_WORDS)
    built = sum(1 for _ in pg.generate_base_combinations(PRUNE_WORDS, 4, 8, prune=pruner))
    missing = pg.count_base_combinations(PRUNE_WORDS, 4, 8) - built
    assert missing > 0
    assert pruner.lines == missing * pg.variation_multiplier(mods)
    assert sum(pruner.by_rule.values()) == pruner.lines


def test_progress_counts_skipped_lines_as_processed(tmp_path):
    live = {}
    result = pg.generate_and_save_combinations(PRUNE_WORDS, str(tmp_path / "o.txt"), 4, 8, quiet=True,
                                               filters=['pattern_repetition'], live=live)
    assert result['skipped'] > 0
    assert live['processed'] == pg.calculate_total_combinations(PRUNE_WORDS, 4, 8, _mods())
    assert live['filtered_total'] == result['filtered_total'] == sum(result['filtered'].values())


def test_pruning_stays_off_for_inputs_it_cannot_reason_about():
    # an empty word can end a line right after a prefix, and Greek capital sigma
    # lowercases differently at the end of a word: such runs check every line instead
    assert pg.make_pruner(['pattern_repetition'], _mods(), ['a', '']) is None
    assert pg.make_pruner(['pattern_repetition'], _mods(), ['aΣ', 'b']) is None
    assert pg.make_pruner(['pattern_repetition'], _mods(), ['a'], word_end='Σ') is None
    assert pg.make_pruner(['number_only'], _mods(), ['a', 'b']) is None  # judges whole lines only
    assert pg.make_pruner(None, _mods(), ['a', 'b']) is None
    assert pg.make_pruner(['pattern_repetition'], _mods(), ['a', 'b']) is not None


def test_preview_with_rules_matches_the_run(tmp_path):
    out = tmp_path / "o.txt"
    pg.generate_and_save_combinations(PRUNE_WORDS, str(out), 4, 8, quiet=True, filters=['pattern_repetition'])
    sample = pg.preview_combinations(PRUNE_WORDS, 4, 8, filters=['pattern_repetition'], count=500,
                                     time_budget=5)
    assert sample == out.read_text(encoding='utf-8').splitlines()[:500]


def test_resume_with_rules_matches_an_uninterrupted_run(tmp_path, monkeypatch):
    rules = ['pattern_repetition']
    full = tmp_path / "full.txt"
    pg.generate_and_save_combinations(PRUNE_WORDS, str(full), 4, 8, quiet=True, filters=rules)
    out = tmp_path / "o.txt"
    _interrupt_after(monkeypatch, 40)
    pg.generate_and_save_combinations(PRUNE_WORDS, str(out), 4, 8, resume=True, filters=rules)
    assert os.path.exists(str(out) + ".pgckpt")
    monkeypatch.undo()
    pg.generate_and_save_combinations(PRUNE_WORDS, str(out), 4, 8, resume=True, filters=rules)
    assert out.read_text(encoding='utf-8').splitlines() == full.read_text(encoding='utf-8').splitlines()


def test_checkpoints_from_before_rules_skipped_branches_start_over(tmp_path, capsys):
    # back then a position counted every combination, so resuming one would skip the wrong lines
    import hashlib
    rules = ['pattern_repetition']
    fields = {'words': PRUNE_WORDS, 'min': 4, 'max': 8, 'modifiers': _mods(), 'ws': None, 'we': None,
              'gzip': False, 'filters': rules}
    old = hashlib.sha1(json.dumps(fields, sort_keys=True).encode('utf-8')).hexdigest()
    out = tmp_path / "o.txt"
    out.write_text('abab\n', encoding='utf-8')
    with open(str(out) + '.pgckpt', 'w', encoding='utf-8') as f:
        json.dump({'signature': old, 'position': 5, 'written': 1}, f)
    pg.generate_and_save_combinations(PRUNE_WORDS, str(out), 4, 8, resume=True, filters=rules)
    assert 'Resuming' not in capsys.readouterr().out


def test_cli_reports_lines_skipped_without_building_them(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['PassGenerator.py', '-w', *PRUNE_WORDS, '-m', '4', '-M', '8',
                                      '-o', str(tmp_path / "o.txt"), '--filters', 'pattern_repetition'])
    pg.main()
    assert 'never generated' in capsys.readouterr().out


def test_cli_filters_accept_commas(tmp_path, monkeypatch):
    out = tmp_path / "o.txt"
    monkeypatch.setattr(sys, 'argv', ['PassGenerator.py', '-w', 'a', 'b', '-m', '4', '-M', '4',
                                      '-o', str(out), '--filters', 'repetitive_chars,pattern_repetition'])
    pg.main()
    lines = _lines(out)
    assert 'aaaa' not in lines and 'abab' not in lines and 'aabb' in lines


# --- exact size --------------------------------------------------------------------

def test_size_estimate_matches_written_file(tmp_path):
    out = tmp_path / "o.txt"
    words = ['ab', 'c', 'ğü']  # 'ğü' is 2 characters but 4 bytes
    pg.generate_and_save_combinations(words, str(out), 2, 5, word_start='x', quiet=True)
    assert pg.estimate_output_bytes(words, 2, 5, _mods(), word_start='x') == out.stat().st_size


def test_size_estimate_scales_with_variations():
    plain = pg.estimate_output_bytes(['ab', 'c'], 2, 5, _mods())
    assert pg.estimate_output_bytes(['ab', 'c'], 2, 5, _mods(capitalize=True)) == plain * 2
