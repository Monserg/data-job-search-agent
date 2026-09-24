# Job Search Agent

Автоматичний агент, який раз на день шукає нові вакансії за списком
пошукових запитів (`search.queries` у `config.yaml`) на 12 джерелах,
відсіює вже бачені й невідповідні (сеньйорність, роки досвіду,
не-AI/ML вакансії — детальніше нижче) і публікує результат у вигляді
рядків у Google Sheets та карток у Telegram. Жодного AI API для самого
матчингу не використовується — усе на власній текстовій фільтрації,
повністю на безкоштовних сервісах.

Щоденний запуск ініціює ЗОВНІШНІЙ сервіс cron-job.org (не внутрішній
розклад GitHub Actions) — деталі налаштування в SETUP.md, крок 6.

## Як фільтрується список вакансій

1. **Пошук** — кожне джерело опитується за всіма запитами з
   `search.queries` (config.yaml). Це не "ключове слово десь у
   тексті" — `keyword_matches` (`src/scrapers/base.py`) вимагає збіг
   із межами слова.
2. **Виключення** (`filters.exclude_keywords`) — вакансії з ознаками
   сеньйорності ("Senior", "Lead", "Architect" тощо) чи вимогою років
   досвіду ("3+ years", "at least 2 years") прибираються
   (`is_excluded`).
3. **Тематичний гейт** — AI/ML-маркер має бути саме в НАЗВІ вакансії
   (`is_ai_title`, `src/scrapers/base.py`) — інакше вакансія
   відкидається, навіть якщо пройшла пошук за запитом.
4. **Дедублікація** — вакансії, вже показані в попередніх прогонах
   (`data/seen_jobs.json`), повторно в звіт не потрапляють.

Це навмисно СИРИЙ список — без Match Score, без рекомендації резюме,
без AI-аналізу "чому підходить". Шар матчингу проти резюме (локальний
і через Gemini) прибрано з пайплайна 2026-09-20 як недостовірний; сам
код цього шару (`resume_matcher.py`, `drive_client.py`,
`gemini_client.py`) видалено з репозиторію.

## Швидкий старт

Дивись **SETUP.md** — покроково (GitHub, Google Service Account,
Sheets, Telegram-бот, зовнішній cron).

## Структура проєкту

```
config.yaml — ключові слова, джерела, налаштування таблиці
src/main.py — точка входу / оркестратор
src/scrapers/ — по одному файлу на кожне джерело вакансій
src/resume_matcher.py — локальний розрахунок Match Score (без AI)
src/drive_client.py — читання 12 резюме з Google Drive
src/sheets_client.py — запис звіту в Google Sheets
src/telegram_client.py — надсилання дайджесту в Telegram
src/dedup.py — щоб вакансії не дублювались day-to-day
data/seen_jobs.json — сховище "вже показаних" вакансій
.github/workflows/ — сам workflow виконання (GitHub Actions).
Запускається ТІЛЬКИ вручну/через
workflow_dispatch — щоденний тригер живе поза репозиторієм, у cron-job.org
```


## Джерела вакансій (12)

Djinni, DOU.ua, RemoteOK, WeWorkRemotely, NoFluffJobs, JustRemote,
Remotive, Himalayas — скрапляться напряму.
Robota.ua, Work.ua, LinkedIn — через email-сповіщення на скриньку
msm.search.job@gmail.com (IMAP, одні й ті самі секрети
WORK_UA_EMAIL_ADDRESS / WORK_UA_EMAIL_APP_PASSWORD; джерела
розрізняються за відправником листа). Для LinkedIn потрібен Job alert
з доставкою на email — див. docstring src/scrapers/linkedin_email.py.
Indeed — наразі немає стабільного безкоштовного способу (закритий RSS,
блокує скрапінг); `src/scrapers/indeed.py` завжди повертає `[]`.

## Google Sheets — що пише код, а що вручну

Код дописує лише колонки A-E: Дата додавання, Посада/Вакансія,
Компанія, Джерело, Посилання (URL). Усі колонки правіше (CANVA, EN,
На адаптацію, Виконано, Feedback тощо) — повністю ручні; ні
`src/main.py`, ні `src/sheets_client.py` їх не читають і не
перезаписують.

## Локальний запуск для тесту

```bash
pip install -r requirements.txt
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
cd src && python main.py
```
