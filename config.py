import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


# Токен Telegram-бота из переменной BOT_TOKEN в файле .env.
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("Задайте BOT_TOKEN в файле .env")


# Пауза между нажатиями кнопок покупки одним пользователем, в секундах.
COOLDOWN_TIME = 5
# Интервал между бесплатными командами /beer одного пользователя в одном чате, в секундах.
COOLDOWN_SECONDS = 3600
# Количество строк на одной странице рейтинга и статистики.
ROWS_PER_PAGE = 20
# Пауза между запросами страниц, чтобы ограничить частые нажатия кнопок, в секундах.
PAGINATION_COOLDOWN_SECONDS = 3
# Часовой пояс для отображения дат и ввода абсолютных дат промокодов.
TIMEZONE = "Europe/Moscow"

# Каталог, где хранятся SQLite-базы чатов и промокодов.
DATABASE_DIRECTORY = Path("sqlite3")
DATABASE_DIRECTORY.mkdir(exist_ok=True)

# Пакеты дополнительных попыток: ключ — идентификатор варианта, attempts — число попыток,
# stars — цена в Telegram Stars.
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

# Срок действия неоплаченного счёта, в секундах.
INVOICE_LIFETIME = 600

# Как часто запускать фоновую очистку устаревших счетов и просроченных промокодов, в секундах.
DB_CLEAN_INTERVAL = 3600

# Удалять неоплаченные счета старше этого срока, в секундах.
INVOICE_CLEAN_THRESHOLD = 1800

# Статусы участников чата, которым бот разрешает пользоваться командами.
ALLOWED_STATUSES = ["creator", "administrator", "member", "restricted"]

# Telegram ID пользователей, которым доступна административная панель бота.
admins = [
    7697996660
]
# Количество промокодов на одной странице панели администратора.
PROMOS_PER_PAGE = 10
