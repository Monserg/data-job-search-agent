"""
RemoteOK має публічний JSON API: https://remoteok.com/api
Перший елемент відповіді — це не вакансія, а легальний дисклеймер, тому
його пропускаємо. Параметри профілю не використовуються (ендпоінт
?tag=<tag> віддає сміття, перевірено 2026-09-30) — фільтрація за
текстовими запитами на нашому боці.
"""
from .base import get_session, keyword_matches, DEFAULT_TIMEOUT

API_URL = "https://remoteok.com/api"


def search(queries: list, params: dict = None) -> list:
    resp = get_session().get(API_URL, timeout=DEFAULT_TIMEOUT)
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

        if not keyword_matches(full_text, queries):
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
