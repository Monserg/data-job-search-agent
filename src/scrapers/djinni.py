"""
Djinni.co — офіційний RSS-фід: https://djinni.co/jobs/rss/

Фільтрація НА БОЦІ ДЖЕРЕЛА через параметри профілю
(config.yaml -> profiles.<name>.sources.djinni):
    primary_keyword : категорія Djinni ("ML AI", "iOS", "Python", ...) —
                      рядок або список; один запит на кожну категорію.
    exp_level       : рівень досвіду ("no_exp", "1y", "2y", "3y", "5y") —
                      рядок або список. Перевірено 2026-09-30: Djinni
                      приймає лише ОДНЕ значення за запит (список через
                      кому ігнорує й віддає все), тому на кожне значення
                      робиться окремий запит, результати зливаються за URL.
    fetch_company   : true (за замовчуванням) — довантажувати сторінку
                      вакансії заради назви компанії (RSS її не містить;
                      og:title має вигляд "Посада в Компанія").

Якщо primary_keyword задано, фільтр за текстовими запитами профілю
НЕ застосовується (категорія вже обмежила тематику; далі спрацює
title_regex профілю в main.py). Без primary_keyword — загальний фід,
відфільтрований keyword_matches.
"""
import re
import time

from .base import fetch_feed, fetch_page_title_meta, keyword_matches, logger

FEED_URL = "https://djinni.co/jobs/rss/"
PAGE_FETCH_DELAY_SECONDS = 0.3

_DJINNI_SUFFIX_RE = re.compile(r"\s+[–—-]\s+Djinni\s*$")
_AT_COMPANY_RE = re.compile(r"^(?:в|at)\s+(.+)$", re.IGNORECASE)
_LAST_AT_RE = re.compile(r"\s+(?:в|at)\s+([^–—]+)$", re.IGNORECASE)


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _feed_urls(params: dict) -> list:
    keywords = _as_list(params.get("primary_keyword")) or [None]
    levels = _as_list(params.get("exp_level")) or [None]
    urls = []
    for kw in keywords:
        for lvl in levels:
            query = []
            if kw:
                query.append(("primary_keyword", kw))
            if lvl:
                query.append(("exp_level", lvl))
            if query:
                from urllib.parse import urlencode
                urls.append(f"{FEED_URL}?{urlencode(query)}")
            else:
                urls.append(FEED_URL)
    return urls


def company_from_og_title(og_title: str, feed_title: str = "") -> str:
    """'iOS Engineer Senior (Driver Team) в Uklon – Djinni' -> 'Uklon'."""
    if not og_title:
        return ""
    text = _DJINNI_SUFFIX_RE.sub("", og_title.strip())
    # Надійний шлях: відкинути відому назву посади з фіду й прочитати
    # "в <Компанія>" з решти — так " в " усередині самої посади не заважає.
    feed_title = (feed_title or "").strip()
    if feed_title and text.lower().startswith(feed_title.lower()):
        m = _AT_COMPANY_RE.match(text[len(feed_title):].strip())
        if m:
            return m.group(1).strip()
    m = _LAST_AT_RE.search(text)
    return m.group(1).strip() if m else ""


def search(queries: list, params: dict = None) -> list:
    params = params or {}
    source_filtered = bool(params.get("primary_keyword"))
    fetch_company = params.get("fetch_company", True)

    results = []
    seen_links = set()
    for url in _feed_urls(params):
        feed = fetch_feed(url)
        if feed is None:
            continue
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or link in seen_links:
                continue
            title = entry.get("title", "")
            summary = entry.get("summary", "") or ""
            full_text = f"{title} {summary}"
            if not source_filtered and not keyword_matches(full_text, queries):
                continue
            seen_links.add(link)
            results.append({
                "title": title,
                "company": "",
                "url": link,
                "source": "Djinni",
                "text": full_text,
                "date": entry.get("published", ""),
            })

    if fetch_company:
        for job in results:
            og = fetch_page_title_meta(job["url"])
            job["company"] = company_from_og_title(og, job["title"])
            time.sleep(PAGE_FETCH_DELAY_SECONDS)

    logger.info("Djinni: %d вакансій з %d фід(ів)", len(results), len(_feed_urls(params)))
    return results
