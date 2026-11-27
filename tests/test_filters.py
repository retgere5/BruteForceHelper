"""Tests for the PasswordFilter rule engine and FilterStats."""
import random
import re
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


# --- the slow checks as first written, kept as the reference for the faster ones ---

def _ref_pattern_repetition(password):
    for i in range(2, len(password) // 2 + 1):
        for j in range(len(password) - i * 2 + 1):
            if password[j:j + i] == password[j + i:j + i * 2]:
                return True
    return False


def _ref_sequential(password):
    lower_pass = password.lower()
    for seq in ('0123456789', 'abcdefghijklmnopqrstuvwxyz'):
        for i in range(len(seq) - 3):
            if seq[i:i + 4] in lower_pass or seq[i:i + 4][::-1] in lower_pass:
                return True
    return False


def _ref_single_char_type(password):
    if not password:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_alpha = any(c.isalpha() for c in password)
    has_other = any(not c.isalnum() for c in password)
    return (has_digit + has_alpha + has_other) == 1


_REF_LEET = {'a': ['4', '@'], 'e': ['3'], 'i': ['1', '!'], 'o': ['0'], 's': ['5', '$'], 't': ['7'],
             'l': ['1'], 'z': ['2']}


def _ref_leet_speak(password):
    lower_pass = password.lower()
    for char, replacements in _REF_LEET.items():
        for replacement in replacements:
            if replacement in password and char in lower_pass:
                return True
    return False


_REF_DATES = [re.compile(p) for p in (r'\d{2}[.-/]\d{2}[.-/]\d{4}', r'\d{4}[.-/]\d{2}[.-/]\d{2}', r'\d{8}')]
_REF_PHONES = [re.compile(p) for p in (r'05\d{9}', r'5\d{9}', r'\+905\d{9}')]

REFERENCE = {
    'pattern_repetition': _ref_pattern_repetition,
    'sequential_chars': _ref_sequential,
    'single_char_type': _ref_single_char_type,
    'leet_speak': _ref_leet_speak,
    'date_patterns': lambda s: any(p.search(s) for p in _REF_DATES),
    'phone_patterns': lambda s: any(p.search(s) for p in _REF_PHONES),
}


def _random_lines(seed, alphabet, count, longest):
    rng = random.Random(seed)
    return [''.join(rng.choice(alphabet) for _ in range(rng.randint(0, longest))) for _ in range(count)]


def _tricky_lines():
    # Greek sigma, dotted I and the Kelvin sign change length or context when lowered;
    # \udc80 is how undecodable bytes arrive from a latin-1 wordlist; ½ is numeric but no
    # digit, ² a digit but no decimal, ٣ an Arabic-Indic digit
    return (_random_lines(1, 'abAB01!@.-/5ΣσςİK x\n\udc80', 6000, 14)
            + _random_lines(4, 'aZ4@3!$7l½²٣ß_', 6000, 6)
            + _random_lines(2, '0123456789.-/+5', 6000, 16)
            + _random_lines(3, 'abcdzyxw98761234', 6000, 10)
            + ['', 'abab', 'abcabc', 'aXbXaXbX', 'dcba', 'ZYXW', '9876', '12.34.5678',
               '1234-56-78', '12/34/5678', '+905321234567', '5321234567', 'İabcd'])


def test_rules_give_the_same_verdicts_as_the_original_checks():
    pf, st = PasswordFilter(), FilterStats()
    for name, reference in REFERENCE.items():
        opts = _opts(**{name: True})
        for line in _tricky_lines():
            assert pf.is_valid_password(line, opts, st) is (not reference(line)), (name, line)


# --- rules that look for a piece inside the password ---------------------------------

SUBSTRING_RULES = ['repetitive_chars', 'pattern_repetition', 'sequential_chars', 'keyboard_patterns',
                   'special_patterns', 'year_patterns', 'common_words', 'date_patterns',
                   'phone_patterns', 'leet_speak']
EVERY_RULE = _opts(**{name: True for name in vars(_opts())})
PATTERN_SAMPLES = ['qwerty', 'zxcvbn9', 'MyPassword', 'admin', 'x!@#y', '123!@#', 'Dragon', 'aaaa', 'l33t']


def test_substring_rules_follow_the_check_order():
    names = [name for name, _ in PasswordFilter().substring_rules(EVERY_RULE)]
    assert names == SUBSTRING_RULES


def test_substring_rules_lists_only_active_rules():
    rules = PasswordFilter().substring_rules(_opts(pattern_repetition=True, number_only=True))
    assert [name for name, _ in rules] == ['pattern_repetition']


def test_substring_rule_checks_agree_with_is_valid_password():
    pf, st = PasswordFilter(), FilterStats()
    for name, check in pf.substring_rules(EVERY_RULE):
        opts = _opts(**{name: True})
        for line in _tricky_lines() + PATTERN_SAMPLES:
            assert bool(check(line)) is (not pf.is_valid_password(line, opts, st)), (name, line)


def test_substring_rules_keep_matching_when_text_is_added():
    rng = random.Random(7)
    around = 'aZ1!@.-/5ΣσςİK x\n'
    for name, check in PasswordFilter().substring_rules(EVERY_RULE):
        hits = 0
        for line in _tricky_lines() + PATTERN_SAMPLES:
            if not check(line):
                continue
            hits += 1
            for _ in range(3):
                before = ''.join(rng.choice(around) for _ in range(rng.randint(0, 4)))
                after = ''.join(rng.choice(around) for _ in range(rng.randint(0, 4)))
                assert check(before + line + after), (name, before, line, after)
        assert hits, name


def test_whole_line_rules_can_change_their_verdict_when_text_is_added():
    pf, st = PasswordFilter(), FilterStats()
    cases = {'min_length_filter': ('abc', 'abcd'), 'number_only': ('123456', '123456a'),
             'letter_only': ('abcdef', 'abcdef1'), 'single_char_type': ('abcd', 'abcd1')}
    for name, (dropped, longer) in cases.items():
        opts = _opts(**{name: True})
        assert pf.is_valid_password(dropped, opts, st) is False
        assert pf.is_valid_password(longer, opts, st) is True
        assert pf.substring_rules(opts) == []
