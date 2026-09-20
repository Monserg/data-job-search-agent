"""
Djinni.co — офіційний RSS-фід (знайдений внизу сторінки пошуку):
https://djinni.co/jobs/rss/?primary_keyword=<Keyword>

Це замінює попередній підхід через HTML-скрапінг, який зламався, бо
Djinni змінив структуру URL вакансій з /jobs/vacancies/12345-title/
на просто /jobs/12345-title/. RSS набагато стабільніший, бо не залежить
від верстки сторінки.

Фільтрація за запитами відбувається на нашому боці (як і в інших
RSS-скраперах), бо RSS не підтримує довільний текстовий пошук — лише
параметр primary_keyword з обмеженим списком категорій Djinni.
"""
import feedparser
from .base import keyword_matches

FEED_URL = "https://djinni.co/jobs/rss/"


def search(keywords: list) -> list:
    feed = feedparser.parse(FEED_URL)
    results = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "") or ""
        full_text = f"{title} {summary}"

        if not keyword_matches(full_text, keywords):
            continue

        results.append({
            "title": title,
            "company": "",
            "url": entry.get("link", ""),
            "source": "Djinni",
            "text": full_text,
            "date": entry.get("published", ""),
        })
    return results
