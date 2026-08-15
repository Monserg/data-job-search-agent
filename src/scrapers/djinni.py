"""
Djinni.co — фільтрація по URL-патерну /jobs/keyword-<slug>/
Приклад: https://djinni.co/jobs/keyword-python/
Посилання на самі вакансії виглядають як /jobs/vacancies/12345-title/
"""
from .base import html_link_scrape, slugify

BASE_URL = "https://djinni.co"
LINK_PATTERN = r"/jobs/vacancies/\d+"


def search(keywords: list) -> list:
    all_results = []
    for kw in keywords:
        url = f"{BASE_URL}/jobs/keyword-{slugify(kw)}/"
        all_results.extend(
            html_link_scrape(url, LINK_PATTERN, BASE_URL, "Djinni", kw)
        )
    return all_results
