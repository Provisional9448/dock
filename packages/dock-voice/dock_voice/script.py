"""What the line says and how answers map to events. Pure functions; no guava import."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROLES = ("driver", "shipper", "consignee", "broker")

DRIVER_STATUS = {
    "checked in, waiting for a door": "arrived",
    "still waiting": "waiting",
    "unload started": "unload_started",
    "unload finished": "unload_done",
}


def pick_role(answer: object) -> str:
    """'Driver. Hi, this is Luis' -> driver. Names on the load count too, so a caller who opens with who they
    are is never asked again."""
    text = str(answer or "").lower()
    first = None
    for role in ROLES:
        at = text.find(role)
        if at >= 0 and (first is None or at < first[0]):
            first = (at, role)
    if first:
        return first[1]
    names = {
        "consignee": ("receiver", "receiving", "dc", "warehouse", "harbor", "dock office", "priya"),
        "shipper": ("northwind", "sam ", "sam,", "sam.", "this is sam"),
        "broker": ("lantern", "alex"),
        "driver": ("carrier", "dispatch", "truck", "luis", "red kettle"),
    }
    for role, words in names.items():
        if any(re.search(rf"\b{re.escape(word.strip(' ,.'))}\b", text) for word in words):
            return role
    return "driver"


def pick_status(answer: object) -> str:
    """Waiting beats unloading: 'waiting to start unloading' is a wait, not an unload start."""
    text = " ".join(str(answer or "").lower().split())
    if text in DRIVER_STATUS:
        return DRIVER_STATUS[text]
    if "still" in text and "wait" in text:
        return "waiting"
    if any(w in text for w in ("waiting", "wait for", "checked in", "check in", "no door", "not ready", "not unloading")):
        return "waiting" if "still" in text else "arrived"
    if any(w in text for w in ("finished", "done unloading", "unload done", "unload finished", "empty", "all done")):
        return "unload_done"
    if any(w in text for w in ("started unloading", "start unloading", "unload started", "they're unloading",
                               "they are unloading", "unloading now", "unloading me", "began unloading")):
        return "unload_started"
    if "still" in text:
        return "waiting"
    return "arrived"


def spoken(text: str) -> str:
    """Text the line will say aloud: 'ET' is read as 'eat' by TTS, so say 'Eastern'; '$0.00' -> 'zero dollars'."""
    out = re.sub(r"\bET\b", "Eastern", text)
    out = out.replace("$0.00", "zero dollars")
    return out


def span_words(minutes: int | None) -> str:
    """118 -> '1 hour 58 minutes'."""
    if minutes is None:
        return ""
    hours, mins = divmod(int(minutes), 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if mins or not hours:
        parts.append(f"{mins} minute" + ("s" if mins != 1 else ""))
    return " ".join(parts)


def money_line(snap: dict) -> str:
    """The clock in one sentence, with the rate, so $0.00 is never said without context."""
    s = snap["summary"]
    rate = snap["policy"]
    per_hour = str(rate["rate_usd_per_hour"]).removesuffix(".00")
    steps = f"billed in {rate['increment_minutes']}-minute steps"
    if s["phase"] in ("running", "warning"):
        return (
            f"Free time ends at {s['free_time_ends_local']}, {span_words(s['remaining_free_minutes'])} from now. "
            f"No charges yet; detention is ${per_hour} an hour after {s['free_time_ends_local']}, {steps}."
        )
    if s["phase"] == "accruing":
        return (
            f"Free time ended at {s['free_time_ends_local']}. The detention estimate is ${s['estimated_charge_usd']} "
            f"so far at ${per_hour} an hour, {steps}. It is an estimate, not an invoice."
        )
    if s["phase"] == "closed":
        return f"The clock is stopped. The record supports ${s['estimated_charge_usd']} of detention. It is not an invoice."
    return "No detention clock is running yet."


_NUMBER_WORDS = {
    "five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "twenty-five": 25, "twenty five": 25, "thirty": 30,
    "thirty-five": 35, "thirty five": 35, "forty": 40, "forty-five": 45, "forty five": 45, "fifty": 50,
    "sixty": 60, "ninety": 90,
}
_CLOCK_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*([ap])?\.?\s*m?\.?\b", re.I)
_HOUR_AMPM_RE = re.compile(r"\b(\d{1,2})\s*([ap])\.?\s*m\b\.?", re.I)
_AGO_RE = re.compile(r"\b(\d{1,3}|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")\s*min\w*\s+ago\b", re.I)


def parse_minutes(answer: object) -> int | None:
    """'maybe 40 minutes', 'another 20', 'half an hour', 'an hour and a half' -> minutes. None if no estimate."""
    text = " ".join(str(answer or "").lower().replace("–", "-").split())
    if not text:
        return None
    text = _CLOCK_RE.sub(" ", text)
    if "hour and a half" in text or "hour and half" in text:
        return 90
    if "half an hour" in text or "half hour" in text:
        return 30
    match = re.search(r"\b(\d{1,3})\s*(?:min|minutes|mins)\b", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d{1,2})\s*hours?\b", text)
    if match:
        return int(match.group(1)) * 60
    for word in sorted(_NUMBER_WORDS, key=len, reverse=True):
        if re.search(rf"\b{word}\b", text):
            return _NUMBER_WORDS[word]
    if re.search(r"\b(an|one) hour\b", text):
        return 60
    match = re.search(r"\b(?:another|about|maybe|around|like|in)\s+(\d{1,3})\b", text)
    if match:
        return int(match.group(1))
    return None


def parse_clock(answer: object, now: datetime, zone: str, *, ahead_minutes: int = 15) -> datetime | None:
    """A time the caller said ('2:06', '2:06 PM', '4:48', '10 minutes ago', 'just now') -> UTC datetime.

    No AM/PM: the latest reading not more than `ahead_minutes` past now. None if nothing sensible."""
    text = " ".join(str(answer or "").lower().split())
    if not text:
        return None
    if re.search(r"\bnow\b", text) and not re.search(r"\d", text):
        return now
    ago = _AGO_RE.search(text)
    if ago:
        raw = ago.group(1)
        minutes = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
        return now - timedelta(minutes=minutes)
    tz = ZoneInfo(zone)
    local_now = now.astimezone(tz)
    hour = minute = None
    half = None
    match = _CLOCK_RE.search(text)
    if match:
        hour, minute, half = int(match.group(1)), int(match.group(2)), match.group(3)
    else:
        match = _HOUR_AMPM_RE.search(text)
        if match:
            hour, minute, half = int(match.group(1)), 0, match.group(2)
    if hour is None or minute is None or minute > 59 or hour > 23:
        return None
    if half:
        if hour > 12:
            return None
        hours = [(hour % 12) + (12 if half.lower() == "p" else 0)]
    elif hour >= 13 or hour == 0:
        hours = [hour]
    else:
        hours = [hour % 12, hour % 12 + 12]
    limit = now + timedelta(minutes=ahead_minutes)
    best = None
    for h in hours:
        for days in (0, -1):
            moment = (local_now + timedelta(days=days)).replace(hour=h, minute=minute, second=0, microsecond=0)
            moment = moment.astimezone(timezone.utc)
            if moment <= limit and (best is None or moment > best):
                best = moment
    if best is None or now - best > timedelta(hours=12):
        return None
    return best


def driver_readback(snap: dict, status: str, record: dict | None = None) -> str:
    """Exactly what the line says back to the driver after logging. Literal text, spoken verbatim."""
    r = record or {}
    at = r.get("at_local") or snap["clock_local"]
    said_by = r.get("said_by") or "The receiver"
    promise = f" {said_by} said: {r['said']}." if r.get("said") else ""
    eta = f" That's about {r['estimate_minutes']} minutes, around {r['eta_local']}." if r.get("estimate_minutes") and r.get("eta_local") else ""
    if status == "arrived":
        text = (
            f"Logged. You checked in at the receiving window at {at}.{promise}{eta} {money_line(snap)} "
            "It's on the load record with timestamps, and Dock will warn the shipper and the broker before free "
            "time runs out. Call back when they give you a new time or start unloading."
        )
    elif status == "waiting":
        text = (
            f"Logged at {at}: still waiting.{promise}{eta} {money_line(snap)} The shipper and the broker get a "
            "heads-up before any charge starts. Call back when they start unloading."
        )
    elif status == "unload_started":
        text = f"Logged: unloading started at {at}. {money_line(snap)}"
    else:
        text = f"Logged: unload finished at {at}. Thanks, Luis."
    return spoken(text)


def driver_reply(snap: dict, status: str, record: dict | None = None) -> str:
    """Back-compat: final instruction wrapping the read-back."""
    return f"Say exactly: '{driver_readback(snap, status, record)}' Do not give directions."


def answer_question(snap: dict, question: str) -> str:
    """on_question: answer from the live clock, read at the moment the caller asks."""
    s = snap["summary"]
    parts = [f"It is {snap['clock_local']} on the Dock clock."]
    if s["phase"] == "not_started":
        parts.append("The driver has not checked in yet, so no detention clock is running.")
        return spoken(" ".join(parts))
    parts.append(money_line(snap))
    parts.append(f"Status: {s['detail']} {s['how_to_avoid']}")
    rate = snap["policy"]
    parts.append(
        f"Policy: {rate['free_minutes']} minutes free, then ${rate['rate_usd_per_hour']} an hour in "
        f"{rate['increment_minutes']}-minute steps. Load {snap['load']['load_id']}, {snap['load']['reference']}, "
        f"{snap['load']['commodity']}, {snap['load']['facility']}."
    )
    return spoken(" ".join(parts))
