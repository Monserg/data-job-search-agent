"""
Пише рядки у Google Sheets таблицю зі структурою:
A: Дата додавання | B: Посада/Вакансія | C: Компанія & Джерело |
D: Посилання (URL) | E: Match Score (%) | F: Короткий аналіз |
G: Рекомендоване CV | H: Пріоритет | I: CANVA | J: EN | K: На адаптацію
(L: Виконано, M: Feedback — керуються вручну, код туди не пише)

Рядок 1 — заголовок, рядок 2 — ручний рядок фільтрів користувача.
Обидва рядки код ніколи не чіпає; нові дані вставляються з рядка 3.

Авторизація — той самий Service Account, що й для Google Drive
(GOOGLE_SERVICE_ACCOUNT_JSON), просто з іншим scope.
"""
import json
import os

import gspread
from google.oauth2 import service_account

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW = [
    "Дата додавання",
    "Посада / Вакансія",
    "Компанія & Джерело",
    "Посилання (URL)",
    "Match Score (%)",
    "Короткий аналіз (чому підходить)",
    "Рекомендоване CV",
    "Пріоритет",
    "CANVA",
    "EN",
    "На адаптацію",
]


def _get_client():
    raw_key = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw_key)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_worksheet(gc, spreadsheet_id: str, worksheet_name: str):
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=len(HEADER_ROW))
        ws.append_row(HEADER_ROW)
    if ws.row_count == 0 or not ws.row_values(1):
        ws.append_row(HEADER_ROW)
    return ws


def append_rows(spreadsheet_id: str, worksheet_name: str, rows: list) -> None:
    """
    rows: list[list] — вже у порядку колонок A-K, і вже відсортовані за
    ярусом (Tier 1 → 2 → 3) усередині одного запуску, як формує main.py.

    Назва функції лишена для сумісності (main.py її й досі викликає), але
    поведінка змінена: замість дописування в кінець таблиці рядки
    ВСТАВЛЯЮТЬСЯ у рядок 3 (не 2!). Рядок 1 — заголовок, рядок 2 —
    ручний рядок фільтрів користувача, який ніколи не повинен рухатись
    чи перезаписуватись. Свіжі вакансії щодня опиняються одразу під
    фільтрами, а порядок усередині сьогоднішньої партії (Tier 1→2→3)
    зберігається, бо вона вставляється одним блоком.
    """
    if not rows:
        return
    gc = _get_client()
    ws = _get_or_create_worksheet(gc, spreadsheet_id, worksheet_name)
    ws.insert_rows(rows, row=3, value_input_option="USER_ENTERED")
