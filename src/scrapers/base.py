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


def humanize_slug(slug: str) -> str:
    """'lemberg-solutions' -> 'Lemberg Solutions'."""
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def html_link_scrape(url: str, link_pattern, base_url: str, source_name: str,
                      keyword: str, timeout: int = 20, company_pattern=None) -> list:
    """
    Універсальний HTML-скрапер "за посиланнями": замість того, щоб
    покладатись на CSS-класи (які сайти часто змінюють і які я не можу
    перевірити наживо з пісочниці), він шукає всі <a href> що підпадають
    під regex-патерн вакансії на конкретному сайті.

    Це простіше й довговічніше, і НЕ витягує компанію окремим CSS-
    селектором — але якщо сайт кодує назву компанії прямо в URL вакансії
    (як DOU: /companies/<slug>/vacancies/<id>), можна передати
    `company_pattern` — regex з однією групою, яка й буде slug'ом
    компанії. Він буде "олюднений" (дефіси -> пробіли, Capitalize).
    Якщо `company_pattern` не передано або не збігся — company = "".
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

        company = ""
        if company_pattern:
            m = re.search(company_pattern, href)
            if m:
                company = humanize_slug(m.group(1))

        results.append({
            "title": title,
            "company": company,
            "url": full_url,
            "source": source_name,
            "text": f"{title} {keyword}",
            "date": "",
        })
    return results


def fetch_page_text(url: str, timeout: int = 15) -> str:
    """
    Довантажує сторінку вакансії й повертає її текстовий вміст — видимий
    текст сторінки (get_text) ПЛЮС текст+href усіх посилань. Друге
    важливо: деякі сигнали (наприклад, категорійні бейджі на кшталт
    "deftech" на DOU) — це посилання, і хоча їхній анкор-текст зазвичай
    видимий, надійніше ловити і href, бо розмітка сайтів час від часу
    змінюється, а href-шлях таких бейджів зазвичай стабільніший за CSS.

    Призначення: скрапери за замовчуванням (html_link_scrape) беруть у
    `text` лише заголовок посилання зі сторінки СПИСКУ вакансій — сам
    опис вакансії (де і можуть зустрічатись стоп-слова на кшталт
    "deftech", вимоги до досвіду тощо) на сторінці списку відсутній.
    Ця функція дозволяє довантажити саме сторінку ОКРЕМОЇ вакансії, щоб
    фільтри (exclude_keywords, tier23_exclude_keywords,
    requires_experience) бачили реальний вміст, а не тільки заголовок.

    Повертає порожній рядок при БУДЬ-ЯКІЙ помилці (мережа, 404, таймаут
    тощо) — виклик НЕ повинен ламати весь скрапер; той, хто викликає цю
    функцію, просто лишає коротший `text`, як і раніше.
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_page_text: не вдалось завантажити %s (%s)", url, exc)
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    visible_text = soup.get_text(separator=" ", strip=True)
    link_hints = " ".join(
        f"{a.get_text(strip=True)} {a.get('href', '')}"
        for a in soup.find_all("a", href=True)
    )
    return f"{visible_text} {link_hints}"
