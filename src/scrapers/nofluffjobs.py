"""
NoFluffJobs має публічний (без ключа) REST-ендпоінт пошуку:
POST https://nofluffjobs.com/api/search/posting
Це той самий запит, що робить їхній фронтенд — офіційного документованого
API немає, тому структура відповіді може змінитись. Якщо цей скрапер почне
падати — перевір актуальну структуру через DevTools → Network на сайті.
"""
import requests
from .base import DEFAULT_HEADERS, keyword_matches, logger

SEARCH_URL = "https://nofluffjobs.com/api/search/posting"


def search(keywords: list) -> list:
    try:
        resp = requests.post(
            SEARCH_URL,
            json={"criteriaSearch": {"country": {"code": "UA", "remote": True}}},
            headers={**DEFAULT_HEADERS, "Content-Type": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("NoFluffJobs: не вдалось отримати список (%s)", exc)
        return []

    postings = data.get("postings", []) if isinstance(data, dict) else []
    results = []
    for item in postings:
        title = item.get("title", "")
        name = (item.get("name") or "") if isinstance(item.get("name"), str) else ""
        full_text = f"{title} {name}"
        if not keyword_matches(full_text, keywords):
            continue
        url_slug = item.get("url") or item.get("id", "")
        results.append({
            "title": title,
            "company": item.get("name", ""),
            "url": f"https://nofluffjobs.com/job/{url_slug}",
            "source": "NoFluffJobs",
            "text": full_text,
            "date": item.get("posted", ""),
        })
    return results
