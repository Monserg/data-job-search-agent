"""
Перевірка зв'язку з Telegram без запуску пошуку.

Запуск: Actions → Daily Job Search → Run workflow → telegram_check = true,
або локально:
  TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python src/telegram_check.py

Логує відповіді getMe / getChat / sendMessage і завершується з кодом 1,
якщо тестове повідомлення не дійшло — тоді в логу видно точну причину
від Telegram ("chat not found", "need administrator rights" тощо).
"""
import logging
import os
import sys

import telegram_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logging.error("Потрібні TELEGRAM_BOT_TOKEN і TELEGRAM_CHAT_ID.")
        return 1
    return 0 if telegram_client.check_connection(token, chat_id) else 1


if __name__ == "__main__":
    sys.exit(main())
