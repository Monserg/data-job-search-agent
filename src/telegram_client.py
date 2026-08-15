"""
Надсилає щоденний дайджест у Telegram через звичайний Bot API
(безкоштовно, без лімітів для такого обсягу повідомлень).

Потрібні змінні середовища:
  TELEGRAM_BOT_TOKEN — токен бота від @BotFather
  TELEGRAM_CHAT_ID   — chat_id, куди слати (свій особистий або груповий)
"""
import os
import requests

API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Telegram обмежує повідомлення ~4096 символами.
MAX_MESSAGE_LEN = 3800


def _chunk_text(text: str, max_len: int = MAX_MESSAGE_LEN) -> list:
    lines = text.split("\n")
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)
    return chunks


def build_digest(new_jobs: list, spreadsheet_url: str = "") -> str:
    if not new_jobs:
        return "📭 Сьогодні нових вакансій за твоїми ключовими словами не знайдено."

    lines = [f"📋 <b>Нові вакансії на сьогодні: {len(new_jobs)}</b>\n"]
    for job in new_jobs:
        lines.append(
            f"• <b>{job['title']}</b> ({job['source']})\n"
            f"  Match: {job['match_score']}% | CV: {job['best_resume']}\n"
            f"  {job['url']}"
        )
    if spreadsheet_url:
        lines.append(f"\n📊 Повна таблиця: {spreadsheet_url}")
    return "\n".join(lines)


def send_digest(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = API_URL.format(token=token)

    for chunk in _chunk_text(text):
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        resp.raise_for_status()
