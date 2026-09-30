"""
Пише рядки у Google Sheets таблицю зі структурою:
A: Дата додавання | B: Посада/Вакансія | C: Компанія | D: Джерело |
E: Посилання (URL)

Аркуш задається профілем (profiles.<name>.worksheet у config.yaml) і
створюється автоматично, якщо його немає. Колонки правіше E
заповнюються вручну і цим кодом не чіпаються.

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


def _get_or_create_worksheet(gc, spreadsheet_id: str, worksheet_name: str):
    sh = gc.open_by_key(spreadsheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=10)
        ws.append_row(HEADER_ROW, value_input_option="RAW")
        return ws
    if not ws.row_values(1):
        ws.append_row(HEADER_ROW, value_input_option="RAW")
    return ws


def append_rows(spreadsheet_id: str, worksheet_name: str, rows: list) -> None:
    """rows: list[list] — у порядку колонок A-E (Дата, Посада, Компанія, Джерело, URL)."""
    if not rows:
        return
    gc = _get_client()
    ws = _get_or_create_worksheet(gc, spreadsheet_id, worksheet_name)
    ws.append_rows(rows, value_input_option="RAW")
