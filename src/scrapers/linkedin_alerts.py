"""
LinkedIn не має безкоштовного публічного API/RSS для вакансій, а пряме
скрапінг-парсення сторінок LinkedIn порушує їхні умови використання і
швидко призводить до блокування IP.

Легальна безкоштовна альтернатива: Google Alerts.
1. Зайди на https://www.google.com/alerts
2. Створи алерт на запит: site:linkedin.com/jobs "data analyst" remote
   (по одному алерту на кожен напрямок/ключове слово)
3. У налаштуваннях алерту постав "Доставляти через: RSS-канал"
4. Скопіюй посилання на RSS і встав у config.yaml → sources.linkedin_alerts.feed_urls
"""
import feedparser
from .base import keyword_matches


def search(keywords: list, feed_urls: list = None) -> list:
    feed_urls = feed_urls or []
    if not feed_urls:
        return []

    results = []
    for feed_url in feed_urls:
        feed = feedparser.parse(feed_url)
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
                "source": "LinkedIn (Google Alerts)",
                "text": full_text,
                "date": entry.get("published", ""),
            })
    return results
