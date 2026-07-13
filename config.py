import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Задайте BOT_TOKEN в файле .env")


COOLDOWN_SECONDS = 60 * 60
ROWS_PER_PAGE = 20
PAGINATION_COOLDOWN_SECONDS = 3


DATABASE_DIRECTORY = Path("sqlite3")
DATABASE_DIRECTORY.mkdir(exist_ok=True)