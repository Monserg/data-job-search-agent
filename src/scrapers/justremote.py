"""
JustRemote — пошук: https://justremote.co/remote-jobs?search=<keyword>

УВАГА: сайт побудований на Gatsby (SPA) — список вакансій, найімовірніше,
довантажується через JS і в статичний HTML не потрапляє. Якщо в звіті
здоров'я джерел (Telegram) це джерело стабільно дає 0 — вимкни його в
config.yaml (sources.justremote.enabled: false).
"""
import urllib.parse
from .base import html_link_scrape

BASE_URL = "https://justremote.co"
LINK_PATTERN = r"/remote-jobs/[a-z0-9\-]+"


def search(queries: list, params: dict = None) -> list:
    all_results = []
    for kw in queries or []:
        q = urllib.parse.quote(kw)
        url = f"{BASE_URL}/remote-jobs?search={q}"
        all_results.extend(html_link_scrape(url, LINK_PATTERN, BASE_URL, "JustRemote"))
    return all_results
