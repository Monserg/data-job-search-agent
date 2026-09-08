"""
DOU.ua — пошук вакансій за ключовим словом:
https://jobs.dou.ua/vacancies/?search=<keyword>
Посилання на вакансії: /companies/<company>/vacancies/<id>/
"""
import urllib.parse
from .base import html_link_scrape

BASE_URL = "https://jobs.dou.ua"
LINK_PATTERN = r"/companies/[^/]+/vacancies/\d+"
COMPANY_PATTERN = r"/companies/([^/]+)/vacancies/\d+"


def search(keywords: list) -> list:
    all_results = []
    for kw in keywords:
        q = urllib.parse.quote(kw)
        url = f"{BASE_URL}/vacancies/?search={q}"
        all_results.extend(
            html_link_scrape(url, LINK_PATTERN, BASE_URL, "DOU.ua", kw,
                              company_pattern=COMPANY_PATTERN)
        )
    return all_results
