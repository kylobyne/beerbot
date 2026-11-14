import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import database


class DatabaseConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_directory = Path(self.temp_dir.name)
        self.directory_patch = patch.object(database, "DATABASE_DIRECTORY", self.database_directory)
        self.directory_patch.start()
        self.addCleanup(self.directory_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def assert_connection_closed(self, connection):
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_chat_connection_commits_and_closes(self):
        connection = database.get_connection(123)
        self.addCleanup(connection.close)
        with connection as active_connection:
            active_connection.execute(
                "INSERT INTO drinkers (user_id, name) VALUES (?, ?)",
                (1, "Test User"),
            )

        self.assert_connection_closed(connection)

        with closing(sqlite3.connect(database.database_path(123))) as verification_connection:
            row = verification_connection.execute(
                "SELECT name FROM drinkers WHERE user_id = ?",
                (1,),
            ).fetchone()
        self.assertEqual(row[0], "Test User")

    def test_paid_connection_rolls_back_and_closes(self):
        paid_database_path = self.database_directory / "paid.sqlite3"
        with patch.object(database, "PAID_ATTEMPTS_DATABASE", paid_database_path):
            connection = database.get_paid_connection()
            self.addCleanup(connection.close)
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                with connection as active_connection:
                    active_connection.execute(
                        "INSERT INTO paid_attempts (user_id, attempts) VALUES (?, ?)",
                        (1, 5),
                    )
                    raise RuntimeError("rollback")

            self.assert_connection_closed(connection)
            with closing(sqlite3.connect(paid_database_path)) as verification_connection:
                row = verification_connection.execute(
                    "SELECT attempts FROM paid_attempts WHERE user_id = ?",
                    (1,),
                ).fetchone()
            self.assertIsNone(row)

    def test_chat_database_migration_preserves_rows_and_adds_columns(self):
        chat_path = self.database_directory / "chat_456.sqlite3"
        with closing(sqlite3.connect(chat_path)) as old_connection:
            old_connection.executescript(
                """
                CREATE TABLE drinkers (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    total_liters REAL NOT NULL DEFAULT 0,
                    last_drink INTEGER NOT NULL DEFAULT 0
                );
                INSERT INTO drinkers VALUES (7, 'Legacy User', 12.5, 100);
                CREATE TABLE drink_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    liters REAL NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL
                );
                INSERT INTO drink_attempts
                    (user_id, full_name, outcome, liters, created_at)
                VALUES (7, 'Legacy User', 'success', 1.5, 100);
                """
            )

        with database.get_connection(456) as connection:
            drinker_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(drinkers)")
            }
            attempt_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(drink_attempts)")
            }
            drinker = connection.execute(
                "SELECT name, total_liters FROM drinkers WHERE user_id = ?",
                (7,),
            ).fetchone()
            attempt = connection.execute(
                "SELECT full_name, liters FROM drink_attempts WHERE user_id = ?",
                (7,),
            ).fetchone()

        self.assertIn("is_member", drinker_columns)
        self.assertIn("membership_checked", drinker_columns)
        self.assertIn("cooldown_delay_seconds", attempt_columns)
        self.assertEqual(tuple(drinker), ("Legacy User", 12.5))
        self.assertEqual(tuple(attempt), ("Legacy User", 1.5))

    def test_leaderboard_keeps_unchecked_users_and_hides_known_nonmembers(self):
        with database.get_connection(789) as connection:
            connection.executemany(
                """
                INSERT INTO drinkers
                    (user_id, name, total_liters, is_member, membership_checked)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (1, "Left", 10, 0, 1),
                    (2, "Current", 8, 1, 1),
                    (3, "Legacy", 6, 1, 0),
                ],
            )

        self.assertEqual(
            [row["user_id"] for row in database.get_leaderboard(789)],
            [2, 3],
        )

        database.update_unchecked_drinker_memberships(789, {3: False})

        self.assertEqual(
            [row["user_id"] for row in database.get_leaderboard(789)],
            [2],
        )

    def test_free_cooldown_is_per_chat_and_paid_attempts_are_global(self):
        paid_database_path = self.database_directory / "paid.sqlite3"
        with (
            patch.object(database, "PAID_ATTEMPTS_DATABASE", paid_database_path),
            patch("database.time.time", return_value=100_000),
            patch("database.random.randint", return_value=10),
        ):
            first_chat = database.drink(100, 42, "Test User")
            same_chat = database.drink(100, 42, "Test User")
            other_chat = database.drink(200, 42, "Test User")

            self.assertTrue(first_chat[0])
            self.assertFalse(same_chat[0])
            self.assertTrue(other_chat[0])

            database.add_paid_attempts(42, 1)
            self.assertTrue(database.use_paid_attempt(42))
            self.assertFalse(database.use_paid_attempt(42))

    def test_promo_connection_closes_on_context_exit(self):
        with patch.object(database, "PROMO_DB", self.database_directory / "promo.sqlite3"):
            connection = database.promo_connect()
            with connection as active_connection:
                active_connection.execute("CREATE TABLE sample (value INTEGER)")

            self.assert_connection_closed(connection)


class PromoDatabaseRefactorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.promo_path = Path(self.temp_dir.name) / "promo.sqlite3"
        self.promo_path_patch = patch.object(database, "PROMO_DB", self.promo_path)
        self.promo_path_patch.start()
        self.addCleanup(self.promo_path_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)
        database.create_promo_database()

    def test_all_promos_page_uses_newest_first_order(self):
        for code in ("FIRST", "SECOND", "THIRD"):
            database.create_promo({"name": code})

        rows = database.get_all_promos_page()

        self.assertEqual([row[1] for row in rows], ["THIRD", "SECOND", "FIRST"])

    def test_missing_promo_timestamps_are_not_expired(self):
        with patch.object(database, "now_timestamp", return_value=200):
            self.assertFalse(database.is_expires_at_expired(None))
            self.assertFalse(database.is_duration_expired("2h", None))

    def test_promo_expiration_boundaries(self):
        with patch.object(database, "now_timestamp", return_value=200):
            self.assertTrue(database.is_expires_at_expired(199))
            self.assertTrue(database.is_expires_at_expired(200))
            self.assertFalse(database.is_expires_at_expired(201))
            self.assertTrue(database.is_duration_expired("1s", 199))
            self.assertFalse(database.is_duration_expired("1s", 200))

    def test_legacy_text_timestamps_migrate_without_losing_rows(self):
        self.promo_path.unlink()
        with closing(sqlite3.connect(self.promo_path)) as old_connection:
            old_connection.executescript(
                """
                CREATE TABLE promocodes (
                    id INTEGER PRIMARY KEY,
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
                );
                CREATE TABLE promo_uses (
                    id INTEGER PRIMARY KEY,
                    promo_id INTEGER,
                    user_id INTEGER,
                    used_at TEXT
                );
                INSERT INTO promocodes
                    (id, code, reward_type, expires_at, created_at, updated_at)
                VALUES (1, 'LEGACY', 'beer', '14.11.2026 12:00', '14.11.2026 10:00', '14.11.2026 10:00');
                INSERT INTO promo_uses (id, promo_id, user_id, used_at)
                VALUES (1, 1, 7, '14.11.2026 11:00');
                """
            )

        database.create_promo_database()

        with database.promo_connect() as connection:
            expiry_type = next(
                row[2] for row in connection.execute("PRAGMA table_info(promocodes)")
                if row[1] == "expires_at"
            )
            promo = connection.execute(
                "SELECT code, expires_at FROM promocodes WHERE id = 1"
            ).fetchone()
            usage = connection.execute(
                "SELECT promo_id, user_id, used_at FROM promo_uses WHERE id = 1"
            ).fetchone()

        self.assertEqual(expiry_type, "INTEGER")
        self.assertEqual(promo[0], "LEGACY")
        self.assertIsInstance(promo[1], int)
        self.assertEqual(usage[0:2], (1, 7))
        self.assertIsInstance(usage[2], int)


class PaidInvoiceSettlementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_directory = Path(self.temp_dir.name)
        self.directory_patch = patch.object(database, "DATABASE_DIRECTORY", self.database_directory)
        self.directory_patch.start()
        self.paid_path_patch = patch.object(
            database,
            "PAID_ATTEMPTS_DATABASE",
            self.database_directory / "paid.sqlite3",
        )
        self.paid_path_patch.start()
        self.addCleanup(self.directory_patch.stop)
        self.addCleanup(self.paid_path_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_settlement_is_atomic_and_idempotent(self):
        database.create_invoice("invoice-1", user_id=42, created_at=100)

        total = database.settle_paid_invoice("invoice-1", user_id=42, amount=10)
        duplicate = database.settle_paid_invoice("invoice-1", user_id=42, amount=10)

        self.assertEqual(total, 10)
        self.assertIsNone(duplicate)
        self.assertEqual(database.get_invoice_status("invoice-1"), "paid")
        self.assertEqual(database.get_paid_attempts(42), 10)

    def test_settlement_rejects_another_users_invoice(self):
        database.create_invoice("invoice-2", user_id=42, created_at=100)

        result = database.settle_paid_invoice("invoice-2", user_id=99, amount=10)

        self.assertIsNone(result)
        self.assertEqual(database.get_invoice_status("invoice-2"), "pending")
        self.assertEqual(database.get_paid_attempts(99), 0)

    def test_failed_credit_rolls_back_invoice_status(self):
        database.create_invoice("invoice-3", user_id=42, created_at=100)
        with database.get_paid_connection() as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_paid_attempts
                BEFORE INSERT ON paid_attempts
                BEGIN
                    SELECT RAISE(ABORT, 'test failure');
                END
                """
            )

        with self.assertRaises(sqlite3.IntegrityError):
            database.settle_paid_invoice("invoice-3", user_id=42, amount=10)

        self.assertEqual(database.get_invoice_status("invoice-3"), "pending")
        self.assertEqual(database.get_paid_attempts(42), 0)


if __name__ == "__main__":
    unittest.main()
