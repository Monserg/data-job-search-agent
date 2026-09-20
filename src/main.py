"""
Точка входу. Викликається щоранку GitHub Actions'ом (9:00-10:00 Kyiv).

Порядок дій:
1. Завантажити конфіг.
2. Опитати всі увімкнені джерела вакансій за AI-запитами, відкинувши
   вакансії, що підпадають під exclude_keywords (сеньйорність тощо).
3. Прибрати дублікати (порівняно з попередніми запусками).
4. Дописати рядки у Google Sheets.
5. Надіслати картки в Telegram.
6. Зберегти оновлений список "вже бачених" вакансій.

ПРИМІТКА: розрахунок Match Score / рекомендація резюме / Gemini-аналіз
навмисно прибрані (2026-09-20) — визнано, що вони давали недостовірну
картину. Звіт тепер — сирий список вакансій без жодної оцінки
відповідності.
"""
import datetime
import logging
import sys

from config_loader import load_config
from dedup import load_seen, save_seen, filter_new_jobs
from scrapers import REGISTRY
from scrapers.base import safe_call, is_excluded
import sheets_client
import telegram_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("job_agent.main")


def collect_jobs(config: dict) -> list:
    queries = config["search"]["queries"]
    exclude_keywords = config.get("filters", {}).get("exclude_keywords", [])
    all_jobs = []

    for name, module in REGISTRY.items():
        source_cfg = config["sources"].get(name, {})
        if not source_cfg.get("enabled"):
            continue

        logger.info("Опитую джерело: %s", name)
        if name == "linkedin_alerts":
            jobs = safe_call(module.search, queries, source_cfg.get("feed_urls", []))
        else:
            jobs = safe_call(module.search, queries)

        before = len(jobs)
        jobs = [j for j in jobs if not is_excluded(j["text"], exclude_keywords)]
        excluded_count = before - len(jobs)

        logger.info("  -> знайдено %d вакансій%s", len(jobs),
                     f" (ще {excluded_count} відкинуто фільтром exclude_keywords)" if excluded_count else "")
        all_jobs.extend(jobs)

    return all_jobs


def finalize_jobs(jobs: list) -> list:
    """Додає дату і сортує за джерелом+назвою (без жодного скорингу)."""
    today = datetime.date.today().isoformat()
    for job in jobs:
        job["date_added"] = today
    jobs.sort(key=lambda j: (j["source"], j["title"]))
    return jobs


def jobs_to_sheet_rows(jobs: list) -> list:
    """Порядок колонок відповідає реальній структурі трекера:
    A Дата додавання, B Посада/Вакансія, C Компанія, D Джерело,
    E Посилання (URL). Колонки F-J (CANVA/EN/На адаптацію/Виконано/
    Feedback) заповнюються вручну і цим кодом не чіпаються."""
    rows = []
    for job in jobs:
        rows.append([
            job["date_added"],
            job["title"],
            job.get("company", "") or "—",
            job["source"],
            job["url"],
        ])
    return rows


def main() -> int:
    config = load_config()

    raw_jobs = collect_jobs(config)
    logger.info("Всього знайдено %d вакансій (з усіх джерел, до дедублікації)", len(raw_jobs))

    seen_ids = load_seen()
    new_jobs, updated_seen = filter_new_jobs(raw_jobs, seen_ids)
    logger.info("З них нових (раніше не звітованих): %d", len(new_jobs))

    final_jobs = finalize_jobs(new_jobs)

    rows = jobs_to_sheet_rows(final_jobs)
    try:
        sheets_client.append_rows(
            config["google_sheets"]["spreadsheet_id"],
            config["google_sheets"]["worksheet_name"],
            rows,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Не вдалось записати у Google Sheets: %s", exc)

    try:
        telegram_client.send_job_cards(final_jobs)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не вдалось надіслати Telegram-повідомлення: %s", exc)

    save_seen(updated_seen)
    logger.info("Готово.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
