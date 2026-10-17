from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dock_clock.policy import DetentionPolicy, policy_from_context
from dock_clock.tick import replay_clock, tick
from dock_events.context import arrived_payload, load_context
from dock_events.model import Actor, Event, event_from_dict, load_jsonl
from dock_events.timeutil import parse_time

AS_OF_END = parse_time("2026-10-17T22:05:00Z")
DRIVER = Actor(role="driver", party_id="pty_luis", channel="voice")


def _policy(sample_dir) -> DetentionPolicy:
    return policy_from_context(load_context(sample_dir / "parties.json"))


def _raw(sample_dir) -> list[Event]:
    return load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))


def _replace_arrived(sample_dir, occurred_at: str) -> Event:
    context = load_context(sample_dir / "parties.json")
    return Event(
        event_id="evt_arrive_ll88421",
        type="arrived",
        occurred_at=occurred_at,
        recorded_at=occurred_at,
        load_id="LL-88421",
        actor=DRIVER,
        payload=arrived_payload(context),
        source="sample",
    )


def _roundtrip(events: list[Event]) -> list[Event]:
    return [event_from_dict(event.to_dict()) for event in events]


def test_replay_matches_the_story(sample_dir):
    produced = _roundtrip(replay_clock(_raw(sample_dir), as_of=AS_OF_END, policy=_policy(sample_dir)))
    risks = [event for event in produced if event.type == "charge_risk"]
    assert [event.payload["phase"] for event in risks] == ["warning", "accruing", "closed"]
    assert [event.payload["estimated_charge_usd"] for event in risks] == ["0.00", "18.75", "56.25"]
    assert risks[1].payload["billable_minutes"] == 15
    assert risks[2].payload["billable_minutes"] == 45
    assert risks[2].payload["elapsed_minutes"] == 162
    started = next(event for event in produced if event.type == "clock_started")
    assert started.payload["anchor"] == "arrived"
    assert started.payload["free_time_ends_at"] == "2026-10-17T20:06:00Z"


def test_replay_is_idempotent(sample_dir):
    policy = _policy(sample_dir)
    once = replay_clock(_raw(sample_dir), as_of=AS_OF_END, policy=policy)
    twice = replay_clock(once, as_of=AS_OF_END, policy=policy)
    assert [event.event_id for event in once] == [event.event_id for event in twice]


def test_future_facts_do_not_stop_the_clock(sample_dir):
    policy = _policy(sample_dir)
    produced = tick(_raw(sample_dir), as_of=parse_time("2026-10-17T19:36:00Z"), policy=policy)
    assert [event.type for event in produced] == ["clock_started", "charge_risk"]
    assert produced[1].payload["phase"] == "warning"
    assert produced[1].payload["remaining_free_minutes"] == 30


def test_early_driver_waits_for_the_appointment(sample_dir):
    policy = _policy(sample_dir)
    early = _replace_arrived(sample_dir, "2026-10-17T17:40:00Z")
    before = tick([early], as_of=parse_time("2026-10-17T17:50:00Z"), policy=policy)
    assert before == []
    running = tick([early], as_of=parse_time("2026-10-17T18:30:00Z"), policy=policy)
    assert running[0].payload["anchor"] == "appointment"
    assert running[0].payload["clock_started_at"] == "2026-10-17T18:00:00Z"
    assert all(event.type != "charge_risk" for event in running)


def test_daily_storage_uses_the_same_clock(sample_dir):
    arrived = _replace_arrived(sample_dir, "2026-10-14T18:00:00Z")
    payload = dict(arrived.payload)
    payload["appointment_at"] = "2026-10-14T12:00:00Z"
    arrived = Event(
        event_id=arrived.event_id,
        type=arrived.type,
        occurred_at=arrived.occurred_at,
        recorded_at=arrived.recorded_at,
        load_id=arrived.load_id,
        actor=arrived.actor,
        payload=payload,
        source=arrived.source,
    )
    policy = DetentionPolicy(
        free_minutes=2 * 1440,
        warn_minutes=1440,
        rate_usd_per_hour=Decimal("6.25"),
        increment_minutes=1440,
    )
    produced = tick([arrived], as_of=parse_time("2026-10-17T18:00:00Z"), policy=policy)
    risk = next(event for event in produced if event.type == "charge_risk")
    assert risk.payload["phase"] == "accruing"
    assert risk.payload["billable_minutes"] == 1440
    assert risk.payload["estimated_charge_usd"] == "150.00"


def test_stop_on_unload_done_keeps_charging_through_unload_start(sample_dir):
    raw = _raw(sample_dir)
    policy = DetentionPolicy(stop_on="unload_done")
    produced = tick(raw, as_of=parse_time("2026-10-17T21:00:00Z"), policy=policy)
    risk = next(event for event in produced if event.type == "charge_risk")
    assert risk.payload["phase"] == "accruing"
    assert risk.payload["elapsed_minutes"] == 174
    assert risk.payload["estimated_charge_usd"] == "75.00"
