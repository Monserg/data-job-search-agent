"""
Work.ua — вакансії через email-сповіщення "збереженого пошуку", а не
пряме HTML-скрапінг сайту (прямий скрапінг був ненадійний з GitHub Actions).

IMAP-механіка (підключення, читання UNSEEN, парсинг HTML-тіла листа)
винесена в src/scrapers/email_common.py — цей файл лише задає
Work.ua-специфічні sender_filter і link_pattern.

ПРОФІЛІ: джерело не залежить від профілю (PROFILE_AGNOSTIC) — лист уже
відфільтрований збереженим пошуком на боці work.ua. Для кожного профілю
(AI junior, iOS middle+) створюється ОКРЕМИЙ збережений пошук на ту саму
скриньку; до якого профілю належить вакансія, визначає title_regex
профілю в main.py.

Потрібні змінні середовища (спільні для всіх email-джерел):
    WORK_UA_EMAIL_ADDRESS
    WORK_UA_EMAIL_APP_PASSWORD
"""
import re

from .email_common import fetch_unread_jobs

PROFILE_AGNOSTIC = True

SENDER_FILTER = "work.ua"
LINK_PATTERN = re.compile(r"/jobs/(\d+)")


def search(queries: list, params: dict = None) -> list:
    """queries/params ігноруються — фільтрація вже відбулась на боці work.ua."""
    return fetch_unread_jobs(SENDER_FILTER, LINK_PATTERN, "Work.ua")
