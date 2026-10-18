"""One-load inbound demo facts, persisted through the shared append-only log."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from threading import RLock

from dock_clock.policy import DetentionPolicy
from dock_clock.tick import tick
from dock_events.log import EventLog
from dock_events.model import Actor, Event, event_from_dict
from dock_events.timeutil import format_local_long, format_time, parse_time

LOAD_ID = "LL-88421"
STATES = {"waiting": "delay_reported", "unloading_started": "unload_started", "unloading_done": "unload_done"}


class InboundSession:
    def __init__(self, root: Path, log_path: Path, as_of: datetime):
        format_time(as_of)  # Reject naive demo clocks before creating a file.
        if Path(log_path).resolve().is_relative_to((Path(root) / "data/samples").resolve()):
            raise ValueError("Runtime log must not modify sample fixtures.")
        self.as_of = as_of
        self.log = EventLog(log_path)
        self._lock = RLock()
        sample = EventLog(Path(root) / "data/samples/harbor-rye.raw.jsonl").read()
        # Never import the sample's prerecorded call or unloading outcome.
        seeds = [e for e in sample if e.load_id == LOAD_ID
                 and e.type in ("arrived", "delay_reported")
                 and parse_time(e.occurred_at) <= as_of]
        self.log.append(seeds)
        # A restart cannot hide an already accepted operational update.
        accepted = [parse_time(e.occurred_at) for e in self.log.read()
                    if e.load_id == LOAD_ID and e.source == "dock-intake"
                    and e.type in STATES.values()]
        self.as_of = max([as_of, *accepted])

    def _facts(self, load_id: str) -> list[Event]:
        return sorted((e for e in self.log.read() if e.load_id == load_id
                       and e.type in ("arrived", *STATES.values())
                       and parse_time(e.occurred_at) <= self.as_of),
                      key=lambda e: (parse_time(e.occurred_at), parse_time(e.recorded_at)))

    def status(self, load_id: str) -> dict:
        with self._lock:
            facts = self._facts(load_id) if load_id == LOAD_ID else []
            arrival = next((e for e in facts if e.type == "arrived"), None)
            base = {"load_id": load_id, "known": arrival is not None,
                    "as_of": format_time(self.as_of)}
            if arrival is None:
                return {**base, "detail": "No recorded shipment facts for this load. Ask dispatch to review; no contact has been made."}
            latest = facts[-1]
            timezone = arrival.payload["timezone"]
            stage = "waiting"
            if any(e.type == "unload_started" for e in facts):
                stage = "unloading_started"
            if any(e.type == "unload_done" for e in facts):
                stage = "unloading_done"
            derived = tick(facts, as_of=self.as_of, policy=DetentionPolicy())
            started = next((e for e in derived if e.type == "clock_started"), None)
            risk = next((e for e in derived if e.type == "charge_risk"), None)
            clock = dict(risk.payload) if risk else dict(started.payload) if started else {}
            if not risk:
                remaining = max(int((parse_time(clock["free_time_ends_at"]) - self.as_of).total_seconds() // 60), 0) if started else None
                clock.update(phase="free_time" if started else "not_started",
                             estimated_charge_usd="0.00", remaining_free_minutes=remaining)
            return {**base, "stage": stage, "facility": arrival.payload["facility"],
                    "source_timestamp": latest.occurred_at, "eta": None,
                    "timezone": timezone,
                    "source_timestamp_local": format_local_long(latest.occurred_at, timezone),
                    "as_of_local": format_local_long(base["as_of"], timezone),
                    "expected_start": latest.payload.get("expected_start") if stage == "waiting" else None,
                    "detail": latest.payload.get("detail", ""), "clock": clock,
                    "disclaimer": "Fictional demo; last reported facts, not live GPS. Charges are estimates, not an invoice. Expected start is a caller report, not a confirmed ETA."}

    def report(self, load_id: str, *, state: str, confirmed: bool,
               occurred_at: datetime, detail: str = "", expected_start: str = "",
               action_id: str) -> dict:
        with self._lock:
            if confirmed is not True:
                raise ValueError("Confirm the caller's actual report before saving.")
            if state not in STATES:
                raise ValueError("Use waiting, unloading_started or unloading_done.")
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("A stable action_id is required.")
            if not isinstance(detail, str) or not isinstance(expected_start, str):
                raise ValueError("Report detail and expected start must be text.")
            detail = detail.strip() or {
                "waiting": "Caller confirmed still waiting on site for unloading.",
                "unloading_started": "Caller confirmed actual unloading has started.",
                "unloading_done": "Caller confirmed actual unloading is complete.",
            }[state]
            expected_start = expected_start.strip()
            stamp = format_time(occurred_at)
            if occurred_at > self.as_of:
                raise ValueError("Future events are expectations, not actual unloading.")
            if expected_start and state != "waiting":
                raise ValueError("Expected start cannot be recorded as actual unloading.")
            current = self.status(load_id)
            if not current["known"]:
                raise ValueError("Unknown load; no shipment facts saved.")
            facts = self._facts(load_id)
            arrival = next(e for e in facts if e.type == "arrived")
            if occurred_at < parse_time(arrival.occurred_at):
                raise ValueError("The report cannot precede recorded on-site arrival.")
            event_id = "inbound-" + sha256(f"{load_id}:{action_id}".encode()).hexdigest()[:40]
            payload = {"reason": "still_waiting", "detail": detail} if state == "waiting" else {"door": "not reported", "detail": detail}
            payload.update(expected_start=expected_start, confirmed=True)
            existing = next((e for e in self.log.read() if e.event_id == event_id), None)
            if existing:
                if existing.type != STATES[state] or existing.occurred_at != stamp or existing.payload != payload:
                    raise ValueError("action_id already belongs to a different report.")
                return {"saved": True, "event_id": event_id, "duplicate": True, "status": current}
            if state == "waiting" and current["stage"] != "waiting":
                raise ValueError("Unloading has already been recorded; dispatch must review a conflicting report.")
            if state == "unloading_started" and current["stage"] != "waiting":
                raise ValueError("Actual unloading start has already been recorded.")
            if state == "unloading_done":
                starts = [parse_time(e.occurred_at) for e in facts if e.type == "unload_started"]
                if not starts or occurred_at < min(starts):
                    raise ValueError("Record actual unloading start before completion.")
            event = Event(event_id=event_id, type=STATES[state], occurred_at=stamp,
                          recorded_at=format_time(self.as_of), load_id=load_id,
                          actor=Actor(role="driver", party_id="inbound-caller", channel="voice"),
                          payload=payload, caused_by=arrival.event_id, source="dock-intake")
            event = event_from_dict(event.to_dict())
            appended = self.log.append([event])
            return {"saved": True, "event_id": event_id, "duplicate": not bool(appended.appended),
                    "status": self.status(load_id)}
