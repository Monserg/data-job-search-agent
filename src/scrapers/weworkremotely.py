"""
WeWorkRemotely — офіційний публічний RSS.
Загальний фід (усі категорії): https://weworkremotely.com/remote-jobs.rss
Фільтрація за ключовими словами відбувається вже на нашому боці, бо
фід не підтримує пошук за keyword у query-рядку.
"""
import feedparser
from .base import keyword_matches

FEED_URL = "https://weworkremotely.com/remote-jobs.rss"


def search(keywords: list) -> list:
    feed = feedparser.parse(FEED_URL)
    results = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "") or ""
        full_text = f"{title} {summary}"

        if not keyword_matches(full_text, keywords):
            continue

        # Заголовки WWR часто у форматі "Компанія: Посада"
        company = ""
        clean_title = title
        if ":" in title:
            company, clean_title = title.split(":", 1)

        results.append({
            "title": clean_title.strip(),
            "company": company.strip(),
            "url": entry.get("link", ""),
            "source": "WeWorkRemotely",
            "text": full_text,
            "date": entry.get("published", ""),
        })
    return results
