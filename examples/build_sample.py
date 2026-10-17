"""Write the curated Harbor & Rye facts, then the derived trail.

Run from the repo root:

    uv run python examples/build_sample.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dock_clock.policy import policy_from_context
from dock_clock.tick import replay_clock
from dock_events.context import arrived_payload, load_context
from dock_events.model import Actor, Event, dump_jsonl, event_from_dict
from dock_events.timeutil import parse_time
from dock_notify.compose import apply_notices

RAW = ROOT / "data" / "samples" / "harbor-rye.raw.jsonl"
TRAIL = ROOT / "data" / "samples" / "harbor-rye.trail.jsonl"
PARTIES = ROOT / "data" / "samples" / "parties.json"
AS_OF = "2026-10-17T22:05:00Z"


def facts(context: dict) -> list[Event]:
    load_id = context["load"]["load_id"]
    driver = Actor(role="driver", party_id="pty_luis", channel="voice")
    system = Actor(role="system", party_id="dock-call", channel="voice")
    door = context["load"]["door"]
    return [
        Event(
            event_id="evt_arrive_ll88421",
            type="arrived",
            occurred_at="2026-10-17T18:06:00Z",
            recorded_at="2026-10-17T18:06:22Z",
            load_id=load_id,
            actor=driver,
            payload=arrived_payload(context),
            source="sample",
        ),
        Event(
            event_id="evt_delay_ll88421",
            type="delay_reported",
            occurred_at="2026-10-17T18:08:00Z",
            recorded_at="2026-10-17T18:08:18Z",
            load_id=load_id,
            actor=driver,
            payload={
                "reason": "door_occupied",
                "detail": "Door 4 is occupied. They are not ready to unload.",
            },
            source="sample",
        ),
        Event(
            event_id="evt_call_priya_ll",
            type="call_result",
            occurred_at="2026-10-17T19:40:00Z",
            recorded_at="2026-10-17T19:41:05Z",
            load_id=load_id,
            actor=system,
            payload={
                "goal": "receiver_delay",
                "outcome": "reached",
                "to_party_id": "pty_harbor_rye",
                "to_name": "Priya Shah",
                "to_role": "consignee",
                "summary": "Priya said door 4 is still occupied and they can start in about 40 minutes.",
            },
            source="sample",
        ),
        Event(
            event_id="evt_unload_start_ll",
            type="unload_started",
            occurred_at="2026-10-17T20:48:00Z",
            recorded_at="2026-10-17T20:48:40Z",
            load_id=load_id,
            actor=driver,
            payload={"door": door},
            source="sample",
        ),
        Event(
            event_id="evt_unload_done_ll",
            type="unload_done",
            occurred_at="2026-10-17T22:05:00Z",
            recorded_at="2026-10-17T22:06:11Z",
            load_id=load_id,
            actor=driver,
            payload={"door": door},
            source="sample",
        ),
    ]


def main() -> None:
    context = load_context(PARTIES)
    raw = facts(context)
    RAW.write_text(dump_jsonl(raw), encoding="utf-8")
    policy = policy_from_context(context)
    clocked = replay_clock(raw, as_of=parse_time(AS_OF), policy=policy)
    trailed = apply_notices(clocked)
    for event in trailed:
        event_from_dict(event.to_dict())
    TRAIL.write_text(dump_jsonl(trailed), encoding="utf-8")
    print(f"wrote {RAW.relative_to(ROOT)} ({len(raw)} facts)")
    print(f"wrote {TRAIL.relative_to(ROOT)} ({len(trailed)} events)")


if __name__ == "__main__":
    main()
