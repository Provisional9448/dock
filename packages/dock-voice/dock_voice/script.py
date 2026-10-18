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
    out = re.sub(r"\b0(\d):(\d\d)\b", r"\1:\2", out)  # '02:06' -> '2:06'
    out = re.sub(r"\b(Louise|Lewis|Louis|Luiz)\b", "Luis", out)
    out = out.replace("$0.00", "zero dollars")
    return out


LOAD_SPOKEN = "8 8 4 2 1"
NAMES = {"driver": "Luis", "shipper": "Sam", "consignee": "Priya", "broker": "Alex"}


def hm(local: str | None) -> str:
    """'2:06 PM ET' -> '2:06' (how a dispatcher says it to someone at the dock)."""
    m = re.match(r"\s*0?(\d{1,2}:\d\d)", str(local or ""))
    return m.group(1) if m else str(local or "")


def hm_zone(local: str | None) -> str:
    """'2:06 PM ET' -> '2:06 Eastern' (for callers in another time zone)."""
    return f"{hm(local)} Eastern" if local else ""


def caller_party(context: dict, number: object, env: dict | None = None) -> dict | None:
    """Caller ID -> the party on the load. Demo numbers in parties.json 'caller_ids' map a real phone to a party;
    DOCK_CALLER_ROLE (e.g. 'shipper') makes the demo number play that role for a take. None if unknown."""
    import os

    env = os.environ if env is None else env
    digits = re.sub(r"\D", "", str(number or ""))[-10:]
    if len(digits) != 10:
        return None
    by_role = {p["role"]: p for p in context.get("parties", [])}
    demo = {re.sub(r"\D", "", k)[-10:]: v for k, v in (context.get("caller_ids") or {}).items()}
    party = None
    if digits in demo:
        override = str(env.get("DOCK_CALLER_ROLE", "")).strip().lower()
        party = by_role.get(override) or next((p for p in context["parties"] if p["party_id"] == demo[digits]), None)
    else:
        party = next((p for p in context.get("parties", []) if re.sub(r"\D", "", p.get("phone", ""))[-10:] == digits), None)
    if party and party["role"] == "carrier":
        party = by_role.get("driver", party)
    if not party or party["role"] not in ROLES:
        return None
    return party


def greeting(role: str | None) -> str:
    """First thing the line says. Known caller: by name, like a dispatcher picking up. Unknown: who's this?"""
    if role in NAMES:
        ask = "What's going on?" if role == "driver" else "What's up?"
        return f"Hey {NAMES[role]}, Doc on {LOAD_SPOKEN}. Automated line, it's recorded. {ask}"
    return f"Hey, Doc on {LOAD_SPOKEN}, Red Kettle's automated line, it's recorded. Who's this?"


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
    if s["phase"] in ("running", "warning"):
        return (
            f"Free time runs out at {hm_zone(s['free_time_ends_local'])}, about {span_words(s['remaining_free_minutes'])} "
            f"from now. Nothing owed yet; after that it's ${per_hour} an hour."
        )
    if s["phase"] == "accruing":
        return (
            f"Free time ran out at {hm_zone(s['free_time_ends_local'])}. It's about ${s['estimated_charge_usd']} so far, "
            f"${per_hour} an hour. That's an estimate, not a bill."
        )
    if s["phase"] == "closed":
        return f"Clock's stopped, about ${s['estimated_charge_usd']} of detention. That's an estimate, not a bill."
    return "No clock running yet."


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
    if hour is None:
        # speech-to-text often writes "2:06" as "206" or "2 06"
        match = re.search(r"\b(?:at|around|about)?\s*(\d{1,2})\s?(\d{2})\b(?!\s*(?:min|minutes|pallets|%))", text)
        if match and re.search(r"\b(at|around|about|checked in|started|start)\b", text):
            hour, minute = int(match.group(1)), int(match.group(2))
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
    """Exactly what the line says back to the driver. Drivers are paid for waiting and don't pay detention, so the
    driver call only captures and confirms his update: no free time, countdown, dollars, or rate here (those are
    for shipper, consignee and broker calls). One or two short sentences, then 'Anything else?'."""
    r = record or {}
    at = hm(r.get("at_local") or snap["clock_local"])
    said_by = r.get("said_by") or "they"
    said = (r.get("said") or "").strip().rstrip(".")
    if said:
        told = f", {said_by} said {said}"
    elif r.get("estimate_minutes"):
        told = f", {said_by} said about {r['estimate_minutes']}"
    else:
        told = ""
    if status == "arrived":
        text = f"Got it, checked in {at}{told}. Call me when they pull you in. Anything else?"
    elif status == "waiting":
        text = f"Got it, still waiting as of {at}{told}. Call me when they pull you in. Anything else?"
    elif status == "unload_started":
        text = f"Got it, they started unloading at {at}. Call me when you're empty. Anything else?"
    else:
        text = f"Got it, empty at {at}. Anything else?"
    return spoken(text)


def _driver_report(snap: dict) -> dict:
    """What the driver put on the record: check-in time and the latest thing the receiver told him."""
    zone = snap["load"].get("timezone", "America/New_York")
    events = [row["event"] for row in snap.get("events", [])]
    arrived = next((e for e in events if e["type"] == "arrived"), None)
    delays = [e for e in events if e["type"] == "delay_reported"]
    from dock_events.timeutil import format_local

    out = {"checked_in": format_local(arrived["occurred_at"], zone) if arrived else None, "said": "", "eta": None}
    if delays:
        detail = delays[-1]["payload"].get("detail", "")
        said = re.search(r"said: ([^.]*)", detail)
        out["said"] = said.group(1).strip() if said else ""
        eta = re.search(r"around (\d{1,2}:\d\d [AP]M \w+)", detail)
        out["eta"] = eta.group(1) if eta else None
    return out


def _rate(snap: dict) -> str:
    rate = snap["policy"]
    return f"${str(rate['rate_usd_per_hour']).removesuffix('.00')} an hour"


def payer_role(snap: dict) -> str:
    """Who pays detention on this load (per-load terms; carrier invoices them). Shipper or consignee."""
    role = str(snap.get("load", {}).get("payer_role", "shipper")).lower()
    return role if role in ("shipper", "consignee") else "shipper"


def _carrier(snap: dict) -> str:
    return "Red Kettle"


def _money(snap: dict) -> str:
    """Free-time cutoff and what a charge would be: only for the payer (and the broker)."""
    s = snap["summary"]
    if s["phase"] in ("running", "warning"):
        return (
            f"Free time runs out at {hm(s['free_time_ends_local'])}, so about {span_words(s['remaining_free_minutes'])} "
            f"left. After that {_carrier(snap)} charges {_rate(snap)}."
        )
    if s["phase"] == "accruing":
        return (
            f"Free time ran out at {hm(s['free_time_ends_local'])}. It's about ${s['estimated_charge_usd']} so far, "
            f"{_rate(snap)}, till they start unloading."
        )
    if s["phase"] == "closed":
        return f"Clock stopped at about ${s['estimated_charge_usd']} of detention."
    return ""


def _status(snap: dict) -> str:
    s, d = snap["summary"], _driver_report(snap)
    if not d["checked_in"]:
        return "Luis hasn't checked in yet."
    if s["phase"] == "closed":
        return f"Luis checked in at {hm_zone(d['checked_in'])}, and they're unloading him now."
    told = _told(d)
    return f"Luis checked in at {hm_zone(d['checked_in'])}{told}, waiting on a door."


def _told(d: dict) -> str:
    m = re.search(r"(\d+)\s*min", d.get("said") or "")
    if m:
        return f", they told him about {m.group(1)} minutes"
    if d.get("eta"):
        return f", they said around {hm(d['eta'])}"
    return ""


def shipper_brief(snap: dict) -> str:
    """Shipper: on time? If the shipper pays on this load: will it cost me and what to do (call the DC).
    Otherwise status only."""
    s, d = snap["summary"], _driver_report(snap)
    if d["checked_in"] and s["phase"] in ("running", "warning", "accruing"):
        text = f"Luis checked in at Harbor and Rye at {hm_zone(d['checked_in'])}{_told(d)}."
    else:
        text = _status(snap)
    if payer_role(snap) == "shipper" and s["phase"] != "not_started":
        text += " " + _money(snap)
        if s["phase"] in ("running", "warning", "accruing"):
            text += " Want to give Harbor and Rye receiving a call and call me back with what they say?"
    return spoken(text)


def promise_readback(promise: dict) -> str:
    who = promise["who"]
    who = who if who.startswith(("the ", "receiving")) else f"the {who}"
    door = f" {promise['door']}" if promise.get("door") else ""
    return spoken(f"Got it, {who} says{door} by {hm(promise['eta_local'])}. I'll let Lantern Lane know. Anything else?")


def consignee_brief(snap: dict) -> str:
    """Consignee / receiver: confirm what the driver reported, then we take their door or unload time.
    Money only if the consignee is the payer on this load."""
    s, d = snap["summary"], _driver_report(snap)
    if not d["checked_in"]:
        return spoken("Luis from Red Kettle hasn't checked in with you yet.")
    told = f" He says your team told him {d['said'].rstrip('.')}." if d["said"] else ""
    text = f"Luis from Red Kettle checked in at your window at {hm(d['checked_in'])}.{told}"
    if payer_role(snap) == "consignee" and s["phase"] != "not_started":
        text += " " + _money(snap)
    return spoken(text)


def broker_brief(snap: dict) -> str:
    """Broker: status for their customer, exposure, and that the carrier invoices off the timestamped record."""
    s = snap["summary"]
    payer = payer_role(snap)
    text = _status(snap)
    if s["phase"] != "not_started":
        text += " " + _money(snap)
    text += f" The {payer} pays on this one, and {_carrier(snap)} bills off our timestamps."
    return spoken(text)


def goodbye_line(role: str) -> str:
    """The one closing line. Spoken once, with the right name."""
    if role == "driver":
        return "Thanks Luis, talk soon."
    who = f" {NAMES[role]}" if role in NAMES else ""
    return f"Thanks{who}, bye."


def driver_reply(snap: dict, status: str, record: dict | None = None) -> str:
    """Back-compat: final instruction wrapping the read-back."""
    return f"Say exactly: '{driver_readback(snap, status, record)}' Do not give directions."


def answer_question(snap: dict, question: str) -> str:
    """on_question: answer from the live clock, read at the moment the caller asks."""
    s = snap["summary"]
    rate = snap["policy"]
    parts = [f"It's {hm_zone(snap['clock_local'])}."]
    if s["phase"] == "not_started":
        parts.append("Luis hasn't checked in yet, so no clock's running.")
    else:
        parts.append(_status(snap))
        parts.append(money_line(snap))
    parts.append(
        f"For reference: {rate['free_minutes']} minutes free, then ${str(rate['rate_usd_per_hour']).removesuffix('.00')} "
        f"an hour. {snap['load']['commodity']} going to {snap['load']['facility']}."
    )
    return spoken(" ".join(parts))
