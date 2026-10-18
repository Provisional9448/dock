"""One JSON object per line. Events are facts. Modules append. Nobody rewrites."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from dock_events.timeutil import parse_time

SCHEMA_VERSION = 1
EVENT_TYPES = (
    "arrived",
    "unload_started",
    "unload_done",
    "delay_reported",
    "notice_sent",
    "call_result",
    "clock_started",
    "charge_risk",
    "claim_drafted",
    "tracking_requested",
)
ROLES = ("driver", "shipper", "consignee", "broker", "carrier", "system")
CHANNELS = ("voice", "sms", "web", "system", "cli")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
SOURCE_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
MONEY_RE = re.compile(r"^\d+\.\d{2}$")
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")

_ISO = "iso"
_ISO_OR_NULL = "iso_or_null"
_MONEY = "money"
_INT = "int"
_STR = "str"


def _iso(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp")
    parse_time(value)


PAYLOAD_RULES: dict[str, dict[str, str]] = {
    "arrived": {
        "facility": _STR,
        "appointment_at": _ISO_OR_NULL,
        "timezone": _STR,
        "reference": _STR,
        "commodity": _STR,
        "origin": _STR,
        "destination": _STR,
        "driver_name": _STR,
        "driver_party_id": _STR,
        "driver_phone": "phone",
        "carrier_name": _STR,
        "carrier_party_id": _STR,
        "shipper_name": _STR,
        "shipper_party_id": _STR,
        "shipper_phone": "phone",
        "consignee_name": _STR,
        "consignee_party_id": _STR,
        "consignee_phone": "phone",
        "broker_name": _STR,
        "broker_party_id": _STR,
        "truck": _STR,
    },
    "unload_started": {"door": _STR},
    "unload_done": {"door": _STR},
    "delay_reported": {"reason": _STR, "detail": _STR},
    "notice_sent": {
        "channel": "notice_channel",
        "to_party_id": _STR,
        "to_role": "role",
        "to_name": _STR,
        "body": _STR,
        "estimated_charge_usd": _MONEY,
        "phase": "phase",
    },
    "call_result": {
        "goal": _STR,
        "outcome": "call_outcome",
        "to_party_id": _STR,
        "to_name": _STR,
        "to_role": "role",
        "summary": _STR,
    },
    "clock_started": {
        "clock_started_at": _ISO,
        "free_time_ends_at": _ISO,
        "free_minutes": _INT,
        "anchor": "anchor",
        "anchor_event_id": _STR,
        "timezone": _STR,
        "rate_usd_per_hour": _MONEY,
        "increment_minutes": _INT,
        "stop_on": "stop_on",
    },
    "charge_risk": {
        "phase": "phase",
        "free_minutes": _INT,
        "elapsed_minutes": _INT,
        "remaining_free_minutes": _INT,
        "billable_minutes": _INT,
        "estimated_charge_usd": _MONEY,
        "rate_usd_per_hour": _MONEY,
        "increment_minutes": _INT,
        "clock_started_at": _ISO,
        "free_time_ends_at": _ISO,
        "how_to_avoid": _STR,
        "timezone": _STR,
        "stop_on": "stop_on",
    },
    "claim_drafted": {
        "title": _STR,
        "markdown": _STR,
        "estimated_charge_usd": _MONEY,
    },
    "tracking_requested": {
        "intent": _STR,
        "summary": _STR,
    },
}


@dataclass(frozen=True)
class Actor:
    role: str
    party_id: str
    channel: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "party_id": self.party_id, "channel": self.channel}


@dataclass(frozen=True)
class Event:
    event_id: str
    type: str
    occurred_at: str
    recorded_at: str
    load_id: str
    actor: Actor
    payload: dict[str, Any]
    schema_version: int = SCHEMA_VERSION
    caused_by: str | None = None
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "type": self.type,
            "occurred_at": self.occurred_at,
            "recorded_at": self.recorded_at,
            "load_id": self.load_id,
            "actor": self.actor.to_dict(),
            "payload": self.payload,
            "caused_by": self.caused_by,
            "source": self.source,
        }


def dumps_event(event: Event) -> str:
    return json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads_event(line: str) -> Event:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not JSON: {exc.msg}") from exc
    if not isinstance(obj, dict):
        raise ValueError("event must be a JSON object")
    return event_from_dict(obj)


def load_jsonl(text: str) -> list[Event]:
    events: list[Event] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            events.append(loads_event(raw))
        except ValueError as exc:
            raise ValueError(f"line {number}: {exc}") from exc
    return events


def dump_jsonl(events: Iterable[Event]) -> str:
    lines = [dumps_event(event) for event in events]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def event_from_dict(obj: Mapping[str, Any]) -> Event:
    missing = [key for key in ("event_id", "type", "occurred_at", "recorded_at", "load_id", "actor", "payload", "source") if key not in obj]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    if obj.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {obj.get('schema_version')!r}")
    event_id = obj["event_id"]
    if not isinstance(event_id, str) or not EVENT_ID_RE.match(event_id):
        raise ValueError(f"bad event_id {event_id!r}")
    event_type = obj["type"]
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown type {event_type!r}")
    occurred_at = obj["occurred_at"]
    recorded_at = obj["recorded_at"]
    _iso(occurred_at, "occurred_at")
    _iso(recorded_at, "recorded_at")
    load_id = obj["load_id"]
    if not isinstance(load_id, str) or not load_id.strip():
        raise ValueError("load_id must be a non-empty string")
    source = obj["source"]
    if not isinstance(source, str) or not SOURCE_RE.match(source):
        raise ValueError(f"bad source {source!r}")
    caused_by = obj.get("caused_by")
    if caused_by is not None and (not isinstance(caused_by, str) or not caused_by):
        raise ValueError("caused_by must be a string or null")
    actor = _actor(obj["actor"])
    payload = obj["payload"]
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    _check_payload(event_type, payload)
    return Event(
        event_id=event_id,
        type=event_type,
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        load_id=load_id,
        actor=actor,
        payload=dict(payload),
        schema_version=SCHEMA_VERSION,
        caused_by=caused_by,
        source=source,
    )


def _actor(value: object) -> Actor:
    if not isinstance(value, dict):
        raise ValueError("actor must be an object")
    role = value.get("role")
    party_id = value.get("party_id")
    channel = value.get("channel")
    if role not in ROLES:
        raise ValueError(f"bad actor.role {role!r}")
    if not isinstance(party_id, str) or not party_id:
        raise ValueError("actor.party_id must be a non-empty string")
    if channel not in CHANNELS:
        raise ValueError(f"bad actor.channel {channel!r}")
    return Actor(role=role, party_id=party_id, channel=channel)


def _check_payload(event_type: str, payload: Mapping[str, Any]) -> None:
    for field, kind in PAYLOAD_RULES[event_type].items():
        if field not in payload:
            raise ValueError(f"{event_type} payload missing {field}")
        _check_field(f"payload.{field}", payload[field], kind)


def _check_field(field: str, value: object, kind: str) -> None:
    if kind == _STR:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
    elif kind == _INT:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    elif kind == _ISO:
        _iso(value, field)
    elif kind == _ISO_OR_NULL:
        if value is not None:
            _iso(value, field)
    elif kind == _MONEY:
        if not isinstance(value, str) or not MONEY_RE.match(value):
            raise ValueError(f"{field} must be a dollar string like 56.25")
    elif kind == "phone":
        if not isinstance(value, str) or not PHONE_RE.match(value):
            raise ValueError(f"{field} must be E.164")
    elif kind == "role":
        if value not in ROLES:
            raise ValueError(f"{field} must be a role")
    elif kind == "notice_channel":
        if value not in ("voice", "sms"):
            raise ValueError(f"{field} must be voice or sms")
    elif kind == "phase":
        if value not in ("warning", "accruing", "closed"):
            raise ValueError(f"{field} must be warning, accruing, or closed")
    elif kind == "anchor":
        if value not in ("appointment", "arrived", "delay_reported"):
            raise ValueError(f"{field} must be appointment, arrived, or delay_reported")
    elif kind == "stop_on":
        if value not in ("unload_started", "unload_done"):
            raise ValueError(f"{field} must be unload_started or unload_done")
    elif kind == "call_outcome":
        if value not in ("reached", "voicemail", "no_answer", "wrong_person", "dry_run"):
            raise ValueError(f"{field} is not a known call outcome")
    else:
        raise ValueError(f"unknown field kind {kind}")
