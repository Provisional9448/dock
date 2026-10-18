from datetime import timedelta

import pytest

from dock_events.timeutil import parse_time
from dock_intake.session import InboundSession

AS_OF = parse_time("2026-10-17T20:21:00Z")
FACT_TYPES = {"arrived", "delay_reported", "unload_started", "unload_done"}


def test_status_omits_future_and_prerecorded_outcomes(root, tmp_path):
    session = InboundSession(root, tmp_path / "events.jsonl", AS_OF)
    status = session.status("LL-88421")
    assert status["stage"] == "waiting"
    assert status["source_timestamp"] == "2026-10-17T18:08:00Z"
    assert status["eta"] is None
    assert status["clock"]["estimated_charge_usd"] == "18.75"
    assert not session.status("UNKNOWN")["known"]
    assert {event.type for event in session.log.read()} == {"arrived", "delay_reported"}
    assert status["notices"] == []
    assert status["call_results"] == []


def test_late_clock_still_omits_scripted_call_and_unload(root, tmp_path):
    session = InboundSession(root, tmp_path / "events.jsonl", parse_time("2026-10-17T22:30:00Z"))
    assert {event.type for event in session.log.read()} <= FACT_TYPES
    assert not any(event.type in {"call_result", "notice_sent", "unload_started"} for event in session.log.read())


def test_confirmed_report_persists_and_retry_is_idempotent(root, tmp_path):
    path = tmp_path / "events.jsonl"
    session = InboundSession(root, path, AS_OF)
    args = dict(state="unloading_started", confirmed=True, occurred_at=AS_OF, action_id="call-1-report-1")
    result = session.report("LL-88421", **args)
    assert result["saved"] and not result["duplicate"]
    restarted = InboundSession(root, path, AS_OF + timedelta(minutes=30))
    assert restarted.report("LL-88421", **args)["duplicate"]
    assert restarted.status("LL-88421")["clock"]["estimated_charge_usd"] == "18.75"
    assert restarted.status("LL-88421")["clock"]["phase"] == "closed"
    assert len([event for event in restarted.log.read() if event.type == "unload_started"]) == 1
    old_clock_restart = InboundSession(root, path, parse_time("2026-10-17T19:36:00Z"))
    assert old_clock_restart.as_of == AS_OF
    assert old_clock_restart.status("LL-88421")["stage"] == "unloading_started"
    with pytest.raises(ValueError, match="different report"):
        restarted.report("LL-88421", **{**args, "detail": "changed"})


def test_negative_and_predicted_reports_never_stop_clock(root, tmp_path):
    session = InboundSession(root, tmp_path / "events.jsonl", AS_OF)
    session.report(
        "LL-88421",
        state="waiting",
        confirmed=True,
        occurred_at=AS_OF,
        detail="They have not started unloading yet. The trailer is not empty.",
        expected_start="in 20 minutes",
        action_id="call-1-report-1",
    )
    status = session.status("LL-88421")
    assert status["stage"] == "waiting"
    assert status["expected_start"] == "in 20 minutes"
    assert status["clock"]["phase"] == "accruing"
    for changes in (
        {"confirmed": False},
        {"expected_start": "in 20 minutes"},
        {"occurred_at": AS_OF + timedelta(minutes=20)},
    ):
        args = dict(state="unloading_started", confirmed=True, occurred_at=AS_OF, action_id="call-1-report-2")
        with pytest.raises(ValueError):
            session.report("LL-88421", **{**args, **changes})
    assert not any(event.type.startswith("unload") for event in session.log.read())
    assert not any(event.type in {"notice_sent", "call_result"} for event in session.log.read())


def test_past_timestamp_needs_a_timezone_and_future_actuals_are_rejected(root, tmp_path):
    session = InboundSession(root, tmp_path / "events.jsonl", AS_OF)
    before = session.log.path.read_bytes()
    with pytest.raises(ValueError, match="timezone"):
        session.report(
            "LL-88421",
            state="waiting",
            confirmed=True,
            occurred_at=AS_OF.replace(tzinfo=None),
            action_id="naive",
        )
    with pytest.raises(ValueError, match="Future"):
        session.report(
            "LL-88421",
            state="unloading_started",
            confirmed=True,
            occurred_at=AS_OF + timedelta(minutes=1),
            action_id="future",
        )
    assert session.log.path.read_bytes() == before
    saved = session.report(
        "LL-88421",
        state="waiting",
        confirmed=True,
        occurred_at=AS_OF - timedelta(minutes=30),
        action_id="past-zoned",
    )
    assert saved["saved"]
    assert {event.type for event in session.log.read()} <= FACT_TYPES


def test_read_only_status_and_invalid_reports(root, tmp_path):
    path = tmp_path / "events.jsonl"
    session = InboundSession(root, path, parse_time("2026-10-17T18:10:00Z"))
    before = path.read_bytes()
    status = session.status("LL-88421")
    assert status["clock"]["estimated_charge_usd"] == "0.00"
    assert status["clock"]["remaining_free_minutes"] == 116
    assert path.read_bytes() == before
    with pytest.raises(ValueError):
        session.report("UNKNOWN", state="waiting", confirmed=True, occurred_at=session.as_of, action_id="1")
    with pytest.raises(ValueError):
        session.report("LL-88421", state="unloading_done", confirmed=True, occurred_at=session.as_of, action_id="2")
    assert path.read_bytes() == before


def test_optional_detail_produces_valid_event(root, tmp_path):
    session = InboundSession(root, tmp_path / "events.jsonl", AS_OF)
    result = session.report("LL-88421", state="waiting", confirmed=True, occurred_at=AS_OF, action_id="1")
    assert result["saved"]
    assert session.status("LL-88421")["detail"] == "Caller confirmed still waiting on site for unloading."
    before = session.log.path.read_bytes()
    with pytest.raises(ValueError):
        session.report("LL-88421", state="waiting", confirmed=True, occurred_at=AS_OF, action_id="2", detail={})
    assert session.log.path.read_bytes() == before


def test_runtime_rejects_sample_path_and_symlink(root, tmp_path):
    fixture = root / "data/samples/harbor-rye.raw.jsonl"
    before = fixture.read_bytes()
    with pytest.raises(ValueError, match="sample fixtures"):
        InboundSession(root, fixture, AS_OF)
    alias = tmp_path / "alias.jsonl"
    alias.symlink_to(fixture)
    with pytest.raises(ValueError, match="sample fixtures"):
        InboundSession(root, alias, AS_OF)
    assert fixture.read_bytes() == before


def test_session_does_not_write_another_logs_notices(root, tmp_path):
    path = tmp_path / "inbound.jsonl"
    other = tmp_path / "other.jsonl"
    other.write_text("leave-me\n", encoding="utf-8")
    session = InboundSession(root, path, AS_OF)
    session.status("LL-88421")
    session.report(
        "LL-88421",
        state="unloading_started",
        confirmed=True,
        occurred_at=AS_OF,
        detail="Observed unloading now.",
        action_id="merge-report",
    )
    assert {event.type for event in session.log.read()} <= FACT_TYPES
    assert other.read_text(encoding="utf-8") == "leave-me\n"
