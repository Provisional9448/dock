"""Append tracking_requested. Same request twice is the same event id."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from dock_events.log import EventLog
from dock_events.model import CHANNELS, ROLES, Actor, Event
from dock_events.timeutil import format_time, parse_time

from dock_track.parse import TrackRequest, parse_request


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
    parsed = request
    if parsed is None and text.strip():
        parsed = parse_request(text)
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
        event_id=_event_id(load_id, parsed),
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
        "summary": "tracking requested",
        "text": summary_text,
        "caller_role": body.get("role"),
        "identifier_kind": body.get("kind"),
        "identifier_value": body.get("value"),
        "same_instructions": bool(body.get("same_instructions")),
        "identifiers": body.get("identifiers") or [],
        "condition": body.get("condition"),
    }


def _event_id(load_id: str, parsed: TrackRequest | None) -> str:
    if parsed is None:
        blob = f"{load_id}|track"
    else:
        ids = ",".join(f"{item.kind}:{item.value}" for item in parsed.identifiers)
        condition = parsed.condition
        if condition is None:
            cond = ""
        else:
            cond = f"{condition.trigger}:{condition.city or ''}:{condition.place or ''}:{condition.interval_hours or ''}"
        blob = "|".join(
            [
                load_id,
                parsed.intent,
                parsed.role or "",
                ids,
                cond,
                "1" if parsed.same_instructions else "0",
            ]
        )
    digest = hashlib.sha256(blob.encode()).hexdigest()[:10]
    return f"trk-{_slug(load_id)}-{digest}"


def _slug(load_id: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in load_id).strip("-")
    return cleaned[:40] or "load"
