"""
Зберігає ID вже надісланих вакансій у data/seen_jobs.json,
щоб агент не дублював їх у наступних щоденних звітах.

Файл комітиться назад у репозиторій GitHub Actions'ом після кожного
запуску (див. .github/workflows/daily_job_search.yml).

ЯК РАХУЄТЬСЯ ID:
- якщо джерело віддало компанію — від пари (нормалізована компанія,
  посада). Та сама вакансія часто публікується на кількох джоб-бордах
  під різними посиланнями (Djinni + LinkedIn + сайт компанії), і
  дедублікація за URL їх не ловила;
- якщо компанії НЕМАЄ (Work.ua, Robota.ua, JustRemote, іноді Djinni) —
  від канонічного URL (без query/фрагмента). Раніше такі вакансії
  хешувались як "|<посада>", тобто ВСІ "Junior AI Engineer" від різних
  компаній зливались в один ID, і після першої решта губились назавжди.

ПЕРЕХІД ЗІ СТАРОЇ СХЕМИ: для вакансій без компанії додатково
перевіряється старий ID ("|<посада>"), щоб уже показані вакансії не
з'явились у звіті вдруге одразу після оновлення.

ПОРЯДОК: seen_ids зберігаються як СПИСОК у порядку додавання, тож при
обрізанні до MAX_STORED_IDS випадають найстаріші, а не випадкові (set
не має порядку — саме так було раніше).

НОРМАЛІЗАЦІЯ НАЗВИ КОМПАНІЇ: та сама компанія на різних джерелах може
бути записана по-різному ("Lemberg Solutions" / "Lemberg Solutions LLC" /
ТОВ "Lemberg Solutions" / "lemberg-solutions"). normalize_company()
зводить усе це до одного канонічного вигляду перед хешуванням.
"""
import hashlib
import json
import os
import re

from scrapers.base import canonical_url

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seen_jobs.json")

# Скільки останніх ID тримати у файлі, щоб він не ріс нескінченно.
MAX_STORED_IDS = 5000

# Юридичні форми (укр + найпоширеніші англ), які прибираємо з назви
# компанії перед порівнянням. \b-межі слова гарантують, що не зачепимо
# середину слова (наприклад "co" не зріже "Codex").
_LEGAL_FORMS = [
    r"тов", r"тзов", r"пп", r"фоп", r"пат", r"ат",
    r"llc", r"inc", r"incorporated", r"ltd", r"limited",
    r"gmbh", r"llp", r"corp", r"corporation", r"co",
    r"s\.?a\.?", r"s\.?r\.?o\.?",
]
_LEGAL_FORM_RE = re.compile(r"\b(?:" + "|".join(_LEGAL_FORMS) + r")\b", re.IGNORECASE)

_QUOTES_BRACKETS_RE = re.compile(r'["\'«»()]')
_SEPARATORS_RE = re.compile(r"[-_]+")
_PUNCT_RE = re.compile(r"[.,]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_company(company: str) -> str:
    """
    "Lemberg Solutions", "lemberg-solutions", 'ТОВ "Lemberg Solutions"',
    "Lemberg Solutions LLC" -> усі стають "lemberg solutions".
    """
    if not company:
        return ""
    text = company.strip().lower()
    text = _SEPARATORS_RE.sub(" ", text)
    text = _QUOTES_BRACKETS_RE.sub(" ", text)
    text = _LEGAL_FORM_RE.sub(" ", text)
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_title(title: str) -> str:
    return _WHITESPACE_RE.sub(" ", (title or "").strip().lower())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def job_id(title: str, company: str, url: str = "") -> str:
    """(компанія|посада) якщо компанія відома, інакше хеш канонічного URL."""
    company_n = normalize_company(company)
    if company_n:
        return _hash(f"{company_n}|{normalize_title(title)}")
    url_c = canonical_url(url)
    if url_c:
        return _hash(f"url|{url_c}")
    return _hash(f"|{normalize_title(title)}")


def legacy_job_id(title: str, company: str) -> str:
    """Стара схема (до переходу на URL для порожньої компанії)."""
    return _hash(f"{normalize_company(company)}|{normalize_title(title)}")


def load_seen() -> list:
    """Список ID у порядку додавання (найстаріші першими)."""
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    ids = data.get("seen_ids", [])
    # прибираємо дублі, зберігаючи порядок
    return list(dict.fromkeys(ids))


def save_seen(seen_ids: list) -> None:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    ids_list = list(dict.fromkeys(seen_ids))[-MAX_STORED_IDS:]
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({"seen_ids": ids_list}, f, ensure_ascii=False, indent=2)


def filter_new_jobs(jobs: list, seen_ids: list) -> tuple:
    """
    Повертає (нові_вакансії, оновлений_список_seen_ids).

    Перевірка йде проти вже оновленого набору, а не лише проти вихідного
    seen_ids: та сама вакансія може потрапити в `jobs` кілька разів за
    один прогін (кілька запитів, кілька джерел, кілька профілів) — такі
    внутрішньопрогонні дублі теж відсіюються.
    """
    updated = list(seen_ids)
    known = set(updated)
    new_jobs = []
    for job in jobs:
        title = job.get("title", "")
        company = job.get("company", "")
        jid = job_id(title, company, job.get("url", ""))
        if jid in known:
            continue
        if not normalize_company(company) and legacy_job_id(title, company) in known:
            continue
        new_jobs.append(job)
        updated.append(jid)
        known.add(jid)
    return new_jobs, updated
