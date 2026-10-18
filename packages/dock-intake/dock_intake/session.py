"""Confirmed inbound facts for one fictional load.

The live desk still classifies SMS with normalize_message. This session is the
opt-in path: a caller confirms a structured report, and only that report is
appended. Clock math stays in dock-clock. Notices and call results are not
written here.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from threading import RLock

from dock_clock.policy import policy_from_context
from dock_clock.tick import tick
from dock_events.context import load_context
from dock_events.log import EventLog
from dock_events.model import Actor, Event, event_from_dict
from dock_events.timeutil import format_time, parse_time

LOAD_ID = "LL-88421"
SAMPLE_LOG = "data/samples/harbor-rye.raw.jsonl"
PARTIES = "data/samples/parties.json"

# Seed the runtime log with on-site facts only. The sample's call_result and
# later unload are a scripted outcome, not something this call observed.
SEED_TYPES = ("arrived", "delay_reported")
STATES = {
    "waiting": "delay_reported",
    "unloading_started": "unload_started",
    "unloading_done": "unload_done",
}
FACT_TYPES = frozenset(STATES.values())
FABRICATED_TYPES = frozenset({"notice_sent", "call_result", "claim_drafted"})

_DEFAULT_DETAIL = {
    "waiting": "Caller confirmed still waiting on site for unloading.",
    "unloading_started": "Caller confirmed actual unloading has started.",
    "unloading_done": "Caller confirmed actual unloading is complete.",
}


class InboundSession:
    def __init__(self, root: Path, log_path: Path, as_of: datetime):
        format_time(as_of)
        samples = (Path(root) / "data/samples").resolve()
        if Path(log_path).resolve().is_relative_to(samples):
            raise ValueError("Runtime log must not modify sample fixtures.")
        self.as_of = as_of
        self.policy = policy_from_context(load_context(Path(root) / PARTIES))
        self.log = EventLog(log_path)
        self._lock = RLock()
        sample = EventLog(Path(root) / SAMPLE_LOG).read()
        seeds = [
            event
            for event in sample
            if event.load_id == LOAD_ID
            and event.type in SEED_TYPES
            and parse_time(event.occurred_at) <= as_of
        ]
        self.log.append(seeds)
        # A restart must not hide an operational update that was already accepted.
        accepted = [
            parse_time(event.occurred_at)
            for event in self.log.read()
            if event.load_id == LOAD_ID
            and event.source == "dock-intake"
            and event.type in FACT_TYPES
        ]
        self.as_of = max([as_of, *accepted])

    def _facts(self, load_id: str) -> list[Event]:
        return sorted(
            (
                event
                for event in self.log.read()
                if event.load_id == load_id
                and event.type in ("arrived", *FACT_TYPES)
                and parse_time(event.occurred_at) <= self.as_of
            ),
            key=lambda event: (parse_time(event.occurred_at), parse_time(event.recorded_at)),
        )

    def status(self, load_id: str) -> dict:
        with self._lock:
            facts = self._facts(load_id) if load_id == LOAD_ID else []
            arrival = next((event for event in facts if event.type == "arrived"), None)
            base = {
                "load_id": load_id,
                "known": arrival is not None,
                "as_of": format_time(self.as_of),
            }
            if arrival is None:
                return {
                    **base,
                    "detail": (
                        "No recorded shipment facts for this load. "
                        "Ask dispatch to review; no contact has been made."
                    ),
                }
            latest = facts[-1]
            stage = "waiting"
            if any(event.type == "unload_started" for event in facts):
                stage = "unloading_started"
            if any(event.type == "unload_done" for event in facts):
                stage = "unloading_done"
            derived = tick(facts, as_of=self.as_of, policy=self.policy)
            started = next((event for event in derived if event.type == "clock_started"), None)
            risk = next((event for event in derived if event.type == "charge_risk"), None)
            if risk is not None:
                clock = dict(risk.payload)
            elif started is not None:
                clock = dict(started.payload)
            else:
                clock = {}
            if risk is None:
                if started is None:
                    remaining = None
                else:
                    free_end = parse_time(clock["free_time_ends_at"])
                    remaining = max(int((free_end - self.as_of).total_seconds() // 60), 0)
                clock.update(
                    phase="free_time" if started else "not_started",
                    estimated_charge_usd="0.00",
                    remaining_free_minutes=remaining,
                )
            expected = latest.payload.get("expected_start") if stage == "waiting" else None
            return {
                **base,
                "stage": stage,
                "facility": arrival.payload["facility"],
                "source_timestamp": latest.occurred_at,
                "eta": None,
                "expected_start": expected,
                "detail": latest.payload.get("detail", ""),
                "clock": clock,
                "notices": [],
                "call_results": [],
                "disclaimer": (
                    "Fictional demo; last reported facts, not live GPS. "
                    "Charges are estimates, not an invoice. "
                    "Expected start is a caller report, not a confirmed ETA. "
                    "No notice or call result was fabricated."
                ),
            }

    def report(
        self,
        load_id: str,
        *,
        state: str,
        confirmed: bool,
        occurred_at: datetime,
        detail: str = "",
        expected_start: str = "",
        action_id: str,
    ) -> dict:
        with self._lock:
            if confirmed is not True:
                raise ValueError("Confirm the caller's actual report before saving.")
            if state not in STATES:
                raise ValueError("Use waiting, unloading_started or unloading_done.")
            if not isinstance(action_id, str) or not action_id.strip():
                raise ValueError("A stable action_id is required.")
            if not isinstance(detail, str) or not isinstance(expected_start, str):
                raise ValueError("Report detail and expected start must be text.")
            if occurred_at.tzinfo is None:
                raise ValueError("A past timestamp needs a timezone. Dock will not guess one.")
            detail = detail.strip() or _DEFAULT_DETAIL[state]
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
            arrival = next(event for event in facts if event.type == "arrived")
            if occurred_at < parse_time(arrival.occurred_at):
                raise ValueError("The report cannot precede recorded on-site arrival.")
            event_type = STATES[state]
            if event_type in FABRICATED_TYPES or event_type not in FACT_TYPES:
                raise ValueError("Inbound intake does not write notices or call results.")
            event_id = "inbound-" + sha256(f"{load_id}:{action_id}".encode()).hexdigest()[:40]
            payload = _payload(state, detail, expected_start)
            existing = next((event for event in self.log.read() if event.event_id == event_id), None)
            if existing:
                if (
                    existing.type != event_type
                    or existing.occurred_at != stamp
                    or existing.payload != payload
                ):
                    raise ValueError("action_id already belongs to a different report.")
                return {
                    "saved": True,
                    "event_id": event_id,
                    "duplicate": True,
                    "status": current,
                }
            if state == "waiting" and current["stage"] != "waiting":
                raise ValueError(
                    "Unloading has already been recorded; dispatch must review a conflicting report."
                )
            if state == "unloading_started" and current["stage"] != "waiting":
                raise ValueError("Actual unloading start has already been recorded.")
            if state == "unloading_done":
                starts = [
                    parse_time(event.occurred_at)
                    for event in facts
                    if event.type == "unload_started"
                ]
                if not starts or occurred_at < min(starts):
                    raise ValueError("Record actual unloading start before completion.")
            event = Event(
                event_id=event_id,
                type=event_type,
                occurred_at=stamp,
                recorded_at=format_time(self.as_of),
                load_id=load_id,
                actor=Actor(role="driver", party_id="inbound-caller", channel="voice"),
                payload=payload,
                caused_by=arrival.event_id,
                source="dock-intake",
            )
            event = event_from_dict(event.to_dict())
            appended = self.log.append([event])
            return {
                "saved": True,
                "event_id": event_id,
                "duplicate": not bool(appended.appended),
                "status": self.status(load_id),
            }


def _payload(state: str, detail: str, expected_start: str) -> dict:
    if state == "waiting":
        payload: dict = {"reason": "still_waiting", "detail": detail}
    else:
        payload = {"door": "not reported", "detail": detail}
    payload["expected_start"] = expected_start
    payload["confirmed"] = True
    return payload
