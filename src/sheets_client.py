"""
Пише рядки у Google Sheets таблицю зі структурою:
A: Дата додавання | B: Посада/Вакансія | C: Компанія & Джерело |
D: Посилання (URL) | E: Match Score (%) | F: Короткий аналіз |
G: Рекомендоване CV

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
    """rows: list[list] — вже у порядку колонок A-G."""
    if not rows:
        return
    gc = _get_client()
    ws = _get_or_create_worksheet(gc, spreadsheet_id, worksheet_name)
    ws.append_rows(rows, value_input_option="USER_ENTERED")
