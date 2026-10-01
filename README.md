# Job Search Agent

Автоматичний агент, який раз на день шукає нові вакансії на 11 джерелах
за кількома **профілями** пошуку (`profiles` у `config.yaml`), відсіює
вже бачені й невідповідні, і публікує результат рядками в Google Sheets
та картками в Telegram. Жодного AI API для матчингу не використовується —
усе на власній текстовій фільтрації, повністю на безкоштовних сервісах.

Поточні профілі:

| Профіль | Що шукає | Аркуш у Sheets | Хештег |
|---|---|---|---|
| `ai_junior` | AI / LLM / ML, Junior / Entry level, без вимог досвіду | `Vacancies` | `#AI` |
| `ios_middle_senior` | iOS / Swift, Middle+ / Senior | `Vacancies-iOS` | `#iOS` |
| `frontend_senior` | Frontend / Full-stack (React, TypeScript, Node), Middle+ / Senior | `Vacancies-Frontend` | `#Frontend` |

Щоденний запуск ініціює ВИКЛЮЧНО зовнішній сервіс cron-job.org — через
`workflow_dispatch`. Внутрішнього розкладу GitHub Actions немає (деталі
в SETUP.md, крок 6).

## Як фільтрується список вакансій

Для кожного профілю окремо:

1. **Пошук** — джерела, що вміють фільтрувати на своєму боці (Djinni —
   категорія + рівень досвіду, DOU — категорія + досвід), отримують
   параметри з `profiles.<name>.sources`. Решта опитується за текстовими
   запитами `queries` (`keyword_matches` у `src/scrapers/base.py`: для
   запитів з 1-2 слів потрібна точна фраза, для 3+ слів — усі слова).
2. **Стоп-слова в назві** (`exclude_title`) — сеньйорність для AI-профілю
   ("Senior", "Lead", ...), джуніорність для iOS ("Junior", "Trainee",
   "Стажер"). Пошук із межами слова: "Lead" не збігається з "leadership".
3. **Стоп-фрази в описі** (`exclude_text`) — "3+ years", рівень
   англійської тощо. Для iOS-профілю список порожній.
4. **Тематичний гейт** (`title_regex`) — маркер напрямку має бути саме в
   НАЗВІ вакансії. Плюс `title_reject_regex` для суміжних напрямків
   (Android/Flutter/QA/ASO для iOS).
5. **Дедублікація** (`src/dedup.py`) — проти спільного для всіх профілів
   `data/seen_jobs.json` і всередині прогону. ID — від пари
   (компанія, посада), а якщо джерело не віддає компанію — від URL без
   трекінг-параметрів.

Звіт навмисно СИРИЙ — без Match Score чи AI-оцінки відповідності.

## Здоров'я джерел

Кількість сирих (до фільтрів) вакансій по кожному джерелу зберігається в
`data/source_health.json`. Якщо джерело дає 0 три дні поспіль (для
email-джерел — сім), у Telegram приходить попередження — далі див.
SETUP.md, розділ "Що робити, якщо якийсь сайт перестав повертати вакансії".

## Швидкий старт

Дивись **SETUP.md** — покроково (GitHub, Google Service Account,
Sheets, Telegram-бот, email-сповіщення, зовнішній cron).

## Структура проєкту

- config.yaml — профілі пошуку, джерела, таблиця, health
- src/main.py — точка входу / оркестратор
- src/scrapers/base.py — спільні функції: HTTP-сесія, фільтри, парсинг
- src/scrapers/<джерело>.py — по одному файлу на джерело: search(queries, params)
- src/scrapers/email_common.py— IMAP-логіка для email-джерел
- src/dedup.py — дедублікація day-to-day
- src/health.py — лічильник "мовчазних" джерел
- src/sheets_client.py — запис у Google Sheets
- src/telegram_client.py — картки в Telegram
- data/seen_jobs.json — сховище "вже показаних" вакансій
- data/source_health.json — стан здоров'я джерел
- tests/ — pytest: фільтри, дедублікація, парсери
- .github/workflows/ — workflow (запускається ТІЛЬКИ через
workflow_dispatch; щоденний тригер — зовнішній
cron-job.org, деталі в SETUP.md)


## Джерела вакансій

| Джерело | Спосіб | Фільтр на боці джерела |
|---|---|---|
| Djinni | RSS | `primary_keyword`, `exp_level` (одне значення на запит) |
| DOU.ua | HTML, лише remote | `category` (рядок або список), `exp` |
| RemoteOK | JSON API | — |
| WeWorkRemotely | RSS | `feed` (фід категорії) |
| Remotive | RSS | — |
| Himalayas | RSS | — |
| NoFluffJobs | недокументований REST | `requirement`, `seniority` |
| Just Join IT | JSON API фронтенду (`justjoin.it/api/candidate-api/offers`) | `categories`, `experience_levels` (одне значення на запит); `workplace_types`, `max_age_days`, `ukrainians_only`, `with_description` — клієнтські |
| JustRemote | HTML (SPA, ймовірно 0) | — |
| Work.ua, Robota.ua, LinkedIn | email-сповіщення через IMAP | збережений пошук / Job alert на кожен профіль |
| Indeed | вимкнено (немає безкоштовного шляху) | — |

Email-джерела читають одну скриньку (секрети `WORK_UA_EMAIL_ADDRESS` /
`WORK_UA_EMAIL_APP_PASSWORD`) і розрізняються за відправником. Вони не
знають про профілі: вакансія з листа потрапляє в профіль, чий
`title_regex` збігся з її назвою.

## Google Sheets — що пише код, а що вручну

Код дописує лише колонки A-E: Дата додавання, Посада/Вакансія, Компанія,
Джерело, Посилання (URL) — у аркуш профілю (`worksheet`), який
створюється автоматично. Колонки правіше — повністю ручні, код їх не
читає і не перезаписує. Дані дописуються після останнього заповненого
рядка колонки A, але не вище `sheet_first_data_row` профілю (2 за
замовчуванням; 3 для `Vacancies-Frontend`, де рядок 2 — фільтри по
колонках).

## Локальний запуск

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python src/main.py
```

Без секретів Sheets/Telegram скрипт усе одно опитає джерела й залогує
результат — помилки запису лише логуються.

## Як додати новий профіль

Скопіюй блок профілю в `config.yaml`, задай `queries`, `title_regex`,
`exclude_title`/`exclude_text`, `worksheet`, `hashtag` і за потреби
параметри `sources` для Djinni/DOU. Для email-джерел створи окремий
збережений пошук / Job alert на ту саму скриньку. Додай кілька реальних
назв вакансій у `tests/test_filters.py`, щоб зафіксувати очікувану
поведінку.
