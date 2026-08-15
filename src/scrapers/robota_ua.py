"""
Robota.ua — пошук за ключовим словом у розділі "Віддалена робота":
https://robota.ua/zapros/<keyword>/ukraine?remote=1

УВАГА: Robota.ua — SPA на React, тому частина вакансій може довантажуватись
через JS і НЕ потрапляти у статичний HTML. Якщо цей скрапер стабільно
повертає 0 результатів — це означає, що потрібен рендеринг через
headless-браузер (playwright), що виходить за межі "простого й безкоштовного"
рішення на GitHub Actions. Тимчасовий обхід: покладайся на Email Alerts
з самого robota.ua (безкоштовна вбудована функція сайту) паралельно.
"""
import urllib.parse
from .base import html_link_scrape

BASE_URL = "https://robota.ua"
LINK_PATTERN = r"/(?:vacancy|company)[a-z0-9\-/]*\d+"


def search(keywords: list) -> list:
    all_results = []
    for kw in keywords:
        slug = urllib.parse.quote(kw)
        url = f"{BASE_URL}/zapros/{slug}/ukraine?remote=1"
        all_results.extend(
            html_link_scrape(url, LINK_PATTERN, BASE_URL, "Robota.ua", kw)
        )
    return all_results
