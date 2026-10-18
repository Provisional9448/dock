"""Pure clock. Same inputs, same event ids, no file and no network."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from dock_events.model import Actor, Event
from dock_events.timeutil import format_local, format_time, parse_time

from dock_clock.policy import DetentionPolicy

SYSTEM = Actor(role="system", party_id="dock-clock", channel="system")


def tick(events: list[Event], *, as_of: datetime, policy: DetentionPolicy) -> list[Event]:
    """New clock events for this instant. Ignores facts that have not happened yet."""
    if as_of.tzinfo is None:
        raise ValueError("as_of needs a timezone")
    moment = as_of.astimezone(timezone.utc)
    created: list[Event] = []
    known = {event.event_id for event in events}
    for load_id in _load_ids(events):
        created.extend(_tick_load(events, load_id, moment, policy, known))
        known.update(event.event_id for event in created)
    return created


def replay_clock(events: list[Event], *, as_of: datetime, policy: DetentionPolicy) -> list[Event]:
    """Fold tick() across the warning, accrual, and stop checkpoints up through as_of.

    Facts after as_of are left out. Derived events already in the input are kept
    only when their occurred_at is at or before as_of, and tick() will not repeat them.
    """
    visible = [event for event in events if parse_time(event.occurred_at) <= as_of]
    acc = list(visible)
    for point in _checkpoints(acc, as_of, policy):
        acc.extend(tick(acc, as_of=point, policy=policy))
    return acc


def _tick_load(
    events: list[Event],
    load_id: str,
    as_of: datetime,
    policy: DetentionPolicy,
    known: set[str],
) -> list[Event]:
    facts = [
        event
        for event in events
        if event.load_id == load_id and parse_time(event.occurred_at) <= as_of
    ]
    anchor = _anchor(facts)
    if anchor is None:
        return []
    start, anchor_name, anchor_event = anchor
    if as_of < start:
        return []
    stop = _stop_at(facts, policy)
    if stop is not None and stop < start:
        stop = start
    frozen = stop is not None and as_of >= stop
    end = stop if frozen and stop is not None else as_of
    elapsed = _minutes(start, end)
    remaining = max(policy.free_minutes - elapsed, 0)
    over = max(elapsed - policy.free_minutes, 0)
    billable = _billable(over, policy.increment_minutes)
    charge = _charge(billable, policy)
    zone = _timezone(facts)
    free_end = start + timedelta(minutes=policy.free_minutes)
    out: list[Event] = []
    started = _clock_started(
        load_id, start, free_end, anchor_name, anchor_event, zone, policy, known, recorded_at=as_of
    )
    if started is not None:
        out.append(started)
        known = known | {started.event_id}

    if frozen:
        phase = "closed"
        event_id = f"clk-{_slug(load_id)}-closed"
    elif over > 0:
        phase = "accruing"
        event_id = f"clk-{_slug(load_id)}-accruing-{_stamp(as_of)}"
    elif remaining <= policy.warn_minutes:
        phase = "warning"
        event_id = f"clk-{_slug(load_id)}-warning"
    else:
        return out

    if _already_closed(facts) or event_id in known:
        return out
    risk = Event(
        event_id=event_id,
        type="charge_risk",
        occurred_at=format_time(end if frozen else as_of),
        recorded_at=format_time(as_of),
        load_id=load_id,
        actor=SYSTEM,
        payload={
            "phase": phase,
            "free_minutes": policy.free_minutes,
            "elapsed_minutes": elapsed,
            "remaining_free_minutes": remaining,
            "billable_minutes": billable,
            "estimated_charge_usd": charge,
            "rate_usd_per_hour": policy.rate_text,
            "increment_minutes": policy.increment_minutes,
            "clock_started_at": format_time(start),
            "free_time_ends_at": format_time(free_end),
            "how_to_avoid": _how_to_avoid(phase, free_end, zone, charge, policy),
            "timezone": zone,
            "stop_on": policy.stop_on,
        },
        caused_by=anchor_event.event_id,
        source="dock-clock",
    )
    out.append(risk)
    return out


def _clock_started(
    load_id: str,
    start: datetime,
    free_end: datetime,
    anchor_name: str,
    anchor_event: Event,
    zone: str,
    policy: DetentionPolicy,
    known: set[str],
    *,
    recorded_at: datetime,
) -> Event | None:
    event_id = f"clk-{_slug(load_id)}-started"
    if event_id in known:
        return None
    return Event(
        event_id=event_id,
        type="clock_started",
        occurred_at=format_time(start),
        recorded_at=format_time(recorded_at),
        load_id=load_id,
        actor=SYSTEM,
        payload={
            "clock_started_at": format_time(start),
            "free_time_ends_at": format_time(free_end),
            "free_minutes": policy.free_minutes,
            "anchor": anchor_name,
            "anchor_event_id": anchor_event.event_id,
            "timezone": zone,
            "rate_usd_per_hour": policy.rate_text,
            "increment_minutes": policy.increment_minutes,
            "stop_on": policy.stop_on,
        },
        caused_by=anchor_event.event_id,
        source="dock-clock",
    )


def _anchor(facts: list[Event]) -> tuple[datetime, str, Event] | None:
    arrived = _first(facts, "arrived")
    if arrived is not None:
        arrived_at = parse_time(arrived.occurred_at)
        appointment = arrived.payload.get("appointment_at")
        if isinstance(appointment, str):
            appointment_at = parse_time(appointment)
            if arrived_at < appointment_at:
                return appointment_at, "appointment", arrived
        return arrived_at, "arrived", arrived
    delay = _first(facts, "delay_reported")
    if delay is None:
        return None
    return parse_time(delay.occurred_at), "delay_reported", delay


def _stop_at(facts: list[Event], policy: DetentionPolicy) -> datetime | None:
    stops = [parse_time(event.occurred_at) for event in facts if event.type == policy.stop_on]
    if not stops:
        return None
    return min(stops)


def _already_closed(facts: list[Event]) -> bool:
    return any(
        event.type == "charge_risk" and event.payload.get("phase") == "closed" for event in facts
    )


def _first(facts: list[Event], event_type: str) -> Event | None:
    found = [event for event in facts if event.type == event_type]
    if not found:
        return None
    return min(found, key=lambda event: (parse_time(event.occurred_at), event.event_id))


def _timezone(facts: list[Event]) -> str:
    """Facility zone from the arrival the anchor uses."""
    arrived = _first(facts, "arrived")
    if arrived is not None:
        zone = _zone_of(arrived)
        if zone is not None:
            return zone
    ordered = sorted(facts, key=lambda event: (parse_time(event.occurred_at), event.event_id))
    for event in ordered:
        zone = _zone_of(event)
        if zone is not None:
            return zone
    return "America/New_York"


def _zone_of(event: Event) -> str | None:
    zone = event.payload.get("timezone")
    if isinstance(zone, str) and zone:
        return zone
    return None


def _load_ids(events: list[Event]) -> list[str]:
    seen: dict[str, None] = {}
    for event in events:
        seen.setdefault(event.load_id, None)
    return list(seen)


def _minutes(start: datetime, end: datetime) -> int:
    return max(int((end - start).total_seconds() // 60), 0)


def _billable(over_minutes: int, increment: int) -> int:
    if over_minutes <= 0:
        return 0
    steps = (over_minutes + increment - 1) // increment
    return steps * increment


def _charge(billable_minutes: int, policy: DetentionPolicy) -> str:
    if billable_minutes == 0:
        return "0.00"
    amount = (policy.rate_usd_per_hour * Decimal(billable_minutes) / Decimal(60)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"{amount:.2f}"


def _how_to_avoid(phase: str, free_end: datetime, zone: str, charge: str, policy: DetentionPolicy) -> str:
    ends = format_local(format_time(free_end), zone)
    step = _charge(policy.increment_minutes, policy)
    if phase == "warning":
        return (
            f"Start the unload before {ends}. "
            f"After that, this trail adds ${step} every {policy.increment_minutes} minutes."
        )
    if policy.stop_on == "unload_started":
        stop_now = "the unload starts"
        stop_past = "the unload started"
    else:
        stop_now = "the unload finishes"
        stop_past = "the unload finished"
    if phase == "accruing":
        return (
            f"Unload has not started. This trail shows ${charge} so far. "
            f"This clock stops when {stop_now}."
        )
    return (
        f"This clock stopped when {stop_past}. "
        f"This trail supports ${charge}. It is not an invoice."
    )


def _checkpoints(events: list[Event], as_of: datetime, policy: DetentionPolicy) -> list[datetime]:
    points: list[datetime] = []
    for load_id in _load_ids(events):
        facts = [event for event in events if event.load_id == load_id]
        anchor = _anchor(facts)
        if anchor is None:
            continue
        start, _, _ = anchor
        if as_of < start:
            continue
        free_end = start + timedelta(minutes=policy.free_minutes)
        warning_at = free_end - timedelta(minutes=policy.warn_minutes)
        stop = _stop_at([event for event in facts if parse_time(event.occurred_at) <= as_of], policy)
        points.append(start)
        if start < warning_at <= as_of:
            points.append(warning_at)
        if stop is not None and stop <= as_of:
            mid = free_end + timedelta(minutes=policy.increment_minutes)
            if free_end < mid < stop and mid <= as_of:
                points.append(mid)
            points.append(stop)
        elif as_of > free_end:
            points.append(as_of)
    unique = sorted({point for point in points if point <= as_of})
    return unique


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(load_id: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in load_id).strip("-")
    return cleaned[:24] or "load"
