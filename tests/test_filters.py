"""Чисті функції фільтрації (src/scrapers/base.py) та фільтри профілів (main.py)."""
import pytest

from config_loader import load_config
from main import apply_profile_filters
from scrapers.base import (
    canonical_url, find_excluded, is_excluded, keyword_matches, title_matches,
)


# ---------------------------------------------------------------- keyword_matches

@pytest.mark.parametrize("text,expected", [
    ("We hire an AI Engineer for our team", True),
    ("AI-Engineer wanted", True),
    ("Maintain our email pipeline, engineer role", False),   # "ai" усередині слів
    ("Respond promptly, engineer", False),
])
def test_short_query_requires_exact_phrase(text, expected):
    assert keyword_matches(text, ["AI Engineer"]) is expected


def test_long_query_all_words_any_order():
    assert keyword_matches("AI Engineer (Junior) — LLM apps", ["Junior LLM Engineer"])
    assert not keyword_matches("Junior Engineer", ["Junior LLM Engineer"])


def test_query_with_slash_separator():
    assert keyword_matches("iOS/Swift Developer", ["Swift Developer"])


# ---------------------------------------------------------------- exclusions

@pytest.mark.parametrize("text,keywords,expected", [
    ("stay ahead of the curve", ["Head of"], None),
    ("Head of AI", ["Head of"], "Head of"),
    ("strong leadership skills", ["Lead"], None),
    ("Tech Lead", ["Lead"], "Lead"),
    ("clean architecture", ["Architect"], None),
    ("Solutions Architect", ["Architect"], "Architect"),
    ("Sr. AI Engineer", ["Sr."], "Sr."),
    ("Requires 2+ years of experience", ["2+ years"], "2+ years"),
    ("Requires 12+ years", ["2+ years"], None),
    ("досвід від 1 року", ["від 1 року"], "від 1 року"),
    ("English B2+ required", ["English B2"], "English B2"),
    ("", ["Senior"], None),
    ("Senior", [], None),
])
def test_find_excluded_word_boundaries(text, keywords, expected):
    assert find_excluded(text, keywords) == expected
    assert is_excluded(text, keywords) is (expected is not None)


def test_exclusion_is_case_insensitive_and_collapses_spaces():
    assert find_excluded("HEAD   OF Engineering", ["Head of"]) == "Head of"


# ---------------------------------------------------------------- title_matches

def test_title_regex_multiline_block_is_joined():
    pattern = "(?<![a-z0-9])(ios|\n      swift)(?![a-z0-9])"
    assert title_matches("Senior Swift Developer", pattern)
    assert not title_matches("Android Developer", pattern)


def test_title_matches_empty_pattern_is_false():
    assert title_matches("anything", "") is False


# ---------------------------------------------------------------- canonical_url

@pytest.mark.parametrize("url,expected", [
    ("https://www.work.ua/jobs/123/?utm_source=x#top", "https://www.work.ua/jobs/123"),
    ("HTTPS://Djinni.co/jobs/1-x/", "https://djinni.co/jobs/1-x"),
    ("", ""),
])
def test_canonical_url(url, expected):
    assert canonical_url(url) == expected


# ---------------------------------------------------------------- профілі з config.yaml

@pytest.fixture(scope="module")
def profiles():
    return load_config()["profiles"]


def _passes(profile, title, text=None):
    kept, _ = apply_profile_filters([{"title": title, "text": text or title}], profile)
    return bool(kept)


@pytest.mark.parametrize("title,expected", [
    ("Junior AI Engineer", True),
    ("Trainee AI Engineer (5810)", True),
    ("AI / Prompt Engineer (Python, LLM)", True),
    ("Junior Computer Vision / ML Engineer", True),
    ("Machine Learning Engineer", True),
    ("Customer Support Agent", False),          # "agent" — не AI-маркер
    ("Senior AI Engineer", False),
    ("Lead AI Design Engineer", False),
    ("Middle AI Engineer", False),
    ("Full Stack Developer (Python/React)", False),
    ("Project Coordinator", False),
])
def test_ai_junior_profile_titles(profiles, title, expected):
    assert _passes(profiles["ai_junior"], title) is expected


def test_ai_junior_profile_rejects_experience_in_description(profiles):
    ai = profiles["ai_junior"]
    assert _passes(ai, "Junior AI Engineer", "Junior AI Engineer. We need 3+ years of Python.") is False
    assert _passes(ai, "Junior AI Engineer", "Junior AI Engineer. Strong leadership, clean architecture.") is True


@pytest.mark.parametrize("title,expected", [
    ("iOS Engineer Senior (Driver Team)", True),
    ("Middle iOS Engineer", True),
    ("Sr iOS Developer", True),
    ("iOS Developer (Swift)", True),
    ("iOS Swift Engineer", True),
    ("Senior ASO Specialist (iOS)", False),
    ("Tech Support Android / iOS (Publisher)", False),
    ("IOS/ Android Architect", False),
    ("Junior iOS Developer", False),
    ("Product Engineer (Swift/Kotlin)", False),
    ("Product Manager / Apps Product Lead (experience in iOS & mobile apps)", False),
    ("Senior Product Designer (iOS/Android B2C)", False),
    ("Mobile Tech Lead", False),                 # без iOS/Swift у назві
])
def test_ios_profile_titles(profiles, title, expected):
    assert _passes(profiles["ios_middle_senior"], title) is expected


def test_ios_profile_keeps_years_of_experience(profiles):
    ios = profiles["ios_middle_senior"]
    assert _passes(ios, "Senior iOS Developer", "Senior iOS Developer, 5+ years of Swift") is True


def test_apply_profile_filters_reports_reasons(profiles):
    jobs = [
        {"title": "Senior iOS Developer", "text": ""},
        {"title": "Android Developer", "text": ""},
        {"title": "Junior iOS Developer", "text": ""},
    ]
    kept, dropped = apply_profile_filters(jobs, profiles["ios_middle_senior"])
    assert [j["title"] for j in kept] == ["Senior iOS Developer"]
    assert dropped == {"немає тематичного маркера в назві": 1, "стоп-слово в назві": 1}
