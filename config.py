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
# Пауза между командами /stats в одном чате, в секундах.
STATS_COOLDOWN_SECONDS = 10
# Количество строк на одной странице рейтинга и статистики.
ROWS_PER_PAGE = 20
# Количество записей аудита на странице.
MOD_AUDIT_PAGE_SIZE = 10
# Количество администраторов на странице настроек прав.
MOD_ADMINS_PAGE_SIZE = 10
# Количество записей истории питья на странице.
MOD_HISTORY_PAGE_SIZE = 10
# Пауза между запросами страниц, чтобы ограничить частые нажатия кнопок, в секундах.
PAGINATION_COOLDOWN_SECONDS = 3
# Часовой пояс для отображения дат и ввода абсолютных дат промокодов.
TIMEZONE = "Europe/Moscow"

# Каталог, где хранятся SQLite-базы чатов и промокодов.
DATABASE_DIRECTORY = Path("sqlite3")
DATABASE_DIRECTORY.mkdir(exist_ok=True)

# Резервные копии SQLite хранятся отдельно от рабочих баз.
SQLITE_BACKUP_DIRECTORY = Path("sqlite3_backups")
SQLITE_BACKUP_DIRECTORY.mkdir(exist_ok=True)

# Автобекап выключен по умолчанию; включение задаётся через .env или окружение процесса.
SQLITE_AUTOBACKUP_ENABLED = os.getenv("SQLITE_AUTOBACKUP_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
# Часовой пояс TIMEZONE и этот час используются для расписания автобэкапов.
SQLITE_AUTOBACKUP_HOUR = 4
if not 0 <= SQLITE_AUTOBACKUP_HOUR <= 23:
    raise ValueError("SQLITE_AUTOBACKUP_HOUR must be between 0 and 23")
# Количество календарных дней между резервными копиями.
SQLITE_AUTOBACKUP_INTERVAL_DAYS = 1
if SQLITE_AUTOBACKUP_INTERVAL_DAYS <= 0:
    raise ValueError("SQLITE_AUTOBACKUP_INTERVAL_DAYS must be positive")

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
