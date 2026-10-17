"""Short lines for the desk. The event itself stays the source of truth."""

from __future__ import annotations

from dock_events.model import Event
from dock_events.timeutil import format_local, parse_time


def event_line(event: Event) -> str:
    payload = event.payload
    if event.type == "arrived":
        return f"{payload['driver_name']} checked in at {payload['facility']}."
    if event.type == "delay_reported":
        return payload["detail"]
    if event.type == "clock_started":
        return (
            f"Free time ends {format_local(payload['free_time_ends_at'], payload['timezone'])}. "
            f"{payload['free_minutes']} minutes, then ${payload['rate_usd_per_hour']}/hour."
        )
    if event.type == "charge_risk":
        return (
            f"{payload['phase']}. ${_money(payload['estimated_charge_usd'])} on the trail. "
            f"{payload['billable_minutes']} billable minutes."
        )
    if event.type == "notice_sent":
        return f"Heads-up to {payload['to_name']} ({payload['to_role']}) by {payload['channel']}."
    if event.type == "call_result":
        return f"{payload['to_name']}: {payload['summary']}"
    if event.type == "unload_started":
        return f"Unload started at {payload['door']}."
    if event.type == "unload_done":
        return f"Unload finished at {payload['door']}."
    if event.type == "claim_drafted":
        return payload["title"]
    return event.type


def zone_for(event: Event) -> str:
    zone = event.payload.get("timezone")
    if isinstance(zone, str) and zone:
        return zone
    return "America/New_York"


def sort_key(event: Event) -> tuple:
    band = 0
    if event.type == "charge_risk" and event.payload.get("phase") == "closed":
        band = 1
    elif event.type == "notice_sent" and event.payload.get("phase") == "closed":
        band = 2
    return (parse_time(event.occurred_at), band, event.type, event.event_id)


def _money(value: str) -> str:
    return value
