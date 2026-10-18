"""Write the eight dispatcher-board logs.

The mock is site/03-dispatcher-board.html. Demo clock is Sat Oct 17, 2026,
3:50 PM ET (2026-10-17T19:50:00Z). Policy matches the sample load: 120 free
minutes, warn at 30 minutes left, $75.00/hour, 15-minute steps rounded up,
clock stops when unload starts.

Run from the repo root:

    uv run python data/samples/board/build_board.py
    uv run python data/samples/board/check_board.py
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from dock_events.model import Actor, Event, dump_jsonl, event_from_dict
from dock_events.timeutil import format_local, format_time, parse_time

HERE = Path(__file__).resolve().parent
ZONE = "America/New_York"
FREE_MINUTES = 120

CARRIER = {
    "carrier_name": "Red Kettle Freight",
    "carrier_party_id": "pty_red_kettle",
}
BROKER = {
    "broker_name": "Lantern Lane Logistics",
    "broker_party_id": "pty_lantern",
}
SHIPPER = {
    "shipper_name": "Northwind Orchards",
    "shipper_contact": "Sam Okonkwo",
    "shipper_party_id": "pty_northwind",
    "shipper_phone": "+15555550131",
}
HARBOR = {
    "consignee_name": "Harbor & Rye Grocery",
    "consignee_contact": "Priya Shah",
    "consignee_party_id": "pty_harbor_rye",
    "consignee_phone": "+15555550121",
    "facility": "Harbor & Rye Grocery DC",
    "destination": "Elizabeth, NJ",
}
CRESTLINE = {
    "consignee_name": "Crestline Foods",
    "consignee_contact": "Crestline desk",
    "consignee_party_id": "pty_crestline",
    "consignee_phone": "+15555550124",
    "facility": "Crestline Foods DC",
    "destination": "Allentown, PA",
}
PINEBROOK = {
    "consignee_name": "Pinebrook Cold Storage",
    "consignee_contact": "Pinebrook desk",
    "consignee_party_id": "pty_pinebrook",
    "consignee_phone": "+15555550125",
    "facility": "Pinebrook Cold Storage",
    "destination": "Secaucus, NJ",
}
MEADOWGATE = {
    "consignee_name": "Meadowgate Market",
    "consignee_contact": "Meadowgate desk",
    "consignee_party_id": "pty_meadowgate",
    "consignee_phone": "+15555550126",
    "facility": "Meadowgate Market DC",
    "destination": "Edison, NJ",
}

# Clock start is the arrival when the driver is late or on time, and the
# appointment when the driver is early. Free time is 120 minutes after that.
LOADS: list[dict] = [
    {
        "load_id": "LL-88407",
        "driver": "Dana Whitfield",
        "party_id": "pty_dana",
        "phone": "+15555550161",
        "truck": "2207",
        "door": "door 11",
        "place": CRESTLINE,
        "commodity": "22 pallets apples",
        "reference": "PO-44107",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T17:00:00Z",  # 1:00 PM ET
        "arrived_at": "2026-10-17T17:20:00Z",  # 1:20 PM ET, 20 min late
        "update": {
            "at": "2026-10-17T19:44:00Z",  # 3:44 PM ET
            "channel": "voice",
            "reason": "receiver_not_ready",
            "detail": "Still blocked. They're short a lumper.",
        },
        "notices": [
            {
                "at": "2026-10-17T18:50:00Z",  # 2:50 PM ET, warning opens
                "role": "consignee",
                "phase": "warning",
                "estimate": "0.00",
                "summary": "Crestline desk heard the heads-up and did not give a commit time.",
            },
            {
                "at": "2026-10-17T19:35:00Z",  # 3:35 PM ET, one 15-min step, $18.75
                "role": "shipper",
                "phase": "accruing",
                "estimate": "18.75",
                "summary": "Sam Okonkwo heard the $18.75 estimate and said he will push Crestline for a door.",
            },
        ],
    },
    {
        "load_id": "LL-88415",
        "driver": "Marcus Bell",
        "party_id": "pty_marcus",
        "phone": "+15555550162",
        "truck": "0932",
        "door": "door 2",
        "place": PINEBROOK,
        "commodity": "16 pallets frozen berries",
        "reference": "PO-44115",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T17:30:00Z",  # 1:30 PM ET
        "arrived_at": "2026-10-17T17:38:00Z",  # 1:38 PM ET, 8 min late
        "update": {
            "at": "2026-10-17T19:41:00Z",  # 3:41 PM ET
            "channel": "sms",
            "reason": "receiver_not_ready",
            "detail": "Dock says 20 more min.",
            "minutes_relayed": 20,  # 3:41 + 20 min = 4:01 PM ET
        },
        "notices": [
            {
                "at": "2026-10-17T19:10:00Z",  # 3:10 PM ET, inside the warning window
                "role": "shipper",
                "phase": "warning",
                "estimate": "0.00",
                "summary": "Sam Okonkwo heard the heads-up. Estimate $0.00. Free time ends 3:38 PM ET.",
            },
        ],
    },
    {
        "load_id": "LL-88421",
        "driver": "Luis Ortega",
        "party_id": "pty_luis",
        "phone": "+15555550114",
        "truck": "1841",
        "door": "door 4",
        "place": HARBOR,
        "commodity": "18 pallets citrus",
        "reference": "PO-44190",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T18:00:00Z",  # 2:00 PM ET
        "arrived_at": "2026-10-17T18:06:00Z",  # 2:06 PM ET, 6 min late
        "update": {
            "at": "2026-10-17T18:08:00Z",  # 2:08 PM ET
            "channel": "sms",
            "reason": "no_door_available",
            "detail": "Checked in 2:06. No doors, told to wait in truck, maybe 40 min.",
        },
        "notices": [
            {
                "at": "2026-10-17T19:40:00Z",  # 3:40 PM ET DC call
                "role": "consignee",
                "phase": "warning",
                "estimate": "0.00",
                "minutes_requested": 40,  # 3:40 + 40 min = 4:20 PM ET, one step, $18.75
                "summary": "Priya said door 4 is still occupied and they can start in about 40 minutes.",
            },
        ],
    },
    {
        "load_id": "LL-88433",
        "driver": "Rosa Delgado",
        "party_id": "pty_rosa",
        "phone": "+15555550163",
        "truck": "3310",
        "door": "door 7",
        "place": MEADOWGATE,
        "commodity": "20 pallets stone fruit",
        "reference": "PO-44133",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T18:00:00Z",  # 2:00 PM ET
        "arrived_at": "2026-10-17T18:17:00Z",  # 2:17 PM ET, 17 min late
        "update": {
            "at": "2026-10-17T19:35:00Z",  # 3:35 PM ET
            "channel": "voice",
            "reason": "door_occupied",
            "detail": "Checked in, doors full. They said maybe four.",
        },
        "notices": [
            {
                "at": "2026-10-17T19:47:00Z",  # 3:47 PM ET, warning opens
                "role": "consignee",
                "phase": "warning",
                "estimate": "0.00",
                "summary": "Meadowgate desk heard the heads-up and did not give a commit time.",
            },
        ],
    },
    {
        "load_id": "LL-88438",
        "driver": "Tom Nguyen",
        "party_id": "pty_tom",
        "phone": "+15555550164",
        "truck": "1177",
        "door": "door 9",
        "place": HARBOR,
        "commodity": "12 pallets citrus",
        "reference": "PO-44138",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T19:00:00Z",  # 3:00 PM ET
        "arrived_at": "2026-10-17T19:12:00Z",  # 3:12 PM ET, 12 min late
        "update": {
            "at": "2026-10-17T19:28:00Z",  # 3:28 PM ET
            "channel": "sms",
            "reason": "receiver_not_ready",
            "detail": "Arrived, waiting on a door.",
        },
    },
    {
        "load_id": "LL-88442",
        "driver": "Keisha Brooks",
        "party_id": "pty_keisha",
        "phone": "+15555550165",
        "truck": "0418",
        "door": "door 3",
        "place": CRESTLINE,
        "commodity": "14 pallets apples",
        "reference": "PO-44142",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T19:30:00Z",  # 3:30 PM ET
        "arrived_at": "2026-10-17T19:38:00Z",  # 3:38 PM ET, 8 min late
        "update": {
            "at": "2026-10-17T19:48:00Z",  # 3:48 PM ET
            "channel": "voice",
            "reason": "paperwork",
            "detail": "Backed into door 3, waiting on paperwork.",
        },
    },
    {
        # En route at the demo clock. The 3:30 PM text is a driver_eta note.
        # There is no arrived line: a future arrival would be a fact that has
        # not happened yet, and a delay_reported with no arrival would start
        # the clock. Appointment 4:30 PM ET, ETA 4:15 PM ET.
        "load_id": "LL-88450",
        "driver": "Omar Haddad",
        "party_id": "pty_omar",
        "phone": "+15555550166",
        "truck": "2290",
        "door": None,
        "place": MEADOWGATE,
        "commodity": "18 pallets stone fruit",
        "reference": "PO-44150",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T20:30:00Z",  # 4:30 PM ET
        "eta_at": "2026-10-17T20:15:00Z",  # 4:15 PM ET, not an arrival
        "eta": {
            "at": "2026-10-17T19:30:00Z",  # 3:30 PM ET, about 45 min out
            "channel": "sms",
            "detail": "About 45 out.",
        },
    },
    {
        "load_id": "LL-88419",
        "driver": "Jen Park",
        "party_id": "pty_jen",
        "phone": "+15555550167",
        "truck": "1502",
        "door": "door 5",
        "place": PINEBROOK,
        "commodity": "8 pallets frozen berries",
        "reference": "PO-44119",
        "origin": "Fresno, CA",
        "appointment_at": "2026-10-17T18:00:00Z",  # 2:00 PM ET
        "arrived_at": "2026-10-17T18:00:00Z",  # on time
        "unload": {
            "at": "2026-10-17T19:15:00Z",  # 3:15 PM ET, inside free time
            "channel": "sms",
            "detail": "They started unloading.",
        },
    },
]


def main() -> None:
    for spec in LOADS:
        events = build_load(spec)
        for event in events:
            event_from_dict(event.to_dict())
        path = HERE / f"{spec['load_id']}.jsonl"
        path.write_text(dump_jsonl(events), encoding="utf-8")
        print(f"wrote {path.name} ({len(events)} events)")


def build_load(spec: dict) -> list[Event]:
    load_id = spec["load_id"]
    slug = load_id.replace("-", "").lower()
    events = [
        *_update(spec, slug),
        *_notices(spec, slug),
        *_unload(spec, slug),
    ]
    if not spec.get("eta"):
        events.insert(0, _arrived(spec, slug))
    rank = {
        "arrived": 0,
        "delay_reported": 1,
        "notice_sent": 2,
        "call_result": 3,
        "unload_started": 4,
    }
    return sorted(events, key=lambda event: (event.occurred_at, rank.get(event.type, 9), event.event_id))


def _arrived(spec: dict, slug: str) -> Event:
    place = spec["place"]
    payload = {
        "facility": place["facility"],
        "appointment_at": spec["appointment_at"],
        "timezone": ZONE,
        "reference": spec["reference"],
        "commodity": spec["commodity"],
        "origin": spec["origin"],
        "destination": place["destination"],
        "driver_name": spec["driver"],
        "driver_party_id": spec["party_id"],
        "driver_phone": spec["phone"],
        **CARRIER,
        **SHIPPER,
        "consignee_name": place["consignee_name"],
        "consignee_contact": place["consignee_contact"],
        "consignee_party_id": place["consignee_party_id"],
        "consignee_phone": place["consignee_phone"],
        **BROKER,
        "truck": spec["truck"],
    }
    if spec["door"]:
        payload["door"] = spec["door"]
    return _event(
        _fact_id("arrive", slug, spec["load_id"]),
        "arrived",
        spec["arrived_at"],
        spec["load_id"],
        Actor(role="driver", party_id=spec["party_id"], channel="voice"),
        payload,
        recorded_offset=22,
    )


def _update(spec: dict, slug: str) -> list[Event]:
    if spec.get("eta"):
        return [_eta(spec, slug)]
    update = spec.get("update")
    if update is None:
        return []
    payload = {"reason": update["reason"], "detail": update["detail"]}
    if "minutes_relayed" in update:
        payload["minutes_relayed"] = update["minutes_relayed"]
    return [
        _event(
            _fact_id("delay", slug, spec["load_id"]),
            "delay_reported",
            update["at"],
            spec["load_id"],
            Actor(role="driver", party_id=spec["party_id"], channel=update["channel"]),
            payload,
            recorded_offset=18,
        )
    ]


def _eta(spec: dict, slug: str) -> Event:
    eta = spec["eta"]
    place = spec["place"]
    return _event(
        f"evt_eta_{slug}",
        "call_result",
        eta["at"],
        spec["load_id"],
        Actor(role="driver", party_id=spec["party_id"], channel=eta["channel"]),
        {
            "goal": "driver_eta",
            "outcome": "reached",
            "to_party_id": CARRIER["carrier_party_id"],
            "to_name": "Dispatch",
            "to_role": "carrier",
            "summary": eta["detail"],
            "detail": eta["detail"],
            "eta_at": spec["eta_at"],
            "appointment_at": spec["appointment_at"],
            "facility": place["facility"],
            "destination": place["destination"],
            "driver_name": spec["driver"],
            "truck": spec["truck"],
            "timezone": ZONE,
            "status": "en_route",
        },
        recorded_offset=15,
    )


def _notices(spec: dict, slug: str) -> list[Event]:
    out: list[Event] = []
    for notice in spec.get("notices") or []:
        role = notice["role"]
        who = _who(spec, role)
        notice_id = f"ntc_{slug}_{role}_{notice['phase'][:4]}"
        body = _body(spec, notice)
        out.append(
            _event(
                notice_id,
                "notice_sent",
                notice["at"],
                spec["load_id"],
                Actor(role="system", party_id="dock-voice", channel="voice"),
                {
                    "channel": "voice",
                    "to_party_id": who["party_id"],
                    "to_role": role,
                    "to_name": who["name"],
                    "body": body,
                    "estimated_charge_usd": notice["estimate"],
                    "phase": notice["phase"],
                    "provider": "guava",
                    "delivery_status": "spoken",
                },
                recorded_offset=20,
            )
        )
        call_payload = {
            "goal": "receiver_delay",
            "outcome": "reached",
            "to_party_id": who["party_id"],
            "to_name": who["name"],
            "to_role": role,
            "summary": notice["summary"],
        }
        if "minutes_requested" in notice:
            call_payload["minutes_requested"] = notice["minutes_requested"]
        out.append(
            _event(
                f"call_{slug}_{role}_{notice['phase'][:4]}",
                "call_result",
                notice["at"],
                spec["load_id"],
                Actor(role="system", party_id="dock-voice", channel="voice"),
                call_payload,
                caused_by=notice_id,
                recorded_offset=65,
            )
        )
    return out


def _unload(spec: dict, slug: str) -> list[Event]:
    unload = spec.get("unload")
    if unload is None:
        return []
    return [
        _event(
            f"evt_unload_{slug}",
            "unload_started",
            unload["at"],
            spec["load_id"],
            Actor(role="driver", party_id=spec["party_id"], channel=unload["channel"]),
            {"door": spec["door"], "detail": unload["detail"]},
            recorded_offset=40,
        )
    ]


def _who(spec: dict, role: str) -> dict[str, str]:
    if role == "shipper":
        return {"name": SHIPPER["shipper_contact"], "party_id": SHIPPER["shipper_party_id"]}
    if role == "consignee":
        place = spec["place"]
        return {"name": place["consignee_contact"], "party_id": place["consignee_party_id"]}
    raise ValueError(role)


def _body(spec: dict, notice: dict) -> str:
    place = spec["place"]
    where = place["facility"]
    if spec["door"]:
        where = f"{where}, {spec['door']}"
    start = _clock_start(spec)
    free_end = format_time(parse_time(start) + timedelta(minutes=FREE_MINUTES))
    since = format_local(start, ZONE)
    ends = format_local(free_end, ZONE)
    estimate = notice["estimate"]
    if notice["phase"] == "warning":
        clock_line = f"Free time ends {ends}. Estimate so far ${estimate}. Start the unload before {ends} and this trail stays $0.00."
    else:
        clock_line = (
            f"Free time ended {ends}. Estimate so far ${estimate}. "
            "Unload has not started. This clock stops when the unload starts."
        )
    return (
        f"Dock, load {spec['load_id']}. Not an invoice. "
        f"{spec['driver']} (Red Kettle Freight) has been at {where} since {since}. "
        f"{clock_line}"
    )


def _fact_id(kind: str, slug: str, load_id: str) -> str:
    # LL-88421's arrival and delay already live in harbor-rye.raw.jsonl, with
    # different payloads. The board copy needs its own ids.
    if load_id == "LL-88421" and kind in ("arrive", "delay"):
        return f"evt_board_{kind}_{slug}"
    return f"evt_{kind}_{slug}"


def _clock_start(spec: dict) -> str:
    if parse_time(spec["arrived_at"]) < parse_time(spec["appointment_at"]):
        return spec["appointment_at"]
    return spec["arrived_at"]


def _event(
    event_id: str,
    event_type: str,
    occurred_at: str,
    load_id: str,
    actor: Actor,
    payload: dict,
    *,
    caused_by: str | None = None,
    recorded_offset: int,
) -> Event:
    return Event(
        event_id=event_id,
        type=event_type,
        occurred_at=occurred_at,
        recorded_at=format_time(parse_time(occurred_at) + timedelta(seconds=recorded_offset)),
        load_id=load_id,
        actor=actor,
        payload=payload,
        caused_by=caused_by,
        source="sample",
    )


if __name__ == "__main__":
    main()
