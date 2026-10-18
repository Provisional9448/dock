from datetime import timedelta

import pytest

from dock_events.timeutil import parse_time
from dock_intake.session import InboundSession

AS_OF = parse_time("2026-10-17T20:21:00Z")


def test_status_omits_future_and_prerecorded_outcomes(root, tmp_path):
    session = InboundSession(root, tmp_path / "events.jsonl", AS_OF)
    status = session.status("LL-88421")
    assert status["stage"] == "waiting"
    assert status["source_timestamp"] == "2026-10-17T18:08:00Z"
    assert status["eta"] is None
    assert status["clock"]["estimated_charge_usd"] == "18.75"
    assert not session.status("UNKNOWN")["known"]
    assert {e.type for e in session.log.read()} == {"arrived", "delay_reported"}


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
    assert len([e for e in restarted.log.read() if e.type == "unload_started"]) == 1
    old_clock_restart = InboundSession(root, path, parse_time("2026-10-17T19:36:00Z"))
    assert old_clock_restart.as_of == AS_OF
    assert old_clock_restart.status("LL-88421")["stage"] == "unloading_started"
    with pytest.raises(ValueError, match="different report"):
        restarted.report("LL-88421", **{**args, "detail": "changed"})


def test_negative_and_predicted_reports_never_stop_clock(root, tmp_path):
    session = InboundSession(root, tmp_path / "events.jsonl", AS_OF)
    session.report("LL-88421", state="waiting", confirmed=True, occurred_at=AS_OF,
                   detail="They have not started unloading yet. The trailer is not empty.",
                   expected_start="in 20 minutes", action_id="call-1-report-1")
    status = session.status("LL-88421")
    assert status["stage"] == "waiting"
    assert status["expected_start"] == "in 20 minutes"
    assert status["clock"]["phase"] == "accruing"
    for changes in ({"confirmed": False}, {"expected_start": "in 20 minutes"},
                    {"occurred_at": AS_OF + timedelta(minutes=20)}):
        args = dict(state="unloading_started", confirmed=True, occurred_at=AS_OF, action_id="call-1-report-2")
        with pytest.raises(ValueError):
            session.report("LL-88421", **{**args, **changes})
    assert not any(e.type.startswith("unload") for e in session.log.read())


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
