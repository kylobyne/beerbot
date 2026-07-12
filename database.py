import random
import re
import sqlite3
import time

from config import (
    DATABASE_DIRECTORY,
    COOLDOWN_SECONDS,
    ROWS_PER_PAGE,
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