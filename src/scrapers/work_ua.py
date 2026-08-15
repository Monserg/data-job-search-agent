"""
Work.ua — розділ Remote + пошук за ключовим словом:
https://www.work.ua/jobs-remote/?search=<keyword>
Посилання на вакансії виглядають як /jobs/1234567/

УВАГА: розмітка work.ua змінюється відносно часто. Якщо скрапер раптом
почне повертати 0 результатів — перевір вручну URL вище в браузері і за
потреби скоригуй LINK_PATTERN.
"""
import urllib.parse
from .base import html_link_scrape

BASE_URL = "https://www.work.ua"
LINK_PATTERN = r"/jobs/\d+"


def search(keywords: list) -> list:
    all_results = []
    for kw in keywords:
        q = urllib.parse.quote(kw)
        url = f"{BASE_URL}/jobs-remote/?search={q}"
        all_results.extend(
            html_link_scrape(url, LINK_PATTERN, BASE_URL, "Work.ua", kw)
        )
    return all_results
