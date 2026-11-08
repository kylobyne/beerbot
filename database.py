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
from time_utils import (
    duration_to_seconds,
    legacy_datetime_to_timestamp,
    local_datetime_to_timestamp,
    now_timestamp,
)


DRINK_ATTEMPT_RETENTION_SECONDS = 7 * 24 * 60 * 60
PATTERN_ANALYSIS_WINDOW_SECONDS = 7 * 24 * 60 * 60
PATTERN_ANALYSIS_MAX_ATTEMPTS = 101  # At most 100 adjacent intervals are scored.
AUTOFARM_DEFAULT_RANDOM_SPAN_SECONDS = 30 * 60 - 60  # Plugin fallback: random.randint(60, 1800).
PATTERN_MIN_INTERVALS = 4


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
            last_drink INTEGER NOT NULL DEFAULT 0,
            is_member INTEGER NOT NULL DEFAULT 1,
            membership_checked INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    drinker_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(drinkers)")
    }
    if "is_member" not in drinker_columns:
        connection.execute(
            "ALTER TABLE drinkers ADD COLUMN is_member INTEGER NOT NULL DEFAULT 1"
        )
    if "membership_checked" not in drinker_columns:
        connection.execute(
            "ALTER TABLE drinkers ADD COLUMN membership_checked INTEGER NOT NULL DEFAULT 0"
        )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS drink_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK (outcome IN ('success', 'cooldown')),
            liters REAL NOT NULL DEFAULT 0,
            cooldown_delay_seconds REAL,
            created_at INTEGER NOT NULL
        )
        """
    )

    attempt_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(drink_attempts)")
    }
    if "cooldown_delay_seconds" not in attempt_columns:
        connection.execute(
            "ALTER TABLE drink_attempts ADD COLUMN cooldown_delay_seconds REAL"
        )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS drink_identities (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mod_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0,
            updated_by INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, permission)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS drink_bans (
            user_id INTEGER PRIMARY KEY,
            banned_by INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS drink_ban_notices (
            user_id INTEGER PRIMARY KEY,
            last_sent_at INTEGER NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS mod_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_id INTEGER,
            details TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_drink_attempts_user_created
        ON drink_attempts (user_id, created_at)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_drink_attempts_created
        ON drink_attempts (created_at)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_drink_attempts_free_success
        ON drink_attempts (user_id, created_at DESC)
        WHERE outcome = 'success' AND cooldown_delay_seconds IS NOT NULL
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_drink_identities_username
        ON drink_identities (username COLLATE NOCASE)
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
                        SET name = ?, is_member = 1, membership_checked = 1
                        WHERE user_id = ?
                        """,
                        (name, user_id)
                    )
                else:
                    connection.execute(
                        """
                        UPDATE drinkers
                        SET is_member = 1, membership_checked = 1
                        WHERE user_id = ?
                        """,
                        (user_id,)
                    )

                return (
                    False,
                    float(remaining),
                    float(row["total_liters"]),
                    None,
                )

            cooldown_delay = (
                max(0, now - row["last_drink"] - COOLDOWN_SECONDS)
                if row["last_drink"] > 0
                else None
            )
        else:
            cooldown_delay = None

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

            is_member = 1,

            membership_checked = 1,

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

    return True, amount, float(total), cooldown_delay


def get_leaderboard(chat_id: int):
    """Возвращает участников чата с литрами >= 0.1 в порядке рейтинга."""
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
            SET name = ?, is_member = 1, membership_checked = 1
            WHERE user_id = ?
            """,
            (
                name,
                user_id
            )
        )

        connection.commit()


def get_unchecked_drinker_ids(chat_id: int) -> list[int]:
    """Returns ranked users whose membership has not been reconciled yet."""
    with get_connection(chat_id) as connection:
        rows = connection.execute(
            """
            SELECT user_id
            FROM drinkers
            WHERE total_liters >= 0.1 AND membership_checked = 0
            ORDER BY total_liters DESC
            """
        ).fetchall()

    return [row["user_id"] for row in rows]


def update_unchecked_drinker_memberships(
    chat_id: int,
    memberships: dict[int, bool],
) -> None:
    """Save successful background checks without overwriting newer member events."""
    if not memberships:
        return

    with get_connection(chat_id) as connection:
        connection.executemany(
            """
            UPDATE drinkers
            SET is_member = ?, membership_checked = 1
            WHERE user_id = ? AND membership_checked = 0
            """,
            [
                (int(is_member), user_id)
                for user_id, is_member in memberships.items()
            ],
        )
        connection.commit()


def set_drinker_membership(chat_id: int, user_id: int, is_member: bool) -> None:
    """Save a membership update received from Telegram."""
    with get_connection(chat_id) as connection:
        connection.execute(
            """
            UPDATE drinkers
            SET is_member = ?, membership_checked = 1
            WHERE user_id = ?
            """,
            (int(is_member), user_id),
        )
        connection.commit()


def remember_drinking_user(
    chat_id: int,
    user_id: int,
    username: str | None,
    full_name: str,
    updated_at: int | None = None,
):
    now = updated_at if updated_at is not None else int(time.time())
    with get_connection(chat_id) as connection:
        connection.execute(
            """
            INSERT INTO drink_identities (user_id, username, full_name, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                updated_at = excluded.updated_at
            """,
            (user_id, username, full_name, now),
        )


def resolve_drinking_user(chat_id: int, username: str) -> int | None:
    normalized_username = username.lstrip("@").casefold()
    with get_connection(chat_id) as connection:
        row = connection.execute(
            """
            SELECT user_id
            FROM drink_identities
            WHERE username = ? COLLATE NOCASE
            """,
            (normalized_username,),
        ).fetchone()
    return int(row["user_id"]) if row else None


def record_drink_attempt(
    chat_id: int,
    user_id: int,
    username: str | None,
    full_name: str,
    outcome: str,
    liters: float = 0,
    created_at: int | None = None,
    cooldown_delay_seconds: float | None = None,
):
    timestamp = created_at if created_at is not None else int(time.time())
    cutoff = timestamp - DRINK_ATTEMPT_RETENTION_SECONDS
    with get_connection(chat_id) as connection:
        connection.execute(
            """
            INSERT INTO drink_attempts
                (user_id, username, full_name, outcome, liters, cooldown_delay_seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, full_name, outcome, liters, cooldown_delay_seconds, timestamp),
        )
        connection.execute(
            "DELETE FROM drink_attempts WHERE created_at < ?",
            (cutoff,),
        )
        connection.execute(
            """
            INSERT INTO drink_identities (user_id, username, full_name, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                updated_at = excluded.updated_at
            """,
            (user_id, username, full_name, timestamp),
        )


def get_drink_history(
    chat_id: int,
    user_id: int,
    since: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    cutoff = since if since is not None else int(time.time()) - 48 * 60 * 60
    with get_connection(chat_id) as connection:
        rows = connection.execute(
            """
            SELECT outcome, liters, full_name, created_at
            FROM drink_attempts
            WHERE user_id = ? AND created_at >= ? AND outcome = 'success'
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, cutoff, limit, offset),
        ).fetchall()
        counts = connection.execute(
            """
            SELECT
                COUNT(*) AS attempts,
                COALESCE(SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END), 0) AS successes
            FROM drink_attempts
            WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, cutoff),
        ).fetchone()
    return rows, int(counts["attempts"]), int(counts["successes"])


def get_drink_accuracy(
    chat_id: int,
    user_id: int,
    since: int | None = None,
) -> tuple[float | None, int]:
    cutoff = since if since is not None else int(time.time()) - 48 * 60 * 60
    with get_connection(chat_id) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS samples,
                AVG(MAX(0.0, 100.0 * (1.0 - cooldown_delay_seconds / ?))) AS accuracy
            FROM drink_attempts
            WHERE user_id = ?
                AND created_at >= ?
                AND outcome = 'success'
                AND cooldown_delay_seconds IS NOT NULL
            """,
            (COOLDOWN_SECONDS, user_id, cutoff),
        ).fetchone()
    samples = int(row["samples"])
    return (float(row["accuracy"]) if samples else None, samples)


def get_drink_pattern_match(
    chat_id: int,
    user_id: int,
    since: int | None = None,
) -> tuple[float | None, int]:
    """Estimate how often recent free-drink intervals match AutoFarm-like schedules.

    The score is the best fit of a steady interval with random delay or a
    steadily increasing interval, using at most 100 intervals.
    """
    now = int(time.time())
    cutoff = max(
        since if since is not None else now - PATTERN_ANALYSIS_WINDOW_SECONDS,
        now - PATTERN_ANALYSIS_WINDOW_SECONDS,
    )
    with get_connection(chat_id) as connection:
        rows = connection.execute(
            """
            SELECT created_at
            FROM drink_attempts
            WHERE user_id = ?
                AND created_at >= ?
                AND outcome = 'success'
                AND cooldown_delay_seconds IS NOT NULL
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, cutoff, PATTERN_ANALYSIS_MAX_ATTEMPTS),
        ).fetchall()

    timestamps = [int(row["created_at"]) for row in reversed(rows)]
    intervals = [
        later - earlier
        for earlier, later in zip(timestamps, timestamps[1:])
        if later > earlier
    ]
    interval_count = len(intervals)
    if interval_count < PATTERN_MIN_INTERVALS:
        return None, interval_count

    # Model 1: a fixed base interval plus the plugin's default 1–30 minute jitter.
    ordered = sorted(intervals)
    left = 0
    best_steady_matches = 0
    for right, current in enumerate(ordered):
        while current - ordered[left] > AUTOFARM_DEFAULT_RANDOM_SPAN_SECONDS:
            left += 1
        best_steady_matches = max(best_steady_matches, right - left + 1)

    # Model 2: the plugin can add an accumulating delay after every send.
    mean_index = (interval_count - 1) / 2
    mean_interval = sum(intervals) / interval_count
    index_variance = sum((index - mean_index) ** 2 for index in range(interval_count))
    slope = sum(
        (index - mean_index) * (interval - mean_interval)
        for index, interval in enumerate(intervals)
    ) / index_variance
    intercept = mean_interval - slope * mean_index
    jitter_tolerance = AUTOFARM_DEFAULT_RANDOM_SPAN_SECONDS / 2
    increasing_matches = (
        sum(
            abs(interval - (intercept + slope * index)) <= jitter_tolerance
            for index, interval in enumerate(intervals)
        )
        if slope >= 0
        else 0
    )

    matched_intervals = max(best_steady_matches, increasing_matches)
    return 100.0 * matched_intervals / interval_count, interval_count


def get_mod_permissions(chat_id: int, user_id: int) -> dict[str, bool]:
    with get_connection(chat_id) as connection:
        rows = connection.execute(
            """
            SELECT permission, enabled
            FROM mod_permissions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()
    return {row["permission"]: bool(row["enabled"]) for row in rows}


def clear_mod_permissions(chat_id: int, user_id: int) -> int:
    with get_connection(chat_id) as connection:
        cursor = connection.execute(
            "DELETE FROM mod_permissions WHERE user_id = ?",
            (user_id,),
        )
    return cursor.rowcount


def set_mod_permission(
    chat_id: int,
    user_id: int,
    permission: str,
    enabled: bool,
    updated_by: int,
):
    with get_connection(chat_id) as connection:
        connection.execute(
            """
            INSERT INTO mod_permissions
                (user_id, permission, enabled, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, permission) DO UPDATE SET
                enabled = excluded.enabled,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (user_id, permission, int(enabled), updated_by, int(time.time())),
        )


def is_drink_banned(chat_id: int, user_id: int) -> bool:
    with get_connection(chat_id) as connection:
        row = connection.execute(
            "SELECT 1 FROM drink_bans WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row is not None


def claim_drink_ban_notice(
    chat_id: int,
    user_id: int,
    now: int | None = None,
) -> bool:
    timestamp = now if now is not None else int(time.time())
    with get_connection(chat_id) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT last_sent_at FROM drink_ban_notices WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row and timestamp - row["last_sent_at"] < 60:
            return False

        connection.execute(
            """
            INSERT INTO drink_ban_notices (user_id, last_sent_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_sent_at = excluded.last_sent_at
            """,
            (user_id, timestamp),
        )
    return True


def ban_drinking(chat_id: int, user_id: int, banned_by: int) -> bool:
    with get_connection(chat_id) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO drink_bans (user_id, banned_by, created_at)
            VALUES (?, ?, ?)
            """,
            (user_id, banned_by, int(time.time())),
        )
    return cursor.rowcount > 0


def unban_drinking(chat_id: int, user_id: int) -> bool:
    with get_connection(chat_id) as connection:
        cursor = connection.execute(
            "DELETE FROM drink_bans WHERE user_id = ?",
            (user_id,),
        )
    return cursor.rowcount > 0


def record_mod_audit(
    chat_id: int,
    actor_id: int,
    action: str,
    target_id: int | None = None,
    details: str = "",
):
    with get_connection(chat_id) as connection:
        connection.execute(
            """
            INSERT INTO mod_audit (actor_id, action, target_id, details, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (actor_id, action, target_id, details, int(time.time())),
        )


def get_mod_audit(chat_id: int, limit: int = 20, offset: int = 0):
    with get_connection(chat_id) as connection:
        return connection.execute(
            """
            WITH ordered AS (
                SELECT
                    id,
                    actor_id,
                    action,
                    target_id,
                    details,
                    created_at,
                    LAG(actor_id) OVER (ORDER BY id DESC) AS previous_actor_id,
                    LAG(action) OVER (ORDER BY id DESC) AS previous_action,
                    LAG(target_id) OVER (ORDER BY id DESC) AS previous_target_id,
                    LAG(details) OVER (ORDER BY id DESC) AS previous_details
                FROM mod_audit
            ),
            numbered AS (
                SELECT
                    *,
                    SUM(
                        CASE
                            WHEN actor_id IS previous_actor_id
                                AND action IS previous_action
                                AND target_id IS previous_target_id
                                AND details IS previous_details
                            THEN 0 ELSE 1
                        END
                    ) OVER (
                        ORDER BY id DESC
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS run_id
                FROM ordered
            ),
            grouped AS (
                SELECT
                    MAX(id) AS id,
                    MAX(actor_id) AS actor_id,
                    MAX(action) AS action,
                    MAX(target_id) AS target_id,
                    MAX(details) AS details,
                    MAX(created_at) AS created_at,
                    COUNT(*) AS repeat_count
                FROM numbered
                GROUP BY run_id
            )
            SELECT
                actor_id,
                action,
                target_id,
                details,
                created_at,
                repeat_count,
                (SELECT COUNT(*) FROM grouped) AS total_groups
            FROM grouped
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()


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
                total_liters,
                is_member,
                membership_checked
            )

            VALUES (?, ?, ?, 1, 1)


            ON CONFLICT(user_id)

            DO UPDATE SET

            name = excluded.name,

            is_member = 1,

            membership_checked = 1,


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


def _create_promocodes_table(cursor, table_name: str):
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            reward_type TEXT,
            reward_amount INTEGER DEFAULT 0,
            time_limited INTEGER DEFAULT 0,
            expires_at INTEGER,
            duration TEXT,
            activation_limited INTEGER DEFAULT 0,
            max_activations INTEGER,
            used_count INTEGER DEFAULT 0,
            bind_users TEXT,
            created_by INTEGER,
            created_at INTEGER,
            updated_at INTEGER,
            active INTEGER DEFAULT 1
        )
        """
    )


def _create_promo_uses_table(cursor, table_name: str):
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promo_id INTEGER,
            user_id INTEGER,
            used_at INTEGER
        )
        """
    )


def _migrate_timestamp_columns(cursor, table_name: str, timestamp_columns: tuple[str, ...], create_table):
    schema = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    if all(
        next((row[2].upper() for row in schema if row[1] == name), "") == "INTEGER"
        for name in timestamp_columns
    ):
        return

    columns = [row[1] for row in schema]
    rows = cursor.execute(f"SELECT {', '.join(columns)} FROM {table_name}").fetchall()
    temp_table = f"{table_name}_unix_migration"
    cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")
    create_table(cursor, temp_table)

    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(columns)
    for row in rows:
        values = list(row)
        for column in timestamp_columns:
            index = columns.index(column)
            values[index] = legacy_datetime_to_timestamp(values[index])
        cursor.execute(
            f"INSERT INTO {temp_table} ({column_list}) VALUES ({placeholders})",
            values,
        )

    cursor.execute(f"DROP TABLE {table_name}")
    cursor.execute(f"ALTER TABLE {temp_table} RENAME TO {table_name}")


def _normalize_promo_time_values(time_limited, expires_at, duration):
    if not time_limited:
        return None, None

    if duration:
        absolute_expiry = local_datetime_to_timestamp(duration, end_of_day=True)
        if absolute_expiry is not None:
            return absolute_expiry, None
        if duration_to_seconds(duration) is None:
            raise ValueError(f"Unsupported promo time value: {duration!r}")
        return None, duration

    if expires_at is None:
        return None, None
    if isinstance(expires_at, str):
        if expires_at.strip().isdigit():
            return int(expires_at.strip()), None
        timestamp = local_datetime_to_timestamp(expires_at, end_of_day=True)
        if timestamp is None:
            raise ValueError(f"Unsupported promo expiry value: {expires_at!r}")
        return timestamp, None
    return int(expires_at), None


def promo_connect():
    return sqlite3.connect(PROMO_DB)


def create_promo_database():
    db = promo_connect()
    cursor = db.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        _create_promocodes_table(cursor, "promocodes")
        _create_promo_uses_table(cursor, "promo_uses")
        _migrate_timestamp_columns(
            cursor,
            "promocodes",
            ("expires_at", "created_at", "updated_at"),
            _create_promocodes_table,
        )
        _migrate_timestamp_columns(
            cursor,
            "promo_uses",
            ("used_at",),
            _create_promo_uses_table,
        )

        legacy_duration_rows = cursor.execute(
            "SELECT id, duration, expires_at FROM promocodes WHERE duration IS NOT NULL"
        ).fetchall()
        for promo_id, duration, expires_at in legacy_duration_rows:
            if "." not in duration:
                continue
            try:
                legacy_expiry = legacy_datetime_to_timestamp(duration)
            except ValueError:
                continue
            cursor.execute(
                "UPDATE promocodes SET expires_at = COALESCE(expires_at, ?), duration = NULL WHERE id = ?",
                (legacy_expiry, promo_id),
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_promo(data):
    db = promo_connect()
    cursor = db.cursor()
    now = now_timestamp()
    expires_at, duration = _normalize_promo_time_values(
        data.get("time_limited", 0),
        data.get("expires_at"),
        data.get("duration"),
    )

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
            expires_at,
            duration,
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
    now = now_timestamp()
    expires_at, duration = _normalize_promo_time_values(
        data.get("time_limited", 0),
        data.get("expires_at"),
        data.get("duration"),
    )

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
            expires_at,
            duration,
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


def is_expires_at_expired(expires_at: int | str | None) -> bool:
    if expires_at is None or expires_at == "":
        return False
    timestamp = (
        legacy_datetime_to_timestamp(expires_at)
        if isinstance(expires_at, str) and not expires_at.strip().isdigit()
        else int(expires_at)
    )
    return now_timestamp() >= timestamp


def is_duration_expired(duration: str, created_at: int | str | None) -> bool:
    if not duration or not created_at:
        return False

    seconds = duration_to_seconds(duration)
    if seconds is None:
        return False

    created_timestamp = (
        legacy_datetime_to_timestamp(created_at)
        if isinstance(created_at, str) and not created_at.strip().isdigit()
        else int(created_at)
    )
    return now_timestamp() >= created_timestamp + seconds


def use_promo(promo_id: int, user_id: int):
    """Записывает использование промокода и проверяет, не исчерпан ли он."""
    db = promo_connect()
    cursor = db.cursor()

    now = now_timestamp()

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
            INSERT INTO drinkers
                (user_id, name, total_liters, is_member, membership_checked)
            VALUES (?, ?, ?, 1, 1)
            
            ON CONFLICT(user_id)
            DO UPDATE SET
            name = excluded.name,
            is_member = 1,
            membership_checked = 1,
            total_liters = ROUND(drinkers.total_liters + excluded.total_liters, 2)
            """,
            (user_id, name, amount)
        )
        connection.commit()


create_promo_database()
