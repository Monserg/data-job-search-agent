"""
Локальний (без AI) розрахунок Match Score між вакансією та кожним із 12
резюме. Підхід: збіг значущих слів (навичок/термінів) між текстом вакансії
та текстом резюме, з невеликим зважуванням.

Це навмисно просто й прозоро — жодних зовнішніх викликів, жодних лімітів,
100% безкоштовно. Якщо пізніше захочеш розумніший аналіз (LLM-судження
"чому підходить"), під це вже є місце в config.yaml (matching.*), і можна
буде підмінити лише compute_match_score / build_reason, не чіпаючи решту
пайплайну.
"""
import re
from collections import Counter

# Короткі "шумові" слова, які не несуть сигналу для метчингу.
STOPWORDS = {
    "and", "the", "for", "with", "you", "our", "are", "will", "from", "this",
    "that", "have", "your", "not", "but", "all", "can", "job", "work",
    "і", "та", "або", "для", "від", "як", "ми", "ви", "це", "яка", "який",
    "на", "по", "з", "у", "в", "до", "за", "що", "не", "буде", "робота",
}

WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯіїєІЇЄ0-9\+\#\.]{2,}")


def tokenize(text: str) -> Counter:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    words = [w for w in words if w not in STOPWORDS]
    return Counter(words)


def compute_match_score(job_text: str, resume_text: str) -> float:
    """
    Проста метрика перетину: скільки % унікальних значущих слів вакансії
    зустрічається також у резюме. Повертає число 0-100.
    """
    job_tokens = set(tokenize(job_text).keys())
    resume_tokens = set(tokenize(resume_text).keys())
    if not job_tokens:
        return 0.0
    overlap = job_tokens & resume_tokens
    score = (len(overlap) / len(job_tokens)) * 100
    return round(min(score, 100.0), 1)


def best_resume_for_job(job_text: str, resumes: dict) -> tuple:
    """
    resumes: {назва_файлу: текст_резюме}
    Повертає (назва_найкращого_резюме, score, спільні_слова[:8])
    """
    best_name, best_score, best_overlap = "", 0.0, []
    job_tokens = set(tokenize(job_text).keys())

    for name, text in resumes.items():
        score = compute_match_score(job_text, text)
        if score > best_score:
            resume_tokens = set(tokenize(text).keys())
            best_overlap = sorted(job_tokens & resume_tokens)[:8]
            best_name, best_score = name, score

    return best_name, best_score, best_overlap


def build_reason(overlap_words: list) -> str:
    if not overlap_words:
        return "Недостатньо збігів навичок/термінів для впевненої оцінки."
    return "Збіги за ключовими термінами: " + ", ".join(overlap_words)
