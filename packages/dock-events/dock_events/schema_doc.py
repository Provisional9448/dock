"""JSON Schema for agents. The validator in model.py is the enforcement."""

from __future__ import annotations

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://dock.local/schema/event.json",
    "title": "Dock event",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "event_id",
        "type",
        "occurred_at",
        "recorded_at",
        "load_id",
        "actor",
        "payload",
        "caused_by",
        "source",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "event_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]{8,80}$"},
        "type": {
            "enum": [
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
            ]
        },
        "occurred_at": {"type": "string", "description": "When the fact happened. UTC, trailing Z."},
        "recorded_at": {"type": "string", "description": "When Dock wrote the line. UTC, trailing Z."},
        "load_id": {"type": "string", "minLength": 1},
        "actor": {
            "type": "object",
            "additionalProperties": False,
            "required": ["role", "party_id", "channel"],
            "properties": {
                "role": {"enum": ["driver", "shipper", "consignee", "broker", "carrier", "system"]},
                "party_id": {"type": "string", "minLength": 1},
                "channel": {"enum": ["voice", "sms", "web", "system", "cli"]},
            },
        },
        "payload": {"type": "object"},
        "caused_by": {"type": ["string", "null"]},
        "source": {"type": "string", "pattern": "^[a-z0-9_-]{1,40}$"},
    },
    "description": (
        "Append-only. Consumers sort by occurred_at. File order is write order. "
        "Money fields are strings with two decimals. Unknown payload keys are allowed; "
        "required payload keys are enforced by dock_events.model."
    ),
}
