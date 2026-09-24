"""
LinkedIn — вакансії через email-сповіщення "Job alerts", а не через
Google Alerts RSS (src/scrapers/linkedin_alerts.py лишається поруч,
не видалений; він працює, лише якщо в config.yaml задано feed_urls) і не
через пряме скрапінг-парсення LinkedIn (порушує їхні умови використання).

IMAP-механіка спільна з work_ua_email.py / robota_ua_email.py -- див.
src/scrapers/email_common.py. Використовує ТУ САМУ поштову скриньку й
ТІ САМІ GitHub Secrets (WORK_UA_EMAIL_ADDRESS / WORK_UA_EMAIL_APP_PASSWORD),
просто з іншим фільтром відправника -- НЕ потрібна окрема Gmail-скринька
чи новий App Password.

Як налаштувати джерело (одноразово, на боці LinkedIn):
  1. LinkedIn -> Jobs -> введи пошук (напр. "AI Engineer", регіон/Remote,
     Experience level: Entry level / Associate) -> тумблер "Job alert"
     ("Створити сповіщення про вакансії").
  2. У налаштуваннях сповіщення: канал "Email", частота "Daily"
     (або "Weekly"), адреса -- msm.search.job@gmail.com (має бути
     підтверджена як email-адреса акаунта LinkedIn: Settings ->
     Sign in & security -> Email addresses).
  3. По одному сповіщенню на кожен напрямок/ключове слово.

Чим відрізняється від robota_ua_email / work_ua_email -- ВЛАСНИЙ ПАРСЕР:
  - Лист LinkedIn містить по кілька посилань на ту саму вакансію
    (картинка, назва, кнопка "View job"), кожне з різними трекінг-
    параметрами. Універсальний parse_jobs_from_html створив би з цього
    дублі і "вакансії" з назвою "View job". Тому тут вакансія
    ідентифікується за числовим job ID (/jobs/view/<id>), а посилання
    нормалізується до https://www.linkedin.com/jobs/view/<id>/ (без
    персональних трекінг-токенів trkEmail/midToken у таблиці).
  - dedup.py дедублікує за (компанія, посада), тож порожня компанія
    склеювала б однакові назви посад з різних компаній. Тому тут
    компанія береться з рядка картки одразу під назвою вакансії
    ("Company · Location" -> "Company"). Якщо розмітка інша й рядок
    не розпізнано -- company = "" (як і в інших email-скраперів).

УВАГА -- НЕ ПЕРЕВІРЕНО на реальному листі (той самий застережний момент,
що й у work_ua_email.py / robota_ua_email.py при першому впровадженні;
тести робились на синтетичному HTML за відомою структурою листів
LinkedIn job alerts):
  - SENDER_FILTERS -- припущення про From-адреси: jobalerts-noreply@
    (щоденні/тижневі "Job alerts") та jobs-listings@ (добірки
    "рекомендовані вакансії"). Навмисно НЕ просто "linkedin.com": інакше
    у "прочитані" потрапляли б листи-запрошення, повідомлення тощо,
    які цей скрапер не обробляє (FETCH BODY[] ставить \\Seen).
  - Структура картки (назва -> рядок "Компанія · Локація") -- евристика.
Якщо після першого реального листа 0 результатів при непустому inbox або
компанія порожня -- відкрий лист у Gmail -> "Показати оригінал" -> скинь
HTML, підправлю.

Потрібні змінні середовища (ті самі, що й для work_ua_email.py /
robota_ua_email.py -- усі читають одну скриньку, розрізняючи джерела за
відправником):
    WORK_UA_EMAIL_ADDRESS
    WORK_UA_EMAIL_APP_PASSWORD
"""
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .email_common import fetch_unread_jobs

SOURCE_NAME = "LinkedIn"

SENDER_FILTERS = [
    "jobalerts-noreply@linkedin.com",
    "jobs-listings@linkedin.com",
]

# /jobs/view/<id>, /comm/jobs/view/<id>, /jobs/view/<slug>-<id>, а також
# ?currentJobId=<id> у посиланнях на добірки. Посилання перед пошуком
# розкодовується (unquote) -- на випадок, якщо URL загорнутий у редирект.
LINK_PATTERN = re.compile(r"/jobs/view/(?:[^/?#&]*-)?(\d{6,})|currentJobId=(\d{6,})")

# Тексти посилань, що НЕ є назвою вакансії (кнопки/бейджі).
_JUNK_TEXTS = {
    "view job", "view jobs", "see job", "see all jobs", "apply", "apply now",
    "easy apply", "new", "promoted", "actively recruiting",
    "be an early applicant", "view", "see more jobs", "unsubscribe",
    "переглянути вакансію", "переглянути вакансії", "переглянути",
    "подати заявку", "швидка подача заявки", "нова", "нове",
    "переглянути всі вакансії",
}

_SEP_RE = re.compile(r"\s*[·•|]\s*")
_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _is_junk(text: str) -> bool:
    t = _norm(text).lower()
    if len(t) < 3 or t in _JUNK_TEXTS:
        return True
    return not re.search(r"[^\W\d_]", t)  # без жодної літери (напр. "·", "—")


def _job_id(href: str):
    """Числовий job ID з href або None, якщо це не посилання на вакансію."""
    m = LINK_PATTERN.search(unquote(href or ""))
    if not m:
        return None
    return m.group(1) or m.group(2)


def _card_strings(anchor, job_id: str) -> list:
    """
    Текстові рядки "картки" вакансії: піднімаємось від посилання-назви
    вгору по DOM, доки предок містить посилання лише на ЦЮ вакансію --
    зупиняємось перед першим предком, у якому з'являється інша вакансія
    (щоб не захопити сусідні картки).
    """
    node = anchor
    for _ in range(8):
        parent = node.parent
        if parent is None or parent.name in ("body", "html", "[document]"):
            break
        other_ids = {
            _job_id(a["href"]) for a in parent.find_all("a", href=True)
        } - {None, job_id}
        if other_ids:
            break
        node = parent
    return [_norm(s) for s in node.stripped_strings if _norm(s)]


def _company_from_card(strings: list, title: str) -> str:
    """Перший змістовний рядок після назви: "Company · Location" -> "Company"."""
    title_n = _norm(title)
    try:
        idx = next(i for i, s in enumerate(strings) if s == title_n)
    except StopIteration:
        return ""
    for s in strings[idx + 1: idx + 5]:
        if _is_junk(s):
            continue
        company = _SEP_RE.split(s)[0].strip()
        if company and not _is_junk(company) and len(company) <= 100:
            return company
        return ""
    return ""


def parse_linkedin_jobs(html: str, link_pattern, source_name: str) -> list:
    """
    Парсер одного листа LinkedIn job alert. Сигнатура сумісна з
    email_common.parse_jobs_from_html (link_pattern тут не використовується --
    ID вакансії витягується власним LINK_PATTERN), тож передається в
    fetch_unread_jobs(parser=...).
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs = {}  # job_id -> dict; dict зберігає порядок появи в листі

    for a in soup.find_all("a", href=True):
        job_id = _job_id(a["href"])
        if not job_id or job_id in jobs:
            continue
        title = _norm(a.get_text(" ", strip=True))
        if _is_junk(title):
            # картинка/кнопка -- назва може бути в іншому <a> тієї ж вакансії
            continue
        company = _company_from_card(_card_strings(a, job_id), title)
        jobs[job_id] = {
            "title": title,
            "company": company,
            "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
            "source": source_name,
            "text": f"{title} {company}".strip(),
            "date": "",
        }
    return list(jobs.values())


def search(queries: list) -> list:
    """queries ігнорується -- фільтрація вже відбулась на боці LinkedIn
    (email-сповіщення налаштовані на Job alert). Сигнатура зберігається
    заради сумісності з REGISTRY у src/main.py."""
    return fetch_unread_jobs(
        SENDER_FILTERS, LINK_PATTERN, SOURCE_NAME, parser=parse_linkedin_jobs,
    )
