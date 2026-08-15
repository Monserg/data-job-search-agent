# Job Search Agent

Автоматичний агент, який щодня о 9:00–10:00 (Kyiv) шукає нові вакансії
за ключовими словами на 10 сайтах, оцінює відповідність кожної з 12
резюме локально (без AI API), пише результат у Google Sheets і надсилає
дайджест у Telegram. Повністю на безкоштовних сервісах.

## Швидкий старт

Дивись **SETUP.md** — покроково, з чого почати (GitHub, Google Service
Account, Drive, Sheets, Telegram-бот).

## Структура проєкту

```
config.yaml              — ключові слова, джерела, налаштування таблиці
src/main.py               — точка входу / оркестратор
src/scrapers/              — по одному файлу на кожне джерело вакансій
src/resume_matcher.py     — локальний розрахунок Match Score (без AI)
src/drive_client.py        — читання 12 резюме з Google Drive
src/sheets_client.py       — запис звіту в Google Sheets
src/telegram_client.py     — надсилання дайджесту в Telegram
src/dedup.py                — щоб вакансії не дублювались day-to-day
data/seen_jobs.json         — сховище "вже показаних" вакансій
.github/workflows/          — розклад автоматичного запуску (GitHub Actions)
```

## Джерела вакансій

Djinni, DOU.ua, RemoteOK, WeWorkRemotely, Robota.ua, Work.ua,
NoFluffJobs, JustRemote — скрапляться напряму.
LinkedIn — через Google Alerts RSS (офіційний безкоштовний обхід,
див. SETUP.md крок 5).
Indeed — наразі немає стабільного безкоштовного способу (закритий RSS,
блокує скрапінг), джерело відключене з поясненням у коді.

## Локальний запуск для тесту

```bash
pip install -r requirements.txt
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
cd src && python main.py
```
# data-job-search-agent
