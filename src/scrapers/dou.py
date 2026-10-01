"""
DOU.ua — лише вакансії, які DOU сам позначає як "віддалено" (параметр
remote): https://jobs.dou.ua/vacancies/?remote&search=<keyword>
Посилання на вакансії: /companies/<company>/vacancies/<id>/

Фільтрація НА БОЦІ ДЖЕРЕЛА через параметри профілю
(config.yaml -> profiles.<name>.sources.dou):
    category : категорія DOU ("iOS/macOS", "Python", "Data Science", ...)
               — рядок або список. Якщо задано — замість пошуку за
               текстовими запитами відкривається сторінка категорії
               (один запит на кожну категорію × exp, а не на кожен
               query). "Full Stack" у випадаючому списку DOU немає,
               але параметр працює (перевірено 2026-10-01).
    exp      : досвід — "0-1", "1-3", "3-5", "5plus" (рядок або список;
               DOU приймає одне значення за запит — на кожне робиться
               окремий запит, результати зливаються за URL).

Для кожної знайденої вакансії довантажується сторінка вакансії, але
в `text` потрапляє лише ТІЛО опису (селектор VACANCY_BODY_SELECTOR),
а не вся сторінка: раніше туди потрапляли навігація та блок "інші
вакансії компанії", і слово "Senior" у сусідній вакансії хибно
виключало junior-позицію. Один URL довантажується один раз за прогін
(кеш page_text_cache).
"""
import time
import urllib.parse

from .base import html_link_scrape, fetch_page_text

BASE_URL = "https://jobs.dou.ua"
LINK_PATTERN = r"/companies/[^/]+/vacancies/\d+"
COMPANY_PATTERN = r"/companies/([^/]+)/vacancies/\d+"
VACANCY_BODY_SELECTOR = "div.vacancy-section, div.b-vacancy, div.l-vacancy"

PAGE_FETCH_DELAY_SECONDS = 0.3


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _list_urls(queries: list, params: dict) -> list:
    categories = _as_list(params.get("category"))
    levels = _as_list(params.get("exp")) or [None]
    urls = []
    if categories:
        for category in categories:
            for lvl in levels:
                q = [("remote", ""), ("category", category)]
                if lvl:
                    q.append(("exp", lvl))
                urls.append(f"{BASE_URL}/vacancies/?{urllib.parse.urlencode(q)}")
        return urls
    for kw in queries or []:
        for lvl in levels:
            q = [("remote", ""), ("search", kw)]
            if lvl:
                q.append(("exp", lvl))
            urls.append(f"{BASE_URL}/vacancies/?{urllib.parse.urlencode(q)}")
    return urls


def search(queries: list, params: dict = None) -> list:
    params = params or {}
    all_results = []
    seen_urls = set()
    page_text_cache = {}

    for url in _list_urls(queries, params):
        results = html_link_scrape(url, LINK_PATTERN, BASE_URL, "DOU.ua",
                                   company_pattern=COMPANY_PATTERN)
        for job in results:
            job_url = job["url"]
            if job_url in seen_urls:
                continue
            seen_urls.add(job_url)
            if job_url not in page_text_cache:
                page_text_cache[job_url] = fetch_page_text(
                    job_url, content_selector=VACANCY_BODY_SELECTOR)
                time.sleep(PAGE_FETCH_DELAY_SECONDS)
            full_text = page_text_cache[job_url]
            if full_text:
                job["text"] = f"{job['text']} {full_text}"
            all_results.append(job)
    return all_results
