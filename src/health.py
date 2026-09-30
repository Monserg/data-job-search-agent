"""
Здоров'я джерел: рахує, скільки днів поспіль джерело повертає 0
вакансій ЩЕ ДО фільтрації профілів. Сайти регулярно змінюють розмітку,
і зламане джерело раніше можна було помітити лише в логах Actions.
Тепер після N нульових днів (config.health) у Telegram іде попередження.

Стан зберігається в data/source_health.json і комітиться разом із
seen_jobs.json.
"""
import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "source_health.json")


def load_state() -> dict:
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def update(state: dict, raw_counts: dict, today: str) -> dict:
    """
    raw_counts: {назва_джерела: кількість сирих вакансій за цей прогін}.
    Один прогін на день: якщо джерело вже оновлене сьогодні (повторний
    запуск), лічильник не змінюється.
    """
    for source, count in raw_counts.items():
        entry = state.setdefault(source, {"zero_streak": 0, "last_nonzero": "", "last_run": ""})
        if entry.get("last_run") == today:
            continue
        entry["last_run"] = today
        if count > 0:
            entry["zero_streak"] = 0
            entry["last_nonzero"] = today
        else:
            entry["zero_streak"] = int(entry.get("zero_streak", 0)) + 1
    return state


def warnings(state: dict, thresholds: dict) -> list:
    """
    thresholds: {назва_джерела: поріг днів}. Джерела без порогу (напр.
    заглушка Indeed) не перевіряються.
    """
    out = []
    for source, limit in thresholds.items():
        entry = state.get(source)
        if not entry:
            continue
        streak = int(entry.get("zero_streak", 0))
        if limit and streak >= limit:
            last = entry.get("last_nonzero") or "ніколи"
            out.append(f"Джерело {source} дає 0 вакансій уже {streak} дн. поспіль "
                       f"(останній результат: {last}). Перевір розмітку/налаштування.")
    return out
