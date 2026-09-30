"""
WeWorkRemotely — офіційний публічний RSS.
Загальний фід (усі категорії): https://weworkremotely.com/remote-jobs.rss
Через params.feed можна вказати фід категорії, напр.
https://weworkremotely.com/categories/remote-programming-jobs.rss
Фільтрація за ключовими словами відбувається на нашому боці.
"""
from .base import fetch_feed, keyword_matches

FEED_URL = "https://weworkremotely.com/remote-jobs.rss"


def search(queries: list, params: dict = None) -> list:
    params = params or {}
    feed = fetch_feed(params.get("feed") or FEED_URL)
    if feed is None:
        return []
    results = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "") or ""
        full_text = f"{title} {summary}"

        if not keyword_matches(full_text, queries):
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
