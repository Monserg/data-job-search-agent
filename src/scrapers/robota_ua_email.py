"""
Robota.ua — вакансії через email-сповіщення "збереженого пошуку", а не
пряме HTML-скрапінг сайту: Robota.ua — SPA на React, вакансії
довантажуються через JS і в статичний HTML не потрапляють (прямий
скрапер стабільно повертав 0 і видалений).

IMAP-механіка спільна — див. src/scrapers/email_common.py. Та сама
скринька й ті самі секрети, що й у work_ua_email.py, інший фільтр
відправника. Досить створити "збережений пошук" на robota.ua з
увімкненими email-сповіщеннями на ту саму адресу.

ПРОФІЛІ: джерело не залежить від профілю (PROFILE_AGNOSTIC) — для
кожного профілю створюється окремий збережений пошук; належність
вакансії до профілю визначає title_regex профілю в main.py.

Потрібні змінні середовища (спільні для всіх email-джерел):
    WORK_UA_EMAIL_ADDRESS
    WORK_UA_EMAIL_APP_PASSWORD
"""
import re

from .email_common import fetch_unread_jobs

PROFILE_AGNOSTIC = True

SENDER_FILTER = "robota.ua"
LINK_PATTERN = re.compile(r"/(?:vacancy|company)[a-z0-9\-/]*\d+")


def search(queries: list, params: dict = None) -> list:
    """queries/params ігноруються — фільтрація вже відбулась на боці robota.ua."""
    return fetch_unread_jobs(SENDER_FILTER, LINK_PATTERN, "Robota.ua")
