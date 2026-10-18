"""Append tracking_requested. A repeat of the same watch is the same event id.

status and driver_report include occurred_at, so a later chase is a new line.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from dock_events.log import EventLog
from dock_events.model import CHANNELS, ROLES, Actor, Event
from dock_events.timeutil import format_time, parse_time

from dock_track.parse import Condition, TrackRequest, parse_request


def watch(
    load_id: str,
    path: str | Path,
    *,
    text: str = "",
    request: TrackRequest | None = None,
    occurred_at: str | None = None,
    recorded_at: str | None = None,
    party_id: str = "pty_requester",
    role: str | None = None,
    channel: str = "sms",
) -> Event:
    """Append a tracking_requested line. WhatsApp is stored as channel sms."""
    if not load_id.strip():
        raise ValueError("load_id must be a non-empty string")
    if request is None and not text.strip():
        raise ValueError("tracking request is empty")
    parsed = request if request is not None else parse_request(text)
    actor_role = role or (parsed.role if parsed is not None else None) or "system"
    if actor_role not in ROLES:
        raise ValueError(f"unexpected role {actor_role}")
    if channel not in CHANNELS:
        raise ValueError(f"unexpected channel {channel}")
    when = occurred_at or format_time(datetime.now(timezone.utc))
    parse_time(when)
    stamp = recorded_at or when
    parse_time(stamp)
    event = Event(
        event_id=_event_id(load_id, parsed, when),
        type="tracking_requested",
        occurred_at=when,
        recorded_at=stamp,
        load_id=load_id,
        actor=Actor(role=actor_role, party_id=party_id, channel=channel),
        payload=_payload(parsed, text),
        caused_by=None,
        source="dock-track",
    )
    EventLog(Path(path)).append([event])
    return event


def _payload(parsed: TrackRequest | None, text: str) -> dict:
    body = parsed.to_dict() if parsed is not None else {}
    summary_text = parsed.text if parsed is not None else " ".join(text.split())
    return {
        "intent": parsed.intent if parsed is not None else "track",
        "summary": _summary(parsed),
        "text": summary_text,
        "caller_role": body.get("role"),
        "identifier_kind": body.get("kind"),
        "identifier_value": body.get("value"),
        "same_instructions": bool(body.get("same_instructions")),
        "identifiers": body.get("identifiers") or [],
        "condition": body.get("condition"),
    }


def _summary(parsed: TrackRequest | None) -> str:
    if parsed is None:
        return "tracking requested"
    parts = [parsed.intent]
    if parsed.value:
        parts.append(parsed.value)
    phrase = _condition_phrase(parsed.condition)
    if phrase:
        parts.append(phrase)
    if len(parts) == 1:
        return parts[0]
    return parts[0] + " " + ", ".join(parts[1:])


def _condition_phrase(condition: Condition | None) -> str:
    if condition is None:
        return ""
    if condition.trigger == "arrive_at":
        where = condition.city or condition.place
        return f"arrive at {where}" if where else "arrive"
    if condition.trigger == "leave_terminal":
        return f"leave {condition.place}" if condition.place else "leave terminal"
    if condition.trigger == "interval_hours" and condition.interval_hours is not None:
        return f"every {condition.interval_hours} hours"
    return condition.trigger


def _event_id(load_id: str, parsed: TrackRequest | None, occurred_at: str) -> str:
    if parsed is None:
        blob = f"{load_id}|track"
    else:
        ids = ",".join(f"{item.kind}:{item.value}" for item in parsed.identifiers)
        condition = parsed.condition
        if condition is None:
            cond = ""
        else:
            cond = f"{condition.trigger}:{condition.city or ''}:{condition.place or ''}:{condition.interval_hours or ''}"
        parts = [
            load_id,
            parsed.intent,
            parsed.role or "",
            ids,
            cond,
            "1" if parsed.same_instructions else "0",
        ]
        if parsed.intent in ("status", "driver_report"):
            parts.append(occurred_at)
        blob = "|".join(parts)
    digest = hashlib.sha256(blob.encode()).hexdigest()[:10]
    return f"trk-{_slug(load_id)}-{digest}"


def _slug(load_id: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in load_id).strip("-")
    return cleaned[:40] or "load"
