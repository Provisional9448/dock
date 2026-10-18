"""Load the fictional parties file. Events still carry their own snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_context(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "load" not in data or "parties" not in data:
        raise ValueError(f"{path} must contain load and parties")
    return data


def party_index(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {party["party_id"]: party for party in context["parties"]}


def arrived_payload(context: dict[str, Any]) -> dict[str, Any]:
    load = context["load"]
    parties = party_index(context)

    def person(party_id: str) -> dict[str, Any]:
        try:
            return parties[party_id]
        except KeyError as exc:
            raise ValueError(f"unknown party {party_id}") from exc

    driver = person(load["driver_party_id"])
    carrier = person(load["carrier_party_id"])
    shipper = person(load["shipper_party_id"])
    consignee = person(load["consignee_party_id"])
    broker = person(load["broker_party_id"])
    return {
        "facility": load["facility"],
        "appointment_at": load["appointment_at"],
        "timezone": load["timezone"],
        "reference": load["reference"],
        "commodity": load["commodity"],
        "origin": load["origin"],
        "destination": load["destination"],
        "driver_name": driver["contact"],
        "driver_party_id": driver["party_id"],
        "driver_phone": driver["phone"],
        "carrier_name": carrier["name"],
        "carrier_party_id": carrier["party_id"],
        "shipper_name": shipper["name"],
        "shipper_contact": shipper["contact"],
        "shipper_party_id": shipper["party_id"],
        "shipper_phone": shipper["phone"],
        "consignee_name": consignee["name"],
        "consignee_contact": consignee["contact"],
        "consignee_party_id": consignee["party_id"],
        "consignee_phone": consignee["phone"],
        "broker_name": broker["name"],
        "broker_contact": broker["contact"],
        "broker_party_id": broker["party_id"],
        "broker_phone": broker["phone"],
        "payer_role": load.get("payer_role", "shipper"),
        "truck": load["truck"],
    }
