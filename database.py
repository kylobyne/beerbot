import random
import re
import sqlite3
import time
from datetime import datetime, timedelta

from config import (
    DATABASE_DIRECTORY,
    COOLDOWN_SECONDS,
    ROWS_PER_PAGE,
    INVOICE_CLEAN_THRESHOLD,
)


def database_path(chat_id: int):
    safe_chat_id = re.sub(
        r"[^0-9-]",
        "",
        str(chat_id)
    )

    return DATABASE_DIRECTORY / f"chat_{safe_chat_id}.sqlite3"


def get_connection(chat_id: int):

    connection = sqlite3.connect(
        database_path(chat_id)
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS drinkers (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            total_liters REAL NOT NULL DEFAULT 0,
            last_drink INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    connection.commit()

    return connection


def drink(chat_id: int, user_id: int, name: str):

    now = int(time.time())

    with get_connection(chat_id) as connection:

        row = connection.execute(
            """
            SELECT last_drink, name, total_liters
            FROM drinkers
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

        if row:

            remaining = COOLDOWN_SECONDS - (
                now - row["last_drink"]
            )

            if remaining > 0:

                if row["name"] != name:
                    connection.execute(
                        """
                        UPDATE drinkers
                        SET name = ?
                        WHERE user_id = ?
                        """,
                        (name, user_id)
                    )

                return (
                    False,
                    float(remaining),
                    float(row["total_liters"])
                )

        amount = round(
            random.randint(1, 50) / 10,
            2
        )

        connection.execute(
            """
            INSERT INTO drinkers
            (
                user_id,
                name,
                total_liters,
                last_drink
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(user_id)
            DO UPDATE SET

            name = excluded.name,

            total_liters =
            ROUND(
                drinkers.total_liters +
                excluded.total_liters,
                2
            ),

            last_drink =
            excluded.last_drink

            """,
            (
                user_id,
                name,
                amount,
                now
            )
        )

        total = connection.execute(
            """
            SELECT total_liters
            FROM drinkers
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()[0]

    return True, amount, float(total)


def get_leaderboard(chat_id: int):
    """Возвращает ВСЕХ пользователей чата с литрами >= 0.1 для последующей фильтрации."""
    with get_connection(chat_id) as connection:
        rows = connection.execute(
            """
            SELECT
                user_id,
                name,
                total_liters
            FROM drinkers
            WHERE total_liters >= 0.1
            ORDER BY
                total_liters DESC,
                name COLLATE NOCASE ASC
            """
        ).fetchall()

    return rows


def update_user_name(
    chat_id: int,
    user_id: int,
    name: str
):

    with get_connection(chat_id) as connection:

        connection.execute(
            """
            UPDATE drinkers
            SET name = ?
            WHERE user_id = ?
            """,
            (
                name,
                user_id
            )
        )

        connection.commit()


# ============================================================
# Платные дополнительные попытки (общая база для всех чатов)
# ============================================================

PAID_ATTEMPTS_DATABASE = DATABASE_DIRECTORY / "payd_attemps.sqlite3"


def get_paid_connection():

    connection = sqlite3.connect(
        PAID_ATTEMPTS_DATABASE
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS paid_attempts
        (
            user_id INTEGER PRIMARY KEY,
            attempts INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices
        (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'paid')),
            created_at INTEGER NOT NULL
        )
        """
    )

    connection.commit()

    return connection


def create_invoice(
    invoice_id: str,
    user_id: int,
    created_at: int
):
    """Создает запись инвойса со статусом ожидания оплаты."""
    with get_paid_connection() as connection:

        connection.execute(
            """
            INSERT INTO invoices (id, user_id, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (
                invoice_id,
                user_id,
                created_at
            )
        )

        connection.commit()


def get_invoice_status(invoice_id: str):
    """Возвращает текущий статус инвойса ('pending', 'paid') или None."""
    with get_paid_connection() as connection:

        row = connection.execute(
            """
            SELECT status
            FROM invoices
            WHERE id = ?
            """,
            (
                invoice_id,
            )
        ).fetchone()

        if not row:
            return None

        return row["status"]


def mark_invoice_as_paid(invoice_id: str) -> bool:
    """
    Переводит инвойс в статус 'paid' строго из статуса 'pending'.
    Защищает от состояния гонки и дублирующихся запросов Telegram.
    Возвращает True, если статус изменен (успех), иначе False.
    """
    with get_paid_connection() as connection:

        cursor = connection.execute(
            """
            UPDATE invoices
            SET status = 'paid'
            WHERE id = ? AND status = 'pending'
            """,
            (
                invoice_id,
            )
        )

        connection.commit()

        return cursor.rowcount > 0


def delete_old_pending_invoices():
    """Удаляет из базы все инвойсы в статусе 'pending', созданные ранее установленного порога."""
    expire_time = int(time.time()) - INVOICE_CLEAN_THRESHOLD

    with get_paid_connection() as connection:
        connection.execute(
            """
            DELETE FROM invoices
            WHERE status = 'pending' AND created_at < ?
            """,
            (expire_time,)
        )
        connection.commit()


def add_paid_attempts(
    user_id: int,
    amount: int
):

    with get_paid_connection() as connection:

        connection.execute(
            """
            INSERT INTO paid_attempts
            (
                user_id,
                attempts
            )

            VALUES (?, ?)


            ON CONFLICT(user_id)

            DO UPDATE SET

            attempts =
            attempts + excluded.attempts

            """,
            (
                user_id,
                amount
            )
        )

        connection.commit()


def get_paid_attempts(
    user_id: int
):

    with get_paid_connection() as connection:

        row = connection.execute(
            """
            SELECT attempts

            FROM paid_attempts

            WHERE user_id = ?
            """,
            (
                user_id,
            )
        ).fetchone()

        if not row:
            return 0

        return row["attempts"]


def use_paid_attempt(
    user_id: int
):

    with get_paid_connection() as connection:

        row = connection.execute(
            """
            SELECT attempts

            FROM paid_attempts

            WHERE user_id = ?
            """,
            (
                user_id,
            )
        ).fetchone()

        if not row or row["attempts"] <= 0:
            return False

        connection.execute(
            """
            UPDATE paid_attempts

            SET attempts = attempts - 1

            WHERE user_id = ?

            """,
            (
                user_id,
            )
        )

        connection.commit()

        return True


# ============================================================
# Выпивание за платную попытку
# Добавляет литры в рейтинг, но НЕ меняет last_drink
# ============================================================


def drink_paid(
    chat_id: int,
    user_id: int,
    name: str
):

    amount = round(
        random.randint(1, 50) / 10,
        2
    )

    with get_connection(chat_id) as connection:

        connection.execute(
            """
            INSERT INTO drinkers
            (
                user_id,
                name,
                total_liters
            )

            VALUES (?, ?, ?)


            ON CONFLICT(user_id)

            DO UPDATE SET

            name = excluded.name,


            total_liters =

            ROUND(
                drinkers.total_liters +
                excluded.total_liters,
                2
            )

            """,
            (
                user_id,
                name,
                amount
            )
        )

        total = connection.execute(
            """
            SELECT total_liters

            FROM drinkers

            WHERE user_id = ?

            """,
            (
                user_id,
            )
        ).fetchone()[0]

    return amount, float(total)


# =====================================
# PROMO DATABASE
# =====================================

PROMO_DB = "sqlite3/promo.sqlite3"


def promo_connect():
    return sqlite3.connect(PROMO_DB)


def create_promo_database():
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        reward_type TEXT,
        reward_amount INTEGER DEFAULT 0,
        time_limited INTEGER DEFAULT 0,
        expires_at TEXT,
        duration TEXT,
        activation_limited INTEGER DEFAULT 0,
        max_activations INTEGER,
        used_count INTEGER DEFAULT 0,
        bind_users TEXT,
        created_by INTEGER,
        created_at TEXT,
        updated_at TEXT,
        active INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promo_id INTEGER,
        user_id INTEGER,
        used_at TEXT
    )
    """)

    db.commit()
    db.close()


def create_promo(data):
    db = promo_connect()
    cursor = db.cursor()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    bind_users = data.get("bind_users")
    if isinstance(bind_users, list):
        bind_users = ",".join(str(uid) for uid in bind_users)
    elif bind_users:
        bind_users = str(bind_users)

    cursor.execute(
        """
        INSERT INTO promocodes (
            code,
            reward_type,
            reward_amount,
            time_limited,
            expires_at,
            duration,
            activation_limited,
            max_activations,
            bind_users,
            created_by,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data.get("reward_type"),
            data.get("reward_amount", 0),
            data.get("time_limited", 0),
            data.get("expires_at"),
            data.get("duration"),
            data.get("activation_limited", 0),
            data.get("max_activations"),
            bind_users,
            data.get("created_by"),
            now,
            now
        )
    )

    db.commit()
    db.close()


def get_promo(code):
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT *
        FROM promocodes
        WHERE code = ?
        """,
        (code,)
    )

    result = cursor.fetchone()
    db.close()

    return result


def get_all_promos_page(page=1, limit=10):
    offset = (page - 1) * limit

    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT *
        FROM promocodes
        ORDER BY active ASC, id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )

    result = cursor.fetchall()
    db.close()

    return result

def get_active_promos_page(page=1, limit=10):
    offset = (page - 1) * limit

    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT *
        FROM promocodes
        WHERE active = 1
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )

    result = cursor.fetchall()
    db.close()

    return result


def get_active_promos_count():
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM promocodes
        WHERE active = 1
        """
    )

    count = cursor.fetchone()[0]
    db.close()

    return count


def get_all_promos_page(page=1, limit=10):
    offset = (page - 1) * limit

    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT *
        FROM promocodes
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset)
    )

    result = cursor.fetchall()
    db.close()

    return result


def get_all_promos_count():
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM promocodes
        """
    )

    count = cursor.fetchone()[0]
    db.close()

    return count


def get_promos_page(page=1, limit=10):
    return get_active_promos_page(page, limit)


def get_promos_count():
    return get_active_promos_count()


def update_promo(code, data):
    db = promo_connect()
    cursor = db.cursor()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    bind_users = data.get("bind_users")
    if isinstance(bind_users, list):
        bind_users = ",".join(str(uid) for uid in bind_users)
    elif bind_users:
        bind_users = str(bind_users)

    cursor.execute(
        """
        UPDATE promocodes
        SET
        code = ?,
        reward_type = ?,
        reward_amount = ?,
        time_limited = ?,
        expires_at = ?,
        duration = ?,
        activation_limited = ?,
        max_activations = ?,
        bind_users = ?,
        updated_at = ?
        WHERE code = ?
        """,
        (
            data.get("name"),
            data.get("reward_type"),
            data.get("reward_amount", 0),
            data.get("time_limited", 0),
            data.get("expires_at"),
            data.get("duration"),
            data.get("activation_limited", 0),
            data.get("max_activations"),
            bind_users,
            now,
            code
        )
    )

    db.commit()
    db.close()


def delete_promo(code):
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        DELETE FROM promo_uses
        WHERE promo_id = (
            SELECT id
            FROM promocodes
            WHERE code = ?
        )
        """,
        (code,)
    )

    cursor.execute(
        """
        DELETE FROM promocodes
        WHERE code = ?
        """,
        (code,)
    )

    db.commit()
    db.close()


def has_used_promo(promo_id: int, user_id: int) -> bool:
    """Проверяет, активировал ли пользователь этот промокод."""
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM promo_uses
        WHERE promo_id = ? AND user_id = ?
        """,
        (promo_id, user_id)
    )

    count = cursor.fetchone()[0]
    db.close()

    return count > 0


def is_expires_at_expired(expires_at: str) -> bool:
    """
    Проверяет, истекла ли дата.
    Поддерживает форматы:
    - ДД.ММ.ГГГГ ЧЧ:ММ
    - ДД.ММ.ГГ ЧЧ:ММ
    - ДД.ММ.ГГГГ (до конца дня)
    - ДД.ММ.ГГ (до конца дня)
    """
    if not expires_at:
        return False
    
    try:
        expiry = datetime.strptime(expires_at, "%d.%m.%Y %H:%M")
        return datetime.now() > expiry
    except ValueError:
        pass
    
    try:
        expiry = datetime.strptime(expires_at, "%d.%m.%y %H:%M")
        return datetime.now() > expiry
    except ValueError:
        pass
    
    try:
        expiry = datetime.strptime(expires_at, "%d.%m.%Y")
        expiry = expiry.replace(hour=23, minute=59, second=59)
        return datetime.now() > expiry
    except ValueError:
        pass
    
    try:
        expiry = datetime.strptime(expires_at, "%d.%m.%y")
        expiry = expiry.replace(hour=23, minute=59, second=59)
        return datetime.now() > expiry
    except ValueError:
        pass
    
    return False


def is_duration_expired(duration: str, created_at: str) -> bool:
    """
    Проверяет, истекла ли длительность.
    Поддерживает форматы: 2d, 5h, 30m, 10s, 2d5h30m, 3h15m, 2h5s
    """
    if not duration or not created_at:
        return False
    
    try:
        created = datetime.strptime(created_at, "%d.%m.%Y %H:%M")
    except ValueError:
        return False
    
    days = 0
    hours = 0
    minutes = 0
    seconds = 0
    
    d_match = re.search(r'(\d+)d', duration)
    h_match = re.search(r'(\d+)h', duration)
    m_match = re.search(r'(\d+)m', duration)
    s_match = re.search(r'(\d+)s', duration)
    
    if d_match:
        days = int(d_match.group(1))
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    if s_match:
        seconds = int(s_match.group(1))
    
    expiry = created + timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )
    
    return datetime.now() > expiry


def use_promo(promo_id: int, user_id: int):
    """Записывает использование промокода и проверяет, не исчерпан ли он."""
    db = promo_connect()
    cursor = db.cursor()

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    cursor.execute(
        """
        INSERT INTO promo_uses (promo_id, user_id, used_at)
        VALUES (?, ?, ?)
        """,
        (promo_id, user_id, now)
    )

    cursor.execute(
        """
        UPDATE promocodes
        SET used_count = used_count + 1
        WHERE id = ?
        """,
        (promo_id,)
    )

    db.commit()
    db.close()

    if is_promo_exhausted(promo_id):
        db = promo_connect()
        cursor = db.cursor()
        cursor.execute("SELECT code FROM promocodes WHERE id = ?", (promo_id,))
        code = cursor.fetchone()[0]
        db.close()

        deactivate_promo(code)


def is_promo_exhausted(promo_id: int) -> bool:
    """Проверяет, исчерпан ли промокод (с учетом времени)."""
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT bind_users, activation_limited, max_activations, used_count,
               time_limited, expires_at, duration, created_at, active
        FROM promocodes
        WHERE id = ?
        """,
        (promo_id,)
    )

    promo = cursor.fetchone()

    if not promo:
        db.close()
        return True

    bind_users = promo[0]
    activation_limited = promo[1]
    max_activations = promo[2]
    used_count = promo[3]
    time_limited = promo[4]
    expires_at = promo[5]
    duration = promo[6]
    created_at = promo[7]
    active = promo[8]

    # Если уже неактивен
    if not active:
        db.close()
        return True

    # ПРОВЕРКА ВРЕМЕНИ
    if time_limited:
        # Проверка по expires_at
        if expires_at and is_expires_at_expired(expires_at):
            db.close()
            return True
        
        # Проверка по duration
        if duration and is_duration_expired(duration, created_at):
            db.close()
            return True

    # Проверка по лимиту активаций
    if activation_limited and used_count >= max_activations:
        db.close()
        return True

    # Проверка по привязанным пользователям
    if bind_users:
        user_ids = [int(uid.strip()) for uid in bind_users.split(",") if uid.strip()]

        for uid in user_ids:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM promo_uses
                WHERE promo_id = ? AND user_id = ?
                """,
                (promo_id, uid)
            )

            if cursor.fetchone()[0] == 0:
                db.close()
                return False

        db.close()
        return True

    db.close()
    return False


def deactivate_promo(code: str):
    """Деактивирует промокод."""
    db = promo_connect()
    cursor = db.cursor()

    cursor.execute(
        """
        UPDATE promocodes
        SET active = 0
        WHERE code = ?
        """,
        (code,)
    )

    db.commit()
    db.close()


def deactivate_expired_promos():
    """Деактивирует все промокоды с истекшим временем действия."""
    db = promo_connect()
    cursor = db.cursor()
    
    # Получаем все активные промокоды с ограничением по времени
    cursor.execute(
        """
        SELECT id, code, expires_at, duration, created_at, time_limited
        FROM promocodes
        WHERE active = 1 AND time_limited = 1
        """
    )
    
    promos = cursor.fetchall()
    db.close()
    
    for promo in promos:
        promo_id = promo[0]
        code = promo[1]
        expires_at = promo[2]
        duration = promo[3]
        created_at = promo[4]
        is_expired = False
        
        # Проверяем expires_at
        if expires_at and is_expires_at_expired(expires_at):
            is_expired = True
        
        # Проверяем duration
        if not is_expired and duration and is_duration_expired(duration, created_at):
            is_expired = True
        
        if is_expired:
            deactivate_promo(code)


def add_beer_reward(chat_id: int, user_id: int, name: str, amount: float):
    """Добавляет литры пива пользователю в чате."""
    with get_connection(chat_id) as connection:
        connection.execute(
            """
            INSERT INTO drinkers (user_id, name, total_liters)
            VALUES (?, ?, ?)
            
            ON CONFLICT(user_id)
            DO UPDATE SET
            name = excluded.name,
            total_liters = ROUND(drinkers.total_liters + excluded.total_liters, 2)
            """,
            (user_id, name, amount)
        )
        connection.commit()


create_promo_database()