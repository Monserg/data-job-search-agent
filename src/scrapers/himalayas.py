"""
Himalayas — офіційний публічний JSON API (без ключа):
https://himalayas.app/docs/remote-jobs-api

Раніше брали RSS (https://himalayas.app/jobs/rss), але з ~жовтня 2026 він
віддає лише 20 випадкових найновіших вакансій з усіх професій — після
фільтра за запитами залишалось 0, і health-check бив тривогу. Тепер
шукаємо на боці сайту: /jobs/api/search?q=<query>&sort=recent для кожного
запиту профілю. Пошук у Himalayas нечіткий, тому keyword_matches
лишається на нашому боці.
"""
import datetime
import logging

from .base import get_session, keyword_matches, DEFAULT_TIMEOUT

logger = logging.getLogger("job_agent.scrapers")

SEARCH_URL = "https://himalayas.app/jobs/api/search"


def _iso_date(ts) -> str:
    try:
        return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def search(queries: list, params: dict = None) -> list:
    results = []
    seen_urls = set()
    for query in queries or []:
        try:
            resp = get_session().get(
                SEARCH_URL, params={"q": query, "sort": "recent"}, timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            jobs = resp.json().get("jobs") or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Himalayas: запит %r не вдався (%s)", query, exc)
            continue

        for item in jobs:
            url = item.get("applicationLink") or item.get("guid") or ""
            if not url or url in seen_urls:
                continue
            title = item.get("title", "") or ""
            description = item.get("description") or item.get("excerpt") or ""
            full_text = f"{title} {description}"

            if not keyword_matches(full_text, queries):
                continue
            seen_urls.add(url)

            results.append({
                "title": title,
                "company": item.get("companyName", "") or "",
                "url": url,
                "source": "Himalayas",
                "text": full_text,
                "date": _iso_date(item.get("pubDate")),
            })
    return results
