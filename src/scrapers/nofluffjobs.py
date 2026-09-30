"""
NoFluffJobs має публічний (без ключа) REST-ендпоінт пошуку — той самий,
що робить їхній фронтенд:
POST https://nofluffjobs.com/api/search/posting
     ?pageTo=1&pageSize=20&salaryCurrency=PLN&salaryPeriod=month&region=pl
Без query-параметрів salaryCurrency/salaryPeriod відповідає 400 (саме
так зламався попередній варіант скрапера; перевірено 2026-09-30).

Фільтрація НА БОЦІ ДЖЕРЕЛА через параметри профілю
(config.yaml -> profiles.<name>.sources.nofluffjobs):
    requirement : теги технологій NFJ — список ("iOS", "Swift", "AI",
                  "LLM", "Machine Learning"). Без них — весь список
                  віддалених вакансій, відфільтрований за queries.
    seniority   : список рівнів NFJ ("Trainee", "Junior", "Mid",
                  "Senior", "Expert") — вакансія лишається, якщо хоч
                  один її рівень є в списку. Без нього — не фільтрується.
    city        : список міст, за замовчуванням ["remote"].
    region      : регіон сайту, за замовчуванням "pl" (найбільший;
                  для "ua" ендпоінт віддає 0 з критеріями).

Офіційної документації немає, тому структура відповіді може змінитись —
якщо скрапер почне повертати 0, перевір DevTools → Network на сайті.
"""
from .base import get_session, keyword_matches, logger, DEFAULT_TIMEOUT

SEARCH_URL = "https://nofluffjobs.com/api/search/posting"
JOB_URL = "https://nofluffjobs.com/job/{slug}"


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def search(queries: list, params: dict = None) -> list:
    params = params or {}
    requirement = _as_list(params.get("requirement"))
    seniority = {s.lower() for s in _as_list(params.get("seniority"))}
    city = _as_list(params.get("city")) or ["remote"]
    region = params.get("region") or "pl"

    # Кілька requirement NFJ трактує як "І" (усі теги разом) — а нам треба
    # "АБО", тому на кожен тег робиться окремий запит, результати
    # зливаються за slug'ом.
    postings = []
    for req in (requirement or [None]):
        criteria = {"city": city}
        if req:
            criteria["requirement"] = [req]
        try:
            resp = get_session().post(
                SEARCH_URL,
                params={"pageTo": 1, "pageSize": 100, "salaryCurrency": "PLN",
                        "salaryPeriod": "month", "region": region},
                json={"criteriaSearch": criteria, "page": 1},
                headers={"Content-Type": "application/json"},
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("NoFluffJobs: не вдалось отримати список (%s)", exc)
            continue
        postings.extend(data.get("postings", []) if isinstance(data, dict) else [])

    results = []
    seen = set()
    for item in postings:
        slug = item.get("url") or item.get("id", "")
        if not slug or slug in seen:
            continue
        title = (item.get("title") or "").strip()
        company = item.get("name") if isinstance(item.get("name"), str) else ""
        levels = {str(s).lower() for s in _as_list(item.get("seniority"))}
        if seniority and levels and not (levels & seniority):
            continue
        full_text = f"{title} {company} {item.get('technology') or ''}"
        if not requirement and not keyword_matches(full_text, queries):
            continue
        seen.add(slug)
        results.append({
            "title": title,
            "company": company or "",
            "url": JOB_URL.format(slug=slug),
            "source": "NoFluffJobs",
            "text": full_text,
            "date": str(item.get("posted", "")),
        })
    logger.info("NoFluffJobs: %d з %d вакансій (requirement=%s, seniority=%s)",
                len(results), len(postings), requirement, sorted(seniority))
    return results
