"""
Work.ua — розділ Remote + пошук за ключовим словом.

Пошуковий термін вбудовується прямо в шлях URL (а не в query-параметр
?search=, як було раніше):
    https://www.work.ua/jobs-remote-<термін>/?advs=1&employment=74&anyword=1&days=122
де пробіли всередині терміну кодуються як "+" (quote_plus), напр.:
    "iOS Developer"    -> /jobs-remote-ios+developer/
    "iOS-програміст"   -> /jobs-remote-ios-програміст/
Посилання на вакансії виглядають як /jobs/1234567/

Фільтри (підтверджено вручну через UI work.ua):
    advs=1        — розширений пошук
    employment=74 — повна зайнятість
    anyword=1     — шукати за будь-яким зі слів (не точна фраза)
    days=...      — НЕ буквальна кількість днів, а закодоване значення
                    випадаючого списку "Вакансії за період":
                        122 -> "За 1 день"
                        123 -> "За 7 днів"
                        124 -> "За 14 днів"
                    (далі, ймовірно, послідовно 125/126/... -> 30/60/...
                    днів, але це не перевірено — не екстраполюй без
                    ручної звірки в UI).
                    Обрано 122 ("за 1 день"), бо пайплайн ганяється раз
                    на день о 9:00 — цього достатньо і мінімізує дублі.

УВАГА: цю схему URL і фільтри підтверджено вручну на прикладі одного
ключового слова ("qa"), не перевірено проти живої розмітки з пісочниці
(robots.txt work.ua блокує автоматичний фетч). Якщо скрапер раптом
почне повертати 0 результатів — перевір вручну один згенерований URL
у браузері і за потреби скоригуй LINK_PATTERN.
"""
import urllib.parse
from .base import html_link_scrape

BASE_URL = "https://www.work.ua"
LINK_PATTERN = r"/jobs/\d+"

EMPLOYMENT = "74"   # повна зайнятість

# Закодовані значення випадаючого списку "Вакансії за період" (НЕ дні):
DAYS_1 = "122"    # За 1 день
DAYS_7 = "123"    # За 7 днів
DAYS_14 = "124"   # За 14 днів

DAYS = DAYS_7  # щоденний прогін о 9:00 -> досить "за 7 днів"


def search(keywords: list) -> list:
    all_results = []
    for kw in keywords:
        q = urllib.parse.quote_plus(kw)
        url = (
            f"{BASE_URL}/jobs-remote-{q}/"
            f"?advs=1&employment={EMPLOYMENT}&anyword=1&days={DAYS}"
        )
        all_results.extend(
            html_link_scrape(url, LINK_PATTERN, BASE_URL, "Work.ua", kw)
        )
    return all_results
