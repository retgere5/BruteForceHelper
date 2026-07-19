"""Tests for the PasswordFilter rule engine and FilterStats."""
from types import SimpleNamespace

from modules.filters import PasswordFilter, FilterStats
from modules.language_manager import LanguageManager


def _opts(**over):
    base = dict(
        min_length_filter=False, repetitive_chars=False, pattern_repetition=False,
        number_only=False, letter_only=False, sequential_chars=False,
        keyboard_patterns=False, special_patterns=False, year_patterns=False,
        single_char_type=False, common_words=False, date_patterns=False,
        phone_patterns=False, leet_speak=False,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_all_filters_off_passes():
    assert PasswordFilter().is_valid_password("Anything9!", _opts(), FilterStats()) is True


def test_min_length_filter():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("abc", _opts(min_length_filter=True), st) is False
    assert pf.is_valid_password("abcd", _opts(min_length_filter=True), st) is True


def test_repetitive_chars():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("aaaa1", _opts(repetitive_chars=True), st) is False
    assert pf.is_valid_password("ab12", _opts(repetitive_chars=True), st) is True


def test_number_only():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("123456", _opts(number_only=True), st) is False
    assert pf.is_valid_password("12345a", _opts(number_only=True), st) is True


def test_sequential_chars():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("abcd", _opts(sequential_chars=True), st) is False
    assert pf.is_valid_password("1234", _opts(sequential_chars=True), st) is False


def test_keyboard_patterns():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("qwertyX", _opts(keyboard_patterns=True), st) is False


def test_common_words():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("mypassword", _opts(common_words=True), st) is False


def test_year_patterns():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("john1999", _opts(year_patterns=True), st) is False


def test_phone_patterns():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("05321234567", _opts(phone_patterns=True), st) is False


def test_single_char_type_removes_one_category():
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("password", _opts(single_char_type=True), st) is False  # all letters
    assert pf.is_valid_password("123456", _opts(single_char_type=True), st) is False    # all digits


def test_single_char_type_keeps_mixed_alnum():
    # Regression: PASS123 / Pass123 mix letters and digits -> not single-type -> keep.
    pf, st = PasswordFilter(), FilterStats()
    assert pf.is_valid_password("PASS123", _opts(single_char_type=True), st) is True
    assert pf.is_valid_password("Pass123", _opts(single_char_type=True), st) is True


def test_stats_increment_on_removal():
    pf, st = PasswordFilter(), FilterStats()
    pf.is_valid_password("123456", _opts(number_only=True), st)
    assert st.stats["number_only"] == 1


def test_filterstats_display_handles_zero_total():
    # No active filters and zero total must not raise.
    FilterStats().display(0)


def test_filterstats_display_uses_translations(capsys):
    lm = LanguageManager()
    lm.set_language("en")
    st = FilterStats(lm)
    st.stats["number_only"] = 5
    st.display(10)
    out = capsys.readouterr().out
    assert "Total" in out
    assert "Most effective filters" in out


def test_filterstats_display_fallback_without_language(capsys):
    st = FilterStats()  # no language manager -> Turkish fallback
    st.stats["number_only"] = 5
    st.display(10)
    assert "Toplam" in capsys.readouterr().out
