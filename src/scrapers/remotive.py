"""
Remotive — офіційний публічний RSS: https://remotive.com/feed
Оновлюється в реальному часі, фільтрація за ключовими словами на нашому боці.
"""
import feedparser
from .base import keyword_matches

FEED_URL = "https://remotive.com/feed"


def search(keywords: list) -> list:
    feed = feedparser.parse(FEED_URL)
    results = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "") or ""
        full_text = f"{title} {summary}"

        if not keyword_matches(full_text, keywords):
            continue

        company = entry.get("author", "") or ""

        results.append({
            "title": title,
            "company": company,
            "url": entry.get("link", ""),
            "source": "Remotive",
            "text": full_text,
            "date": entry.get("published", ""),
        })
    return results
