"""Tests for the standalone PassGenerator tool."""
import gzip
import json
import os
import sys

import PassGenerator as pg


def _interrupt_after(monkeypatch, n):
    """Patch apply_modifications to raise KeyboardInterrupt after n calls."""
    real = pg.apply_modifications
    calls = {"n": 0}

    def fake(word, mods):
        calls["n"] += 1
        if calls["n"] > n:
            raise KeyboardInterrupt
        return real(word, mods)

    monkeypatch.setattr(pg, "apply_modifications", fake)


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
    monkeypatch.setattr(pg, "MEMORY_WARNING_BYTES", 5)  # trip on the first word
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
