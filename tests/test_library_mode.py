"""Programmatic use of both tools (as the web interface drives them): quiet mode,
progress callbacks, stop events, previews and the --webui flag."""
import json
import os
import sys
import threading
import time
from itertools import product

import pytest

import PassGenerator as pg
import WordlistFixer as wf
from modules.language_manager import LanguageManager


def _mods(**over):
    base = {key: False for key in ('uppercase', 'capitalize', 'reverse',
                                   'reverse_capitalize', 'reverse_upper', 'leet')}
    base.update(over)
    return base


def _options(inp, outp, **over):
    base = dict(
        input=str(inp), output=str(outp), min_length=None, max_length=None, keep_stats=False,
        min_length_filter=False, repetitive_chars=False, pattern_repetition=False,
        number_only=False, letter_only=False, sequential_chars=False, keyboard_patterns=False,
        special_patterns=False, year_patterns=False, single_char_type=False,
        common_words=False, date_patterns=False, phone_patterns=False, leet_speak=False,
    )
    base.update(over)
    return base


def _naive_bases(words, min_length, max_length):
    """Reference: every product up to the token cap, filtered by character length."""
    out = []
    for n in range(1, pg.max_token_count(words, max_length) + 1):
        for combo in product(words, repeat=n):
            combined = ''.join(combo)
            if len(combined) >= min_length and (not max_length or len(combined) <= max_length):
                out.append(combined)
    return out


# --- PassGenerator ------------------------------------------------------------

def test_min_length_skip_keeps_output_identical():
    cases = ((["ab", "c"], 5, None), (["a", "bbbb"], 6, 8), (["x"], 3, 5), (["", "ab"], 2, 4))
    for words, lo, hi in cases:
        assert list(pg.generate_base_combinations(words, lo, hi)) == _naive_bases(words, lo, hi)


def test_min_length_skip_avoids_hopeless_rounds():
    # Without the skip this walks 2**1 + ... + 2**39 short combinations first
    start = time.monotonic()
    first = next(pg.generate_base_combinations(["a", "b"], 40, 40))
    assert first == "a" * 40
    assert time.monotonic() - start < 2


def test_generate_base_combinations_honours_stop_event():
    stop = threading.Event()
    stop.set()
    assert list(pg.generate_base_combinations(["a", "b"], 1, 30, stop_event=stop)) == []


def test_preview_matches_real_output(tmp_path):
    out = tmp_path / "o.txt"
    words = ["ab", "cd", "ab"]
    pg.generate_and_save_combinations(words, str(out), 2, 6, uppercase=True, reverse=True, leet=True,
                                      word_start="x", word_end="!")
    written = out.read_text(encoding="utf-8").splitlines()
    sample = pg.preview_combinations(words, 2, 6, _mods(uppercase=True, reverse=True, leet=True),
                                     "x", "!", count=15)
    assert sample == written[:15]


def test_preview_without_dedup_keeps_repeats():
    sample = pg.preview_combinations(["a", "a"], 1, 2, _mods(), count=6, dedup=False)
    assert sample == ["a", "a", "aa", "aa", "aa", "aa"]


def test_preview_respects_time_budget():
    words = ["a", "b" * 30]  # nearly every long combination is too long, so matches are rare
    start = time.monotonic()
    sample = pg.preview_combinations(words, 1, 30, _mods(), count=1000, time_budget=0.05)
    assert time.monotonic() - start < 2
    assert "a" in sample


def test_quiet_mode_prints_nothing_and_returns_summary(tmp_path, capsys):
    out = tmp_path / "o.txt"
    calls = []
    summary = pg.generate_and_save_combinations(["a", "b", "c"], str(out), 1, 3, quiet=True,
                                                progress=lambda done, total: calls.append(done))
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    lines = out.read_text(encoding="utf-8").splitlines()
    assert summary["written"] == len(lines) == 39
    assert summary["stopped_by"] is None
    assert summary["path"] == os.path.abspath(str(out))
    assert calls and calls[-1] == 39


def test_progress_called_in_batches(tmp_path, monkeypatch, python_engine):
    monkeypatch.setattr(pg, "PROGRESS_UPDATE_BATCH", 10)
    calls = []
    pg.generate_and_save_combinations(["a", "b"], str(tmp_path / "o.txt"), 1, 5, quiet=True,
                                      progress=lambda done, total: calls.append((done, total)))
    assert [done for done, _ in calls] == [10, 20, 30, 40, 50, 60, 62]
    assert {total for _, total in calls} == {pg.calculate_total_combinations(["a", "b"], 1, 5, _mods())}


def test_stop_event_ends_run_and_keeps_output(tmp_path, python_engine):
    stop = threading.Event()
    out = tmp_path / "o.txt"

    def on_progress(done, total):
        if done >= 2000:
            stop.set()

    summary = pg.generate_and_save_combinations(list("abcdefghij"), str(out), 1, 8, quiet=True,
                                                progress=on_progress, stop_event=stop)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert summary["stopped_by"] == "user"
    assert summary["written"] == len(lines)
    assert 2000 <= len(lines) < 100_000


def test_limit_is_reported_as_stop_reason(tmp_path):
    summary = pg.generate_and_save_combinations(["a", "b"], str(tmp_path / "o.txt"), 1, None,
                                                limit=3, quiet=True)
    assert summary["stopped_by"] == "limit" and summary["written"] == 3


def test_quiet_mode_raises_instead_of_printing(tmp_path, capsys):
    with pytest.raises(OSError):
        pg.generate_and_save_combinations(["a"], str(tmp_path / "missing" / "o.txt"), quiet=True)
    assert capsys.readouterr().out == ""


def test_passgenerator_webui_flag_starts_server(monkeypatch):
    import webui.server
    calls = []
    monkeypatch.setattr(webui.server, "run", lambda **kw: calls.append(kw))
    monkeypatch.setattr(sys, "argv", ["PassGenerator.py", "--webui", "--port", "9999", "--no-browser"])
    pg.main()
    assert calls == [{"port": 9999, "open_browser": False, "start_tab": "generate"}]


# --- WordlistOptimizer --------------------------------------------------------

def test_optimize_quiet_returns_summary_without_output(tmp_path, capsys):
    inp = tmp_path / "in.txt"
    inp.write_text("123456\nStr0ngPass!\naaaa\nhello\n", encoding="utf-8")
    calls = []
    opt = wf.WordlistOptimizer(_options(inp, tmp_path / "out.txt", number_only=True, repetitive_chars=True),
                               LanguageManager())
    summary = opt.optimize(quiet=True, progress=lambda *args: calls.append(args))
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    assert (summary["total"], summary["removed"], summary["remaining"]) == (4, 2, 2)
    assert summary["filter_stats"]["number_only"] == 1
    assert summary["filter_stats"]["repetitive_chars"] == 1
    assert summary["stopped"] is False and summary["stats_file"] is None
    assert calls[0][:3] == (0, 4, 0) and calls[-1][:3] == (4, 4, 2)


def test_optimize_stop_event_stops_after_current_chunk(tmp_path, monkeypatch):
    monkeypatch.setattr(wf.mp, "cpu_count", lambda: 1)  # in-process, 1000-line chunks
    inp = tmp_path / "in.txt"
    inp.write_text("".join(f"word{i}\n" for i in range(5000)), encoding="utf-8")
    stop = threading.Event()
    stop.set()
    summary = wf.WordlistOptimizer(_options(inp, tmp_path / "out.txt"), LanguageManager()).optimize(
        quiet=True, stop_event=stop)
    assert summary["stopped"] is True
    assert summary["total"] == 1000


def test_optimize_quiet_ignores_stale_checkpoint(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    outp = tmp_path / "out.txt"
    checkpoint = tmp_path / "out.txt.checkpoint"
    checkpoint.write_text(json.dumps({"position": 2, "processed_count": 2, "removed_count": 0}),
                          encoding="utf-8")
    summary = wf.WordlistOptimizer(_options(inp, outp), LanguageManager()).optimize(quiet=True)
    assert summary["total"] == 3
    assert outp.read_text(encoding="utf-8").splitlines() == ["alpha", "beta", "gamma"]
    assert checkpoint.exists()  # left alone for the console run that owns it


def test_optimize_quiet_raises_on_missing_input(tmp_path):
    opt = wf.WordlistOptimizer(_options(tmp_path / "missing.txt", tmp_path / "out.txt"), LanguageManager())
    with pytest.raises(FileNotFoundError):
        opt.optimize(quiet=True)


def test_optimize_stats_file_path_is_returned(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("123456\nabc\n", encoding="utf-8")
    summary = wf.WordlistOptimizer(_options(inp, tmp_path / "out.txt", number_only=True, keep_stats=True),
                                   LanguageManager()).optimize(quiet=True)
    assert summary["stats_file"] and os.path.isfile(summary["stats_file"])


def test_invalid_utf8_lines_survive_unchanged(tmp_path):
    inp = tmp_path / "in.txt"
    raw = b"caf\xe9\nplain\n\xff\xfeodd\n"
    inp.write_bytes(raw)
    outp = tmp_path / "out.txt"
    wf.WordlistOptimizer(_options(inp, outp), LanguageManager()).optimize(quiet=True)
    assert outp.read_bytes().splitlines() == raw.splitlines()  # bytes kept (newlines follow the OS)


def test_analyze_handles_invalid_utf8(tmp_path):
    wl = tmp_path / "wl.txt"
    wl.write_bytes(b"caf\xe9\n123456\n")
    stats = wf.analyze_wordlist(str(wl))
    assert stats["total"] == 2 and stats["digit_only"] == 1


def test_analyze_progress_and_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(wf, "ANALYZE_CHECK_INTERVAL", 2)
    wl = tmp_path / "wl.txt"
    wl.write_text("a\nbb\nccc\ndddd\n", encoding="utf-8")
    calls = []
    stats = wf.analyze_wordlist(str(wl), progress=lambda lines, chars: calls.append((lines, chars)))
    assert calls == [(2, 3), (4, 10)] and stats["stopped"] is False
    stop = threading.Event()
    stop.set()
    partial = wf.analyze_wordlist(str(wl), stop_event=stop)
    assert partial["stopped"] is True and partial["total"] == 2


def test_wordlistfixer_webui_flag_starts_server(monkeypatch):
    import webui.server
    calls = []
    monkeypatch.setattr(webui.server, "run", lambda **kw: calls.append(kw))
    monkeypatch.setattr(sys, "argv", ["WordlistFixer.py", "--webui"])
    wf.main()
    assert calls == [{"port": None, "open_browser": True, "start_tab": "clean"}]
