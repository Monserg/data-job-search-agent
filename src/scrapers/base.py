"""
Спільний контракт для всіх скраперів.

Кожен скрапер — це функція search(queries: list[str], params: dict) -> list[dict],
де кожен dict має поля:
    title    : str  — назва вакансії
    company  : str  — компанія (або "" якщо невідома)
    url      : str  — посилання на вакансію
    source   : str  — назва джерела (напр. "Djinni")
    text     : str  — заголовок + опис (для фільтрів за описом)
    date     : str  — дата публікації, якщо є (інакше "")

`params` — секція `profiles.<name>.sources.<source>` з config.yaml: параметри
фільтрації на боці джерела (категорія Djinni/DOU, рівень досвіду тощо).
Скрапер, який їх не підтримує, просто ігнорує аргумент.

Скрапери НЕ повинні кидати виняток назовні при мережевій помилці —
краще повернути [] і залогувати попередження, щоб один "впалий" сайт
не зупиняв весь щоденний прогін.

Джерела, що не залежать від профілю (email-сповіщення: вакансії вже
відфільтровані на боці сайту, а прочитаний лист двічі не віддається),
позначаються `PROFILE_AGNOSTIC = True` — main.py опитує їх ОДИН раз на
прогін і роздає результат усім профілям.
"""
import logging
import re
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("job_agent.scrapers")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

DEFAULT_TIMEOUT = 20

_session = None


def get_session() -> requests.Session:
    """Спільна HTTP-сесія з повторами при 5xx/429 і мережевих збоях."""
    global _session
    if _session is None:
        retry = Retry(
            total=2,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        s = requests.Session()
        s.headers.update(DEFAULT_HEADERS)
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        _session = s
    return _session


def fetch_feed(url: str, timeout: int = DEFAULT_TIMEOUT):
    """
    Завантажує RSS/Atom-фід через requests (таймаут + User-Agent) і лише
    потім віддає його feedparser. Прямий feedparser.parse(url) не має
    таймауту: один завислий фід тримав би весь прогін до ліміту
    GitHub Actions.
    """
    import feedparser

    try:
        resp = get_session().get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_feed: не вдалось завантажити %s (%s)", url, exc)
        return None
    return feedparser.parse(resp.content)


def safe_call(fn, *args, **kwargs):
    """Обгортка: ловить будь-яку помилку скрапера й повертає []."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — навмисно широкий catch
        logger.warning("Scraper %s failed: %s", getattr(fn, "__module__", fn), exc)
        return []


def keyword_matches(text: str, queries: list) -> bool:
    """
    Вакансія проходить, якщо ХОЧА Б ОДИН query відповідає тексту.

    - Для запитів з 1-2 слів вимагається ТОЧНА ФРАЗА (сусідні слова,
      з межами слова, допускається дефіс/слеш/пробіл між ними).
    - Для довших запитів (3+ слова, напр. "Junior LLM Engineer")
      достатньо, щоб усі слова були присутні в тексті в будь-якому
      порядку (з межами слова).
    """
    text_low = (text or "").lower()
    for query in queries or []:
        words = query.lower().split()
        if not words:
            continue
        if len(words) <= 2:
            pattern = r"\b" + r"[\s/-]+".join(re.escape(w) for w in words) + r"\b"
            if re.search(pattern, text_low):
                return True
        else:
            if all(re.search(r"\b" + re.escape(w) + r"\b", text_low) for w in words):
                return True
    return False


@lru_cache(maxsize=64)
def _compile_exclusions(keywords: tuple):
    """
    Кожне стоп-слово/фраза -> regex з межами слова З ОБОХ БОКІВ.
    Lookaround (?<!\\w)/(?!\\w) замість \\b, бо \\b не працює для фраз,
    що починаються чи закінчуються не-літерою ("2+ years", "Sr.").
    Так "Head of" більше не збігається з "ahead of", "Lead" — з
    "leadership", "Architect" — з "architecture".
    """
    compiled = []
    for kw in keywords:
        kw_low = kw.strip().lower()
        if not kw_low:
            continue
        pattern = r"(?<!\w)" + re.escape(kw_low).replace(r"\ ", r"\s+") + r"(?!\w)"
        compiled.append((kw, re.compile(pattern, re.IGNORECASE)))
    return tuple(compiled)


def find_excluded(text: str, exclude_keywords: list):
    """Повертає перше стоп-слово, знайдене в тексті, або None."""
    if not text or not exclude_keywords:
        return None
    for kw, rx in _compile_exclusions(tuple(exclude_keywords)):
        if rx.search(text):
            return kw
    return None


def is_excluded(text: str, exclude_keywords: list) -> bool:
    """True, якщо в тексті є хоча б одна заборонена фраза."""
    return find_excluded(text, exclude_keywords) is not None


@lru_cache(maxsize=32)
def _compile_title_regex(pattern: str):
    # У config.yaml довгі regex записані багаторядковим блоком (|-):
    # переноси рядків і відступи навколо них — не частина патерну.
    pattern = re.sub(r"\s*\n\s*", "", pattern)
    return re.compile(pattern, re.IGNORECASE)


def title_matches(title: str, pattern: str) -> bool:
    """True, якщо regex профілю (title_regex / title_reject_regex) збігається з назвою."""
    if not pattern:
        return False
    return bool(_compile_title_regex(pattern).search(title or ""))


def canonical_url(url: str) -> str:
    """
    Прибирає query-рядок та фрагмент (трекінг-параметри utm_*, trk, ref
    тощо) і кінцевий слеш — щоб одна й та сама вакансія з різних листів/
    сторінок давала однаковий ключ дедублікації.
    """
    if not url:
        return ""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def slugify(keyword: str) -> str:
    return keyword.strip().lower().replace(" ", "-")


def humanize_slug(slug: str) -> str:
    """'lemberg-solutions' -> 'Lemberg Solutions'."""
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def html_link_scrape(url: str, link_pattern, base_url: str, source_name: str,
                     timeout: int = DEFAULT_TIMEOUT, company_pattern=None) -> list:
    """
    Універсальний HTML-скрапер "за посиланнями": шукає всі <a href>, що
    підпадають під regex-патерн вакансії на конкретному сайті. Якщо сайт
    кодує компанію в URL (як DOU: /companies/<slug>/vacancies/<id>),
    `company_pattern` — regex з однією групою для slug'а компанії.
    """
    from bs4 import BeautifulSoup

    try:
        resp = get_session().get(url, timeout=timeout)
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
            "text": title,
            "date": "",
        })
    return results


def fetch_page_text(url: str, timeout: int = 15, content_selector: str = None) -> str:
    """
    Довантажує сторінку вакансії й повертає її текст. Якщо передано
    `content_selector` (CSS) і елемент знайдено — береться лише ТІЛО
    вакансії: інакше в текст потрапляють навігація, футер і блок
    "інші вакансії компанії", де слово "Senior" у сусідній вакансії
    хибно виключало б junior-позицію. Без селектора (або якщо його не
    знайдено) — видимий текст усієї сторінки плюс текст/href посилань.

    Повертає порожній рядок при будь-якій помилці — виклик не повинен
    ламати весь скрапер.
    """
    from bs4 import BeautifulSoup

    try:
        resp = get_session().get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_page_text: не вдалось завантажити %s (%s)", url, exc)
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    if content_selector:
        node = soup.select_one(content_selector)
        if node is not None:
            return node.get_text(separator=" ", strip=True)
        logger.info("fetch_page_text: селектор %r не знайдено на %s, беру всю сторінку",
                    content_selector, url)

    visible_text = soup.get_text(separator=" ", strip=True)
    link_hints = " ".join(
        f"{a.get_text(strip=True)} {a.get('href', '')}"
        for a in soup.find_all("a", href=True)
    )
    return f"{visible_text} {link_hints}"


def fetch_page_title_meta(url: str, timeout: int = 15) -> str:
    """og:title сторінки (або <title>), або "" при помилці."""
    from bs4 import BeautifulSoup

    try:
        resp = get_session().get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_page_title_meta: не вдалось завантажити %s (%s)", url, exc)
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""
