"""In-memory Saturday desk. The sample file is not rewritten."""

from __future__ import annotations

import threading
from pathlib import Path

from dock_clock.policy import DetentionPolicy, policy_from_context
from dock_clock.tick import replay_clock
from dock_events.context import load_context
from dock_events.log import EventLog
from dock_events.model import Event, load_jsonl
from dock_events.timeutil import format_local, format_local_long, format_time, parse_time
from dock_intake.normalize import normalize_message
from dock_notify.compose import apply_notices
from dock_notify.provider import LogProvider
from dock_proof.render import render_markdown

from dock_web.present import event_line, sort_key, zone_for
from dock_web.presets import DRIVER_PROMPTS, PRESETS


class Desk:
    def __init__(self, context: dict, facts: list[Event]):
        self.context = context
        self.policy: DetentionPolicy = policy_from_context(context)
        self.runtime_log: Path | None = None
        self._base = list(facts)
        self._extra: list[Event] = []
        self.as_of = parse_time(PRESETS[0]["as_of"])
        self._lock = threading.Lock()
        self.note = "Sample Saturday. No phone call or SMS leaves this machine."

    @classmethod
    def from_repo(cls, root: Path) -> Desk:
        context_path = root / "data" / "samples" / "parties.json"
        raw_path = root / "data" / "samples" / "harbor-rye.raw.jsonl"
        context = load_context(context_path)
        facts = load_jsonl(raw_path.read_text(encoding="utf-8"))
        return cls(context, facts)

    @classmethod
    def from_runtime(cls, root: Path, log_path: Path, as_of: str) -> Desk:
        context = load_context(root / "data" / "samples" / "parties.json")
        if not log_path.is_file():
            raise ValueError("runtime log does not exist; initialize with dock-inbound status first")
        desk = cls(context, [])
        desk.runtime_log = log_path
        desk.as_of = parse_time(as_of)
        desk.note = "Confirmed inbound reports. Refresh to read the latest saved facts."
        return desk

    def _require_sample(self) -> None:
        if self.runtime_log is not None:
            raise ValueError("inbound evidence view is read-only; report changes through the inbound agent")

    def reset(self) -> None:
        self._require_sample()
        with self._lock:
            self._extra.clear()
            self.as_of = parse_time(PRESETS[0]["as_of"])
            self.note = "Reset to the sample. Driver messages you added are gone."

    def jump(self, as_of: str) -> None:
        self._require_sample()
        with self._lock:
            self.as_of = parse_time(as_of)
            self.note = f"Demo clock moved to {format_local_long(as_of, self._zone())}."

    def jump_preset(self, preset_id: str) -> None:
        match = next((item for item in PRESETS if item["id"] == preset_id), None)
        if match is None:
            raise ValueError(f"unknown preset {preset_id}")
        self.jump(match["as_of"])

    def report_driver(self, text: str) -> None:
        self._require_sample()
        load = self.context["load"]
        occurred = format_time(self.as_of)
        events = normalize_message(
            text,
            load_id=load["load_id"],
            party_id=load["driver_party_id"],
            role="driver",
            channel="sms",
            occurred_at=occurred,
            context=self.context,
            recorded_at=occurred,
        )
        with self._lock:
            self._extra.extend(events)
            kinds = ", ".join(event.type for event in events)
            self.note = f"Logged {kinds} at {format_local(occurred, self._zone())}."

    def snapshot(self) -> dict:
        with self._lock:
            raw = EventLog(self.runtime_log).read() if self.runtime_log is not None else [*self._base, *self._extra]
            raw = [event for event in raw if event.load_id == self.context["load"]["load_id"]]
            as_of = self.as_of
            if self.runtime_log is not None and raw:
                as_of = max(as_of, *(parse_time(event.occurred_at) for event in raw))
            facts = [event for event in raw if parse_time(event.occurred_at) <= as_of]
            note = self.note
        projected = replay_clock(facts, as_of=as_of, policy=self.policy)
        if self.runtime_log is None:
            projected = apply_notices(projected, provider=LogProvider())
        ordered = sorted(projected, key=sort_key)
        load = self.context["load"]
        zone = load["timezone"]
        summary = _summary(ordered, as_of, zone)
        markdown = render_markdown(ordered, load["load_id"])
        active = next((item["id"] for item in PRESETS if parse_time(item["as_of"]) == as_of), None)
        return {
            "runtime_mode": self.runtime_log is not None,
            "banner": ("Fictional inbound demo. Saved reports only; no outbound calls or SMS."
                       if self.runtime_log is not None else "Fictional Saturday desk. No call or SMS leaves this machine."),
            "note": note,
            "demo_as_of": format_time(as_of),
            "demo_as_of_local": format_local_long(format_time(as_of), zone),
            "active_preset": active,
            "presets": [] if self.runtime_log is not None else list(PRESETS),
            "driver_prompts": [] if self.runtime_log is not None else list(DRIVER_PROMPTS),
            "load": load,
            "parties": self.context["parties"],
            "policy": {
                "free_minutes": self.policy.free_minutes,
                "warn_minutes": self.policy.warn_minutes,
                "rate_usd_per_hour": self.policy.rate_text,
                "increment_minutes": self.policy.increment_minutes,
                "stop_on": self.policy.stop_on,
            },
            "summary": summary,
            "events": [
                {
                    "event": event.to_dict(),
                    "occurred_local": format_local(event.occurred_at, zone_for(event) if event.payload.get("timezone") else zone),
                    "line": event_line(event),
                }
                for event in ordered
            ],
            "proof_markdown": markdown,
        }

    def _zone(self) -> str:
        return self.context["load"]["timezone"]


def _summary(events: list[Event], as_of, zone: str) -> dict:
    clocks = [event for event in events if event.type == "clock_started"]
    risks = [event for event in events if event.type == "charge_risk"]
    if not clocks:
        return {
            "phase": "not_started",
            "stamp": "NO CLOCK",
            "headline": "No clock yet",
            "detail": "The clock starts when the driver arrives, or at the appointment if the driver is early.",
            "estimated_charge_usd": "0.00",
            "remaining_free_minutes": None,
            "elapsed_minutes": None,
            "billable_minutes": 0,
            "free_time_ends_local": None,
            "how_to_avoid": "Wait for an arrival before talking about detention.",
        }
    clock = clocks[0]
    free_end = parse_time(clock.payload["free_time_ends_at"])
    start = parse_time(clock.payload["clock_started_at"])
    latest = max(risks, key=lambda event: (event.occurred_at, event.event_id)) if risks else None
    phase = latest.payload["phase"] if latest else "running"
    remaining = max(int((free_end - as_of).total_seconds() // 60), 0)
    elapsed = max(int((min(as_of, free_end) - start).total_seconds() // 60), 0)
    if latest and phase == "closed":
        elapsed = latest.payload["elapsed_minutes"]
        remaining = 0
    elif latest and phase == "accruing":
        elapsed = latest.payload["elapsed_minutes"]
        remaining = 0
    charge = latest.payload["estimated_charge_usd"] if latest else "0.00"
    billable = latest.payload["billable_minutes"] if latest else 0
    ends_local = format_local(clock.payload["free_time_ends_at"], zone)
    if phase == "running":
        headline = f"{_span(remaining)} free"
        stamp = "ON FREE TIME"
        detail = f"Free time ends {ends_local}. Nothing has accrued."
    elif phase == "warning":
        headline = f"{_span(remaining)} free"
        stamp = "FREE TIME LOW"
        detail = f"Heads-up territory. Free time ends {ends_local}."
    elif phase == "accruing":
        headline = f"${charge} on the trail"
        stamp = "ACCRUING"
        detail = f"{billable} billable minutes. Unload has not started."
    else:
        headline = f"${charge} supported"
        stamp = "CLOCK STOPPED"
        detail = f"Unload started. This trail supports ${charge}. It is not an invoice."
    how = latest.payload["how_to_avoid"] if latest else f"Start the unload before {ends_local}."
    return {
        "phase": phase,
        "stamp": stamp,
        "headline": headline,
        "detail": detail,
        "estimated_charge_usd": charge,
        "remaining_free_minutes": remaining,
        "elapsed_minutes": elapsed,
        "billable_minutes": billable,
        "free_time_ends_local": ends_local,
        "how_to_avoid": how,
    }


def _span(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"
