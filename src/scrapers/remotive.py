"""
Remotive — офіційний публічний RSS: https://remotive.com/remote-jobs/feed
(стара адреса /feed віддає 404 з 2026-09). Фід містить елемент
<company>, який feedparser віддає як entry["company"]; author — запасний
варіант. Фільтрація за ключовими словами на нашому боці.
"""
from .base import fetch_feed, keyword_matches

FEED_URL = "https://remotive.com/remote-jobs/feed"


def search(queries: list, params: dict = None) -> list:
    feed = fetch_feed(FEED_URL)
    if feed is None:
        return []
    results = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "") or ""
        full_text = f"{title} {summary}"

        if not keyword_matches(full_text, queries):
            continue

        results.append({
            "title": title,
            "company": entry.get("company") or entry.get("author") or "",
            "url": entry.get("link", ""),
            "source": "Remotive",
            "text": full_text,
            "date": entry.get("published", ""),
        })
    return results
