"""
Надсилає ОДНЕ окреме повідомлення на КОЖНУ нову вакансію у стилі
"картки" — жирний заголовок, іконки-емодзі для полів, посилання внизу.
Перед картками кожного профілю йде заголовок з назвою профілю й
кількістю; в кінці — попередження про "мовчазні" джерела, якщо є.

Помилка відправки однієї картки НЕ зупиняє решту: картка логується як
невдала, надсилання продовжується.

Потрібні змінні середовища:
  TELEGRAM_BOT_TOKEN — токен бота від @BotFather
  TELEGRAM_CHAT_ID   — chat_id, куди слати (свій особистий або груповий)
"""
import html
import logging
import os
import time

import requests

logger = logging.getLogger("job_agent.telegram")

API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Пауза між повідомленнями, щоб не впертись у Telegram flood control.
SEND_DELAY_SECONDS = 1.2


def _esc(text: str) -> str:
    """Екранує текст для HTML parse_mode Telegram."""
    return html.escape(str(text), quote=False)


def _hashtag(text: str) -> str:
    tag = "".join(ch for ch in (text or "") if ch.isalnum())
    return f"#{tag}" if tag else ""


def build_job_message(job: dict, profile_hashtag: str = "") -> str:
    """Формує одне повідомлення-картку для однієї вакансії."""
    title = _esc(job.get("title", "Без назви"))
    company = _esc(job.get("company") or "—")
    source = _esc(job.get("source", ""))
    url = job.get("url", "")

    lines = [
        f"📌 <b>{title}</b> в {company}",
        "",
        f"🌍 <b>Джерело:</b> {source}",
        "",
    ]
    if url:
        lines.append(f'🔗 <a href="{url}">Переглянути вакансію</a>')

    tags = " ".join(t for t in (_hashtag(profile_hashtag), _hashtag(source)) if t)
    if tags:
        lines.append(f"\n{tags}")
    return "\n".join(lines)


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


def _try_send(url: str, chat_id: str, text: str, what: str) -> bool:
    try:
        _send_single(url, chat_id, text)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram: не вдалось надіслати %s: %s", what, exc)
        return False
    finally:
        time.sleep(SEND_DELAY_SECONDS)


def send_report(profile_results: list, warnings: list = None) -> int:
    """
    profile_results: список пар (profile_cfg: dict, jobs: list) у порядку
    профілів. warnings: рядки попереджень (здоров'я джерел тощо).
    Повертає кількість вакансій, які НЕ вдалось надіслати.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = API_URL.format(token=token)

    total = sum(len(jobs) for _, jobs in profile_results)
    failed = 0

    if total == 0:
        _try_send(url, chat_id,
                  "📭 Сьогодні нових вакансій за жодним профілем не знайдено.",
                  "повідомлення 'нічого нового'")
    else:
        for profile, jobs in profile_results:
            if not jobs:
                continue
            name = _esc(profile.get("name", ""))
            tag = _hashtag(profile.get("hashtag", ""))
            _try_send(url, chat_id, f"📋 <b>{name}: нових вакансій {len(jobs)}</b> {tag}".strip(),
                      f"заголовок профілю {name}")
            for job in jobs:
                if not _try_send(url, chat_id, build_job_message(job, profile.get("hashtag", "")),
                                 f"картку {job.get('url', '')}"):
                    failed += 1

    for warning in warnings or []:
        _try_send(url, chat_id, f"⚠️ {_esc(warning)}", "попередження")

    return failed
