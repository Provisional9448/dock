"""Replay the dispatcher board and assert the mock's top strip.

Demo clock Sat Oct 17, 2026, 3:50 PM ET. Each LL-*.jsonl file is one load of
raw facts in the dock-events envelope. dock-clock derives the phase and the
dollars; this script does not hard-code those totals.

    uv run python data/samples/board/check_board.py

Heads-ups on the strip are the five voice notice_sent lines already in the
files (inbound calls). dock-notify would compose extra SMS on read; those are
not part of the "5 logged from inbound calls" count.

Identity (driver, facility, door, appointment) lives on arrived, except
LL-88450. Omar is en route: his 3:30 PM text is a driver_eta call_result, and
the file has no arrived line. A delay_reported with no arrival would start
the clock. LL-88421 uses evt_board_arrive_ll88421 and evt_board_delay_ll88421
so those ids do not collide with data/samples/harbor-rye.raw.jsonl.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from dock_clock.policy import DetentionPolicy
from dock_clock.tick import replay_clock
from dock_events.model import Event, load_jsonl
from dock_events.timeutil import format_local, format_local_long, format_time, parse_time
from dock_web.desk import _summary

HERE = Path(__file__).resolve().parent
AS_OF = "2026-10-17T19:50:00Z"
ZONE = "America/New_York"
FREE_MINUTES = 120

# Board order: accruing first, then least free time left.
EXPECTED = [
    {
        "load_id": "LL-88407",
        "driver": "Dana Whitfield",
        "truck": "2207",
        "facility": "Crestline Foods DC",
        "destination": "Allentown, PA",
        "door": "door 11",
        "phase": "accruing",
        "charge": "37.50",
        "past_free_minutes": 30,
        "billable_minutes": 30,
        "free_local": "3:20 PM ET",
        "quote": "Still blocked. They're short a lumper.",
        "channel": "voice",
        "update_at": "2026-10-17T19:44:00Z",
    },
    {
        "load_id": "LL-88415",
        "driver": "Marcus Bell",
        "truck": "0932",
        "facility": "Pinebrook Cold Storage",
        "destination": "Secaucus, NJ",
        "door": "door 2",
        "phase": "accruing",
        "charge": "18.75",
        "past_free_minutes": 12,
        "billable_minutes": 15,
        "free_local": "3:38 PM ET",
        "quote": "Dock says 20 more min.",
        "channel": "sms",
        "update_at": "2026-10-17T19:41:00Z",
    },
    {
        "load_id": "LL-88421",
        "driver": "Luis Ortega",
        "truck": "1841",
        "facility": "Harbor & Rye Grocery DC",
        "destination": "Elizabeth, NJ",
        "door": "door 4",
        "phase": "warning",
        "charge": "0.00",
        "remaining": 16,
        "free_local": "4:06 PM ET",
        "quote": "Still waiting. Door is occupied.",
        "channel": "sms",
        "update_at": "2026-10-17T18:08:00Z",
    },
    {
        "load_id": "LL-88433",
        "driver": "Rosa Delgado",
        "truck": "3310",
        "facility": "Meadowgate Market DC",
        "destination": "Edison, NJ",
        "door": "door 7",
        "phase": "warning",
        "charge": "0.00",
        "remaining": 27,
        "free_local": "4:17 PM ET",
        "quote": "Checked in, doors full. They said maybe four.",
        "channel": "voice",
        "update_at": "2026-10-17T19:35:00Z",
    },
    {
        "load_id": "LL-88438",
        "driver": "Tom Nguyen",
        "truck": "1177",
        "facility": "Harbor & Rye Grocery DC",
        "destination": "Elizabeth, NJ",
        "door": "door 9",
        "phase": "running",
        "charge": "0.00",
        "remaining": 82,
        "free_local": "5:12 PM ET",
        "quote": "Arrived, waiting on a door.",
        "channel": "sms",
        "update_at": "2026-10-17T19:28:00Z",
    },
    {
        "load_id": "LL-88442",
        "driver": "Keisha Brooks",
        "truck": "0418",
        "facility": "Crestline Foods DC",
        "destination": "Allentown, PA",
        "door": "door 3",
        "phase": "running",
        "charge": "0.00",
        "remaining": 108,
        "free_local": "5:38 PM ET",
        "quote": "Backed into door 3, waiting on paperwork.",
        "channel": "voice",
        "update_at": "2026-10-17T19:48:00Z",
    },
    {
        "load_id": "LL-88450",
        "driver": "Omar Haddad",
        "truck": "2290",
        "facility": "Meadowgate Market DC",
        "destination": "Edison, NJ",
        "door": None,
        "phase": "not_started",
        "charge": "0.00",
        "quote": "About 45 out.",
        "channel": "sms",
        "update_at": "2026-10-17T19:30:00Z",
        "appointment_at": "2026-10-17T20:30:00Z",
        "eta_at": "2026-10-17T20:15:00Z",
    },
    {
        "load_id": "LL-88419",
        "driver": "Jen Park",
        "truck": "1502",
        "facility": "Pinebrook Cold Storage",
        "destination": "Secaucus, NJ",
        "door": "door 5",
        "phase": "closed",
        "charge": "0.00",
        "remaining": 0,
        "elapsed_minutes": 75,
        "free_local": "4:00 PM ET",
        "quote": "They started unloading.",
        "channel": "sms",
        "update_at": "2026-10-17T19:15:00Z",
    },
]

HEADS_UPS = [
    ("LL-88407", "consignee", "2026-10-17T18:50:00Z", "warning", "0.00"),
    ("LL-88407", "shipper", "2026-10-17T19:35:00Z", "accruing", "18.75"),
    ("LL-88415", "shipper", "2026-10-17T19:10:00Z", "warning", "0.00"),
    ("LL-88421", "consignee", "2026-10-17T19:40:00Z", "warning", "0.00"),
    ("LL-88433", "consignee", "2026-10-17T19:47:00Z", "warning", "0.00"),
]


def test_dispatcher_board() -> None:
    """4 at risk, $56.25 accruing, next free time 4:06 PM ET on LL-88421."""
    moment = parse_time(AS_OF)
    assert format_local_long(AS_OF, ZONE) == "Sat Oct 17, 2026, 3:50 PM ET"
    raw = _load_files()
    policy = DetentionPolicy()
    assert policy.free_minutes == FREE_MINUTES
    assert policy.rate_text == "75.00"
    assert policy.increment_minutes == 15
    assert policy.warn_minutes == 30
    assert policy.stop_on == "unload_started"

    projected = replay_clock([event for events in raw.values() for event in events], as_of=moment, policy=policy)
    by_load: dict[str, list[Event]] = {load_id: [] for load_id in raw}
    for event in projected:
        by_load[event.load_id].append(event)

    rows = []
    for spec in EXPECTED:
        load_id = spec["load_id"]
        summary = _summary(by_load[load_id], moment, ZONE)
        update = _last_driver_update(raw[load_id], moment)
        arrived = [event for event in raw[load_id] if event.type == "arrived"]
        identity = arrived[0] if arrived else update
        row = {
            "load_id": load_id,
            "phase": summary["phase"],
            "charge": summary["estimated_charge_usd"],
            "remaining": summary["remaining_free_minutes"],
            "elapsed": summary["elapsed_minutes"],
            "billable": summary["billable_minutes"],
            "free_local": summary["free_time_ends_local"],
            "free_end": _free_end(by_load[load_id]),
        }
        rows.append(row)
        if spec["phase"] == "not_started":
            assert arrived == []
        else:
            assert len(arrived) == 1
        _expect_identity(spec, identity, update)
        _expect_clock(spec, summary, by_load[load_id])

    accruing = [row for row in rows if row["phase"] == "accruing"]
    warning = [row for row in rows if row["phase"] == "warning"]
    assert len(accruing) == 2, accruing
    assert len(warning) == 2, warning
    assert len(accruing) + len(warning) == 4
    total = sum((Decimal(row["charge"]) for row in accruing), Decimal("0.00"))
    assert total == Decimal("56.25"), total
    step = (Decimal("75.00") * Decimal(15) / Decimal(60)).quantize(Decimal("0.01"))
    assert step == Decimal("18.75")
    assert step * len(accruing) == Decimal("37.50")

    still_open = [row for row in rows if row["phase"] in ("warning", "running")]
    nxt = min(still_open, key=lambda row: row["free_end"])
    assert nxt["load_id"] == "LL-88421"
    assert nxt["free_local"] == "4:06 PM ET"
    assert [row["load_id"] for row in sorted(rows, key=_board_order)] == [spec["load_id"] for spec in EXPECTED]

    notices = [event for events in raw.values() for event in events if event.type == "notice_sent"]
    assert len(notices) == 5
    assert {(event.load_id, event.payload["to_role"], event.occurred_at, event.payload["phase"], event.payload["estimated_charge_usd"]) for event in notices} == set(HEADS_UPS)
    assert all(event.payload["channel"] == "voice" for event in notices)
    quiet = {"LL-88438", "LL-88442", "LL-88450", "LL-88419"}
    assert not any(event.load_id in quiet for event in notices)

    _expect_story_beats(raw, policy)
    _expect_distinct_ids(raw)


def _expect_identity(spec: dict, arrived: Event, update: Event) -> None:
    payload = arrived.payload
    assert payload["driver_name"] == spec["driver"]
    assert payload["truck"] == spec["truck"]
    assert payload["facility"] == spec["facility"]
    assert payload["destination"] == spec["destination"]
    assert payload.get("door") == spec["door"]
    assert payload["timezone"] == ZONE
    quote = update.payload.get("detail") or update.payload["summary"]
    assert quote == spec["quote"], (spec["load_id"], quote)
    assert update.actor.channel == spec["channel"]
    assert update.actor.role == "driver"
    assert update.occurred_at == spec["update_at"]
    if "appointment_at" in spec:
        assert payload["appointment_at"] == spec["appointment_at"]
    if "eta_at" in spec:
        assert payload["eta_at"] == spec["eta_at"]
        assert update.payload["eta_at"] == spec["eta_at"]


def _expect_clock(spec: dict, summary: dict, projected: list[Event]) -> None:
    assert summary["phase"] == spec["phase"], (spec["load_id"], summary)
    assert summary["estimated_charge_usd"] == spec["charge"]
    if spec["phase"] == "accruing":
        assert summary["elapsed_minutes"] - FREE_MINUTES == spec["past_free_minutes"]
        assert summary["billable_minutes"] == spec["billable_minutes"]
        assert summary["free_time_ends_local"] == spec["free_local"]
    elif spec["phase"] in ("warning", "running"):
        assert summary["remaining_free_minutes"] == spec["remaining"]
        assert summary["estimated_charge_usd"] == "0.00"
        assert summary["free_time_ends_local"] == spec["free_local"]
        if spec["phase"] == "running":
            assert spec["remaining"] > 30
        else:
            assert spec["remaining"] <= 30
    elif spec["phase"] == "closed":
        assert summary["remaining_free_minutes"] == 0
        assert summary["elapsed_minutes"] == spec["elapsed_minutes"]
        assert summary["elapsed_minutes"] < FREE_MINUTES
        assert summary["free_time_ends_local"] == spec["free_local"]
        assert "not an invoice" in summary["how_to_avoid"].lower()
    else:
        assert spec["phase"] == "not_started"
        assert summary["free_time_ends_local"] is None
        assert not any(event.type == "clock_started" for event in projected)
    if spec["phase"] != "not_started":
        clock = next(event for event in projected if event.type == "clock_started")
        assert clock.payload["free_minutes"] == FREE_MINUTES
        assert clock.payload["rate_usd_per_hour"] == "75.00"
        assert clock.payload["increment_minutes"] == 15
        assert clock.payload["stop_on"] == "unload_started"


def _expect_story_beats(raw: dict[str, list[Event]], policy: DetentionPolicy) -> None:
    marcus = _only(raw["LL-88415"], "delay_reported")
    commit = parse_time(marcus.occurred_at) + timedelta(minutes=marcus.payload["minutes_relayed"])
    assert format_time(commit) == "2026-10-17T20:01:00Z"
    assert format_local(format_time(commit), ZONE) == "4:01 PM ET"

    luis_call = _only(raw["LL-88421"], "call_result")
    asked = parse_time(luis_call.occurred_at) + timedelta(minutes=luis_call.payload["minutes_requested"])
    assert format_time(asked) == "2026-10-17T20:20:00Z"
    luis_later = _summary(replay_clock(raw["LL-88421"], as_of=asked, policy=policy), asked, ZONE)
    assert luis_later["phase"] == "accruing"
    assert luis_later["estimated_charge_usd"] == "18.75"
    assert luis_later["billable_minutes"] == 15

    tom = _summary(
        replay_clock(raw["LL-88438"], as_of=parse_time(AS_OF), policy=policy),
        parse_time(AS_OF),
        ZONE,
    )
    flag = _free_end_from_summary_events(raw["LL-88438"], policy) - timedelta(minutes=30)
    assert format_local(format_time(flag), ZONE) == "4:42 PM ET"
    assert tom["phase"] == "running"

    omar = raw["LL-88450"]
    assert not any(event.type == "arrived" for event in omar)
    eta_note = _only(omar, "call_result")
    assert eta_note.payload["goal"] == "driver_eta"
    assert eta_note.payload["status"] == "en_route"
    assert eta_note.payload["eta_at"] == "2026-10-17T20:15:00Z"
    assert eta_note.payload["appointment_at"] == "2026-10-17T20:30:00Z"
    for stamp in (AS_OF, "2026-10-17T20:15:00Z", "2026-10-17T20:30:00Z"):
        projected = replay_clock(omar, as_of=parse_time(stamp), policy=policy)
        assert not any(event.type == "clock_started" for event in projected)

    future = [
        event
        for events in raw.values()
        for event in events
        if parse_time(event.occurred_at) > parse_time(AS_OF)
    ]
    assert future == []


def _expect_distinct_ids(raw: dict[str, list[Event]]) -> None:
    sample = load_jsonl((HERE.parent / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))
    sample_ids = {event.event_id for event in sample}
    board_ids = [event.event_id for events in raw.values() for event in events]
    assert len(board_ids) == len(set(board_ids))
    assert not (sample_ids & set(board_ids))
    luis = {event.event_id for event in raw["LL-88421"]}
    assert "evt_board_arrive_ll88421" in luis
    assert "evt_board_delay_ll88421" in luis


def _free_end_from_summary_events(events: list[Event], policy: DetentionPolicy):
    projected = replay_clock(events, as_of=parse_time(AS_OF), policy=policy)
    return _free_end(projected)


def _free_end(events: list[Event]):
    clocks = [event for event in events if event.type == "clock_started"]
    if not clocks:
        return None
    return parse_time(clocks[0].payload["free_time_ends_at"])


def _load_files() -> dict[str, list[Event]]:
    paths = sorted(HERE.glob("LL-*.jsonl"))
    assert [path.stem for path in paths] == sorted(spec["load_id"] for spec in EXPECTED)
    found: dict[str, list[Event]] = {}
    for path in paths:
        events = load_jsonl(path.read_text(encoding="utf-8"))
        assert events, path.name
        assert {event.load_id for event in events} == {path.stem}
        found[path.stem] = events
    assert len(found) == 8
    return found


def _last_driver_update(events: list[Event], moment) -> Event:
    updates = [
        event
        for event in events
        if event.actor.role == "driver"
        and event.type != "arrived"
        and parse_time(event.occurred_at) <= moment
    ]
    assert updates
    return max(updates, key=lambda event: (event.occurred_at, event.event_id))


def _only(events: list[Event], event_type: str) -> Event:
    found = [event for event in events if event.type == event_type]
    assert len(found) == 1, (event_type, len(found))
    return found[0]


def _board_order(row: dict) -> tuple:
    if row["phase"] == "accruing":
        return (0, -Decimal(row["charge"]))
    if row["phase"] == "warning":
        return (1, row["remaining"])
    if row["phase"] == "running":
        return (2, row["remaining"])
    if row["phase"] == "not_started":
        return (3, 0)
    return (4, 0)


def main() -> int:
    try:
        test_dispatcher_board()
    except AssertionError as exc:
        print(f"board-check: {exc}", file=sys.stderr)
        return 1
    print(
        "board-check: 8 loads, 4 at risk, $56.25 accruing, "
        "next free time 4:06 PM ET on LL-88421"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
