"""Rules in code. A later Guava agent can call this with a transcript. It does not import Guava."""

from __future__ import annotations

import uuid
from typing import Any

from dock_events.context import arrived_payload
from dock_events.model import Actor, Event
from dock_events.timeutil import format_time, parse_time

_DONE = (
    "empty",
    "done unloading",
    "unload is done",
    "finished unloading",
    "unloaded",
)
_START = (
    "started unloading",
    "started unload",
    "they're unloading",
    "they are unloading",
    "unloading me",
    "unload started",
)
_DELAY = (
    "not ready",
    "won't unload",
    "will not unload",
    "can't unload",
    "cannot unload",
    "still waiting",
    "nobody",
    "no one",
    "occupied",
    "not unloading",
)
_ARRIVED = (
    "i'm here",
    "i am here",
    "im here",
    "on site",
    "at the dock",
    "arrived",
    "at harbor",
    "checked in",
)


def normalize_message(
    text: str,
    *,
    load_id: str,
    party_id: str,
    role: str,
    channel: str,
    occurred_at: str,
    context: dict[str, Any],
    recorded_at: str | None = None,
) -> list[Event]:
    if channel not in ("voice", "sms"):
        raise ValueError("intake channel must be voice or sms")
    if role not in ("driver", "shipper", "consignee", "broker", "carrier"):
        raise ValueError(f"unexpected role {role}")
    if context["load"]["load_id"] != load_id:
        raise ValueError(f"context load is {context['load']['load_id']}, message says {load_id}")
    kinds = classify(text)
    if not kinds:
        raise ValueError(
            "could not classify that message. "
            "Say that you arrived, that they are not ready, that unload started, or that it is done."
        )
    parse_time(occurred_at)
    stamp = recorded_at or occurred_at
    parse_time(stamp)
    actor = Actor(role=role, party_id=party_id, channel=channel)
    events: list[Event] = []
    for kind in kinds:
        events.append(
            Event(
                event_id=f"evt-{kind[:8]}-{uuid.uuid4().hex[:12]}",
                type=kind,
                occurred_at=occurred_at,
                recorded_at=stamp,
                load_id=load_id,
                actor=actor,
                payload=_payload(kind, text, context),
                caused_by=None,
                source="dock-intake",
            )
        )
    return events


def classify(text: str) -> list[str]:
    low = " ".join(text.lower().split())
    kinds: list[str] = []
    if any(phrase in low for phrase in _ARRIVED):
        kinds.append("arrived")
    if any(phrase in low for phrase in _DELAY):
        kinds.append("delay_reported")
    if any(phrase in low for phrase in _DONE):
        kinds.append("unload_done")
    elif any(phrase in low for phrase in _START):
        kinds.append("unload_started")
    return kinds


def _payload(kind: str, text: str, context: dict[str, Any]) -> dict[str, Any]:
    door = context["load"].get("door", "door 4")
    if kind == "arrived":
        return arrived_payload(context)
    if kind == "delay_reported":
        return {"reason": _reason(text), "detail": text.strip()}
    if kind in ("unload_started", "unload_done"):
        return {"door": door}
    raise ValueError(kind)


def _reason(text: str) -> str:
    low = text.lower()
    if "occup" in low:
        return "door_occupied"
    if "still waiting" in low or "nobody" in low or "no one" in low:
        return "still_waiting"
    return "receiver_not_ready"
