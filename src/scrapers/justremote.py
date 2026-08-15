"""
JustRemote — пошук: https://justremote.co/remote-jobs?search=<keyword>
"""
import urllib.parse
from .base import html_link_scrape

BASE_URL = "https://justremote.co"
LINK_PATTERN = r"/remote-jobs/[a-z0-9\-]+"


def search(keywords: list) -> list:
    all_results = []
    for kw in keywords:
        q = urllib.parse.quote(kw)
        url = f"{BASE_URL}/remote-jobs?search={q}"
        all_results.extend(
            html_link_scrape(url, LINK_PATTERN, BASE_URL, "JustRemote", kw)
        )
    return all_results
