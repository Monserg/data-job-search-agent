"""
Читає всі .pdf з обраної папки Google Drive (12 резюме) і повертає
{назва_файлу: витягнутий_текст}.

Авторизація — через Service Account (безкоштовно, без ліміту для такого
обсягу запитів). Кроки налаштування — у SETUP.md.

GOOGLE_SERVICE_ACCOUNT_JSON — вміст JSON-ключа сервісного акаунта,
переданий через змінну середовища (у GitHub Actions — через Secrets).
"""
import io
import json
import os

import pdfplumber
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _get_drive_service():
    raw_key = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw_key)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _list_pdfs(service, folder_id: str) -> list:
    query = f"'{folder_id}' in parents and mimeType = 'application/pdf' and trashed = false"
    resp = service.files().list(q=query, fields="files(id, name)").execute()
    files = resp.get("files", [])
    if not files:
        raise RuntimeError(
            f"У папці Drive (ID: {folder_id}) не знайдено жодного .pdf. "
            "Перевір, що папку розшарено на email сервісного акаунта "
            "(Share -> вставити email -> Viewer)."
        )
    return files


def _download_and_extract_text(service, file_id: str) -> str:
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)

    text_parts = []
    with pdfplumber.open(buf) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def load_resumes(folder_id: str) -> dict:
    service = _get_drive_service()
    pdf_files = _list_pdfs(service, folder_id)

    resumes = {}
    for f in pdf_files:
        resumes[f["name"]] = _download_and_extract_text(service, f["id"])
    return resumes
