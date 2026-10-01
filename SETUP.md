# Налаштування агента пошуку вакансій (100% безкоштовно)

Все на безкоштовних тарифах: GitHub Actions (публічний або приватний
репозиторій, лише ВИКОНАННЯ — без внутрішнього розкладу),
cron-job.org (зовнішній щоденний тригер), Google Sheets (Service
Account), Telegram Bot API.

## Крок 1. Створи GitHub-репозиторій

1. Зайди на github.com → New repository → назви, наприклад, `job-search-agent`.
2. Обери **Private** (щоб дані не були публічними).
3. Заливаєш увесь цей проєкт у репозиторій (git init / git push, або
   просто перетягни файли через веб-інтерфейс "Add file → Upload files").

## Крок 2. Створи Google Service Account (для Sheets)

1. Йди на https://console.cloud.google.com/ → створи новий проєкт (або
   візьми існуючий).
2. У меню зліва: **APIs & Services → Library** → увімкни:
   - Google Sheets API
   - Google Drive API (потрібен лише тому, що `gspread` запитує scope
     `.../auth/drive` для роботи з таблицею за ID — жодні файли з
     Drive пайплайн не читає)
3. **APIs & Services → Credentials → Create Credentials → Service Account**.
   Назви як завгодно, наприклад `job-agent`.
4. Відкрий створений сервісний акаунт → вкладка **Keys → Add Key → Create
   new key → JSON**. Завантажиться файл — це твій `GOOGLE_SERVICE_ACCOUNT_JSON`.
5. Скопіюй email сервісного акаунта (виглядає як
   `job-agent@<project>.iam.gserviceaccount.com`) — він знадобиться далі.

## Крок 3. Google Sheets — таблиця звіту

Твоя таблиця вже є: https://docs.google.com/spreadsheets/d/1RYP2ub_m7sCtag-MLuZKeukyUhn9WkzvMRKnZ52jeDw/edit

Розшаруй її на сервісний акаунт:
1. Відкрий таблицю → **Share**.
2. Встав email сервісного акаунта з Кроку 2.
3. Права — **Editor** (агент має дописувати рядки).

ID таблиці вже вписаний у `config.yaml → google_sheets.spreadsheet_id`.
Агент сам створить аркуш (worksheet) кожного профілю (`Vacancies` для
AI, `Vacancies-iOS` для iOS — поле `worksheet` у `config.yaml`) і
заголовки колонок A–E при першому запуску, якщо їх ще немає. Колонки
правіше E — CANVA/EN/На адаптацію/Виконано/Feedback тощо — керуються
вручну, код їх не чіпає.

## Крок 4. Telegram-бот

1. У Telegram напиши боту **@BotFather** → `/newbot` → дай ім'я.
   Отримаєш `TELEGRAM_BOT_TOKEN`.
2. Напиши своєму новому боту будь-яке повідомлення (щоб він міг тобі
   відповідати).
3. Дізнайся свій `chat_id`: напиши боту **@userinfobot** — він покаже
   твій ID (число).
4. Хочеш отримувати картки в **канал**, а не в особистий чат:
   - додай бота в канал як **адміністратора** з правом *Post messages*
     (без цього Telegram відповідає `chat not found` / `need
     administrator rights`, і жодна картка не доходить);
   - `chat_id` каналу — число з `-100` на початку, наприклад
     `-1004434962721` (у web.telegram.org воно є в адресі
     `#-1004434962721`);
   - після зміни секрету запусти **Run workflow → telegram_check = true**:
     у лозі буде відповідь Telegram на getMe / getChat / sendMessage, а в
     канал прийде тестове повідомлення. Доки цей тест не зелений, не
     запускай повний пошук.

## Крок 5. Додай секрети в GitHub

У репозиторії: **Settings → Secrets and variables → Actions → New
repository secret**. Додай п'ять секретів:

| Назва секрету | Значення |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | весь вміст JSON-файлу з Кроку 2 (цілком, як текст) |
| `TELEGRAM_BOT_TOKEN` | токен з Кроку 4 |
| `TELEGRAM_CHAT_ID` | твій chat_id з Кроку 4 |
| `WORK_UA_EMAIL_ADDRESS` | Gmail-скринька для email-сповіщень (Work.ua, Robota.ua, LinkedIn) |
| `WORK_UA_EMAIL_APP_PASSWORD` | App Password цієї скриньки (Google Account → Security → App passwords) |

## Крок 5а. Email-сповіщення на кожен профіль

Work.ua, Robota.ua та LinkedIn не скрапляться напряму — агент читає
листи-сповіщення зі скриньки з Кроку 5 через IMAP. Для КОЖНОГО профілю
(AI Junior, iOS Middle+/Senior) створи окреме сповіщення на ту саму
адресу:

| Сайт | Де | Що задати |
|---|---|---|
| Work.ua | Збережені пошуки → дзвіночок "Сповіщення" + "Ел. пошта" | AI: "AI Engineer", без досвіду. iOS: "iOS Developer", досвід від 3 років |
| Robota.ua | Збережений пошук → email-сповіщення | те саме, віддалено |
| LinkedIn | Jobs → пошук → тумблер "Job alert" → Email, Daily | AI: Experience level Entry/Associate. iOS: Mid-Senior |

Лист не повідомляє, з якого сповіщення він прийшов: вакансія потрапляє в
той профіль, чий `title_regex` збігся з її назвою. Агент читає лише
НЕПРОЧИТАНІ листи й позначає їх прочитаними після успішного парсингу —
не відкривай ці листи вручну до ранкового прогону.

## Крок 6. Автоматичний щоденний запуск — через cron-job.org

Внутрішній розклад GitHub Actions (`schedule:` у workflow-файлі)
НАВМИСНО НЕ використовується — на цьому репозиторії він ненадійний:
реальні запуски затримувались на 4–7+ годин відносно заданого часу
(траплялись звіти о 15:00 і навіть 17:10 замість ранку). Тримати його
як "резервний" паралельний тригер теж не варіант: він лише вимагав
окремого захисту від подвійного звіту, не даючи жодної реальної
переваги. Тому `.github/workflows/daily_job_search.yml` має ЛИШЕ
`workflow_dispatch` — жодного `schedule:` там немає.

Щоденний тригер о 9:00 Europe/Kyiv налаштовано в безкоштовному сервісі
**cron-job.org**:

1. Зареєструйся на https://cron-job.org (безкоштовно).
2. Створи Personal Access Token у GitHub: **Settings акаунта →
   Developer settings → Personal access tokens → Fine-grained tokens**.
   - Repository access: обмеж лише цим репозиторієм.
   - Permissions → **Actions: Read and write**.
   - Expiration — постав конкретну дату (не "без обмежень") і онови
     токен заздалегідь до її настання: якщо він протермінується,
     тригер тихо перестане працювати (GitHub API поверне 401), а
     cron-job.org не сповіщає про це за замовчуванням — увімкни
     сповіщення про невдалі запуски в налаштуваннях job'у.
3. У cron-job.org створи новий Cron Job:
   - **URL:**
     `https://api.github.com/repos/<твій-акаунт>/data-job-search-agent/actions/workflows/daily_job_search.yml/dispatches`
   - **Метод:** POST
   - **Заголовки:**
     - `Authorization: Bearer <твій PAT>`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - **Тіло запиту:** `{"ref": "main"}`
   - **Розклад:** щодня, 09:00, часовий пояс `Europe/Kyiv` (сервіс сам
     враховує перехід на літній/зимовий час).
4. Перевір тестовим запуском кнопки "Run now" у cron-job.org — очікувана
   відповідь `204 No Content`, і в GitHub Actions одразу з'явиться новий
   запуск workflow "Daily Job Search". Далі перевір **Execution
   history** у cron-job.org за наступну добу — там має бути рівно ОДИН
   запис на день.

## Крок 7. Перевір вручну (без очікування щоденного тригера)

У репозиторії: вкладка **Actions → Daily Job Search → Run workflow**
(кнопка справа) — запустить пайплайн одразу. Перед агентом виконуються
тести (`pytest`) — якщо вони впали, агент не запускається. Дивись логи
кроків: для кожного профілю й джерела там видно, скільки вакансій
знайдено і скільки відкинуто за якою причиною.

## Що робити, якщо якийсь сайт перестав повертати вакансії

Сайти регулярно змінюють розмітку сторінок. Агент сам рахує дні, коли
джерело повертає 0 вакансій ще до фільтрів (`data/source_health.json`),
і після 3 нульових днів (7 для email-джерел; пороги в `config.yaml →
health`) надсилає попередження в Telegram. Коли таке попередження
прийшло:

1. Відкрий відповідний файл у `src/scrapers/<назва>.py`.
2. Зайди на сайт у браузері, відкрий DevTools (F12) → подивись, чи
   змінився URL пошуку або структура посилань на вакансії.
3. Скоригуй `LINK_PATTERN` або URL у файлі.

Кожен скрапер ізольований — якщо один сайт "зламався", решта джерел
продовжують працювати як звичайно (помилка одного джерела не зупиняє
весь щоденний прогін).
