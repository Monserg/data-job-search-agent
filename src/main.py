"""
Точка входу / оркестратор.

Запуск: зовнішній cron-job.org щодня о 9:00 Europe/Kyiv робить POST
workflow_dispatch; резервний внутрішній `schedule:` у workflow спрацьовує
пізніше і виходить без звіту, якщо прогін за сьогодні вже був
(data/last_run_date.txt, див. run_guard у config.yaml). Ручний запуск
через Actions → Run workflow ставить FORCE_RUN=true і захист обходить.

Порядок дій:
1. Завантажити конфіг.
2. Для кожного ПРОФІЛЮ (config.profiles) опитати увімкнені джерела з
   параметрами профілю і застосувати його фільтри: стоп-слова в назві,
   стоп-фрази в описі, тематичний title_regex, title_reject_regex.
   Джерела, що не залежать від профілю (email-сповіщення), опитуються
   один раз, а вакансії з них роздаються профілям за title_regex.
3. Прибрати дублікати проти спільного data/seen_jobs.json (і всередині
   прогону — між запитами, джерелами й профілями).
4. Дописати рядки в аркуш профілю у Google Sheets.
5. Надіслати картки в Telegram (заголовок на профіль + картки) і
   попередження про джерела, що кілька днів дають 0.
6. Зберегти seen_jobs.json, source_health.json, last_run_date.txt.

Звіт навмисно СИРИЙ — без Match Score чи AI-оцінки відповідності
(шар матчингу прибрано 2026-09-20 як недостовірний).
"""
import datetime
import logging
import os
import sys
from collections import defaultdict
from zoneinfo import ZoneInfo

from config_loader import load_config
from dedup import load_seen, save_seen, filter_new_jobs
import health
from scrapers import REGISTRY
from scrapers.base import safe_call, find_excluded, title_matches
import sheets_client
import telegram_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("job_agent.main")

LAST_RUN_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "last_run_date.txt")


# ----------------------------------------------------------------------
# Фільтри профілю
# ----------------------------------------------------------------------

def apply_profile_filters(jobs: list, profile: dict) -> tuple:
    """
    Повертає (вакансії, що пройшли; {причина: кількість відкинутих}).
    Порядок перевірок: стоп-слова в назві -> стоп-фрази в описі ->
    тематичний title_regex -> title_reject_regex.
    """
    exclude_title = profile.get("exclude_title") or []
    exclude_text = profile.get("exclude_text") or []
    title_regex = profile.get("title_regex") or ""
    reject_regex = profile.get("title_reject_regex") or ""

    kept = []
    dropped = defaultdict(int)
    for job in jobs:
        title = job.get("title", "")
        if find_excluded(title, exclude_title):
            dropped["стоп-слово в назві"] += 1
            continue
        if find_excluded(job.get("text", ""), exclude_text):
            dropped["стоп-фраза в описі"] += 1
            continue
        if title_regex and not title_matches(title, title_regex):
            dropped["немає тематичного маркера в назві"] += 1
            continue
        if reject_regex and title_matches(title, reject_regex):
            dropped["суміжний напрямок у назві"] += 1
            continue
        kept.append(job)
    return kept, dict(dropped)


# ----------------------------------------------------------------------
# Збір
# ----------------------------------------------------------------------

def _source_enabled(config: dict, profile: dict, name: str) -> bool:
    if not config.get("sources", {}).get(name, {}).get("enabled"):
        return False
    params = (profile.get("sources") or {}).get(name) or {}
    return params.get("enabled", True)


def collect_for_profile(key: str, profile: dict, config: dict,
                        agnostic_cache: dict, raw_counts: dict) -> list:
    """Опитує джерела для одного профілю й застосовує його фільтри."""
    queries = profile.get("queries") or []
    collected = []

    for name, module in REGISTRY.items():
        if not _source_enabled(config, profile, name):
            continue
        params = dict((profile.get("sources") or {}).get(name) or {})
        params.pop("enabled", None)
        agnostic = getattr(module, "PROFILE_AGNOSTIC", False)

        if agnostic:
            if name not in agnostic_cache:
                logger.info("[%s] Опитую джерело: %s (спільне для всіх профілів)", key, name)
                agnostic_cache[name] = safe_call(module.search, queries, params)
                raw_counts[name] = max(raw_counts.get(name, 0), len(agnostic_cache[name]))
            jobs = [dict(j) for j in agnostic_cache[name]]
        else:
            logger.info("[%s] Опитую джерело: %s", key, name)
            jobs = safe_call(module.search, queries, params)
            raw_counts[name] = raw_counts.get(name, 0) + len(jobs)

        kept, dropped = apply_profile_filters(jobs, profile)
        summary = ", ".join(f"{reason}: {n}" for reason, n in dropped.items())
        logger.info("[%s]   %s -> %d з %d%s", key, name, len(kept), len(jobs),
                    f" (відкинуто — {summary})" if summary else "")
        for job in kept:
            job["profile"] = key
        collected.extend(kept)

    return collected


# ----------------------------------------------------------------------
# Допоміжне
# ----------------------------------------------------------------------

def today_str(config: dict) -> str:
    tz_name = (config.get("run_guard") or {}).get("timezone") or "Europe/Kyiv"
    return datetime.datetime.now(ZoneInfo(tz_name)).date().isoformat()


def already_ran_today(today: str) -> bool:
    if not os.path.exists(LAST_RUN_PATH):
        return False
    with open(LAST_RUN_PATH, "r", encoding="utf-8") as f:
        return f.read().strip() == today


def mark_ran_today(today: str) -> None:
    os.makedirs(os.path.dirname(LAST_RUN_PATH), exist_ok=True)
    with open(LAST_RUN_PATH, "w", encoding="utf-8") as f:
        f.write(today + "\n")


def jobs_to_sheet_rows(jobs: list, date_added: str) -> list:
    """A Дата додавання, B Посада, C Компанія, D Джерело, E Посилання."""
    return [
        [date_added, job["title"], job.get("company", "") or "—", job["source"], job["url"]]
        for job in jobs
    ]


def health_thresholds(config: dict) -> dict:
    cfg = config.get("health") or {}
    default = int(cfg.get("zero_days_warn", 3) or 0)
    email = int(cfg.get("zero_days_warn_email", 7) or 0)
    thresholds = {}
    for name, module in REGISTRY.items():
        if not config.get("sources", {}).get(name, {}).get("enabled"):
            continue
        if getattr(module, "ALWAYS_EMPTY", False):
            continue
        thresholds[name] = email if getattr(module, "PROFILE_AGNOSTIC", False) else default
    return thresholds


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main() -> int:
    config = load_config()
    today = today_str(config)
    force = os.environ.get("FORCE_RUN", "").lower() in ("1", "true", "yes") or "--force" in sys.argv

    if (config.get("run_guard") or {}).get("enabled", True) and not force and already_ran_today(today):
        logger.info("Прогін за %s уже був — виходжу без звіту (FORCE_RUN=true, щоб обійти).", today)
        return 0

    profiles = config.get("profiles") or {}
    if not profiles:
        logger.error("У config.yaml немає жодного профілю (profiles:).")
        return 1

    agnostic_cache, raw_counts = {}, {}
    all_jobs = []
    for key, profile in profiles.items():
        all_jobs.extend(collect_for_profile(key, profile, config, agnostic_cache, raw_counts))
    logger.info("Всього після фільтрів: %d вакансій (до дедублікації)", len(all_jobs))

    seen_ids = load_seen()
    new_jobs, updated_seen = filter_new_jobs(all_jobs, seen_ids)
    logger.info("З них нових (раніше не звітованих): %d", len(new_jobs))

    by_profile = defaultdict(list)
    for job in new_jobs:
        job["date_added"] = today
        by_profile[job["profile"]].append(job)
    for jobs in by_profile.values():
        jobs.sort(key=lambda j: (j["source"], j["title"]))

    spreadsheet_id = config["google_sheets"]["spreadsheet_id"]
    for key, profile in profiles.items():
        jobs = by_profile.get(key, [])
        if not jobs:
            continue
        try:
            sheets_client.append_rows(spreadsheet_id, profile["worksheet"],
                                      jobs_to_sheet_rows(jobs, today))
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] Не вдалось записати у Google Sheets: %s", key, exc)

    state = health.update(health.load_state(), raw_counts, today)
    health.save_state(state)
    warnings = health.warnings(state, health_thresholds(config))
    for w in warnings:
        logger.warning(w)

    try:
        failed = telegram_client.send_report(
            [(profile, by_profile.get(key, [])) for key, profile in profiles.items()],
            warnings,
        )
        if failed:
            logger.error("Telegram: %d карток не надіслано", failed)
    except Exception as exc:  # noqa: BLE001
        logger.error("Не вдалось надіслати Telegram-повідомлення: %s", exc)

    save_seen(updated_seen)
    mark_ran_today(today)
    logger.info("Готово.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
