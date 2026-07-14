import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Задайте BOT_TOKEN в файле .env")


# config.py
COOLDOWN_TIME = 5  # Время ограничения в секундах
COOLDOWN_SECONDS = 3600
ROWS_PER_PAGE = 20
PAGINATION_COOLDOWN_SECONDS = 3

DATABASE_DIRECTORY = Path("sqlite3")
DATABASE_DIRECTORY.mkdir(exist_ok=True)

# Товары
BUY_OPTIONS = {
    "5": {
        "attempts": 5,
        "stars": 15
    },

    "10": {
        "attempts": 10,
        "stars": 20
    },

    "15": {
        "attempts": 15,
        "stars": 25
    }
}

#Время жизни счета
INVOICE_LIFETIME = 600

# Интервал автоматической очистки базы данных в секундах (3600 секунд = 1 час)
DB_CLEAN_INTERVAL = 3600

# Время, через которое заброшенный инвойс удаляется из базы (30 минут = 1800 секунд)
INVOICE_CLEAN_THRESHOLD = 1800

ALLOWED_STATUSES = ["creator", "administrator", "member", "restricted"]
