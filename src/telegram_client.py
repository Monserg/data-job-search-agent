"""
Надсилає ОДНЕ окреме повідомлення на КОЖНУ нову вакансію (замість одного
великого дайджесту), у стилі "картки" — жирний заголовок, іконки-емодзі
для полів, посилання внизу.

Потрібні змінні середовища:
  TELEGRAM_BOT_TOKEN — токен бота від @BotFather
  TELEGRAM_CHAT_ID   — chat_id, куди слати (свій особистий або груповий)
"""
import os
import time
import html
import requests

API_URL = "https://api.telegram.org/bot{token}/sendMessage"

TIER_EMOJI = {
    1: "🥇 Пріоритет 1 — швидкий дохід",
    2: "🥈 Пріоритет 2 — стабільна робота",
    3: "🥉 Пріоритет 3 — стратегічна ціль",
}

# Пауза між повідомленнями, щоб не впертись у Telegram flood control
# (офіційний ліміт — ~30 повідомлень/сек в різні чати, але для одного
# чату безпечніше йти повільніше).
SEND_DELAY_SECONDS = 1.2


def _esc(text: str) -> str:
    """Екранує текст для HTML parse_mode Telegram."""
    return html.escape(str(text), quote=False)


def build_job_message(job: dict) -> str:
    """
    Формує одне повідомлення-картку для однієї вакансії, у стилі:
    жирний заголовок + компанія, іконки для полів, посилання внизу.
    """
    title = _esc(job.get("title", "Без назви"))
    company = _esc(job.get("company") or "—")
    source = _esc(job.get("source", ""))
    score = job.get("match_score", 0)
    resume = _esc(job.get("best_resume", "—"))
    reason = _esc(job.get("reason", ""))
    url = job.get("url", "")
    tier_label = TIER_EMOJI.get(job.get("tier"))

    lines = []
    if tier_label:
        lines.append(f"<b>{tier_label}</b>")
    lines += [
        f"📌 <b>{title}</b> в {company}",
        "",
        f"🌍 <b>Джерело:</b> {source}",
        f"🎯 <b>Match Score:</b> {score}%",
        f"📄 <b>Рекомендоване CV:</b> {resume}",
    ]
    if reason:
        lines.append(f"💬 {reason}")

    lines.append("")
    if url:
        lines.append(f'🔗 <a href="{url}">Переглянути вакансію</a>')

    hashtag_source = "".join(ch for ch in source if ch.isalnum())
    if hashtag_source:
        lines.append(f"\n#{hashtag_source}")

    return "\n".join(lines)


def send_job_cards(jobs: list) -> None:
    """
    Надсилає по одному повідомленню на кожну вакансію зі списку jobs
    (вже відсортованого спершу за ярусом, потім за match_score, як формує main.py).
    Якщо jobs порожній — надсилає одне коротке "нічого не знайдено".
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = API_URL.format(token=token)

    if not jobs:
        _send_single(url, chat_id, "📭 Сьогодні нових вакансій за твоїми ключовими словами не знайдено.")
        return

    tier_counts = {1: 0, 2: 0, 3: 0}
    for job in jobs:
        t = job.get("tier")
        if t in tier_counts:
            tier_counts[t] += 1
    breakdown = (
        f"🥇 Пріоритет 1: {tier_counts[1]}  "
        f"🥈 Пріоритет 2: {tier_counts[2]}  "
        f"🥉 Пріоритет 3: {tier_counts[3]}"
    )

    _send_single(
        url, chat_id,
        f"📋 <b>Нові вакансії на сьогодні: {len(jobs)}</b>\n{breakdown}",
    )
    time.sleep(SEND_DELAY_SECONDS)

    for job in jobs:
        text = build_job_message(job)
        _send_single(url, chat_id, text)
        time.sleep(SEND_DELAY_SECONDS)


def _send_single(url: str, chat_id: str, text: str, retry: int = 1) -> None:
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    if resp.status_code == 429 and retry > 0:
        # Telegram сам підказує, скільки секунд почекати перед повтором.
        retry_after = resp.json().get("parameters", {}).get("retry_after", 3)
        time.sleep(retry_after + 1)
        _send_single(url, chat_id, text, retry=retry - 1)
        return
    resp.raise_for_status()


# Лишаємо старі функції для зворотної сумісності (якщо десь ще викликаються).
def build_digest(new_jobs: list, spreadsheet_url: str = "") -> str:
    if not new_jobs:
        return "📭 Сьогодні нових вакансій за твоїми ключовими словами не знайдено."
    lines = [f"📋 <b>Нові вакансії на сьогодні: {len(new_jobs)}</b>\n"]
    for job in new_jobs:
        lines.append(build_job_message(job))
    if spreadsheet_url:
        lines.append(f"\n📊 Повна таблиця: {spreadsheet_url}")
    return "\n\n".join(lines)


def send_digest(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = API_URL.format(token=token)
    _send_single(url, chat_id, text[:4000])
