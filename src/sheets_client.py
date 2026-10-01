"""
Пише рядки у Google Sheets таблицю зі структурою:
A: Дата додавання | B: Посада/Вакансія | C: Компанія | D: Джерело |
E: Посилання (URL)

Аркуш задається профілем (profiles.<name>.worksheet у config.yaml) і
створюється автоматично, якщо його немає. Колонки правіше E
заповнюються вручну і цим кодом не чіпаються.

Рядок, з якого починаються дані, — profiles.<name>.sheet_first_data_row
(за замовчуванням 2: одразу під заголовком). Якщо між заголовком і
даними є службовий рядок (фільтри по колонках, як у Vacancies-Frontend)
— став 3: код ніколи не пише вище цього рядка, а нові рядки додає
після останнього заповненого в колонці A. Запис іде в явно обчислений
діапазон, а не через append: append шукає "кінець таблиці" сам і
порожній службовий рядок міг би заповнити даними.

Значення пишуться як RAW: назва вакансії, що починається з "=" чи "+",
інакше була б інтерпретована Google Sheets як формула.

Авторизація — Service Account (GOOGLE_SERVICE_ACCOUNT_JSON).
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
    "Компанія",
    "Джерело",
    "Посилання (URL)",
]


def _get_client():
    raw_key = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw_key)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


DEFAULT_FIRST_DATA_ROW = 2


def _get_or_create_worksheet(gc, spreadsheet_id: str, worksheet_name: str):
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=10)
        ws.update(range_name="A1", values=[HEADER_ROW], value_input_option="RAW")
        return ws
    if not ws.row_values(1):
        ws.update(range_name="A1", values=[HEADER_ROW], value_input_option="RAW")
    return ws


def next_free_row(column_a_values: list, first_data_row: int) -> int:
    """
    Рядок для першого нового запису: після останнього непорожнього
    значення в колонці A, але не вище first_data_row. col_values
    повертає значення до останньої непорожньої клітинки включно, тому
    len(...) — номер останнього заповненого рядка.
    """
    first_data_row = max(int(first_data_row or DEFAULT_FIRST_DATA_ROW), 1)
    last_filled = len(column_a_values or [])
    return max(last_filled + 1, first_data_row)


def write_rows(ws, rows: list, first_data_row: int = DEFAULT_FIRST_DATA_ROW) -> int:
    """Пише rows з наступного вільного рядка; повертає номер цього рядка."""
    start = next_free_row(ws.col_values(1), first_data_row)
    needed = start + len(rows) - 1
    if needed > ws.row_count:
        ws.add_rows(needed - ws.row_count)
    ws.update(range_name=f"A{start}", values=rows, value_input_option="RAW")
    return start


def append_rows(spreadsheet_id: str, worksheet_name: str, rows: list,
                first_data_row: int = DEFAULT_FIRST_DATA_ROW) -> None:
    """rows: list[list] — у порядку колонок A-E (Дата, Посада, Компанія, Джерело, URL)."""
    if not rows:
        return
    gc = _get_client()
    ws = _get_or_create_worksheet(gc, spreadsheet_id, worksheet_name)
    write_rows(ws, rows, first_data_row)
