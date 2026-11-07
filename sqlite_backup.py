import asyncio
import logging
import os
import shutil
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone

from config import (
    DATABASE_DIRECTORY,
    SQLITE_AUTOBACKUP_INTERVAL_SECONDS,
    SQLITE_BACKUP_DIRECTORY,
)


BACKUP_TIME_FORMAT = "%d.%m.%Y %H:%M (GMT)"
WINDOWS_BACKUP_TIME_FORMAT = "%d.%m.%Y %H-%M (GMT)"


def _backup_time_from_folder(folder_name: str) -> datetime | None:
    for time_format in (BACKUP_TIME_FORMAT, WINDOWS_BACKUP_TIME_FORMAT):
        try:
            return datetime.strptime(folder_name, time_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _latest_backup_time() -> datetime | None:
    if not SQLITE_BACKUP_DIRECTORY.exists():
        return None

    backup_times = (
        backup_time
        for path in SQLITE_BACKUP_DIRECTORY.iterdir()
        if path.is_dir()
        for backup_time in [_backup_time_from_folder(path.name)]
        if backup_time is not None
    )
    return max(backup_times, default=None)


def _seconds_until_next_backup() -> float:
    latest_backup = _latest_backup_time()
    if latest_backup is None:
        return 0

    elapsed = (datetime.now(timezone.utc) - latest_backup).total_seconds()
    return max(0, SQLITE_AUTOBACKUP_INTERVAL_SECONDS - elapsed)


def create_sqlite_backup() -> str | None:
    """Create a consistent snapshot of every SQLite database in one timestamped folder."""
    source_files = sorted(DATABASE_DIRECTORY.glob("*.sqlite3"))
    if not source_files:
        logging.info("[SQLite backup] No database files found in %s", DATABASE_DIRECTORY)
        return None

    SQLITE_BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    folder_name = now.strftime(BACKUP_TIME_FORMAT)
    if os.name == "nt":
        folder_name = folder_name.replace(":", "-")

    backup_directory = SQLITE_BACKUP_DIRECTORY / folder_name
    if backup_directory.exists():
        logging.info("[SQLite backup] Backup already exists for %s", folder_name)
        return str(backup_directory)

    staging_directory = SQLITE_BACKUP_DIRECTORY / f".pending-{uuid.uuid4().hex}"
    staging_directory.mkdir()

    try:
        for source_file in source_files:
            destination_file = staging_directory / source_file.name
            with closing(sqlite3.connect(source_file, timeout=30)) as source:
                with closing(sqlite3.connect(destination_file, timeout=30)) as destination:
                    source.backup(destination)

        staging_directory.rename(backup_directory)
    except Exception:
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise

    logging.info(
        "[SQLite backup] Saved %d database(s) to %s",
        len(source_files),
        backup_directory,
    )
    return str(backup_directory)


async def periodic_sqlite_backup() -> None:
    retry_seconds = min(SQLITE_AUTOBACKUP_INTERVAL_SECONDS, 60 * 60)

    while True:
        try:
            delay = await asyncio.to_thread(_seconds_until_next_backup)
            if delay:
                await asyncio.sleep(delay)

            backup_path = await asyncio.to_thread(create_sqlite_backup)
            if backup_path is None:
                await asyncio.sleep(retry_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("[SQLite backup] Backup failed; retrying later")
            await asyncio.sleep(retry_seconds)
