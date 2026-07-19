"""Tests for LanguageManager translations."""
from modules.language_manager import LanguageManager


def test_default_language_is_turkish():
    assert LanguageManager().current_language == "tr"


def test_set_language_and_lookup():
    lm = LanguageManager()
    lm.set_language("en")
    assert lm.get_text("welcome") == "Welcome to BruteForce Helper!"


def test_set_invalid_language_is_ignored():
    lm = LanguageManager()
    lm.set_language("en")
    lm.set_language("xx")  # unknown -> keep previous
    assert lm.current_language == "en"


def test_section_lookup():
    assert LanguageManager().get_text("basic_security", "filter_groups")


def test_optimize_runtime_keys_present():
    # Every top-level key optimize() looks up must exist in both languages.
    keys = ("wordlist_optimization", "checkpoint_found", "passwords_processed",
            "chunk_size", "passwords", "password", "press_q_to_stop",
            "press_c_to_checkpoint", "total", "checkpoint_saved",
            "stopping", "taking_checkpoint", "paused_last_stats",
            "saving_checkpoint", "final_filter_stats", "optimization_complete",
            "total_passwords", "removed_passwords", "remaining_passwords",
            "reduction_rate", "error", "file_not_found", "unexpected_error")
    for lang in ("tr", "en"):
        lm = LanguageManager()
        lm.set_language(lang)
        for key in keys:
            assert lm.get_text(key)


def test_common_words_per_language():
    lm = LanguageManager()
    assert lm.get_common_words()          # tr default, non-empty
    lm.set_language("en")
    assert "password" in lm.get_common_words()
