"""
Надсилає ОДНЕ повідомлення на КОЖЕН профіль: жирний заголовок з назвою
напрямку, кількістю та хештегом, а під ним — РОЗГОРТУВАНА ЦИТАТА
(<blockquote expandable>) зі списком вакансій, по рядку на вакансію
(посилання-назва, компанія, джерело). Telegram показує таку цитату
згорнутою (перші кілька рядків + стрілка), тап по стрілці розгортає
й згортає список — без кнопок і без постійно запущеного бота.

Ліміт Telegram — 4096 символів видимого тексту на повідомлення, тому
довгий список ріжеться на кілька повідомлень ("частина 2/3"), кожне зі
своєю цитатою. В кінці — попередження про "мовчазні" джерела, якщо є.

Помилка відправки одного повідомлення НЕ зупиняє решту; вакансії з
повідомлення, що не дійшло, повертаються в main, щоб їх ID НЕ потрапили
в seen_jobs.json і вони пішли в наступний звіт, а не загубились (саме
так зникли 23 вакансії 2026-10-01, коли chat_id указував на канал, де
бот не був адміністратором).

Потрібні змінні середовища:
  TELEGRAM_BOT_TOKEN — токен бота від @BotFather
  TELEGRAM_CHAT_ID   — chat_id, куди слати: особистий (число), група
                       (-123...) або канал (-100123...; бот має бути
                       адміністратором каналу з правом Post messages)
"""
import html
import logging
import os
import re
import time

import requests

logger = logging.getLogger("job_agent.telegram")

API_BASE = "https://api.telegram.org/bot{token}/"
API_URL = API_BASE + "sendMessage"

# Пауза між повідомленнями, щоб не впертись у Telegram flood control.
SEND_DELAY_SECONDS = 1.2

# Ліміт Telegram — 4096 символів ПІСЛЯ розбору HTML (теги й href не
# рахуються). Беремо із запасом; рядків на повідомлення обмежуємо, щоб
# розгорнутий список лишався читабельним.
MAX_VISIBLE_CHARS = 3800
MAX_LINES_PER_MESSAGE = 30


def _esc(text: str) -> str:
    """Екранує текст для HTML parse_mode Telegram."""
    return html.escape(str(text), quote=False)


def _hashtag(text: str) -> str:
    tag = "".join(ch for ch in (text or "") if ch.isalnum())
    return f"#{tag}" if tag else ""


_TAG_RE = re.compile(r"<[^>]+>")


def visible_length(text: str) -> int:
    """Довжина тексту так, як її рахує Telegram: без HTML-тегів і сутностей."""
    return len(html.unescape(_TAG_RE.sub("", text)))


def build_job_line(job: dict) -> str:
    """Один рядок списку: назва-посилання, компанія, джерело."""
    title = _esc(job.get("title") or "Без назви")
    url = job.get("url", "")
    head = f'<a href="{_esc(url)}">{title}</a>' if url else f"<b>{title}</b>"
    company = (job.get("company") or "").strip()
    source = (job.get("source") or "").strip()
    line = f"• {head}"
    if company:
        line += f" — {_esc(company)}"
    if source:
        line += f" ({_esc(source)})"
    return line


def _header(profile: dict, total: int, part: int, parts: int) -> str:
    name = _esc(profile.get("name", ""))
    tag = _hashtag(profile.get("hashtag", ""))
    text = f"📋 <b>{name}: нових вакансій {total}</b> {tag}".strip()
    if parts > 1:
        text += f" (частина {part}/{parts})"
    return text


def build_profile_messages(profile: dict, jobs: list) -> list:
    """
    Повертає список пар (текст повідомлення, вакансії в ньому). Рядки
    пакуються жадібно, поки влазять у MAX_VISIBLE_CHARS і
    MAX_LINES_PER_MESSAGE; список у кожному повідомленні загорнутий у
    <blockquote expandable>.
    """
    if not jobs:
        return []
    header_reserve = visible_length(_header(profile, len(jobs), 99, 99)) + 2

    chunks, current, current_len = [], [], header_reserve
    for job in jobs:
        line = build_job_line(job)
        line_len = visible_length(line) + 1
        if current and (len(current) >= MAX_LINES_PER_MESSAGE
                        or current_len + line_len > MAX_VISIBLE_CHARS):
            chunks.append(current)
            current, current_len = [], header_reserve
        current.append((job, line))
        current_len += line_len
    if current:
        chunks.append(current)

    messages = []
    for idx, chunk in enumerate(chunks, start=1):
        body = "\n".join(line for _, line in chunk)
        text = f"{_header(profile, len(jobs), idx, len(chunks))}\n<blockquote expandable>{body}</blockquote>"
        messages.append((text, [job for job, _ in chunk]))
    return messages


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
    Повертає (failed_jobs, delivered): вакансії з повідомлень, що НЕ
    дійшли, і кількість успішно надісланих повідомлень (будь-яких).
    delivered == 0 означає, що з чатом щось не так.
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
            messages = build_profile_messages(profile, jobs)
            for idx, (text, chunk_jobs) in enumerate(messages, start=1):
                what = f"список {profile.get('name', '')} ({idx}/{len(messages)}, {len(chunk_jobs)} вакансій)"
                if _try_send(url, chat_id, text, what):
                    delivered += 1
                else:
                    failed_jobs.extend(chunk_jobs)

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

    # Тестове повідомлення — у тому ж форматі, що й звіт (розгортувана
    # цитата), щоб одразу побачити, як він виглядає в цьому чаті.
    sample = build_profile_messages(
        {"name": "Тест", "hashtag": "#test"},
        [{"title": "Агент пошуку вакансій бачить цей чат", "company": "✅",
          "url": "https://github.com/Monserg/data-job-search-agent", "source": "telegram_check"}],
    )[0][0]
    sent = _call(token, "sendMessage", chat_id=chat_id, text=sample, parse_mode="HTML",
                 disable_web_page_preview=True)
    if not sent.get("ok"):
        logger.error("sendMessage: %s. Якщо це канал — дай боту право Post messages.",
                     sent.get("description"))
        return False
    logger.info("sendMessage: тестове повідомлення доставлено.")
    return True
