"""
Work.ua — вакансії через email-сповіщення "збереженого пошуку", а не
пряме HTML-скрапінг сайту (окремий src/scrapers/work_ua.py видалено --
прямий HTTP-скрапінг був ненадійний/непідтверджений з GitHub Actions).

IMAP-механіка (підключення, читання UNSEEN, парсинг HTML-тіла листа)
винесена в src/scrapers/email_common.py -- цей файл лише задає
Work.ua-специфічні sender_filter і link_pattern.

Підтверджено вручну (2026-09-24): "Отримувати сповіщення на Work.ua"
та "Ел. пошта" увімкнені для збереженого пошуку -- листи мають йти на
msm.search.job@gmail.com.

УВАГА -- ще НЕ ПЕРЕВІРЕНО на реальному листі саме з work.ua (перший
тестовий непрочитаний лист виявився листом з LinkedIn, а не work.ua):
  - LINK_PATTERN шукає підрядок "/jobs/<цифри>" ДЕ ЗАВГОДНО в href --
    якщо лист загортає посилання в трекінг-редирект, може не спрацювати.
  - SENDER_FILTER = "work.ua" -- припущення, що From-адреса реальних
    сповіщень work.ua містить цей підрядок.
Якщо після першого реального листа 0 результатів при непустому inbox --
відкрий лист у Gmail -> "Показати оригінал" -> скинь HTML, підправлю.

Потрібні змінні середовища (ті самі, що й для robota_ua_email.py --
обидва читають одну скриньку, розрізняючи джерела за відправником):
    WORK_UA_EMAIL_ADDRESS
    WORK_UA_EMAIL_APP_PASSWORD
"""
import re

from .email_common import fetch_unread_jobs

SENDER_FILTER = "work.ua"
LINK_PATTERN = re.compile(r"/jobs/(\d+)")


def search(queries: list) -> list:
    """queries ігнорується -- фільтрація вже відбулась на боці work.ua
    (email-сповіщення налаштовані на "збережений пошук"). Сигнатура
    зберігається заради сумісності з REGISTRY у src/main.py."""
    return fetch_unread_jobs(SENDER_FILTER, LINK_PATTERN, "Work.ua")
