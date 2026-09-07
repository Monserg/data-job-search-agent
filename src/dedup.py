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
"""
import json
import os
import hashlib

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seen_jobs.json")

# Скільки останніх ID тримати у файлі, щоб він не ріс нескінченно.
MAX_STORED_IDS = 5000


def _job_id(title: str, company: str) -> str:
    """
    Нормалізує назву компанії та посади (нижній регістр, обрізає пробіли)
    і хешує їх разом. Порожня компанія ("" — трапляється на джерелах, що
    не віддають компанію, напр. linkedin_alerts) не ламає логіку: тоді
    дедублікація фактично йде лише за назвою посади.
    """
    normalized = f"{(company or '').strip().lower()}|{(title or '').strip().lower()}"
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
    """Повертає (нові_вакансії, оновлений_set_seen_ids)."""
    new_jobs = []
    updated = set(seen_ids)
    for job in jobs:
        jid = _job_id(job.get("title", ""), job.get("company", ""))
        if jid not in seen_ids:
            new_jobs.append(job)
            updated.add(jid)
    return new_jobs, updated
