from datetime import datetime, timezone
import re
from typing import Final
from zoneinfo import ZoneInfo

from config import TIMEZONE as TIMEZONE_NAME

TIMEZONE = ZoneInfo(TIMEZONE_NAME)

LOCAL_DATETIME_FORMATS: Final = (
    ("%d.%m.%Y %H:%M:%S", False),
    ("%d.%m.%y %H:%M:%S", False),
    ("%d.%m.%Y %H:%M", False),
    ("%d.%m.%y %H:%M", False),
    ("%d.%m.%Y", True),
    ("%d.%m.%y", True),
)
DURATION_PATTERN: Final = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")


def now_timestamp() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def to_local_datetime(timestamp: int | float) -> datetime:
    return datetime.fromtimestamp(timestamp, TIMEZONE)


def format_timestamp(timestamp: int | float, date_format: str = "%d.%m.%Y %H:%M:%S") -> str:
    return to_local_datetime(timestamp).strftime(date_format)


def parse_local_datetime(value: str, end_of_day: bool = False) -> datetime | None:
    value = value.strip()
    for date_format, is_date_only in LOCAL_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(value, date_format)
        except ValueError:
            continue
        if is_date_only and end_of_day:
            parsed = parsed.replace(hour=23, minute=59, second=59)
        return parsed.replace(tzinfo=TIMEZONE)
    return None


def local_datetime_to_timestamp(value: str, end_of_day: bool = False) -> int | None:
    parsed = parse_local_datetime(value, end_of_day=end_of_day)
    return int(parsed.timestamp()) if parsed is not None else None


def duration_to_seconds(value: str) -> int | None:
    match = DURATION_PATTERN.fullmatch(value.strip())
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def legacy_datetime_to_timestamp(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if text.isdigit():
        return int(text)

    for date_format, is_date_only in LOCAL_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, date_format)
        except ValueError:
            continue
        if is_date_only:
            parsed = parsed.replace(hour=23, minute=59, second=59)
        return int(parsed.replace(tzinfo=timezone.utc).timestamp())
    raise ValueError(f"Unsupported legacy datetime value: {text!r}")