"""
Опційне збагачення аналізу через Gemini API (безкоштовний тариф).

Викликається НЕ для кожної вакансії, а лише для тих, що вже пройшли
локальний поріг Match Score (config.yaml -> matching.min_score_to_report).
Це економить денний ліміт безкоштовного тарифу — витрачається лише на
дійсно релевантні вакансії, а не на весь потік з усіх джерел.

Потрібна змінна середовища GEMINI_API_KEY (той самий ключ з Google AI
Studio -> API Keys). Якщо її немає — модуль просто повертає None, і
main.py лишає локальний (без AI) результат без помилок.
"""
import json
import os
import requests
import logging

logger = logging.getLogger("job_agent.gemini")

API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

PROMPT_TEMPLATE = """Ти допомагаєш з пошуком роботи. Ось опис вакансії та резюме кандидата.

ВАКАНСІЯ:
{job_text}

РЕЗЮМЕ ({resume_name}):
{resume_text}

Оціни відповідність резюме цій вакансії від 0 до 100 та напиши ОДНЕ
коротке речення українською, чому підходить (або не підходить).

Відповідай СТРОГО у форматі JSON, без жодного тексту навколо:
{{"score": <число 0-100>, "reason": "<одне речення українською>"}}
"""


def is_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def analyze_fit(job_text: str, resume_text: str, resume_name: str,
                 model: str = "gemini-2.5-flash", timeout: int = 30) -> dict:
    """
    Повертає {"score": float, "reason": str} або None при будь-якій помилці
    (мережа, ліміт вичерпано, неочікувана відповідь) — виклик у main.py
    завжди має fallback на локальний результат.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    prompt = PROMPT_TEMPLATE.format(
        job_text=job_text[:3000],       # обрізаємо, щоб економити токени
        resume_name=resume_name,
        resume_text=resume_text[:3000],
    )
    url = API_URL_TEMPLATE.format(model=model)

    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout,
        )
        if resp.status_code == 429:
            logger.warning("Gemini: денний ліміт безкоштовного тарифу вичерпано (429).")
            return None
        resp.raise_for_status()
        data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Gemini іноді огортає JSON у ```json ... ``` — знімаємо обгортку.
        text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)

        return {
            "score": float(parsed.get("score", 0)),
            "reason": str(parsed.get("reason", "")).strip(),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini: не вдалось отримати/розпарсити відповідь (%s)", exc)
        return None
