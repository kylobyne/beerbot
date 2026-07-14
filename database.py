import random
import re
import sqlite3
import time

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
            random.randint(1,50) / 10,
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



def get_leaderboard(chat_id:int,page:int):

    with get_connection(chat_id) as connection:

        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM drinkers
            WHERE total_liters >= 0.1
            """
        ).fetchone()[0]


        pages = max(
            1,
            (total + ROWS_PER_PAGE - 1)
            // ROWS_PER_PAGE
        )


        page = max(
            0,
            min(page,pages-1)
        )


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

            LIMIT ?
            OFFSET ?

            """,
            (
                ROWS_PER_PAGE,
                page * ROWS_PER_PAGE
            )
        ).fetchall()


    return rows,pages



def update_user_name(
    chat_id:int,
    user_id:int,
    name:str
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


    # Таблица для хранения купленных попыток пользователей
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS paid_attempts
        (
            user_id INTEGER PRIMARY KEY,
            attempts INTEGER NOT NULL DEFAULT 0
        )
        """
    )


    # ТАБЛИЦА ИНВОЙСОВ: проверка уникальности чеков и времени создания
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
    import time
    
    # Вычитаем порог времени из текущего Unix-timestamp
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
