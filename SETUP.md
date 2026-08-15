# Налаштування агента пошуку вакансій (100% безкоштовно)

Все на безкоштовних тарифах: GitHub Actions (публічний або приватний
репозиторій), Google Sheets/Drive (Service Account), Telegram Bot API.

## Крок 1. Створи GitHub-репозиторій

1. Зайди на github.com → New repository → назви, наприклад, `job-search-agent`.
2. Обери **Private** (щоб резюме/дані не були публічними).
3. Заливаєш увесь цей проєкт у репозиторій (git init / git push, або
   просто перетягни файли через веб-інтерфейс "Add file → Upload files").

## Крок 2. Створи Google Service Account (для Sheets і Drive)

1. Йди на https://console.cloud.google.com/ → створи новий проєкт (або
   візьми існуючий).
2. У меню зліва: **APIs & Services → Library** → увімкни:
   - Google Sheets API
   - Google Drive API
3. **APIs & Services → Credentials → Create Credentials → Service Account**.
   Назви як завгодно, наприклад `job-agent`.
4. Відкрий створений сервісний акаунт → вкладка **Keys → Add Key → Create
   new key → JSON**. Завантажиться файл — це твій `GOOGLE_SERVICE_ACCOUNT_JSON`.
5. Скопіюй email сервісного акаунта (виглядає як
   `job-agent@<project>.iam.gserviceaccount.com`) — він знадобиться далі.

## Крок 3. Google Drive — папка з 12 резюме

Твоя папка вже є: https://drive.google.com/drive/folders/16wjJ0UDPk28jcX6jcllsvjWxrkPi0qIP

Просто розшаруй її на сервісний акаунт:
1. Відкрий папку → правою кнопкою (або кнопка "Share") → **Share**.
2. Встав email сервісного акаунта з Кроку 2
   (виглядає як `job-agent@<project>.iam.gserviceaccount.com`).
3. Права — **Viewer** достатньо. Надіслати.

ID папки (`16wjJ0UDPk28jcX6jcllsvjWxrkPi0qIP`) уже вписаний у
`config.yaml → google_drive.resumes_folder_id` — нічого міняти не треба.

## Крок 4. Google Sheets — таблиця звіту

Твоя таблиця вже є: https://docs.google.com/spreadsheets/d/1RYP2ub_m7sCtag-MLuZKeukyUhn9WkzvMRKnZ52jeDw/edit

Так само розшаруй її на сервісний акаунт:
1. Відкрий таблицю → **Share**.
2. Встав той самий email сервісного акаунта.
3. Права — **Editor** (агент має дописувати рядки).

ID таблиці вже вписаний у `config.yaml → google_sheets.spreadsheet_id`.
Агент сам створить аркуш (worksheet) `Vacancies` і заголовки колонок
A–G при першому запуску, якщо його ще немає.

## Крок 5. LinkedIn через Google Alerts (безкоштовна легальна альтернатива)

LinkedIn не дає безкоштовного API для вакансій, тому обходимо офіційно:

1. Йди на https://www.google.com/alerts
2. Для кожного напрямку створи алерт типу:
   `site:linkedin.com/jobs "data analyst" remote`
3. У "Show options" постав **Delivery: RSS feed**.
4. Створи алерт, потім відкрий сторінку алертів → напроти нього буде
   іконка RSS — скопіюй посилання.
5. Встав усі такі посилання у `config.yaml`:
   ```yaml
   linkedin_alerts:
     enabled: true
     feed_urls:
       - "https://www.google.com/alerts/feeds/.../..."
       - "https://www.google.com/alerts/feeds/.../..."
   ```

## Крок 6. Telegram-бот

1. У Telegram напиши боту **@BotFather** → `/newbot` → дай ім'я.
   Отримаєш `TELEGRAM_BOT_TOKEN`.
2. Напиши своєму новому боту будь-яке повідомлення (щоб він міг тобі
   відповідати).
3. Дізнайся свій `chat_id`: напиши боту **@userinfobot** — він покаже
   твій ID (число).

## Крок 7. Додай секрети в GitHub

У репозиторії: **Settings → Secrets and variables → Actions → New
repository secret**. Додай чотири секрети:

| Назва секрету | Значення |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | весь вміст JSON-файлу з Кроку 2 (цілком, як текст) |
| `TELEGRAM_BOT_TOKEN` | токен з Кроку 6 |
| `TELEGRAM_CHAT_ID` | твій chat_id з Кроку 6 |
| `GEMINI_API_KEY` | ключ з Google AI Studio (aistudio.google.com/api-keys) |

**Про Gemini:** цей секрет опційний. Якщо його немає — агент рахує
Match Score локально (без AI) і працює як і раніше. Якщо є — для
вакансій, що вже пройшли локальний поріг (`min_score_to_report` у
config.yaml), Gemini додатково генерує розумніший короткий аналіз
"чому підходить". Виклики йдуть лише по вже відфільтрованих вакансіях,
щоб не витрачати денний ліміт безкоштовного тарифу даремно.

⚠️ Ключ Gemini — це такий самий секрет, як пароль. Нікому не показуй
його в незашифрованому вигляді (скріншотах для сторонніх, публічних
репозиторіях) і ніколи не вписуй прямо у файли коду — тільки через
GitHub Secret, як описано вище.

## Крок 8. Перевір вручну

У репозиторії: вкладка **Actions → Daily Job Search → Run workflow**
(кнопка справа) — запустить пайплайн одразу, не чекаючи завтрашнього
ранку. Дивись логи кроків, якщо щось не спрацювало — там буде видно,
на якому саме кроці й чому.

Далі агент буде запускатись автоматично щодня о 7:00 UTC, що завжди
потрапляє у вікно 9:00-10:00 за київським часом (з урахуванням переходу
на літній/зимовий час).

## Що робити, якщо якийсь сайт перестав повертати вакансії

Сайти регулярно змінюють розмітку сторінок. Якщо конкретне джерело
раптом почало повертати 0 результатів кілька днів поспіль:

1. Відкрий відповідний файл у `src/scrapers/<назва>.py`.
2. Зайди на сайт у браузері, відкрий DevTools (F12) → подивись, чи
   змінився URL пошуку або структура посилань на вакансії.
3. Скоригуй `LINK_PATTERN` або URL у файлі.

Кожен скрапер ізольований — якщо один сайт "зламався", решта джерел
продовжують працювати як звичайно (помилка одного джерела не зупиняє
весь щоденний прогін).
