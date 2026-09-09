"""
Djinni.co — офіційний публічний RSS з фільтрацією за ключовим словом.

Ендпоінт: https://djinni.co/jobs/rss/

ВАЖЛИВО (з'ясовано емпірично, ручним звірянням RSS з людською
сторінкою https://djinni.co/jobs/?... — Djinni ніде це не документує,
і поведінка виявилась не інтуїтивною):

- `all_keywords` (текстовий пошук за словом/фразою) — єдиний
  параметр, який НАДІЙНО фільтрує RSS-фід у комбінації з
  `employment`, `region`, `search_type`. Перевірено багаторазово:
  ідентична кількість і склад вакансій, що й на людській сторінці
  з тими самими фільтрами.

- `primary_keyword` (системна категорія Djinni, напр. "iOS",
  "ML AI") — НЕНАДІЙНИЙ у RSS. В одному тесті комбінація
  `all_keywords=iOS&primary_keyword=iOS&employment=remote&
  region=worldwide&search_type=basic-search` коректно повернула
  тільки iOS-вакансії. Але щойно `all_keywords` і `primary_keyword`
  не збігаються дослівно (напр. `all_keywords=AI Engineer` +
  `primary_keyword=ML AI`), фільтр мовчки відключається і
  повертається повний нефільтрований фід — без помилки, без
  порожнього результату, просто найновіші вакансії з усіх категорій.
  Те саме відбувається, якщо `primary_keyword` заданий БЕЗ
  `all_keywords` узагалі. Через цю ненадійність `primary_keyword`
  тут свідомо НЕ використовується — ризик тихо отримати
  нефільтрований фід (і засмітити звіт сотнями нерелевантних
  вакансій) переважує потенційну користь від категорійного фільтру.

- `exp_level`, `salary`, `english_level` — кожен з них ОКРЕМО
  ламає фільтрацію так само тихо (весь нефільтрований фід замість
  помилки), незалежно від того, які ще параметри задані поруч.
  Перевірено кожен окремо. Тому вони НІКОЛИ не додаються до
  запиту — ці критерії (досвід/зарплата/англійська), якщо колись
  знадобляться, треба буде фільтрувати вже на своєму боці з
  тексту вакансії, а не через query-параметри RSS.

Отже: єдина безпечна комбінація параметрів —
`all_keywords` + `employment=remote` + `region=worldwide` +
`search_type=basic-search`, по одному запиту на кожне ключове
слово з config.yaml.
"""
import urllib.parse
import feedparser
from .base import logger

FEED_URL = "https://djinni.co/jobs/rss/"


def _build_url(keyword: str) -> str:
    params = {
        "all_keywords": keyword,
        "employment": "remote",
        "region": "worldwide",
        "search_type": "basic-search",
    }
    return f"{FEED_URL}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"


def search(keywords: list) -> list:
    all_results = []
    for kw in keywords:
        url = _build_url(kw)
        try:
            feed = feedparser.parse(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Djinni: не вдалось завантажити %s (%s)", url, exc)
            continue

        if getattr(feed, "bozo", False) and not feed.entries:
            logger.warning("Djinni: некоректний фід для %s (%s)", kw, url)
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "") or ""
            full_text = f"{title} {summary}"

            all_results.append({
                "title": title,
                "company": "",
                "url": entry.get("link", ""),
                "source": "Djinni",
                "text": full_text,
                "date": entry.get("published", ""),
            })
    return all_results
