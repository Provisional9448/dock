"""Proof reads events. It does not recompute the clock."""

from __future__ import annotations

from datetime import datetime, timezone

from dock_events.model import Actor, Event
from dock_events.timeutil import format_local, format_local_long, format_time, parse_time


def render_markdown(events: list[Event], load_id: str) -> str:
    mine = [event for event in events if event.load_id == load_id]
    if not mine:
        raise ValueError(f"no events for {load_id}")
    arrived = _first(mine, "arrived")
    clock = _first(mine, "clock_started")
    risks = [event for event in mine if event.type == "charge_risk"]
    latest = max(risks, key=lambda event: event.occurred_at) if risks else None
    snap = arrived.payload if arrived else {}
    zone = snap.get("timezone") or (clock.payload["timezone"] if clock else "America/New_York")
    estimate = latest.payload["estimated_charge_usd"] if latest else "0.00"
    lines: list[str] = [
        f"# Detention trail (draft)",
        "",
        f"Load {load_id}. This is not an invoice.",
        "",
        "This pack is a timestamped record of what Dock logged. It is a conversation aid",
        "for a shipper, a carrier, and a broker. It is not a freight bill, a legal demand,",
        "or a finding that anyone breached a contract.",
        "",
        "## Load",
        "",
    ]
    if snap:
        lines.extend(
            [
                f"- Reference: {snap['reference']}",
                f"- Commodity: {snap['commodity']}",
                f"- Lane: {snap['origin']} to {snap['destination']}",
                f"- Facility: {snap['facility']}",
                f"- Appointment: {_long(snap.get('appointment_at'), zone)}",
                "",
                "## Parties",
                "",
                f"- Shipper: {snap['shipper_name']}",
                f"- Consignee: {snap['consignee_name']}",
                f"- Carrier: {snap['carrier_name']}",
                f"- Driver: {snap['driver_name']}",
                f"- Broker: {snap['broker_name']}",
                "",
            ]
        )
    lines.extend(["## Clock", ""])
    if clock is None:
        lines.append("No free-time clock has been started for this load.")
    else:
        payload = clock.payload
        lines.extend(
            [
                f"- Started: {_long(payload['clock_started_at'], zone)} (anchor: {payload['anchor']})",
                f"- Free time: {payload['free_minutes']} minutes",
                f"- Free time ends: {_long(payload['free_time_ends_at'], zone)}",
                f"- Rate on this trail: ${payload['rate_usd_per_hour']} per hour, in {payload['increment_minutes']}-minute steps",
                f"- Policy stop: {payload['stop_on']}",
            ]
        )
    if latest is not None:
        lines.extend(
            [
                f"- Phase: {latest.payload['phase']}",
                f"- Elapsed: {latest.payload['elapsed_minutes']} minutes",
                f"- Billable time: {latest.payload['billable_minutes']} minutes",
                f"- Estimate supported by this trail: ${estimate}",
                "",
                latest.payload["how_to_avoid"],
            ]
        )
    else:
        lines.append("")
        lines.append("No detention estimate yet.")
    lines.extend(["", "## Timeline", "", "| When | Event | What was logged |", "| --- | --- | --- |"])
    for event in sorted(mine, key=_sort_key):
        if event.type == "claim_drafted":
            continue
        lines.append(
            f"| {_short(event.occurred_at, zone)} | {event.type} | {_cell(event)} |"
        )
    notices = [event for event in mine if event.type == "notice_sent"]
    lines.extend(["", "## Notices", ""])
    if not notices:
        lines.append("No heads-up has been logged.")
    for notice in notices:
        lines.extend(
            [
                f"### {_short(notice.occurred_at, zone)} · {notice.payload['to_role']} · {notice.payload['channel']}",
                "",
                "```",
                notice.payload["body"],
                "```",
                "",
            ]
        )
    calls = [event for event in mine if event.type == "call_result"]
    lines.extend(["## Calls", ""])
    if not calls:
        lines.append("No call result has been logged.")
        lines.append("")
    for call in calls:
        lines.append(
            f"- {_short(call.occurred_at, zone)} {call.payload['outcome']} "
            f"({call.payload['goal']}, {call.payload['to_name']}): {call.payload['summary']}"
        )
        lines.append("")
    lines.extend(
        [
            "## What this trail does not say",
            "",
            "- It does not apply a particular carrier tariff. The rate and free time are the policy Dock was given.",
            "- It does not include lumper, layover, or TONU.",
            "- Storage and demurrage use the same clock with day-sized steps. This rendering does not assume which one you ran.",
            "- A missing paperwork delay, a status call, or a crash report is a different module. Those events are not required here.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def claim_event(events: list[Event], load_id: str) -> Event:
    markdown = render_markdown(events, load_id)
    mine = [event for event in events if event.load_id == load_id]
    latest = max(mine, key=lambda event: parse_time(event.occurred_at))
    risks = [event for event in mine if event.type == "charge_risk"]
    estimate = risks[-1].payload["estimated_charge_usd"] if risks else "0.00"
    # Prefer the latest charge by time, not file order.
    if risks:
        estimate = max(risks, key=lambda event: event.occurred_at).payload["estimated_charge_usd"]
    return Event(
        event_id=f"claim-{_slug(load_id)}",
        type="claim_drafted",
        occurred_at=latest.occurred_at,
        recorded_at=format_time(datetime.now(timezone.utc)),
        load_id=load_id,
        actor=Actor(role="system", party_id="dock-proof", channel="system"),
        payload={
            "title": f"Detention trail {load_id}",
            "markdown": markdown,
            "estimated_charge_usd": estimate,
        },
        caused_by=None,
        source="dock-proof",
    )


def _first(events: list[Event], event_type: str) -> Event | None:
    found = [event for event in events if event.type == event_type]
    if not found:
        return None
    return min(found, key=lambda event: event.occurred_at)


def _long(value: object, zone: str) -> str:
    if not isinstance(value, str):
        return "not logged"
    return format_local_long(value, zone)


def _short(value: str, zone: str) -> str:
    return format_local(value, zone)


def _cell(event: Event) -> str:
    payload = event.payload
    if event.type == "arrived":
        return f"{payload['driver_name']} at {payload['facility']}"
    if event.type == "delay_reported":
        return _plain(payload["detail"])
    if event.type == "clock_started":
        return f"free time ends {format_local(payload['free_time_ends_at'], payload['timezone'])}"
    if event.type == "charge_risk":
        return (
            f"{payload['phase']}, ${payload['estimated_charge_usd']}, "
            f"{payload['billable_minutes']} billable min"
        )
    if event.type == "notice_sent":
        return f"{payload['to_role']} via {payload['channel']}, ${payload['estimated_charge_usd']}"
    if event.type == "call_result":
        return f"{payload['outcome']}: {_plain(payload['summary'])}"
    if event.type in ("unload_started", "unload_done"):
        return payload["door"]
    return event.type


def _plain(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


def _sort_key(event: Event) -> tuple:
    band = 0
    if event.type == "charge_risk" and event.payload.get("phase") == "closed":
        band = 1
    elif event.type == "notice_sent" and event.payload.get("phase") == "closed":
        band = 2
    elif event.type == "claim_drafted":
        band = 3
    return (parse_time(event.occurred_at), band, event.type, event.event_id)


def _slug(load_id: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in load_id).strip("-")
    return cleaned[:40] or "load"
