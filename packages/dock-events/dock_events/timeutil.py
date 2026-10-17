"""UTC timestamps in, UTC timestamps out. Local labels are for people."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be an ISO-8601 string with a timezone")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"bad timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {value!r} needs a timezone")
    return parsed.astimezone(timezone.utc)


def format_time(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("refusing to format a naive timestamp")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_local(value: str, zone: str = "America/New_York") -> str:
    """Short clock label, such as '2:06 PM ET' for America/New_York."""
    local = parse_time(value).astimezone(ZoneInfo(zone))
    hour = str(int(local.strftime("%I")))
    suffix = "ET" if zone == "America/New_York" else local.tzname() or zone
    return f"{hour}:{local.strftime('%M %p')} {suffix}"


def format_local_long(value: str, zone: str = "America/New_York") -> str:
    local = parse_time(value).astimezone(ZoneInfo(zone))
    hour = str(int(local.strftime("%I")))
    suffix = "ET" if zone == "America/New_York" else local.tzname() or zone
    return (
        f"{local.strftime('%a')} {local.strftime('%b')} {local.day}, {local.year}, "
        f"{hour}:{local.strftime('%M %p')} {suffix}"
    )
