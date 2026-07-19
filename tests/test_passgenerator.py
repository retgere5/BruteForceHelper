"""Tests for the standalone PassGenerator tool."""
import PassGenerator as pg


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
