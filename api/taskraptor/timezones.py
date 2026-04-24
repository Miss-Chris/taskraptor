from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

UTC_ZONE = ZoneInfo("UTC")
DEFAULT_TIMEZONE = "UTC"


def get_user_zone(timezone_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return UTC_ZONE


def is_valid_timezone(timezone_name: str) -> bool:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return False
    return True


def normalize_to_utc(value: datetime, user_timezone: str | None) -> datetime:
    if timezone.is_naive(value):
        value = timezone.make_aware(value, get_user_zone(user_timezone))
    return value.astimezone(UTC)


def local_date_end_to_utc(value: date, user_timezone: str | None) -> datetime:
    local_end = datetime.combine(value, time.max)
    return normalize_to_utc(local_end, user_timezone)


def parse_user_datetime(value: str | None, user_timezone: str | None) -> tuple[datetime | None, bool]:
    if not value:
        return None, False

    text = value.strip()
    if not text:
        return None, False

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed_date = date.fromisoformat(text)
    except ValueError:
        parsed_date = None
    else:
        return local_date_end_to_utc(parsed_date, user_timezone), True

    parsed_datetime = datetime.fromisoformat(text)
    return normalize_to_utc(parsed_datetime, user_timezone), False


def serialize_datetime_with_local(
    value: datetime | None,
    user_timezone: str | None,
) -> dict[str, str | None]:
    zone = get_user_zone(user_timezone)
    if value is None:
        return {
            "utc": None,
            "local": None,
            "local_date": None,
            "timezone": zone.key,
        }

    utc_value = normalize_to_utc(value, DEFAULT_TIMEZONE)
    local_value = timezone.localtime(utc_value, zone)
    return {
        "utc": utc_value.isoformat(),
        "local": local_value.isoformat(),
        "local_date": local_value.date().isoformat(),
        "timezone": zone.key,
    }


def local_now_context(user_timezone: str | None, now: datetime | None = None) -> dict[str, str]:
    zone = get_user_zone(user_timezone)
    local_now = timezone.localtime(now or timezone.now(), zone)
    return {
        "timezone": zone.key,
        "local_now": local_now.isoformat(),
        "local_date": local_now.date().isoformat(),
    }
