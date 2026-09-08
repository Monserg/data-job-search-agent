"""
Зберігає ID вже надісланих вакансій у data/seen_jobs.json,
щоб агент не дублював їх у наступних щоденних звітах.

Файл комітиться назад у репозиторій GitHub Actions'ом після кожного
запуску (див. .github/workflows/daily_job_search.yml).

ID рахується від пари (компанія, посада), а НЕ від URL. Причина зміни:
та сама вакансія часто публікується на кількох джоб-бордах під різними
посиланнями (Djinni + LinkedIn + сайт компанії тощо), і дедублікація
за URL їх не ловила — в звіті з'являлись повтори однієї й тієї ж позиції.
Дедублікація за (компанія, посада) прибирає такі повтори, але має і
зворотний бік: якщо одна компанія реально відкриє дві РІЗНІ вакансії з
однаковою назвою посади, у звіт потрапить лише перша з них.

Побічний ефект при першому запуску після цієї зміни: старі записи в
seen_jobs.json рахувались за хешем URL, тож жодна з них не збіжиться з
новою схемою хешування — вакансії, які раніше вже бачили, один раз
з'являться в звіті знову, а далі дедублікація вже піде за новими ID.

НОРМАЛІЗАЦІЯ НАЗВИ КОМПАНІЇ: та сама компанія на різних джерелах (або
навіть на одному й тому ж) може бути записана по-різному — з юридичною
формою чи без ("Lemberg Solutions" vs "Lemberg Solutions LLC" vs
ТОВ "Lemberg Solutions"), у форматі URL-slug'а з дефісами
("lemberg-solutions" — саме так compania витягується з посилань DOU),
з різним регістром чи зайвими лапками/дужками. Без нормалізації такі
написання хешуються як РІЗНІ компанії, і одна й та сама вакансія
проходить дедублікацію двічі. normalize_company() зводить усе це до
одного канонічного вигляду перед хешуванням.
"""
import json
import os
import re
import hashlib

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seen_jobs.json")

# Скільки останніх ID тримати у файлі, щоб він не ріс нескінченно.
MAX_STORED_IDS = 5000

# Юридичні форми (укр + найпоширеніші англ), які прибираємо з назви
# компанії перед порівнянням — вони не є частиною "ідентичності"
# компанії, а лише формою запису, яка відрізняється від джерела до
# джерела. \b-межі слова гарантують, що не зачепимо середину слова
# (наприклад "co" не зріже "Codex").
_LEGAL_FORMS = [
    r"тов", r"тзов", r"пп", r"фоп", r"пат", r"ат",
    r"llc", r"inc", r"incorporated", r"ltd", r"limited",
    r"gmbh", r"llp", r"corp", r"corporation", r"co",
    r"s\.?a\.?", r"s\.?r\.?o\.?",
]
_LEGAL_FORM_RE = re.compile(r"\b(?:" + "|".join(_LEGAL_FORMS) + r")\b", re.IGNORECASE)

# Лапки/дужки (ТОВ "Назва") та дефіси/підкреслення (slug'и на кшталт
# "lemberg-solutions" з URL) — не несуть сенсу для порівняння компаній.
_QUOTES_BRACKETS_RE = re.compile(r'["\'«»()]')
_SEPARATORS_RE = re.compile(r"[-_]+")
_PUNCT_RE = re.compile(r"[.,]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_company(company: str) -> str:
    """
    Зводить назву компанії до канонічного вигляду для дедублікації:
    нижній регістр, дефіси/підкреслення -> пробіл, прибрані лапки/дужки,
    прибрана юридична форма (ТОВ/ФОП/LLC/Ltd/Inc/GmbH тощо), прибрана
    зайва пунктуація, схлопнуті пробіли.

    Приклади, які після нормалізації дають однаковий результат:
    "Lemberg Solutions", "lemberg-solutions", 'ТОВ "Lemberg Solutions"',
    "Lemberg Solutions LLC" -> всі стають "lemberg solutions".
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


def _job_id(title: str, company: str) -> str:
    """
    Нормалізує назву компанії (normalize_company — прибирає юридичну
    форму, дефіси, лапки, регістр) і посаду (нижній регістр, обрізані
    пробіли), і хешує їх разом. Порожня компанія ("" — трапляється на
    джерелах, що не віддають компанію, напр. linkedin_alerts) не ламає
    логіку: тоді дедублікація фактично йде лише за назвою посади.
    """
    normalized = f"{normalize_company(company)}|{(title or '').strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def load_seen() -> set:
    if not os.path.exists(DATA_PATH):
        return set()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return set()
    return set(data.get("seen_ids", []))


def save_seen(seen_ids: set) -> None:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    ids_list = list(seen_ids)[-MAX_STORED_IDS:]
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({"seen_ids": ids_list}, f, ensure_ascii=False, indent=2)


def filter_new_jobs(jobs: list, seen_ids: set) -> tuple:
    """
    Повертає (нові_вакансії, оновлений_set_seen_ids).

    ВАЖЛИВО: перевірка йде проти `updated`, а не проти вихідного
    `seen_ids`. Один і той самий job може потрапити в `jobs` кілька
    разів за один прогін (наприклад, вакансія збігається одразу з
    кількома ключовими словами, і скрапер сканує сторінку пошуку
    окремо під кожне слово). Якщо звірятись лише з `seen_ids`
    (як було раніше), такі внутрішньопрогонні дублі не відсіювались —
    обидва входження проходили далі й потрапляли у звіт двічі,
    з різним текстом Gemini-аналізу (бо Gemini викликався для кожного
    входження окремо). Звірка з `updated` ловить і ці дублі теж.
    """
    new_jobs = []
    updated = set(seen_ids)
    for job in jobs:
        jid = _job_id(job.get("title", ""), job.get("company", ""))
        if jid not in updated:
            new_jobs.append(job)
            updated.add(jid)
    return new_jobs, updated
