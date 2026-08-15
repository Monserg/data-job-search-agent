"""
RemoteOK має публічний JSON API: https://remoteok.com/api
Перший елемент відповіді — це не вакансія, а легальний дисклеймер, тому
його пропускаємо.
"""
import requests
from .base import DEFAULT_HEADERS, keyword_matches

API_URL = "https://remoteok.com/api"


def search(keywords: list) -> list:
    resp = requests.get(API_URL, headers=DEFAULT_HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue  # пропускаємо дисклеймер-запис
        title = item.get("position", "")
        description = item.get("description", "") or ""
        tags = " ".join(item.get("tags", []) or [])
        full_text = f"{title} {description} {tags}"

        if not keyword_matches(full_text, keywords):
            continue

        results.append({
            "title": title,
            "company": item.get("company", ""),
            "url": item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}",
            "source": "RemoteOK",
            "text": full_text,
            "date": item.get("date", ""),
        })
    return results
