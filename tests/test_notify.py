"""Heads-up copy: four clock marks, SMS plus a spoken script, and the JSONL pipe."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dock_clock.policy import policy_from_context
from dock_clock.tick import replay_clock, tick
from dock_events.context import load_context
from dock_events.model import dump_jsonl, event_from_dict, load_jsonl
from dock_events.timeutil import parse_time
from dock_notify.cli import main as notify_main
from dock_notify.compose import apply_notices
from dock_notify.messages import Party, compose_heads_up
from dock_notify.provider import LogProvider, Receipt

from helpers import run_cli

ARRIVED = "2026-10-17T18:06:00Z"
FREE_END = "2026-10-17T20:06:00Z"
WARN_AT = "2026-10-17T19:36:00Z"
ACCRUE_15 = "2026-10-17T20:21:00Z"
ACCRUE_30 = "2026-10-17T20:36:00Z"
STOPPED = "2026-10-17T20:48:00Z"

MOCK_WARNING = (
    "Dock · LL-88421: Red Kettle's driver has waited at Harbor & Rye door 4 since 2:06 PM ET. "
    "Free time ends 4:06 PM ET. Estimate so far $0.00."
)

PARTIES = (
    Party("shipper", "Northwind Orchards", "Sam Okonkwo", "+15555550131", "pty_northwind"),
    Party("consignee", "Harbor & Rye Grocery", "Priya Shah", "+15555550121", "pty_harbor_rye"),
    Party("carrier", "Red Kettle Freight", "Dispatch", "+15555550151", "pty_red_kettle"),
)


def _heads(**overrides):
    args = dict(
        load_id="LL-88421",
        parties=PARTIES,
        door="door 4",
        arrived_at=ARRIVED,
        free_minutes=120,
        rate="75.00",
        now=WARN_AT,
        facility="Harbor & Rye",
    )
    args.update(overrides)
    return compose_heads_up(**args)


def test_warning_matches_the_mock_and_says_it_is_not_an_invoice():
    note = _heads()
    assert note is not None
    assert note.phase == "warning"
    assert note.on_cadence is True
    assert note.estimated_charge_usd == "0.00"
    assert note.billable_minutes == 0
    assert note.sms.startswith(MOCK_WARNING)
    assert "Not an invoice." in note.sms
    assert "Sam Okonkwo" in note.sms
    assert "If unload starts before 4:06 PM ET, it stays $0.00." in note.sms
    assert "Not an invoice." in note.voice
    assert "$0.00" in note.voice
    assert "Harbor and Rye door 4" in note.voice
    assert "·" not in note.voice
    assert note.sms == _heads().sms
    assert note.voice == _heads().voice


def test_quiet_free_time_has_no_heads_up():
    assert _heads(now="2026-10-17T19:35:00Z") is None
    late_window = _heads(now="2026-10-17T19:37:00Z")
    assert late_window is not None
    assert late_window.phase == "warning"
    assert late_window.on_cadence is False
    assert late_window.estimated_charge_usd == "0.00"


def test_free_time_ended_is_still_zero():
    note = _heads(now=FREE_END)
    assert note is not None
    assert note.phase == "free_ended"
    assert note.on_cadence is True
    assert note.estimated_charge_usd == "0.00"
    assert "Free time ended 4:06 PM ET." in note.sms
    assert "Estimate so far $0.00." in note.sms
    assert "$18.75" in note.sms
    assert "The next 15 minutes add $18.75" in note.sms
    assert "Not an invoice." in note.voice


def test_accruing_every_fifteen_minutes():
    first = _heads(now=ACCRUE_15)
    second = _heads(now=ACCRUE_30)
    between = _heads(now="2026-10-17T20:13:00Z")
    assert first is not None and second is not None and between is not None
    assert first.phase == "accruing" and first.on_cadence is True
    assert first.estimated_charge_usd == "18.75"
    assert first.billable_minutes == 15
    assert "Estimate so far $18.75." in first.sms
    assert "every 15 minutes" in first.sms
    assert "Not an invoice." in first.sms
    assert second.on_cadence is True
    assert second.estimated_charge_usd == "37.50"
    assert second.billable_minutes == 30
    assert "Estimate so far $37.50." in second.sms
    assert between.on_cadence is False
    assert between.estimated_charge_usd == "18.75"
    assert between.billable_minutes == 15
    consignee = _heads(now=ACCRUE_15, audience="consignee")
    assert consignee is not None
    assert consignee.to_name == "Priya Shah"
    assert "Priya Shah" in consignee.sms
    assert "$18.75" in consignee.voice


def test_clock_stopped_keeps_the_final_amount():
    stopped = _heads(now=STOPPED, stopped_at=STOPPED)
    later = _heads(now="2026-10-17T22:05:00Z", stopped_at=STOPPED)
    assert stopped is not None and later is not None
    assert stopped.phase == "closed" and stopped.on_cadence is True
    assert stopped.estimated_charge_usd == "56.25"
    assert stopped.billable_minutes == 45
    assert "The clock has stopped." in stopped.sms
    assert "Final supported amount $56.25." in stopped.sms
    assert "Not an invoice." in stopped.sms
    assert "Not an invoice." in stopped.voice
    assert "$56.25" in stopped.voice
    assert later.estimated_charge_usd == "56.25"
    assert later.on_cadence is False
    assert later.sms == stopped.sms


def test_early_arrival_does_not_burn_free_time():
    waiting = _heads(
        arrived_at="2026-10-17T17:40:00Z",
        appointment_at="2026-10-17T18:00:00Z",
        now="2026-10-17T17:50:00Z",
    )
    warning = _heads(
        arrived_at="2026-10-17T17:40:00Z",
        appointment_at="2026-10-17T18:00:00Z",
        now="2026-10-17T19:30:00Z",
    )
    assert waiting is None
    assert warning is not None
    assert warning.phase == "warning"
    assert warning.on_cadence is True
    assert "since 2:00 PM ET." in warning.sms
    assert "Free time ends 4:00 PM ET." in warning.sms


def test_estimate_matches_the_clock(sample_dir):
    context = load_context(sample_dir / "parties.json")
    policy = policy_from_context(context)
    raw = load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))
    checks = (
        (WARN_AT, "0.00"),
        (FREE_END, "0.00"),
        (ACCRUE_15, "18.75"),
        (ACCRUE_30, "37.50"),
        (STOPPED, "56.25"),
    )
    for stamp, expected in checks:
        moment = parse_time(stamp)
        created = tick(raw, as_of=moment, policy=policy)
        risks = [event for event in created if event.type == "charge_risk"]
        assert risks, stamp
        assert risks[-1].payload["estimated_charge_usd"] == expected
        note = _heads(now=stamp, stopped_at=STOPPED if stamp == STOPPED else None)
        assert note is not None
        assert note.estimated_charge_usd == expected


def test_partial_step_rounds_half_up_like_the_clock():
    arrived = datetime(2026, 10, 17, 18, 6, tzinfo=timezone.utc)
    note = compose_heads_up(
        "LL-88421",
        PARTIES,
        "door 4",
        arrived,
        0,
        Decimal("10.00"),
        arrived + timedelta(minutes=1),
        facility="Harbor & Rye",
        increment_minutes=1,
        warn_minutes=0,
    )
    assert note is not None
    assert note.phase == "accruing"
    assert note.billable_minutes == 1
    assert note.estimated_charge_usd == "0.17"


def test_bad_inputs_fail_closed():
    naive = datetime(2026, 10, 17, 19, 36)
    try:
        _heads(now=naive)
    except ValueError as exc:
        assert "timezone" in str(exc)
    else:
        raise AssertionError("expected a timezone error")
    try:
        _heads(audience="broker")
    except ValueError as exc:
        assert "audience" in str(exc)
    else:
        raise AssertionError("expected an audience error")
    try:
        _heads(rate="-1.00")
    except ValueError as exc:
        assert "negative" in str(exc)
    else:
        raise AssertionError("expected a rate error")


class _Capture:
    name = "log"

    def __init__(self):
        self.bodies: list[str] = []

    def send(self, message):
        self.bodies.append(message.body)
        return Receipt(provider=self.name, status="logged", detail="test")


def test_pipe_records_sms_and_voice_without_sending(sample_dir):
    context = load_context(sample_dir / "parties.json")
    raw = load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))
    clocked = replay_clock(raw, as_of=parse_time("2026-10-17T22:05:00Z"), policy=policy_from_context(context))
    capture = _Capture()
    noticed = apply_notices(clocked, provider=capture)
    notices = [event for event in noticed if event.type == "notice_sent"]
    assert len(notices) == 6
    assert len(capture.bodies) == 6
    warning = next(event for event in notices if event.payload["phase"] == "warning" and event.payload["to_role"] == "shipper")
    assert warning.payload["body"] in capture.bodies
    assert warning.payload["body"].startswith(
        "Dock · LL-88421: Red Kettle's driver has waited at Harbor & Rye Grocery DC, door 4 since 2:06 PM ET."
    )
    assert "Estimate so far $0.00." in warning.payload["body"]
    assert "Not an invoice." in warning.payload["body"]
    assert "Sam Okonkwo" in warning.payload["body"]
    assert "Start the unload before 4:06 PM ET." in warning.payload["body"]
    assert "Not an invoice." in warning.payload["voice"]
    assert "$0.00" in warning.payload["voice"]
    assert "·" not in warning.payload["voice"]
    assert warning.payload["voice"] not in capture.bodies
    accruing = next(event for event in notices if event.payload["phase"] == "accruing" and event.payload["to_role"] == "shipper")
    assert "$18.75" in accruing.payload["body"]
    assert "Sam Okonkwo" in accruing.payload["body"]
    # payer-only: the shipper pays on LL-88421 (fictional terms), so the consignee gets no money heads-up
    assert not any(event.payload["to_role"] == "consignee" for event in notices)
    broker = next(event for event in notices if event.payload["phase"] == "accruing" and event.payload["to_role"] == "broker")
    assert "The shipper pays on this load; Red Kettle Freight invoices." in broker.payload["body"]
    assert "The timestamped record backs the carrier's invoice." in broker.payload["body"]
    closed = next(event for event in notices if event.payload["phase"] == "closed" and event.payload["to_role"] == "shipper")
    assert "The clock has stopped." in closed.payload["body"]
    assert "Final supported amount $56.25." in closed.payload["body"]
    assert "Not an invoice." in closed.payload["voice"]
    for event in notices:
        event_from_dict(event.to_dict())
    again = apply_notices(noticed, provider=LogProvider())
    assert len(again) == len(noticed)


def test_cli_emits_notice_sent_on_stdout(sample_dir):
    context = load_context(sample_dir / "parties.json")
    raw = load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))
    clocked = replay_clock(raw, as_of=parse_time(WARN_AT), policy=policy_from_context(context))
    code, out, err = run_cli(notify_main, [], dump_jsonl(clocked))
    assert code == 0, err
    assert "dock-notify: composed 2 heads-up events" in err
    assert "Not an invoice." not in err
    notices = [event for event in load_jsonl(out) if event.type == "notice_sent"]
    assert [event.event_id for event in notices] == [
        "ntc-clk-ll-88421-warning-shipper",
        "ntc-clk-ll-88421-warning-broker",
    ]
    assert all(event.payload["channel"] == "sms" for event in notices)
    assert "Not an invoice." in notices[0].payload["voice"]
    assert "backs the carrier's invoice" in notices[1].payload["body"]
    code, again, err = run_cli(notify_main, [], out)
    assert code == 0, err
    assert "composed 0" in err
    assert [event.event_id for event in load_jsonl(again)] == [event.event_id for event in load_jsonl(out)]
    code, _out, err = run_cli(notify_main, ["--audiences", "carrier"], dump_jsonl(clocked))
    assert code == 1
    assert err.startswith("dock-notify:")
