"""Heads-up copy for shipper and consignee. Pure: same inputs, same sentences.

The estimate uses the same rounding as the clock (ceil to the billing step, then
the hourly rate). This module does not read the log and does not send anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from dock_events.timeutil import format_local, format_time, parse_time

_PHASES = ("warning", "free_ended", "accruing", "closed")
_AUDIENCES = ("shipper", "consignee")
_DROPPED_SUFFIXES = (" Freight", " Trucking", " Logistics", " Transport", " Carriers")


@dataclass(frozen=True)
class Party:
    """One company on the load. `name` is the company. `contact` is the person."""

    role: str
    name: str
    contact: str
    phone: str = ""
    party_id: str = ""


@dataclass(frozen=True)
class HeadsUp:
    """SMS text and the spoken script for one audience at one moment."""

    phase: str
    sms: str
    voice: str
    estimated_charge_usd: str
    billable_minutes: int
    on_cadence: bool
    to_role: str
    to_name: str


def compose_heads_up(
    load_id: str,
    parties: Sequence[Party],
    door: str,
    arrived_at: datetime | str,
    free_minutes: int,
    rate: Decimal | str,
    now: datetime | str,
    *,
    audience: str = "shipper",
    facility: str = "",
    increment_minutes: int = 15,
    warn_minutes: int = 30,
    zone: str = "America/New_York",
    stopped_at: datetime | str | None = None,
    appointment_at: datetime | str | None = None,
    how_to_avoid: str = "",
) -> HeadsUp | None:
    """Message for the moment `now` falls in, or None while free time is still quiet.

    Moments that set `on_cadence`: 30 minutes of free time left (or `warn_minutes`),
    the minute free time ends, every billing step while the clock is accruing,
    and the minute the clock stops. Off those marks the same phase still has a
    script, with `on_cadence` false, so a late tick can still be read aloud.
    """
    if audience not in _AUDIENCES:
        raise ValueError(f"no heads-up audience {audience}")
    if free_minutes < 0 or warn_minutes < 0 or increment_minutes <= 0:
        raise ValueError("free time and the warning window must be non-negative, and the step must be positive")
    hourly = _rate(rate)
    listener = _party(parties, audience)
    carrier = _party(parties, "carrier")
    contact = listener.contact.strip() or listener.name.strip()
    if not contact:
        raise ValueError(f"{audience} needs a contact name")
    place = _place(facility, door, parties)
    start = _anchor(_moment(arrived_at, "arrived_at"), _optional_moment(appointment_at, "appointment_at"))
    moment = _moment(now, "now")
    stop = _optional_moment(stopped_at, "stopped_at")
    closed = stop is not None and moment >= stop
    end = stop if closed and stop is not None else moment
    if end < start:
        return None
    elapsed = _minutes(start, end)
    remaining = max(free_minutes - elapsed, 0)
    over = max(elapsed - free_minutes, 0)
    if closed:
        phase = "closed"
    elif over > 0:
        phase = "accruing"
    elif remaining == 0:
        phase = "free_ended"
    elif remaining <= warn_minutes:
        phase = "warning"
    else:
        return None
    billable = _billable(over, increment_minutes)
    estimate = _money(billable, hourly)
    step = _money(increment_minutes, hourly)
    since = _label(start, zone)
    free_end = _label(start + timedelta(minutes=free_minutes), zone)
    sms, voice = notice_text(
        load_id=load_id,
        carrier_name=carrier.name,
        place=place,
        contact_name=contact,
        phase=phase,
        estimated_charge_usd=estimate,
        free_end_label=free_end,
        since_label=since,
        increment_minutes=increment_minutes,
        step_usd=step,
        how_to_avoid=how_to_avoid,
    )
    return HeadsUp(
        phase=phase,
        sms=sms,
        voice=voice,
        estimated_charge_usd=estimate,
        billable_minutes=billable,
        on_cadence=_on_cadence(phase, remaining, over, warn_minutes, increment_minutes, stop, moment),
        to_role=audience,
        to_name=contact,
    )


def notice_text(
    *,
    load_id: str,
    carrier_name: str,
    place: str,
    contact_name: str,
    phase: str,
    estimated_charge_usd: str,
    free_end_label: str,
    since_label: str,
    increment_minutes: int,
    step_usd: str,
    how_to_avoid: str = "",
) -> tuple[str, str]:
    """SMS paragraph and spoken script. Both name the load, the estimate, and that this is not an invoice."""
    if phase not in _PHASES:
        raise ValueError(f"unknown heads-up phase {phase}")
    if not load_id.strip():
        raise ValueError("load_id is required")
    if not contact_name.strip():
        raise ValueError("contact name is required")
    possessive = carrier_possessive(carrier_name)
    opening = (
        f"Dock · {load_id}: {possessive} driver has waited at {place} since {since_label}."
    )
    avoidance = _avoidance(phase, free_end_label, step_usd, increment_minutes, how_to_avoid)
    if phase == "warning":
        status = f"Free time ends {free_end_label}."
        money = f"Estimate so far ${estimated_charge_usd}."
        ask = f"{contact_name}: reply with a time someone will meet the driver."
    elif phase == "free_ended":
        status = f"Free time ended {free_end_label}."
        money = f"Estimate so far ${estimated_charge_usd}."
        ask = f"{contact_name}: reply with a time someone will meet the driver."
    elif phase == "accruing":
        status = f"Free time ended {free_end_label}."
        money = f"Estimate so far ${estimated_charge_usd}."
        ask = f"{contact_name}: reply with a time someone will meet the driver."
    else:
        status = "The clock has stopped."
        money = f"Final supported amount ${estimated_charge_usd}."
        ask = f"{contact_name}, this is the amount the trail supports."
    sms_parts = [opening, status, money, avoidance, "Not an invoice.", ask]
    sms = " ".join(part for part in sms_parts if part)
    spoken_place = place.replace("&", "and")
    voice_opening = (
        f"Dock, load {load_id}. {possessive} driver has waited at {spoken_place} since {since_label}."
    )
    voice_parts = [voice_opening, status, money, _spoken(avoidance), "Not an invoice.", ask]
    voice = " ".join(part for part in voice_parts if part)
    return sms, voice


def carrier_possessive(name: str) -> str:
    stem = " ".join(name.split())
    for suffix in _DROPPED_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)].rstrip()
            break
    if not stem:
        raise ValueError("carrier name is empty")
    if stem.endswith("s"):
        return f"{stem}'"
    return f"{stem}'s"


def format_place(facility: str, door: str) -> str:
    site = " ".join(facility.split())
    dock = " ".join(door.split())
    if not site and not dock:
        raise ValueError("a facility or a door is required")
    if not dock or dock.lower() in site.lower():
        return site or dock
    if not site:
        return dock
    return f"{site} {dock}"


def step_usd(rate: Decimal | str, increment_minutes: int) -> str:
    if increment_minutes <= 0:
        raise ValueError("the billing step must be positive")
    return _money(increment_minutes, _rate(rate))


def _avoidance(phase: str, free_end: str, step: str, increment: int, how_to_avoid: str) -> str:
    if phase == "warning":
        generated = f"If unload starts before {free_end}, it stays $0.00."
    elif phase == "free_ended":
        generated = f"The next {increment} minutes add ${step} unless unload starts."
    elif phase == "accruing":
        generated = f"Another ${step} is added every {increment} minutes until the unload starts."
    else:
        generated = ""
    extra = " ".join(how_to_avoid.split())
    if not extra or phase in ("closed", "accruing"):
        return generated
    return extra


def _spoken(text: str) -> str:
    return text.replace("&", "and")


def _on_cadence(
    phase: str,
    remaining: int,
    over: int,
    warn_minutes: int,
    increment_minutes: int,
    stop: datetime | None,
    moment: datetime,
) -> bool:
    if phase == "closed":
        return stop is not None and _minutes(stop, moment) == 0
    if phase == "warning":
        return remaining == warn_minutes
    if phase == "free_ended":
        return True
    return over > 0 and over % increment_minutes == 0


def _place(facility: str, door: str, parties: Sequence[Party]) -> str:
    site = facility.strip()
    if not site:
        site = _party(parties, "consignee").name.strip()
    return format_place(site, door)


def _party(parties: Sequence[Party], role: str) -> Party:
    found = [party for party in parties if party.role == role]
    if not found:
        raise ValueError(f"no {role} in parties")
    return found[0]


def _anchor(arrived: datetime, appointment: datetime | None) -> datetime:
    if appointment is not None and arrived < appointment:
        return appointment
    return arrived


def _rate(value: Decimal | str) -> Decimal:
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError("rate must be a dollar amount") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("rate cannot be negative")
    return amount


def _moment(value: datetime | str, field: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(f"{field} needs a timezone")
        return value.astimezone(timezone.utc)
    return parse_time(value)


def _optional_moment(value: datetime | str | None, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    return _moment(value, field)


def _label(moment: datetime, zone: str) -> str:
    try:
        return format_local(format_time(moment), zone)
    except Exception as exc:
        raise ValueError(f"bad timezone {zone}") from exc


def _minutes(start: datetime, end: datetime) -> int:
    return max(int((end - start).total_seconds() // 60), 0)


def _billable(over_minutes: int, increment: int) -> int:
    if over_minutes <= 0:
        return 0
    steps = (over_minutes + increment - 1) // increment
    return steps * increment


def _money(billable_minutes: int, rate: Decimal) -> str:
    if billable_minutes == 0:
        return "0.00"
    amount = (rate * Decimal(billable_minutes) / Decimal(60)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"
