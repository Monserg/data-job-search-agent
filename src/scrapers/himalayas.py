"""
Himalayas — офіційний публічний RSS (Atom/XML): https://himalayas.app/jobs/rss
Показує 100 найновіших вакансій, без пагінації, оновлюється раз на добу.
Офіційна документація: https://himalayas.app/docs/remote-jobs-rss
"""
from .base import fetch_feed, keyword_matches

FEED_URL = "https://himalayas.app/jobs/rss"


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

        # Himalayas додає свій namespace himalayasJobs:companyName —
        # feedparser зазвичай мапить це на "himalayasjobs_companyname".
        company = entry.get("himalayasjobs_companyname", "") or ""

        results.append({
            "title": title,
            "company": company,
            "url": entry.get("link", ""),
            "source": "Himalayas",
            "text": full_text,
            "date": entry.get("published", ""),
        })
    return results
