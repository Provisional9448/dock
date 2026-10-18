"""Scenario coverage for the free-time clock.

Fictional Harbor & Rye loads only. Timestamps in the assertions are UTC.
America/New_York labels are ET, including the winter offset.
"""

from datetime import timedelta

import pytest

from dock_clock.cli import main as clock_main
from dock_clock.policy import DetentionPolicy
from dock_clock.tick import replay_clock, tick
from dock_events.context import arrived_payload, load_context
from dock_events.model import Actor, Event, dump_jsonl, event_from_dict, load_jsonl
from dock_events.timeutil import parse_time
from helpers import run_cli

DRIVER = Actor(role="driver", party_id="pty_luis", channel="voice")
POLICY = DetentionPolicy()


def _arrive(
    sample_dir,
    load_id: str,
    occurred_at: str,
    appointment_at: str,
    *,
    event_id: str,
    recorded_at: str | None = None,
    timezone: str = "America/New_York",
) -> Event:
    payload = arrived_payload(load_context(sample_dir / "parties.json"))
    payload["appointment_at"] = appointment_at
    payload["timezone"] = timezone
    return Event(
        event_id=event_id,
        type="arrived",
        occurred_at=occurred_at,
        recorded_at=recorded_at or occurred_at,
        load_id=load_id,
        actor=DRIVER,
        payload=payload,
        source="sample",
    )


def _delay(load_id: str, occurred_at: str, event_id: str, **extra) -> Event:
    payload = {
        "reason": "door_occupied",
        "detail": "Door 4 is occupied. They are not ready to unload.",
    }
    payload.update(extra)
    return Event(
        event_id=event_id,
        type="delay_reported",
        occurred_at=occurred_at,
        recorded_at=occurred_at,
        load_id=load_id,
        actor=DRIVER,
        payload=payload,
        source="sample",
    )


def _unload(load_id: str, occurred_at: str, event_id: str, *, recorded_at: str | None = None) -> Event:
    return Event(
        event_id=event_id,
        type="unload_started",
        occurred_at=occurred_at,
        recorded_at=recorded_at or occurred_at,
        load_id=load_id,
        actor=DRIVER,
        payload={"door": "door 4"},
        source="sample",
    )


def _risks(events: list[Event]) -> list[Event]:
    risks = [event for event in events if event.type == "charge_risk"]
    return sorted(risks, key=lambda event: (parse_time(event.occurred_at), event.event_id))


def _started(events: list[Event]) -> Event:
    return next(event for event in events if event.type == "clock_started")


def _roundtrip(events: list[Event]) -> list[Event]:
    return [event_from_dict(event.to_dict()) for event in events]


def _at(events: list[Event], moment: str) -> list[Event]:
    return _roundtrip(tick(events, as_of=parse_time(moment), policy=POLICY))


def test_on_time_arrival_starts_at_the_appointment_instant(sample_dir):
    # Appointment is +00:00 and arrival is Z. Same instant: on time, not early.
    arrived = _arrive(
        sample_dir,
        "LL-10011",
        "2026-10-17T18:00:00Z",
        "2026-10-17T18:00:00+00:00",
        event_id="evt_arr_ll10011",
    )
    facts = [arrived]

    assert _at(facts, "2026-10-17T17:59:00Z") == []

    started_only = _at(facts, "2026-10-17T18:00:00Z")
    assert [event.type for event in started_only] == ["clock_started"]
    started = started_only[0]
    assert started.payload["anchor"] == "arrived"
    assert started.payload["clock_started_at"] == "2026-10-17T18:00:00Z"
    assert started.payload["free_time_ends_at"] == "2026-10-17T20:00:00Z"
    assert started.payload["timezone"] == "America/New_York"
    assert started.payload["rate_usd_per_hour"] == "75.00"

    still_outside_warning = _at(facts, "2026-10-17T19:29:00Z")
    assert [event.type for event in still_outside_warning] == ["clock_started"]

    warning = _risks(_at(facts, "2026-10-17T19:30:00Z"))
    assert len(warning) == 1
    assert warning[0].payload["phase"] == "warning"
    assert warning[0].payload["elapsed_minutes"] == 90
    assert warning[0].payload["remaining_free_minutes"] == 30
    assert warning[0].payload["billable_minutes"] == 0
    assert warning[0].payload["estimated_charge_usd"] == "0.00"
    assert warning[0].payload["how_to_avoid"] == (
        "Start the unload before 4:00 PM ET. "
        "After that, this trail adds $18.75 every 15 minutes."
    )

    ending = _risks(_at(facts, "2026-10-17T20:00:00Z"))
    assert ending[0].payload["phase"] == "warning"
    assert ending[0].payload["elapsed_minutes"] == 120
    assert ending[0].payload["remaining_free_minutes"] == 0
    assert ending[0].payload["estimated_charge_usd"] == "0.00"


def test_late_arrival_starts_free_time_at_arrival_not_the_appointment(sample_dir):
    # Appointment 2:00 PM ET. Delay call at 2:10. Driver arrives at 3:00 PM ET.
    load = "LL-10012"
    delay = _delay(load, "2026-10-17T18:10:00Z", "evt_delay_ll10012")
    arrived = _arrive(
        sample_dir,
        load,
        "2026-10-17T19:00:00Z",
        "2026-10-17T18:00:00Z",
        event_id="evt_arr_ll10012",
    )
    facts = [delay, arrived]

    before_arrival = _at(facts, "2026-10-17T18:40:00Z")
    assert _started(before_arrival).payload["anchor"] == "delay_reported"
    assert _started(before_arrival).payload["clock_started_at"] == "2026-10-17T18:10:00Z"
    assert _risks(before_arrival) == []

    at_arrival = _at(facts, "2026-10-17T19:00:00Z")
    started = _started(at_arrival)
    assert started.payload["anchor"] == "arrived"
    assert started.payload["clock_started_at"] == "2026-10-17T19:00:00Z"
    assert started.payload["free_time_ends_at"] == "2026-10-17T21:00:00Z"
    assert started.caused_by == "evt_arr_ll10012"
    assert _risks(at_arrival) == []

    # 4:00 PM ET is when free time would have ended if the appointment had started it.
    still_free = _at(facts, "2026-10-17T20:00:00Z")
    assert _started(still_free).payload["free_time_ends_at"] == "2026-10-17T21:00:00Z"
    assert _risks(still_free) == []

    warning = _risks(_at(facts, "2026-10-17T20:30:00Z"))
    assert warning[0].payload["phase"] == "warning"
    assert warning[0].payload["elapsed_minutes"] == 90
    assert warning[0].payload["remaining_free_minutes"] == 30
    assert warning[0].payload["estimated_charge_usd"] == "0.00"
    assert warning[0].payload["clock_started_at"] == "2026-10-17T19:00:00Z"
    assert "5:00 PM ET" in warning[0].payload["how_to_avoid"]


def test_unload_before_free_time_ends_is_zero(sample_dir):
    # Free time ends 8:00 PM ET. Unload starts at 7:50 PM ET, ten minutes left.
    load = "LL-10013"
    facts = [
        _arrive(sample_dir, load, "2026-10-17T18:00:00Z", "2026-10-17T18:00:00Z", event_id="evt_arr_ll10013"),
        _unload(load, "2026-10-17T19:50:00Z", "evt_unload_ll10013"),
    ]

    closed = _risks(_at(facts, "2026-10-17T19:50:00Z"))
    assert [event.payload["phase"] for event in closed] == ["closed"]
    assert closed[0].payload["elapsed_minutes"] == 110
    assert closed[0].payload["remaining_free_minutes"] == 10
    assert closed[0].payload["billable_minutes"] == 0
    assert closed[0].payload["estimated_charge_usd"] == "0.00"
    assert closed[0].payload["how_to_avoid"] == (
        "This clock stopped when the unload started. "
        "This trail supports $0.00. It is not an invoice."
    )
    assert closed[0].occurred_at == "2026-10-17T19:50:00Z"

    later = _risks(_at(facts, "2026-10-17T21:00:00Z"))
    assert later[0].payload["estimated_charge_usd"] == "0.00"
    assert later[0].payload["elapsed_minutes"] == 110
    assert later[0].occurred_at == "2026-10-17T19:50:00Z"
    assert later[0].recorded_at == "2026-10-17T21:00:00Z"
    assert later[0].event_id == "clk-ll-10013-closed"

    replayed = _roundtrip(replay_clock(facts, as_of=parse_time("2026-10-17T21:00:00Z"), policy=POLICY))
    risks = _risks(replayed)
    assert [event.payload["phase"] for event in risks] == ["warning", "closed"]
    assert [event.payload["estimated_charge_usd"] for event in risks] == ["0.00", "0.00"]
    assert all(event.payload["billable_minutes"] == 0 for event in risks)


def test_clock_stop_mid_accrual_freezes_the_rounded_charge(sample_dir):
    # On time 2:00 PM ET. Free time ends 4:00 PM ET. Unload at 4:42 PM ET.
    # 42 minutes past free time bills as 45 minutes: 45 / 60 * 75 = 56.25.
    load = "LL-10014"
    facts = [
        _arrive(sample_dir, load, "2026-10-17T18:00:00Z", "2026-10-17T18:00:00Z", event_id="evt_arr_ll10014"),
        _unload(load, "2026-10-17T20:42:00Z", "evt_unload_ll10014"),
    ]

    closed = _risks(_at(facts, "2026-10-17T20:42:00Z"))
    assert closed[0].payload["phase"] == "closed"
    assert closed[0].payload["elapsed_minutes"] == 162
    assert closed[0].payload["billable_minutes"] == 45
    assert closed[0].payload["estimated_charge_usd"] == "56.25"
    assert closed[0].payload["how_to_avoid"] == (
        "This clock stopped when the unload started. "
        "This trail supports $56.25. It is not an invoice."
    )

    held = _risks(_at(facts, "2026-10-17T23:42:00Z"))
    assert held[0].event_id == closed[0].event_id
    assert held[0].payload["elapsed_minutes"] == 162
    assert held[0].payload["billable_minutes"] == 45
    assert held[0].payload["estimated_charge_usd"] == "56.25"
    assert held[0].occurred_at == "2026-10-17T20:42:00Z"
    assert held[0].recorded_at == "2026-10-17T23:42:00Z"

    replayed = _roundtrip(replay_clock(facts, as_of=parse_time("2026-10-17T23:42:00Z"), policy=POLICY))
    risks = _risks(replayed)
    assert [event.payload["phase"] for event in risks] == ["warning", "accruing", "closed"]
    assert [event.payload["estimated_charge_usd"] for event in risks] == ["0.00", "18.75", "56.25"]
    assert [event.payload["billable_minutes"] for event in risks] == [0, 15, 45]
    assert [event.payload["elapsed_minutes"] for event in risks] == [90, 135, 162]
    assert risks[1].event_id == "clk-ll-10014-accruing-20261017T201500Z"
    assert risks[1].occurred_at == "2026-10-17T20:15:00Z"
    assert risks[2].occurred_at == "2026-10-17T20:42:00Z"
    assert [event.event_id for event in risks].count("clk-ll-10014-closed") == 1


@pytest.mark.parametrize(
    ("minutes_past", "phase", "billable", "charge"),
    [
        (0, "warning", 0, "0.00"),
        (1, "accruing", 15, "18.75"),
        (7, "accruing", 15, "18.75"),
        (15, "accruing", 15, "18.75"),
        (16, "accruing", 30, "37.50"),
        (42, "accruing", 45, "56.25"),
        (45, "accruing", 45, "56.25"),
        (46, "accruing", 60, "75.00"),
    ],
)
def test_billing_rounds_up_to_15_minute_steps_at_75_per_hour(sample_dir, minutes_past, phase, billable, charge):
    start = parse_time("2026-10-17T18:00:00Z")
    moment = start + timedelta(minutes=120 + minutes_past)
    facts = [
        _arrive(
            sample_dir,
            "LL-10015",
            "2026-10-17T18:00:00Z",
            "2026-10-17T18:00:00Z",
            event_id="evt_arr_ll10015",
        )
    ]
    risk = _risks(_roundtrip(tick(facts, as_of=moment, policy=POLICY)))[0]
    assert risk.payload["phase"] == phase
    assert risk.payload["elapsed_minutes"] == 120 + minutes_past
    assert risk.payload["billable_minutes"] == billable
    assert risk.payload["estimated_charge_usd"] == charge
    assert risk.payload["rate_usd_per_hour"] == "75.00"
    assert risk.payload["increment_minutes"] == 15
    assert isinstance(risk.payload["estimated_charge_usd"], str)


def test_crossing_midnight_does_not_reset_elapsed_time(sample_dir):
    # 11:00 PM ET appointment. Free time runs through local midnight and ends 1:00 AM ET.
    load = "LL-10016"
    overnight = [
        _arrive(
            sample_dir,
            load,
            "2026-10-18T03:00:00Z",
            "2026-10-17T23:00:00-04:00",
            event_id="evt_arr_ll10016",
        )
    ]

    after_local_midnight = _at(overnight, "2026-10-18T04:30:00Z")
    started = _started(after_local_midnight)
    assert started.payload["anchor"] == "arrived"
    assert started.payload["clock_started_at"] == "2026-10-18T03:00:00Z"
    assert started.payload["free_time_ends_at"] == "2026-10-18T05:00:00Z"
    warning = _risks(after_local_midnight)
    assert warning[0].payload["phase"] == "warning"
    assert warning[0].payload["elapsed_minutes"] == 90
    assert warning[0].payload["remaining_free_minutes"] == 30
    assert warning[0].payload["estimated_charge_usd"] == "0.00"
    assert warning[0].payload["how_to_avoid"] == (
        "Start the unload before 1:00 AM ET. "
        "After that, this trail adds $18.75 every 15 minutes."
    )

    billed = _risks(_at(overnight, "2026-10-18T05:42:00Z"))
    assert billed[0].payload["phase"] == "accruing"
    assert billed[0].payload["elapsed_minutes"] == 162
    assert billed[0].payload["billable_minutes"] == 45
    assert billed[0].payload["estimated_charge_usd"] == "56.25"
    assert billed[0].event_id == "clk-ll-10016-accruing-20261018T054200Z"

    # 7:40 PM ET through 00:10 UTC is still the same free-time window.
    # The warning an hour later counts 90 minutes from 23:40Z.
    utc_night = [
        _arrive(
            sample_dir,
            "LL-10016B",
            "2026-10-17T23:40:00Z",
            "2026-10-17T23:40:00Z",
            event_id="evt_arr_ll10016b",
        )
    ]
    across_utc = _at(utc_night, "2026-10-18T00:10:00Z")
    assert _started(across_utc).payload["clock_started_at"] == "2026-10-17T23:40:00Z"
    assert _started(across_utc).payload["free_time_ends_at"] == "2026-10-18T01:40:00Z"
    assert _risks(across_utc) == []
    # Still inside free time, so the snapshot is clock_started only. Ask again at the warning line.
    utc_warning = _risks(_at(utc_night, "2026-10-18T01:10:00Z"))
    assert utc_warning[0].payload["elapsed_minutes"] == 90
    assert utc_warning[0].payload["remaining_free_minutes"] == 30
    assert utc_warning[0].payload["free_time_ends_at"] == "2026-10-18T01:40:00Z"
    assert "9:40 PM ET" in utc_warning[0].payload["how_to_avoid"]


def test_et_facility_uses_new_york_wall_time_in_summer_and_winter(sample_dir):
    # Early arrival, appointment written with the October EDT offset. Clock waits.
    summer = [
        _arrive(
            sample_dir,
            "LL-10017",
            "2026-10-17T17:40:00Z",
            "2026-10-17T14:00:00-04:00",
            event_id="evt_arr_ll10017",
        )
    ]
    assert _at(summer, "2026-10-17T17:50:00Z") == []
    summer_warning = _risks(_at(summer, "2026-10-17T19:30:00Z"))
    assert _started(_at(summer, "2026-10-17T18:30:00Z")).payload["anchor"] == "appointment"
    assert _started(_at(summer, "2026-10-17T18:30:00Z")).payload["clock_started_at"] == "2026-10-17T18:00:00Z"
    assert summer_warning[0].payload["timezone"] == "America/New_York"
    assert summer_warning[0].payload["free_time_ends_at"] == "2026-10-17T20:00:00Z"
    assert summer_warning[0].payload["how_to_avoid"].startswith("Start the unload before 4:00 PM ET.")

    # Same wall-clock appointment in January is UTC-5. 4:00 PM ET is 21:00Z, not 20:00Z.
    winter = [
        _arrive(
            sample_dir,
            "LL-10017W",
            "2026-01-16T19:00:00Z",
            "2026-01-16T14:00:00-05:00",
            event_id="evt_arr_ll10017w",
        )
    ]
    winter_warning = _risks(_at(winter, "2026-01-16T20:30:00Z"))
    assert _started(_at(winter, "2026-01-16T19:00:00Z")).payload["anchor"] == "arrived"
    assert winter_warning[0].payload["timezone"] == "America/New_York"
    assert winter_warning[0].payload["free_time_ends_at"] == "2026-01-16T21:00:00Z"
    assert winter_warning[0].payload["how_to_avoid"].startswith("Start the unload before 4:00 PM ET.")

    # 2026-11-01 06:00Z is the ET fallback (2:00 AM EDT back to 1:00 AM EST).
    # 05:00Z to 07:30Z is 150 real minutes, not 90 minutes of wall-clock time.
    fallback = [
        _arrive(
            sample_dir,
            "LL-10017F",
            "2026-11-01T05:00:00Z",
            "2026-11-01T05:00:00Z",
            event_id="evt_arr_ll10017f",
        )
    ]
    across = _risks(_at(fallback, "2026-11-01T07:30:00Z"))
    assert across[0].payload["phase"] == "accruing"
    assert across[0].payload["elapsed_minutes"] == 150
    assert across[0].payload["billable_minutes"] == 30
    assert across[0].payload["estimated_charge_usd"] == "37.50"
    assert across[0].payload["free_time_ends_at"] == "2026-11-01T07:00:00Z"
    assert across[0].payload["timezone"] == "America/New_York"
    at_free_end = _risks(_at(fallback, "2026-11-01T07:00:00Z"))
    assert at_free_end[0].payload["phase"] == "warning"
    assert at_free_end[0].payload["how_to_avoid"].startswith("Start the unload before 2:00 AM ET.")


def test_duplicate_and_out_of_order_events_follow_occurred_at(sample_dir):
    # Two arrivals share 18:20Z. The earlier event id is the ET arrival.
    # A later Chicago arrival is written first. A later unload is written as an
    # offset that sorts ahead of the real stop as text. A future unload is first.
    load = "LL-10018"
    east = _arrive(
        sample_dir,
        load,
        "2026-10-17T18:20:00Z",
        "2026-10-17T18:00:00Z",
        event_id="evt_arr_east_ll10018",
        recorded_at="2026-10-17T18:21:00Z",
    )
    west = _arrive(
        sample_dir,
        load,
        "2026-10-17T18:20:00Z",
        "2026-10-17T19:00:00Z",
        event_id="evt_arr_west_ll10018",
        recorded_at="2026-10-17T18:19:00Z",
        timezone="America/Chicago",
    )
    later = _arrive(
        sample_dir,
        load,
        "2026-10-17T19:30:00Z",
        "2026-10-17T19:30:00Z",
        event_id="evt_arr_late_ll10018",
        recorded_at="2026-10-17T17:00:00Z",
        timezone="America/Chicago",
    )
    delay = _delay(load, "2026-10-17T18:22:00Z", "evt_delay_ll10018", timezone="America/Chicago")
    real_stop = _unload(
        load,
        "2026-10-17T20:32:00Z",
        "evt_unload_real_ll10018",
        recorded_at="2026-10-17T20:40:00Z",
    )
    later_stop = _unload(
        load,
        "2026-10-17T17:00:00-04:00",
        "evt_unload_late_ll10018",
        recorded_at="2026-10-17T18:00:00Z",
    )
    future_stop = _unload(
        load,
        "2026-10-17T22:00:00Z",
        "evt_unload_future_ll10018",
        recorded_at="2026-10-17T17:05:00Z",
    )
    scrambled = [future_stop, later, delay, later_stop, west, real_stop, east, east]

    def assert_closed(produced: list[Event]) -> None:
        started = _started(produced)
        assert started.payload["anchor"] == "arrived"
        assert started.payload["clock_started_at"] == "2026-10-17T18:20:00Z"
        assert started.payload["free_time_ends_at"] == "2026-10-17T20:20:00Z"
        assert started.payload["timezone"] == "America/New_York"
        assert started.caused_by == "evt_arr_east_ll10018"
        risks = _risks(produced)
        assert [event.payload["phase"] for event in risks] == ["closed"]
        assert risks[0].payload["elapsed_minutes"] == 132
        assert risks[0].payload["billable_minutes"] == 15
        assert risks[0].payload["estimated_charge_usd"] == "18.75"
        assert risks[0].payload["timezone"] == "America/New_York"
        assert risks[0].payload["how_to_avoid"] == (
            "This clock stopped when the unload started. "
            "This trail supports $18.75. It is not an invoice."
        )
        assert len({event.event_id for event in produced}) == len(produced)

    as_of = "2026-10-17T21:00:00Z"
    assert_closed(_at(scrambled, as_of))
    assert_closed(_at(list(reversed(scrambled)), as_of))
    warning = _risks(_at(scrambled, "2026-10-17T19:50:00Z"))
    assert warning[0].payload["phase"] == "warning"
    assert warning[0].payload["timezone"] == "America/New_York"
    assert warning[0].payload["how_to_avoid"] == (
        "Start the unload before 4:20 PM ET. "
        "After that, this trail adds $18.75 every 15 minutes."
    )

    clean = [east, delay, real_stop]
    replayed = _roundtrip(replay_clock(scrambled, as_of=parse_time(as_of), policy=POLICY))
    clean_replay = _roundtrip(replay_clock(clean, as_of=parse_time(as_of), policy=POLICY))
    assert [event.event_id for event in _risks(replayed)] == [event.event_id for event in _risks(clean_replay)]
    assert [event.payload for event in _risks(replayed)] == [event.payload for event in _risks(clean_replay)]
    assert [event.payload["phase"] for event in _risks(replayed)] == ["warning", "closed"]
    assert _started(replayed).payload["timezone"] == "America/New_York"
    assert "4:20 PM ET" in _risks(replayed)[0].payload["how_to_avoid"]

    again = replay_clock(replayed, as_of=parse_time(as_of), policy=POLICY)
    assert [event.event_id for event in again] == [event.event_id for event in replayed]

    code, out, err = run_cli(clock_main, ["--as-of", as_of, "--replay"], dump_jsonl(scrambled))
    assert code == 0
    assert err == "dock-clock: held back 1 events after as-of\n"
    streamed = load_jsonl(out)
    assert all(parse_time(event.occurred_at) <= parse_time(as_of) for event in streamed)
    assert "evt_unload_future_ll10018" not in {event.event_id for event in streamed}
    assert _risks(streamed)[-1].payload["estimated_charge_usd"] == "18.75"
    assert _risks(streamed)[-1].payload["timezone"] == "America/New_York"
