"""Дедублікація: ID, нормалізація компанії, порядок збереження, перехід зі старої схеми."""
import json

import pytest

import dedup
from dedup import (
    filter_new_jobs, job_id, legacy_job_id, load_seen, normalize_company, save_seen,
)


@pytest.mark.parametrize("raw", [
    "Lemberg Solutions", "lemberg-solutions", 'ТОВ "Lemberg Solutions"',
    "Lemberg Solutions LLC", "  LEMBERG   SOLUTIONS, Inc.  ",
])
def test_normalize_company_variants_collapse(raw):
    assert normalize_company(raw) == "lemberg solutions"


def test_normalize_company_keeps_word_containing_legal_form():
    assert normalize_company("Codex") == "codex"


def test_same_job_on_two_boards_has_one_id():
    a = job_id("Junior AI Engineer", "Lemberg Solutions", "https://djinni.co/jobs/1")
    b = job_id("junior ai engineer", "lemberg-solutions", "https://www.linkedin.com/jobs/view/2/")
    assert a == b


def test_empty_company_falls_back_to_url_not_title():
    a = job_id("Junior AI Engineer", "", "https://www.work.ua/jobs/1/")
    b = job_id("Junior AI Engineer", "", "https://www.work.ua/jobs/2/")
    assert a != b
    # трекінг-параметри не змінюють ID
    assert a == job_id("Junior AI Engineer", "", "https://www.work.ua/jobs/1/?utm=x")


def test_legacy_id_still_recognised_for_empty_company():
    seen = [legacy_job_id("Junior AI Engineer", "")]
    jobs = [{"title": "Junior AI Engineer", "company": "", "url": "https://x/1"}]
    new, updated = filter_new_jobs(jobs, seen)
    assert new == []
    assert updated == seen


def test_filter_new_jobs_dedups_within_run_and_keeps_order():
    jobs = [
        {"title": "A", "company": "Acme", "url": "u1"},
        {"title": "A", "company": "Acme LLC", "url": "u2"},   # той самий
        {"title": "B", "company": "", "url": "https://x/b"},
        {"title": "B", "company": "", "url": "https://x/b?ref=1"},  # той самий
        {"title": "C", "company": "", "url": "https://x/c"},
    ]
    new, updated = filter_new_jobs(jobs, ["old"])
    assert [j["title"] for j in new] == ["A", "B", "C"]
    assert updated[0] == "old" and len(updated) == 4


def test_save_seen_keeps_newest_ids(tmp_path, monkeypatch):
    path = tmp_path / "seen.json"
    monkeypatch.setattr(dedup, "DATA_PATH", str(path))
    monkeypatch.setattr(dedup, "MAX_STORED_IDS", 3)
    save_seen(["a", "b", "c", "d", "e"])
    assert json.loads(path.read_text())["seen_ids"] == ["c", "d", "e"]
    assert load_seen() == ["c", "d", "e"]


def test_load_seen_tolerates_missing_and_broken_file(tmp_path, monkeypatch):
    path = tmp_path / "seen.json"
    monkeypatch.setattr(dedup, "DATA_PATH", str(path))
    assert load_seen() == []
    path.write_text("{not json")
    assert load_seen() == []
