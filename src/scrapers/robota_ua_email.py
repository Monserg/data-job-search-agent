"""
Robota.ua — вакансії через email-сповіщення "збереженого пошуку", а не
пряме HTML-скрапінг сайту. Прямий скрапер src/scrapers/robota_ua.py
лишається поруч (не видалений), але сам його docstring вже документує
причину: Robota.ua -- SPA на React, частина вакансій довантажується
через JS і не потрапляє у статичний HTML, тому він стабільно повертає
0 вакансій (підтверджено логами щоденних прогонів).

IMAP-механіка спільна з work_ua_email.py -- див.
src/scrapers/email_common.py. Використовує ТУ САМУ поштову скриньку й
ТІ САМІ GitHub Secrets (WORK_UA_EMAIL_ADDRESS / WORK_UA_EMAIL_APP_PASSWORD),
просто з іншим фільтром відправника -- НЕ потрібна окрема Gmail-скринька
чи новий App Password. Досить створити "збережений пошук" на robota.ua
з увімкненими email-сповіщеннями на ту саму адресу msm.search.job@gmail.com
(як і для work.ua -- дзвіночок "Сповіщення" на сторінці збережених пошуків).

УВАГА -- НЕ ПЕРЕВІРЕНО на реальному листі (той самий застережний момент,
що й з work_ua_email.py при першому впровадженні):
  - SENDER_FILTER = "robota.ua" -- припущення, що From-адреса реальних
    сповіщень robota.ua містить цей підрядок.
  - LINK_PATTERN -- той самий патерн посилань, що й у прямому скрапері
    (/vacancy/<id> або /company/<slug>/vacancy/<id>), перенесений сюди
    за аналогією, а не звірений з реальною розміткою листа.
Якщо після першого реального листа 0 результатів при непустому inbox --
відкрий лист у Gmail -> "Показати оригінал" -> скинь HTML, підправлю.

Потрібні змінні середовища (ті самі, що й для work_ua_email.py):
    WORK_UA_EMAIL_ADDRESS
    WORK_UA_EMAIL_APP_PASSWORD
"""
import re

from .email_common import fetch_unread_jobs

SENDER_FILTER = "robota.ua"
LINK_PATTERN = re.compile(r"/(?:vacancy|company)[a-z0-9\-/]*\d+")


def search(queries: list) -> list:
    """queries ігнорується -- фільтрація вже відбулась на боці robota.ua
    (email-сповіщення налаштовані на "збережений пошук"). Сигнатура
    зберігається заради сумісності з REGISTRY у src/main.py."""
    return fetch_unread_jobs(SENDER_FILTER, LINK_PATTERN, "Robota.ua")
