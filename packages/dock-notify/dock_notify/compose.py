"""Build the heads-up from events already on the trail. No clock math here."""

from __future__ import annotations

from dock_events.model import Actor, Event
from dock_events.timeutil import format_local

from dock_notify.messages import format_place, notice_text, step_usd
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
            body, voice = compose_pair(snapshot, charge, role)
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
                        "voice": voice,
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
    return compose_pair(snapshot, charge, role)[0]


def compose_voice(snapshot: dict, charge: Event, role: str) -> str:
    return compose_pair(snapshot, charge, role)[1]


def compose_pair(snapshot: dict, charge: Event, role: str) -> tuple[str, str]:
    """SMS body and spoken script for one charge_risk. The estimate is the clock's, not recomputed."""
    name, _, _ = _who(snapshot, role)
    payload = charge.payload
    zone = str(payload["timezone"])
    facility = snapshot.get("facility")
    if not isinstance(facility, str) or not facility.strip():
        raise ValueError(f"no facility on the arrived event for {charge.load_id}")
    phase = _template_phase(str(payload["phase"]), int(payload["remaining_free_minutes"]))
    how = payload.get("how_to_avoid")
    return notice_text(
        load_id=charge.load_id,
        carrier_name=str(snapshot["carrier_name"]),
        place=format_place(facility, ""),
        contact_name=name,
        phase=phase,
        estimated_charge_usd=str(payload["estimated_charge_usd"]),
        free_end_label=format_local(str(payload["free_time_ends_at"]), zone),
        since_label=format_local(str(payload["clock_started_at"]), zone),
        increment_minutes=int(payload["increment_minutes"]),
        step_usd=step_usd(str(payload["rate_usd_per_hour"]), int(payload["increment_minutes"])),
        how_to_avoid=how if isinstance(how, str) else "",
    )


def _template_phase(clock_phase: str, remaining_free_minutes: int) -> str:
    if clock_phase == "closed":
        return "closed"
    if clock_phase == "accruing":
        return "accruing"
    if remaining_free_minutes <= 0:
        return "free_ended"
    return "warning"


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


