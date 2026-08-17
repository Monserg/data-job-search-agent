"""
Точка входу. Викликається щоранку GitHub Actions'ом (9:00-10:00 Kyiv).

Порядок дій:
1. Завантажити конфіг і резюме з Google Drive.
2. Опитати всі увімкнені джерела вакансій за ключовими словами.
3. Прибрати дублікати (порівняно з попередніми запусками).
4. Порахувати Match Score / найкраще резюме для кожної нової вакансії.
5. Дописати рядки у Google Sheets.
6. Надіслати дайджест у Telegram.
7. Зберегти оновлений список "вже бачених" вакансій.
"""
import datetime
import logging
import sys

from config_loader import load_config
from dedup import load_seen, save_seen, filter_new_jobs
from resume_matcher import best_resume_for_job, build_reason
from scrapers import REGISTRY
from scrapers.base import safe_call
import drive_client
import sheets_client
import telegram_client
import gemini_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("job_agent.main")


def collect_jobs(config: dict) -> list:
    keywords = config["keywords"]
    all_jobs = []

    for name, module in REGISTRY.items():
        source_cfg = config["sources"].get(name, {})
        if not source_cfg.get("enabled"):
            continue

        logger.info("Опитую джерело: %s", name)
        if name == "linkedin_alerts":
            jobs = safe_call(module.search, keywords, source_cfg.get("feed_urls", []))
        else:
            jobs = safe_call(module.search, keywords)

        logger.info("  -> знайдено %d вакансій", len(jobs))
        all_jobs.extend(jobs)

    return all_jobs


def enrich_with_matching(jobs: list, resumes: dict, config: dict) -> list:
    min_score = config["matching"]["min_score_to_report"]
    use_gemini = config["matching"].get("use_gemini_enrichment") and gemini_client.is_configured()
    gemini_model = config["matching"].get("gemini_model", "gemini-2.5-flash")

    today = datetime.date.today().isoformat()
    enriched = []
    for job in jobs:
        best_resume, score, overlap = best_resume_for_job(job["text"], resumes)
        if score < min_score:
            continue

        reason = build_reason(overlap)

        # Gemini-збагачення — лише для вакансій, що вже пройшли поріг,
        # щоб не витрачати денний ліміт безкоштовного тарифу даремно.
        if use_gemini and best_resume:
            gemini_result = safe_call(
                gemini_client.analyze_fit,
                job["text"], resumes[best_resume], best_resume, gemini_model,
            )
            if gemini_result and gemini_result.get("reason"):
                score = gemini_result["score"]
                reason = f"{gemini_result['reason']} (Gemini AI)"

        job["match_score"] = score
        job["best_resume"] = best_resume or "—"
        job["reason"] = reason
        job["date_added"] = today
        enriched.append(job)

    enriched.sort(key=lambda j: j["match_score"], reverse=True)
    return enriched


def jobs_to_sheet_rows(jobs: list) -> list:
    rows = []
    for job in jobs:
        rows.append([
            job["date_added"],
            job["title"],
            f"{job.get('company', '') or '—'} / {job['source']}",
            job["url"],
            job["match_score"],
            job["reason"],
            job["best_resume"],
        ])
    return rows


def main() -> int:
    config = load_config()

    logger.info("Завантажую резюме з Google Drive...")
    try:
        resumes = drive_client.load_resumes(config["google_drive"]["resumes_folder_id"])
        logger.info("Завантажено %d резюме", len(resumes))
    except Exception as exc:  # noqa: BLE001
        logger.error("Не вдалось завантажити резюме: %s", exc)
        return 1

    if not resumes:
        logger.error("У папці Drive немає жодного .pdf резюме — зупиняюсь.")
        return 1

    raw_jobs = collect_jobs(config)
    logger.info("Всього знайдено %d вакансій (з усіх джерел, до дедублікації)", len(raw_jobs))

    seen_ids = load_seen()
    new_jobs, updated_seen = filter_new_jobs(raw_jobs, seen_ids)
    logger.info("З них нових (раніше не звітованих): %d", len(new_jobs))

    matched_jobs = enrich_with_matching(new_jobs, resumes, config)
    logger.info("Пройшли поріг Match Score: %d", len(matched_jobs))

    rows = jobs_to_sheet_rows(matched_jobs)
    try:
        sheets_client.append_rows(
            config["google_sheets"]["spreadsheet_id"],
            config["google_sheets"]["worksheet_name"],
            rows,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Не вдалось записати у Google Sheets: %s", exc)
    try:
        telegram_client.send_job_cards(matched_jobs)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не вдалось надіслати Telegram-повідомлення: %s", exc)

    # Зберігаємо ID навіть тих вакансій, що не пройшли поріг матчингу —
    # інакше вони знову й знову з'являтимуться в майбутніх прогонах.
    save_seen(updated_seen)
    logger.info("Готово.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
