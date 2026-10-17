"""Build the heads-up from events already on the trail. No clock math here."""

from __future__ import annotations

from dock_events.model import Actor, Event
from dock_events.timeutil import format_local

from dock_notify.provider import LogProvider, Notifier, OutboundMessage

_AUDIENCES = {
    "shipper": ("shipper_name", "shipper_party_id", "shipper_phone"),
    "consignee": ("consignee_name", "consignee_party_id", "consignee_phone"),
}


def apply_notices(
    events: list[Event],
    *,
    audiences: tuple[str, ...] = ("shipper", "consignee"),
    provider: Notifier | None = None,
) -> list[Event]:
    sender = provider or LogProvider()
    known = {event.event_id for event in events}
    created: list[Event] = []
    for charge in [event for event in events if event.type == "charge_risk"]:
        snapshot = _snapshot(events, charge.load_id)
        for role in audiences:
            event_id = f"ntc-{charge.event_id}-{role}"
            if event_id in known:
                continue
            body = compose_notice(snapshot, charge, role)
            name, party_id, phone = _who(snapshot, role)
            receipt = sender.send(
                OutboundMessage(
                    channel="sms",
                    to_number=phone,
                    to_name=name,
                    to_role=role,
                    body=body,
                    load_id=charge.load_id,
                )
            )
            created.append(
                Event(
                    event_id=event_id,
                    type="notice_sent",
                    occurred_at=charge.occurred_at,
                    recorded_at=charge.recorded_at,
                    load_id=charge.load_id,
                    actor=Actor(role="system", party_id="dock-notify", channel="sms"),
                    payload={
                        "channel": "sms",
                        "to_party_id": party_id,
                        "to_role": role,
                        "to_name": name,
                        "body": body,
                        "estimated_charge_usd": charge.payload["estimated_charge_usd"],
                        "phase": charge.payload["phase"],
                        "provider": receipt.provider,
                        "delivery_status": receipt.status,
                    },
                    caused_by=charge.event_id,
                    source="dock-notify",
                )
            )
            known.add(event_id)
    return events + created


def compose_notice(snapshot: dict, charge: Event, role: str) -> str:
    name, _, _ = _who(snapshot, role)
    payload = charge.payload
    zone = payload["timezone"]
    since = format_local(payload["clock_started_at"], zone)
    ends = format_local(payload["free_time_ends_at"], zone)
    appointment = snapshot.get("appointment_at")
    when = format_local(appointment, zone) if isinstance(appointment, str) else "unknown"
    charge_text = payload["estimated_charge_usd"]
    step = _step(payload)
    phase = payload["phase"]
    lines = [
        f"Dock, load {charge.load_id}. Not an invoice.",
        "",
        (
            f"{snapshot['driver_name']} ({snapshot['carrier_name']}) has been at "
            f"{snapshot['facility']} since {since}. Appointment was {when}."
        ),
        "",
    ]
    if phase == "warning":
        lines.append(
            f"Free time ends {ends}. Time left: {payload['remaining_free_minutes']} min. "
            f"Detention on this trail so far: ${charge_text}."
        )
        lines.append(
            f"After free time the trail uses ${payload['rate_usd_per_hour']}/hour "
            f"in {payload['increment_minutes']}-minute steps (${step} each)."
        )
        lines.append("")
        lines.append(payload["how_to_avoid"])
    elif phase == "accruing":
        lines.append(
            f"Free time ended {ends}. Unload has not started. "
            f"Detention on this trail so far: ${charge_text} "
            f"({payload['billable_minutes']} billable minutes)."
        )
        lines.append("")
        lines.append(payload["how_to_avoid"])
        lines.append(f"Every further {payload['increment_minutes']} minutes on the trail is another ${step}.")
    else:
        lines.append(
            f"The clock has stopped. This trail supports ${charge_text} "
            f"({payload['billable_minutes']} billable minutes after {payload['free_minutes']} minutes free, "
            f"at ${payload['rate_usd_per_hour']}/hour)."
        )
        lines.append("")
        lines.append(payload["how_to_avoid"])
    lines.append("")
    lines.append(f"{name}: reply with a time someone will meet the driver.")
    return "\n".join(lines)


def _snapshot(events: list[Event], load_id: str) -> dict:
    arrived = [event for event in events if event.load_id == load_id and event.type == "arrived"]
    if not arrived:
        raise ValueError(f"no arrived event for {load_id}; cannot address a heads-up")
    return arrived[0].payload


def _who(snapshot: dict, role: str) -> tuple[str, str, str]:
    try:
        name_key, id_key, phone_key = _AUDIENCES[role]
    except KeyError as exc:
        raise ValueError(f"no heads-up audience {role}") from exc
    contact_key = f"{role}_contact"
    name = snapshot.get(contact_key) or snapshot[name_key]
    return name, snapshot[id_key], snapshot[phone_key]


def _step(payload: dict) -> str:
    from decimal import Decimal, ROUND_HALF_UP

    amount = (
        Decimal(payload["rate_usd_per_hour"])
        * Decimal(payload["increment_minutes"])
        / Decimal(60)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{amount:.2f}"
