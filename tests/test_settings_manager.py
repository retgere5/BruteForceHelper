"""Tests for Settings persistence and FilterRecommender."""
from modules.settings_manager import Settings, FilterRecommender
from modules.language_manager import LanguageManager


def test_settings_roundtrip(tmp_path):
    s = Settings()
    s.settings_file = str(tmp_path / "settings.json")
    data = {"input": "in.txt", "output": "out.txt",
            "min_length_filter": True, "number_only": False}
    s.save_settings(data)
    assert s.load_settings() == data


def test_load_settings_missing(tmp_path):
    s = Settings()
    s.settings_file = str(tmp_path / "does_not_exist.json")
    assert s.load_settings() is None


def test_every_group_filter_has_a_description():
    # Regression: selecting individual filters ('s') looks up each filter name in
    # filter_descriptions; missing keys used to raise KeyError and crash setup.
    groups = Settings().get_filter_groups()
    names = [name for filters in groups.values() for name in filters]
    for lang in ("tr", "en"):
        lm = LanguageManager()
        lm.set_language(lang)
        for name in names:
            assert lm.get_text(name, "filter_descriptions")


def test_recommender_score_bounds():
    r = FilterRecommender()
    assert r.get_filter_score([]) == 0.0
    score = r.get_filter_score(["repetitive_chars", "sequential_chars"])
    assert 0 < score <= 100


def test_recommender_by_size():
    r = FilterRecommender()
    assert r.get_recommendations(500_000)[0][0] == "fast_filtering"
    assert r.get_recommendations(500_000_000)[0][0] == "maximum_security"


def test_recommendation_keys_have_translations():
    r = FilterRecommender()
    keys = set()
    for size in (500_000, 50_000_000, 500_000_000):
        keys.update(key for key, _desc in r.get_recommendations(size))
    for lang in ("tr", "en"):
        lm = LanguageManager()
        lm.set_language(lang)
        for key in keys:
            assert lm.get_text(key, "filter_recommendations")


def test_show_recommendations_outputs(tmp_path, capsys):
    wl = tmp_path / "wl.txt"
    wl.write_text("a\nb\nc\n", encoding="utf-8")
    lm = LanguageManager()
    lm.set_language("en")
    Settings()._show_recommendations(str(wl), lm)
    assert "Recommended filters" in capsys.readouterr().out


def test_show_recommendations_missing_file_is_silent(capsys):
    Settings()._show_recommendations("does_not_exist_xyz.txt", LanguageManager())
    assert capsys.readouterr().out == ""
