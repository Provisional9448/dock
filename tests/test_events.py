from dock_events.context import arrived_payload, load_context
from dock_events.log import EventLog
from dock_events.model import event_from_dict, load_jsonl


def test_sample_facts_validate(sample_dir):
    events = load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))
    assert [event.type for event in events] == [
        "arrived",
        "delay_reported",
        "call_result",
        "unload_started",
        "unload_done",
    ]
    context = load_context(sample_dir / "parties.json")
    assert events[0].payload == arrived_payload(context)


def test_rejects_unknown_type_and_float_money():
    bad = {
        "schema_version": 1,
        "event_id": "evt_not_real",
        "type": "exploded",
        "occurred_at": "2026-10-17T18:06:00Z",
        "recorded_at": "2026-10-17T18:06:00Z",
        "load_id": "LL-1",
        "actor": {"role": "system", "party_id": "x", "channel": "system"},
        "payload": {},
        "caused_by": None,
        "source": "sample",
    }
    try:
        event_from_dict(bad)
    except ValueError as exc:
        assert "unknown type" in str(exc)
    else:
        raise AssertionError("expected a rejection")


def test_append_is_idempotent(tmp_path, sample_dir):
    events = load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))
    log = EventLog(tmp_path / "dock.jsonl")
    first = log.append(events)
    second = log.append(events)
    assert len(first.appended) == 5
    assert second.appended == ()
    assert len(second.skipped_ids) == 5
    assert log.read() == events
