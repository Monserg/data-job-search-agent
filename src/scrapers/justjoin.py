"""
Just Join IT (justjoin.it) — польський IT-джоббоард, багато remote-вакансій
і позначка "Open to hire Ukrainians". Фронтенд (Next.js) ходить до
публічного JSON-API без ключа ЧЕРЕЗ ТОЙ САМИЙ ДОМЕН:

GET https://justjoin.it/api/candidate-api/offers
    ?categories=ai&experienceLevels=junior
    &sortBy=publishedAt&orderBy=descending&from=0&itemsCount=100
GET https://justjoin.it/api/candidate-api/offers/<slug>
    — деталі вакансії; поле body — опис (HTML).

Окремий хост api.justjoin.it (старий v2/user-panel) для не-браузерних
клієнтів віддає 503 — не використовувати.

Перевірено 2026-10-01 (офіційної документації немає):
- categories та experienceLevels приймають лише ОДНЕ значення за запит
  (список через кому або повторений параметр → 0 результатів), тому на
  кожну пару (категорія × рівень) робиться окремий запит, результати
  зливаються за slug.
- Рівні: junior, mid, senior, c_level. Категорії: ai, data, python,
  mobile, javascript, java, devops, testing, ... (повний список:
  /api/candidate-api/offers/categories/count).
- Фільтр за типом роботи (remote/hybrid/office) на боці API НЕ працює
  (будь-який параметр ігнорується) → фільтруємо клієнтськи за полем
  workplaceType. Так само isOpenToHireUkrainians.
- keywords=... — повнотекстовий пошук по назві, скілах І ОПИСУ, тому дуже
  широкий ("LLM" дає DevOps- і SRE-вакансії). Використовується лише коли
  категорій не задано; далі ще раз фільтрується keyword_matches за
  назвою + скілами.
- Пагінація: from/itemsCount (≤100), meta.totalItems; список
  відсортовано за датою публікації (новіші першими), тож за max_age_days
  можна зупинитись раніше.

Фільтрація через параметри профілю
(config.yaml -> profiles.<name>.sources.justjoin):
    categories        : список категорій JJIT; один запит на категорію.
                        Без них — пошук за queries профілю (keywords).
    experience_levels : список рівнів ("junior", "mid", "senior",
                        "c_level"); один запит на рівень. Без нього — всі.
    workplace_types   : клієнтський фільтр ["remote", "hybrid", "office"];
                        без нього — всі типи.
    max_age_days      : брати лише вакансії, опубліковані за останні N
                        днів (0 / відсутнє — без обмеження). Для
                        щоденного прогону старіші вже були показані або
                        відкинуті — економить запити за описами.
    with_description  : true — довантажувати опис кожної вакансії (один
                        запит на вакансію, ~0.3 с) — потрібно профілям з
                        exclude_text (роки досвіду, рівень англійської).
    max_details       : ліміт довантажень описів за прогін (80).
    ukrainians_only   : true — лише з позначкою "Open to hire Ukrainians".
    max_pages         : сторінок по 100 на один запит (3).
"""
import datetime
import time

from .base import get_session, keyword_matches, logger, DEFAULT_TIMEOUT

API_URL = "https://justjoin.it/api/candidate-api/offers"
JOB_URL = "https://justjoin.it/job-offer/{slug}"
SOURCE_NAME = "Just Join IT"
PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 3
DEFAULT_MAX_DETAILS = 80
DETAIL_FETCH_DELAY_SECONDS = 0.2
_HEADERS = {"Accept": "application/json"}


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


# ----------------------------------------------------------------------
# Чисті функції (покриті тестами без мережі)
# ----------------------------------------------------------------------

def request_plans(queries: list, params: dict) -> list:
    """
    Список наборів query-параметрів — по одному запиту на кожну пару
    (категорія × рівень). Без категорій — по запиту на кожен текстовий
    query профілю (keywords) × рівень.
    """
    categories = _as_list(params.get("categories"))
    levels = _as_list(params.get("experience_levels")) or [None]
    base = {"sortBy": "publishedAt", "orderBy": "descending"}

    plans = []
    firsts = categories if categories else (list(queries or []) or [None])
    for first in firsts:
        for level in levels:
            plan = dict(base)
            if categories:
                plan["categories"] = first
            elif first:
                plan["keywords"] = first
            if level:
                plan["experienceLevels"] = level
            plans.append(plan)
    return plans


def published_date(item: dict):
    """date з publishedAt ("2026-09-30T14:00:11.38493Z") або None."""
    raw = str(item.get("publishedAt") or item.get("lastPublishedAt") or "")[:10]
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


def age_cutoff(max_age_days, today: datetime.date = None):
    """Дата, раніше за яку вакансії відкидаються, або None (без обмеження)."""
    try:
        days = int(max_age_days or 0)
    except (TypeError, ValueError):
        days = 0
    if days <= 0:
        return None
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    return today - datetime.timedelta(days=days)


def is_too_old(item: dict, cutoff) -> bool:
    if cutoff is None:
        return False
    published = published_date(item)
    return published is not None and published < cutoff


def client_filter(items: list, params: dict, cutoff=None) -> list:
    """
    Клієнтські фільтри, яких API не підтримує: тип роботи, позначка
    "Open to hire Ukrainians", вік вакансії. Дублікати прибираються:
    - за guid (slug — коли guid немає): та сама вакансія з кількох
      запитів (категорії ai/data/python перетинаються) або з кількома
      містами в locations[];
    - за (компанія, назва): JJIT публікує одну й ту саму вакансію окремим
      оголошенням на кожне місто (EPAM "Python Trainee" — 4 guid). У
      dedup.py вони все одно злились би в один ID, але так не
      витрачаються довантаження описів. Лишається найновіше.
    """
    workplace = {str(w).lower() for w in _as_list(params.get("workplace_types"))}
    ukrainians_only = bool(params.get("ukrainians_only", False))

    seen, seen_titles, kept = set(), set(), []
    for item in items:
        slug = item.get("slug") or ""
        key = item.get("guid") or slug
        title_key = ((item.get("companyName") or "").strip().lower(),
                     (item.get("title") or "").strip().lower())
        if not slug or key in seen or (all(title_key) and title_key in seen_titles):
            continue
        if workplace and str(item.get("workplaceType") or "").lower() not in workplace:
            continue
        if ukrainians_only and not item.get("isOpenToHireUkrainians"):
            continue
        if is_too_old(item, cutoff):
            continue
        seen.add(key)
        seen_titles.add(title_key)
        kept.append(item)
    return kept


def strip_html(html: str) -> str:
    """Текст опису без тегів (body у деталях — HTML редактора Quill)."""
    if not html:
        return ""
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def item_to_job(item: dict, description: str = "") -> dict:
    title = (item.get("title") or "").strip()
    company = (item.get("companyName") or "").strip()
    skills = [s.get("name", "") for s in _as_list(item.get("requiredSkills")) if isinstance(s, dict)]
    skills += [s.get("name", "") for s in _as_list(item.get("niceToHaveSkills")) if isinstance(s, dict)]
    text = " ".join(part for part in (title, company, ", ".join(s for s in skills if s), description) if part)
    published = published_date(item)
    return {
        "title": title,
        "company": company,
        "url": JOB_URL.format(slug=item.get("slug", "")),
        "source": SOURCE_NAME,
        "text": text,
        "date": published.isoformat() if published else "",
    }


def _skills_text(item: dict) -> str:
    skills = [s.get("name", "") for s in _as_list(item.get("requiredSkills")) if isinstance(s, dict)]
    return f"{item.get('title') or ''} {', '.join(skills)}"


# ----------------------------------------------------------------------
# Мережа
# ----------------------------------------------------------------------

def _fetch_list(plan: dict, max_pages: int, cutoff=None) -> list:
    items = []
    for page in range(max_pages):
        query = dict(plan)
        query["from"] = page * PAGE_SIZE
        query["itemsCount"] = PAGE_SIZE
        resp = get_session().get(API_URL, params=query, headers=_HEADERS, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("data") if isinstance(data, dict) else None
        batch = batch or []
        items.extend(batch)

        total = (data.get("meta") or {}).get("totalItems") if isinstance(data, dict) else None
        if len(batch) < PAGE_SIZE or (isinstance(total, int) and len(items) >= total):
            break
        # Список відсортовано за датою: якщо вже дійшли до старих — далі
        # лише старіші.
        if cutoff is not None and batch and is_too_old(batch[-1], cutoff):
            break
    return items


def fetch_description(slug: str) -> str:
    """Опис вакансії (текст без HTML) або "" при помилці."""
    try:
        resp = get_session().get(API_URL + "/" + slug, headers=_HEADERS, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Just Join IT: не вдалось довантажити опис %s (%s)", slug, exc)
        return ""
    return strip_html(data.get("body") or "") if isinstance(data, dict) else ""


def search(queries: list, params: dict = None) -> list:
    params = params or {}
    categories = _as_list(params.get("categories"))
    max_pages = int(params.get("max_pages") or DEFAULT_MAX_PAGES)
    cutoff = age_cutoff(params.get("max_age_days"))

    raw = []
    plans = request_plans(queries, params)
    for plan in plans:
        try:
            raw.extend(_fetch_list(plan, max_pages, cutoff))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Just Join IT: не вдалось отримати список (%s): %s", plan, exc)

    items = client_filter(raw, params, cutoff)
    if not categories:
        # keywords= на боці API шукає і в описі — звужуємо до назви + скілів.
        items = [it for it in items if keyword_matches(_skills_text(it), queries)]

    with_description = bool(params.get("with_description", False))
    max_details = int(params.get("max_details") or DEFAULT_MAX_DETAILS)
    if with_description and len(items) > max_details:
        logger.warning("Just Join IT: %d вакансій, описи довантажу лише для перших %d "
                       "(max_details) — зменш max_age_days або категорії.",
                       len(items), max_details)

    results = []
    for idx, item in enumerate(items):
        description = ""
        if with_description and idx < max_details:
            description = fetch_description(item.get("slug", ""))
            time.sleep(DETAIL_FETCH_DELAY_SECONDS)
        results.append(item_to_job(item, description))

    logger.info("Just Join IT: %d з %d вакансій (%d запитів; categories=%s, levels=%s, "
                "workplace=%s, max_age_days=%s, описи=%s)",
                len(results), len(raw), len(plans), categories,
                _as_list(params.get("experience_levels")), _as_list(params.get("workplace_types")),
                params.get("max_age_days") or 0, "так" if with_description else "ні")
    return results
