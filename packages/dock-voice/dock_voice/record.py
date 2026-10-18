"""The driver's record: check-in time plus what the receiver promised, timestamped.

Dock does not give directions. The driver already checked in at the receiving window and was told to wait;
Dock logs when he checked in (occurred_at), when he told Dock (recorded_at), who said what, and the
receiver's estimate. The clock and the heads-ups to the shipper and broker read from that record.
Works against LiveRun (local or remote desk): only now/set_now/read/has/append/context are used.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from dock_events.context import arrived_payload
from dock_events.model import Actor, Event
from dock_events.timeutil import format_local, format_time, parse_time

log = logging.getLogger("dock-voice")


def build_driver_events(
    run,
    status: str,
    *,
    at: datetime | None = None,
    said_by: str = "",
    said: str = "",
    estimate_minutes: int | None = None,
    channel: str = "voice",
) -> tuple[list[Event], dict]:
    """Build (not append) the driver's events. Returns (new events, read-back record, events already on the log, now).

    Reads the shared log and clock once. Never raises on a failed desk write: the clock catch-up is best
    effort, and the read-back uses the local `now` either way."""
    load = run.context["load"]
    zone = load.get("timezone", "America/New_York")
    now = run.now()
    if at is not None and now < at <= now + timedelta(minutes=15):
        # Demo clock only: "I checked in at 2:06" said a minute before the shared demo clock reaches 2:06.
        # Move the demo clock past the stated time; never rewrite a logged fact.
        target = at + timedelta(minutes=2)
        try:
            run.set_now(target)
        except Exception as exc:  # remote desk refused or slow: keep going on the local clock
            log.warning("demo clock catch-up failed (%s); using local time", exc)
        now = target
    if at is not None and (at > now or now - at > timedelta(hours=12)):
        at = None
    events = run.read()
    arrived_at = next((parse_time(e.occurred_at) for e in events if e.type == "arrived"), None)
    if at is not None and arrived_at is not None and at < arrived_at:
        at = None
    if status == "arrived" and arrived_at is not None:
        status = "waiting"  # already checked in: this is an update
    if status in ("unload_started", "unload_done") and arrived_at is None:
        status = "arrived"  # no check-in on record: never stop a clock that never started
    stamp = format_time(now)
    actor = Actor(role="driver", party_id=load["driver_party_id"], channel=channel)
    door = load.get("door", "door 4")

    def make(kind: str, payload: dict, occurred: datetime | None = None) -> Event:
        return Event(
            event_id=f"evt-{kind[:8]}-{uuid.uuid4().hex[:12]}",
            type=kind,
            occurred_at=format_time(occurred or now),
            recorded_at=stamp,
            load_id=load["load_id"],
            actor=actor,
            payload=payload,
            source="dock-voice" if channel == "voice" else "dock-intake",
        )

    out: list[Event] = []
    when = at or now
    record = {
        "status": status,
        "at_local": format_local(format_time(when), zone),
        "said_by": said_by.strip(),
        "said": said.strip().rstrip("."),
        "estimate_minutes": estimate_minutes or None,
        "eta_local": None,
    }
    if status in ("arrived", "waiting"):
        if arrived_at is None:
            out.append(make("arrived", arrived_payload(run.context), at))
        first = status == "arrived"
        parts = [
            f"Checked in at the receiving window at {record['at_local']}."
            if first
            else f"Still waiting at {format_local(stamp, zone)}."
        ]
        if record["said"]:
            parts.append(f"{record['said_by'] or 'Receiver'} said: {record['said']}.")
        if estimate_minutes:
            base = when if first else now
            record["eta_local"] = format_local(format_time(base + timedelta(minutes=estimate_minutes)), zone)
            parts.append(f"Receiver estimate about {estimate_minutes} min, around {record['eta_local']}.")
        detail = " ".join(parts)
        low = detail.lower()
        if "occup" in low:
            reason = "door_occupied"
        elif "no door" in low or "doors full" in low:
            reason = "no_door_available"
        elif not first:
            reason = "still_waiting"
        else:
            reason = "receiver_not_ready"
        out.append(make("delay_reported", {"reason": reason, "detail": detail}))
        if not first:
            record["at_local"] = format_local(stamp, zone)
    elif status in ("unload_started", "unload_done"):
        out.append(make(status, {"door": door}, at))
    else:
        raise ValueError(f"unknown driver status {status}")
    return out, record, events, now


def log_driver(run, status: str, **kwargs) -> tuple[list[Event], dict]:
    """Build and append synchronously (replay, tests). The phone line uses build_driver_events + post_later."""
    out, record, _base, _now = build_driver_events(run, status, **kwargs)
    return run.append(out), record


def local_snapshot(context: dict, facts: list[Event], now: datetime) -> dict:
    """The desk projection computed in-process from facts we already hold: no network on the speaking path."""
    from dock_web.desk import Desk

    desk = Desk(context, facts)
    desk.as_of = now
    snap = desk.snapshot()
    snap["clock_local"] = format_local(format_time(now), context["load"].get("timezone", "America/New_York"))
    return snap


def post_later(run, events: list[Event], label: str = "driver", write=None) -> threading.Thread:
    """Write to the shared log off the call's thread. On failure, keep the events in a local spool file so
    nothing said on a call is lost, and log why (e.g. desk 403: DOCK_WRITE_TOKEN differs between box and desk)."""
    write = write or run.append

    def work() -> None:
        try:
            appended = write(events)
            log.info("%s events posted: %s", label, [getattr(e, "type", e) for e in appended or []])
        except Exception as exc:
            spool = Path(os.environ.get("DOCK_SPOOL", run.root / "data" / "runtime" / "voice-spool.jsonl"))
            try:
                spool.parent.mkdir(parents=True, exist_ok=True)
                with spool.open("a", encoding="utf-8") as fh:
                    for event in events:
                        fh.write(json.dumps(event.to_dict()) + "\n")
            except Exception:
                pass
            log.error("%s events NOT posted to the desk (%s); spooled to %s", label, exc, spool)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return thread
