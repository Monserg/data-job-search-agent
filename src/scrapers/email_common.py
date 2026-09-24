"""
Спільна логіка для email-скраперів (IMAP + Gmail App Password).

Зараз використовується work_ua_email.py, robota_ua_email.py та
linkedin_email.py — усі читають ТУ САМУ поштову скриньку
(WORK_UA_EMAIL_ADDRESS / WORK_UA_EMAIL_APP_PASSWORD), розрізняючи
джерела за відправником (sender_filter). Назва змінних середовища лишена "WORK_UA_*" з
історичних причин (перший email-скрапер був саме для work.ua) --
секрети НЕ треба перейменовувати чи дублювати для нових джерел, що
падають у ту саму скриньку; кожен новий email-скрапер просто передає
свій sender_filter/link_pattern/source_name у fetch_unread_jobs().
Якщо розмітка листа складніша за "кожне <a> = вакансія" (як у LinkedIn),
можна передати власний parser (див. параметр parser нижче).
"""
import email
import imaplib
import logging
import os
from email.header import decode_header

from bs4 import BeautifulSoup

logger = logging.getLogger("job_agent.scrapers")

IMAP_HOST = "imap.gmail.com"
IMAP_MAILBOX = "INBOX"


def decode_mime_words(raw: str) -> str:
    """Декодує MIME-закодовані заголовки (напр. '=?UTF-8?B?...?=') у звичайний текст."""
    if not raw:
        return ""
    decoded = ""
    for text, charset in decode_header(raw):
        if isinstance(text, bytes):
            decoded += text.decode(charset or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


def extract_html_body(msg) -> str:
    """Витягує text/html частину листа (мультипарт або одинарний)."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                charset = part.get_content_charset() or "utf-8"
                try:
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:  # noqa: BLE001
                    continue
        return ""
    if msg.get_content_type() == "text/html":
        charset = msg.get_content_charset() or "utf-8"
        try:
            return msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:  # noqa: BLE001
            return ""
    return ""


def parse_jobs_from_html(html: str, link_pattern, source_name: str) -> list:
    """
    Витягує вакансії з HTML-тіла одного листа-сповіщення. Кожен
    <a href>, чий href підпадає під link_pattern, вважається окремою
    вакансією; текст посилання -- title. company НЕ витягується
    (лист, ймовірно, не кодує компанію в href) -- лишається "".
    """
    soup = BeautifulSoup(html, "html.parser")
    seen_urls = set()
    jobs = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not link_pattern.search(href):
            continue
        if href in seen_urls:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        seen_urls.add(href)
        jobs.append({
            "title": title,
            "company": "",
            "url": href,
            "source": source_name,
            "text": title,
            "date": "",
        })
    return jobs


def fetch_unread_jobs(sender_filter, link_pattern, source_name: str,
                       address_env: str = "WORK_UA_EMAIL_ADDRESS",
                       password_env: str = "WORK_UA_EMAIL_APP_PASSWORD",
                       parser=None) -> list:
    """
    Підключається по IMAP до Gmail, читає НЕПРОЧИТАНІ листи від
    sender_filter, парсить з кожного вакансії через parser
    (за замовчуванням -- parse_jobs_from_html).

    sender_filter -- рядок АБО список рядків (кілька відправників одного
    сервісу, напр. LinkedIn шле з різних адрес). Листи від усіх
    відправників об'єднуються без дублів.

    parser -- функція з тією ж сигнатурою, що й parse_jobs_from_html:
    parser(html, link_pattern, source_name) -> list[dict].

    Звичайний (не .PEEK) FETCH BODY[] сам позначає прочитаний лист
    \\Seen (RFC 3501) -- тож при наступному запуску той самий лист
    вдруге не потрапить у UNSEEN-вибірку.

    Якщо address_env/password_env не задані -- повертає [] і логує
    попередження, не ламаючи решту пайплайну (той самий підхід, що
    й indeed.py).
    """
    address = os.environ.get(address_env)
    app_password = os.environ.get(password_env)
    if not address or not app_password:
        logger.info(
            "%s (email): %s / %s не задані -- пропускаю.",
            source_name, address_env, password_env,
        )
        return []

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST)
        imap.login(address, app_password)
        imap.select(IMAP_MAILBOX)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s (email): не вдалось підключитись до %s (%s)", source_name, IMAP_HOST, exc)
        return []

    parse = parser or parse_jobs_from_html
    senders = [sender_filter] if isinstance(sender_filter, str) else list(sender_filter)

    all_jobs = []
    try:
        id_list = []
        for sender in senders:
            status, msg_ids = imap.search(None, "UNSEEN", f'FROM "{sender}"')
            if status != "OK":
                logger.warning(
                    "%s (email): IMAP SEARCH (%s) повернув %s", source_name, sender, status,
                )
                continue
            found = msg_ids[0].split()
            logger.info(
                "%s (email): знайдено %d непрочитаних листів від %s",
                source_name, len(found), sender,
            )
            for mid in found:
                if mid not in id_list:
                    id_list.append(mid)

        for msg_id in id_list:
            status, msg_data = imap.fetch(msg_id, "(BODY[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                logger.warning("%s (email): не вдалось прочитати лист %s", source_name, msg_id)
                continue

            raw_bytes = msg_data[0][1]
            msg = email.message_from_bytes(raw_bytes)
            html = extract_html_body(msg)
            if not html:
                subject = decode_mime_words(msg.get("Subject", ""))
                logger.warning(
                    "%s (email): лист '%s' без text/html частини -- пропускаю",
                    source_name, subject,
                )
                continue

            all_jobs.extend(parse(html, link_pattern, source_name))
    finally:
        try:
            imap.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass

    logger.info("%s (email): усього витягнуто %d вакансій", source_name, len(all_jobs))
    return all_jobs
