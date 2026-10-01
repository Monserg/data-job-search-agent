"""
Надсилає ОДНЕ окреме повідомлення на КОЖНУ нову вакансію у стилі
"картки" — жирний заголовок, іконки-емодзі для полів, посилання внизу.
Перед картками кожного профілю йде заголовок з назвою профілю й
кількістю; в кінці — попередження про "мовчазні" джерела, якщо є.

Помилка відправки однієї картки НЕ зупиняє решту: картка логується як
невдала, надсилання продовжується.

Якщо картку не вдалось надіслати, вона повертається в main, щоб її ID
НЕ потрапив у seen_jobs.json і вакансія пішла в наступний звіт, а не
загубилась назавжди (саме так зникли 23 вакансії 2026-10-01, коли
chat_id указував на канал, де бот не був адміністратором).

Потрібні змінні середовища:
  TELEGRAM_BOT_TOKEN — токен бота від @BotFather
  TELEGRAM_CHAT_ID   — chat_id, куди слати: особистий (число), група
                       (-123...) або канал (-100123...; бот має бути
                       адміністратором каналу з правом Post messages)
"""
import html
import logging
import os
import time

import requests

logger = logging.getLogger("job_agent.telegram")

API_BASE = "https://api.telegram.org/bot{token}/"
API_URL = API_BASE + "sendMessage"

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
    if not resp.ok:
        # Telegram кладе причину в JSON ("chat not found", "bot is not a
        # member of the channel chat", "need administrator rights" ...).
        # Без неї в логу лише "400 Client Error", з чого нічого не зрозуміло.
        raise RuntimeError(f"HTTP {resp.status_code}: {_description(resp)}")


def _description(resp) -> str:
    try:
        return resp.json().get("description") or resp.text[:200]
    except ValueError:
        return resp.text[:200]


def _try_send(url: str, chat_id: str, text: str, what: str) -> bool:
    try:
        _send_single(url, chat_id, text)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram: не вдалось надіслати %s: %s", what, exc)
        return False
    finally:
        time.sleep(SEND_DELAY_SECONDS)


def send_report(profile_results: list, warnings: list = None) -> tuple:
    """
    profile_results: список пар (profile_cfg: dict, jobs: list) у порядку
    профілів. warnings: рядки попереджень (здоров'я джерел тощо).
    Повертає (failed_jobs, delivered): вакансії, картки яких НЕ дійшли,
    і кількість успішно надісланих повідомлень (будь-яких, включно із
    заголовками). delivered == 0 означає, що з чатом щось не так.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"].strip()
    url = API_URL.format(token=token)

    total = sum(len(jobs) for _, jobs in profile_results)
    failed_jobs = []
    delivered = 0

    if total == 0:
        delivered += _try_send(url, chat_id,
                               "📭 Сьогодні нових вакансій за жодним профілем не знайдено.",
                               "повідомлення 'нічого нового'")
    else:
        for profile, jobs in profile_results:
            if not jobs:
                continue
            name = _esc(profile.get("name", ""))
            tag = _hashtag(profile.get("hashtag", ""))
            delivered += _try_send(url, chat_id,
                                   f"📋 <b>{name}: нових вакансій {len(jobs)}</b> {tag}".strip(),
                                   f"заголовок профілю {name}")
            for job in jobs:
                if _try_send(url, chat_id, build_job_message(job, profile.get("hashtag", "")),
                             f"картку {job.get('url', '')}"):
                    delivered += 1
                else:
                    failed_jobs.append(job)

    for warning in warnings or []:
        delivered += _try_send(url, chat_id, f"⚠️ {_esc(warning)}", "попередження")

    return failed_jobs, delivered


# ----------------------------------------------------------------------
# Діагностика: чи бачить бот чат (workflow_dispatch з telegram_check=true)
# ----------------------------------------------------------------------

def _call(token: str, method: str, **params) -> dict:
    resp = requests.post(API_BASE.format(token=token) + method, json=params, timeout=15)
    try:
        body = resp.json()
    except ValueError:
        body = {"ok": False, "description": resp.text[:200]}
    return body


def check_connection(token: str, chat_id: str) -> bool:
    """
    Три кроки, кожен з яких логує відповідь Telegram як є:
    getMe (токен), getChat (бот бачить chat_id), sendMessage (право писати).
    Повертає True, якщо тестове повідомлення дійшло.
    """
    chat_id = (chat_id or "").strip()
    me = _call(token, "getMe")
    if not me.get("ok"):
        logger.error("getMe: токен не працює: %s", me.get("description"))
        return False
    logger.info("getMe: бот @%s (id %s)", me["result"].get("username"), me["result"].get("id"))

    chat = _call(token, "getChat", chat_id=chat_id)
    if not chat.get("ok"):
        logger.error("getChat(%s): %s. Для каналу chat_id має бути виду -100XXXXXXXXXX, "
                     "а бот — доданий у канал як адміністратор.", chat_id, chat.get("description"))
        return False
    r = chat["result"]
    logger.info("getChat: %s «%s» (id %s)", r.get("type"), r.get("title") or r.get("username"), r.get("id"))

    sent = _call(token, "sendMessage", chat_id=chat_id,
                 text="✅ Тест: агент пошуку вакансій бачить цей чат.")
    if not sent.get("ok"):
        logger.error("sendMessage: %s. Якщо це канал — дай боту право Post messages.",
                     sent.get("description"))
        return False
    logger.info("sendMessage: тестове повідомлення доставлено.")
    return True
