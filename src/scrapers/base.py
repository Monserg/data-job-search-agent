"""
Спільний контракт для всіх скраперів.

Кожен скрапер — це функція search(keywords: list[str]) -> list[dict],
де кожен dict має поля:
    title    : str  — назва вакансії
    company  : str  — компанія (або "" якщо невідома)
    url      : str  — посилання на вакансію
    source   : str  — назва джерела (напр. "Djinni")
    text     : str  — заголовок + опис (для матчингу з резюме)
    date     : str  — дата публікації, якщо є (інакше "")

Скрапери НЕ повинні кидати виняток назовні при мережевій помилці —
краще повернути [] і залогувати попередження, щоб один "впалий" сайт
не зупиняв весь щоденний прогін.
"""
import logging

logger = logging.getLogger("job_agent.scrapers")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def safe_call(fn, *args, **kwargs):
    """Обгортка: ловить будь-яку помилку скрапера й повертає []."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — навмисно широкий catch
        logger.warning("Scraper %s failed: %s", getattr(fn, "__module__", fn), exc)
        return []


def keyword_matches(text: str, keywords: list) -> bool:
    text_low = text.lower()
    return any(kw.lower() in text_low for kw in keywords)


def slugify(keyword: str) -> str:
    return keyword.strip().lower().replace(" ", "-")


def html_link_scrape(url: str, link_pattern, base_url: str, source_name: str,
                      keyword: str, timeout: int = 20) -> list:
    """
    Універсальний HTML-скрапер "за посиланнями": замість того, щоб
    покладатись на CSS-класи (які сайти часто змінюють і які я не можу
    перевірити наживо з пісочниці), він шукає всі <a href> що підпадають
    під regex-патерн вакансії на конкретному сайті.

    Це простіше й довговічніше, але не витягує компанію/зарплату окремо —
    лише заголовок і посилання. Якщо потрібна деталізація, відредагуй
    відповідний файл у src/scrapers/, додавши точні CSS-селектори після
    того, як подивишся на актуальну розмітку сторінки (F12 → Elements).
    """
    import re
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s: не вдалось завантажити %s (%s)", source_name, url, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    seen_urls = set()
    results = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(link_pattern, href):
            continue
        full_url = href if href.startswith("http") else base_url.rstrip("/") + "/" + href.lstrip("/")
        if full_url in seen_urls:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        seen_urls.add(full_url)
        results.append({
            "title": title,
            "company": "",
            "url": full_url,
            "source": source_name,
            "text": f"{title} {keyword}",
            "date": "",
        })
    return results
