"""
Himalayas — офіційний публічний RSS (Atom/XML): https://himalayas.app/jobs/rss
Показує 100 найновіших вакансій, без пагінації, оновлюється раз на добу.
Офіційна документація: https://himalayas.app/docs/remote-jobs-rss
"""
import feedparser
from .base import keyword_matches

FEED_URL = "https://himalayas.app/jobs/rss"


def search(keywords: list) -> list:
    feed = feedparser.parse(FEED_URL)
    results = []
    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "") or ""
        full_text = f"{title} {summary}"

        if not keyword_matches(full_text, keywords):
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
