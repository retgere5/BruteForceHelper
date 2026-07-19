"""Integration tests for WordlistFixer.WordlistOptimizer.

These guard the previously fatal bugs: WordlistOptimizer never stored
self.options, and it consumed a dict via attribute access -> AttributeError
before any filtering happened.
"""
import gzip
import pickle
from types import SimpleNamespace

import WordlistFixer as wf
from modules.language_manager import LanguageManager


def _filter_opts(**over):
    base = dict(
        min_length=None, max_length=None,
        min_length_filter=False, repetitive_chars=False, pattern_repetition=False,
        number_only=False, letter_only=False, sequential_chars=False, keyboard_patterns=False,
        special_patterns=False, year_patterns=False, single_char_type=False,
        common_words=False, date_patterns=False, phone_patterns=False, leet_speak=False,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _options(inp, outp, **over):
    """Return options as a plain dict, exactly as Settings.get_filter_options does."""
    base = dict(
        input=str(inp), output=str(outp), min_length=None, max_length=None, keep_stats=False,
        min_length_filter=False, repetitive_chars=False, pattern_repetition=False,
        number_only=False, letter_only=False, sequential_chars=False, keyboard_patterns=False,
        special_patterns=False, year_patterns=False, single_char_type=False,
        common_words=False, date_patterns=False, phone_patterns=False, leet_speak=False,
    )
    base.update(over)
    return base


def test_optimizer_runs_on_dict_options(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("123456\nStr0ngPass!\naaaa\n", encoding="utf-8")
    outp = tmp_path / "out.txt"

    opt = wf.WordlistOptimizer(
        _options(inp, outp, number_only=True, repetitive_chars=True), LanguageManager()
    )
    assert hasattr(opt, "options")  # regression: was never assigned

    opt.optimize()  # regression: used to raise AttributeError immediately

    survivors = [ln for ln in outp.read_text(encoding="utf-8").splitlines() if ln]
    assert "123456" not in survivors   # number_only removed it
    assert "aaaa" not in survivors     # repetitive_chars removed it
    assert "Str0ngPass!" in survivors


def test_optimizer_filters_expected_lines(tmp_path):
    inp = tmp_path / "in.txt"
    inp.write_text("111111\n222222\nGoodPass9!\n", encoding="utf-8")
    outp = tmp_path / "out.txt"

    opt = wf.WordlistOptimizer(_options(inp, outp, number_only=True), LanguageManager())
    opt.optimize()

    survivors = [ln for ln in outp.read_text(encoding="utf-8").splitlines() if ln]
    assert survivors == ["GoodPass9!"]


def test_optimizer_empty_input_no_zero_division(tmp_path):
    inp = tmp_path / "empty.txt"
    inp.write_text("", encoding="utf-8")
    outp = tmp_path / "out.txt"

    opt = wf.WordlistOptimizer(_options(inp, outp), LanguageManager())
    opt.optimize()  # must not raise ZeroDivisionError

    assert outp.exists()


def test_filter_chunk_worker_directly():
    valid, stat_counts, chunk_len = wf._filter_chunk_worker(
        (["123456\n", "GoodPass9!\n"], _filter_opts(number_only=True), None, None)
    )
    assert valid == ["GoodPass9!"]
    assert chunk_len == 2
    assert stat_counts["number_only"] == 1


def test_filter_chunk_worker_output_is_picklable():
    # The worker crosses a process boundary, so its return value must pickle.
    result = wf._filter_chunk_worker((["123456\n", "abc\n"], _filter_opts(number_only=True), None, None))
    assert pickle.loads(pickle.dumps(result)) == result


def test_optimize_under_real_multiprocessing(tmp_path, monkeypatch):
    # Force a multi-worker pool regardless of host core count, then verify the
    # parallel imap path filters correctly across chunks and preserves order.
    monkeypatch.setattr(wf.mp, "cpu_count", lambda: 4)
    inp = tmp_path / "big.txt"
    inp.write_text("".join(["123456\n"] * 2500 + ["KEEPTHIS!\n"]), encoding="utf-8")
    outp = tmp_path / "out.txt"

    opt = wf.WordlistOptimizer(_options(inp, outp, number_only=True), LanguageManager())
    opt.optimize()

    survivors = [ln for ln in outp.read_text(encoding="utf-8").splitlines() if ln]
    assert survivors == ["KEEPTHIS!"]


def test_optimizer_gzip_input_and_output(tmp_path):
    inp = tmp_path / "in.txt.gz"
    with gzip.open(inp, "wt", encoding="utf-8") as fh:
        fh.write("123456\nGoodPass9!\n")
    outp = tmp_path / "out.txt.gz"

    opt = wf.WordlistOptimizer(_options(inp, outp, number_only=True), LanguageManager())
    opt.optimize()

    with gzip.open(outp, "rt", encoding="utf-8") as fh:
        survivors = [ln for ln in fh.read().splitlines() if ln]
    assert survivors == ["GoodPass9!"]


def test_checkpoint_manager_roundtrip(tmp_path):
    cp = tmp_path / "run.checkpoint"
    wf.CheckpointManager(str(cp)).save_checkpoint(100, 100, 40)

    reloaded = wf.CheckpointManager(str(cp))
    assert reloaded.last_position == 100
    assert reloaded.processed_count == 100
    assert reloaded.removed_count == 40
