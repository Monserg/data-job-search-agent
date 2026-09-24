"""
Work.ua — вакансії через email-сповіщення "збереженого пошуку", а не
пряме HTML-скрапінг сайту (окремий src/scrapers/work_ua.py лишається
поруч і не чіпається цим файлом — обидва джерела можуть працювати
паралельно, дублі прибере dedup.py за парою компанія+посада).

Механіка (100% безкоштовно, без сторонніх платних сервісів):
1. На work.ua створено "збережений пошук" за потрібними ключовими
   словами -> увімкнено email-сповіщення (вбудована функція сайту).
2. Листи приходять на окрему Gmail-скриньку (WORK_UA_EMAIL_ADDRESS).
3. Для цієї скриньки увімкнено 2FA + згенеровано Gmail App Password
   (Google Account -> Security -> 2-Step Verification -> App passwords)
   -- НЕ пароль від акаунта, окремий 16-символьний ключ для сторонніх
   застосунків. Зберігається в GitHub Secret WORK_UA_EMAIL_APP_PASSWORD.
4. Цей скрапер підключається по IMAP до imap.gmail.com, читає
   НЕПРОЧИТАНІ листи від work.ua, парсить посилання на вакансії з
   HTML-тіла листа.
5. Звичайний (не .PEEK) FETCH BODY[] сам позначає прочитаний лист
   \\Seen (стандартна поведінка IMAP, RFC 3501) -- тож при наступному
   щоденному прогоні той самий лист вдруге не потрапить у UNSEEN-вибірку.
   Додатковий захист від дублів -- dedup.py (компанія+посада), що і так
   вже є для всіх джерел.

УВАГА -- НЕ ПЕРЕВІРЕНО на реальному листі (жодного зразка мені не
показували, тож усе нижче -- обґрунтоване припущення, а не факт):
  - LINK_PATTERN шукає підрядок "/jobs/<цифри>" ДЕ ЗАВГОДНО в href --
    якщо лист загортає посилання в трекінг-редирект (напр.
    click.work.ua/... чи UTM-параметри), цей патерн може не спрацювати.
  - SENDER_FILTER = "work.ua" -- припущення, що From-адреса сповіщень
    містить "work.ua". Якщо сповіщення йдуть з домену стороннього
    email-сервісу (напр. окремий ESP-домен), фільтр треба буде
    скоригувати під реальний Message-From.
  - "text" вакансії -- зараз лише anchor-текст посилання (title), БЕЗ
    опису/сніпету навколо -- HTML листа може містити короткий опис
    поруч із посиланням, але без зразка листа я не знаю, як саме він
    структурований у розмітці, тож не витягую його зараз.
Якщо після першого реального запуску тут 0 результатів при непустому
inbox -- відкрий один такий лист у Gmail -> "Показати оригінал"
(Show original) -> скинь мені HTML-частину, підправлю парсинг.

Потрібні змінні середовища:
    WORK_UA_EMAIL_ADDRESS      -- Gmail-скринька, куди приходять сповіщення
    WORK_UA_EMAIL_APP_PASSWORD -- Gmail App Password (16 символів, НЕ звичайний пароль)
Якщо обох немає -- скрапер просто повертає [] і логує попередження,
не ламаючи решту пайплайну (той самий підхід, що й indeed.py).
"""
import email
import imaplib
import logging
import os
import re
from email.header import decode_header

from bs4 import BeautifulSoup

logger = logging.getLogger("job_agent.scrapers")

IMAP_HOST = "imap.gmail.com"
IMAP_MAILBOX = "INBOX"

# Відправник сповіщень work.ua -- листи від інших адрес ігноруються,
# навіть якщо потрапили в ту саму скриньку. Якщо сповіщення провалюються
# у Spam замість INBOX -- перше, що варто зробити вручну: позначити
# "Не спам" і створити Gmail-фільтр "ніколи не в Spam" для цього From.
SENDER_FILTER = "work.ua"

# /jobs/<id> -- та сама схема посилань на окрему вакансію, що й на
# самому сайті (див. src/scrapers/work_ua.py), шукається як підрядок
# href, а не лише на початку -- на випадок трекінг-обгортки листа.
LINK_PATTERN = re.compile(r"/jobs/(\d+)")


def _decode_mime_words(raw: str) -> str:
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


def _extract_html_body(msg) -> str:
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


def _parse_jobs_from_html(html: str) -> list:
    """
    Витягує вакансії з HTML-тіла одного листа-сповіщення work.ua.
    Кожен <a href>, чий href містить /jobs/<id>, вважається окремою
    вакансією; текст посилання -- title. company НЕ витягується
    (лист, ймовірно, не кодує компанію в href) -- лишається "", як у
    linkedin_alerts.py.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen_urls = set()
    jobs = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not LINK_PATTERN.search(href):
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
            "source": "Work.ua (email)",
            "text": title,
            "date": "",
        })
    return jobs


def search(queries: list) -> list:
    """
    queries ігнорується -- фільтрація за ключовими словами вже
    відбулась на боці work.ua (email-сповіщення налаштовані на
    "збережений пошук" з потрібними термінами), а не тут. Сигнатура
    зберігається заради сумісності з REGISTRY / collect_jobs() у
    src/main.py, який викликає module.search(queries) уніфіковано для
    всіх джерел.
    """
    address = os.environ.get("WORK_UA_EMAIL_ADDRESS")
    app_password = os.environ.get("WORK_UA_EMAIL_APP_PASSWORD")
    if not address or not app_password:
        logger.info(
            "Work.ua (email): WORK_UA_EMAIL_ADDRESS / WORK_UA_EMAIL_APP_PASSWORD "
            "не задані -- пропускаю."
        )
        return []

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST)
        imap.login(address, app_password)
        imap.select(IMAP_MAILBOX)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Work.ua (email): не вдалось підключитись до %s (%s)", IMAP_HOST, exc)
        return []

    all_jobs = []
    try:
        status, msg_ids = imap.search(None, "UNSEEN", f'FROM "{SENDER_FILTER}"')
        if status != "OK":
            logger.warning("Work.ua (email): IMAP SEARCH повернув %s", status)
            return []

        id_list = msg_ids[0].split()
        logger.info(
            "Work.ua (email): знайдено %d непрочитаних листів від %s",
            len(id_list), SENDER_FILTER,
        )

        for msg_id in id_list:
            status, msg_data = imap.fetch(msg_id, "(BODY[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                logger.warning("Work.ua (email): не вдалось прочитати лист %s", msg_id)
                continue

            raw_bytes = msg_data[0][1]
            msg = email.message_from_bytes(raw_bytes)
            html = _extract_html_body(msg)
            if not html:
                subject = _decode_mime_words(msg.get("Subject", ""))
                logger.warning(
                    "Work.ua (email): лист '%s' без text/html частини -- пропускаю", subject
                )
                continue

            all_jobs.extend(_parse_jobs_from_html(html))
    finally:
        try:
            imap.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass

    logger.info("Work.ua (email): усього витягнуто %d вакансій", len(all_jobs))
    return all_jobs
