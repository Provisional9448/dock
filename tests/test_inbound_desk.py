from dock_events.log import EventLog
from dock_events.model import Actor, Event, load_jsonl
from dock_events.timeutil import parse_time
from dock_web.desk import Desk
import pytest


def test_runtime_view_reads_saved_facts_without_synthetic_notices(root, tmp_path):
    path = tmp_path / "runtime.jsonl"
    initial = parse_time("2026-10-17T19:36:00Z")
    facts = load_jsonl((root / "data/samples/harbor-rye.raw.jsonl").read_text())
    facts = [e for e in facts if e.type in {"arrived", "delay_reported"} and parse_time(e.occurred_at) <= initial]
    EventLog(path).append(facts)
    before = path.read_bytes()
    desk = Desk.from_runtime(root, path, "2026-10-17T19:36:00Z")
    first = desk.snapshot()
    assert first["runtime_mode"]
    assert first["summary"]["estimated_charge_usd"] == "0.00"
    assert not first["presets"]
    assert not any(row["event"]["type"] in {"notice_sent", "call_result", "unload_started"} for row in first["events"])
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="read-only"):
        desk.report_driver("They started unloading.")
    with pytest.raises(ValueError, match="read-only"):
        desk.reset()
    with pytest.raises(ValueError, match="read-only"):
        desk.jump("2026-10-17T22:00:00Z")
    EventLog(path).append([Event(event_id="evt_inbound_unload_test", type="unload_started",
        occurred_at="2026-10-17T20:48:00Z", recorded_at="2026-10-17T20:48:00Z",
        load_id="LL-88421", actor=Actor(role="driver",party_id="pty_luis",channel="voice"),
        payload={"door":"door 4"}, caused_by=None, source="dock-intake")])
    updated = desk.snapshot()
    assert updated["summary"]["phase"] == "closed"
    assert updated["summary"]["estimated_charge_usd"] == "56.25"
    assert Desk.from_runtime(root, path, "2026-10-17T19:36:00Z").snapshot()["summary"] == updated["summary"]
