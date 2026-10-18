"""Live desk: one append-only log on disk, one shared demo clock, read by the web and the voice agent.

Every process (dock-web, dock-voice, dock-live) opens the same files under data/runtime/:

- live.jsonl        the event log (facts only; clock and notice events are derived on read)
- live-clock.json   {"offset_seconds": ...}: demo time = wall time + offset

The demo clock runs in real time from the sample Saturday (2:04 PM ET), so a live call
lands at the times the story uses. Jumps move the offset; nothing is rewritten.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dock_events.context import arrived_payload, load_context
from dock_events.log import EventLog
from dock_events.model import Actor, Event
from dock_events.timeutil import format_local, format_time, parse_time
from dock_intake.normalize import normalize_message

from dock_web.desk import Desk

START_AT = "2026-10-17T18:04:00Z"  # 2:04 PM ET, four minutes after the appointment

LIVE_PRESETS = (
    {"id": "plus15", "label": "+15 min"},
    {"id": "warning", "label": "30 min of free time left"},
    {"id": "accruing", "label": "15 min past free time"},
)

LIVE_PROMPTS = (
    "I'm at Harbor and Rye door 4. They are not ready to unload.",
    "Still waiting. Door is occupied.",
    "They started unloading.",
    "Done unloading, empty.",
)


def _wall() -> datetime:
    return datetime.now(timezone.utc)


class _Remote:
    """Same LiveRun, backed by a dock-web desk elsewhere (DOCK_LIVE_URL). Lets the voice agent run on one
    machine and the public desk on another while sharing one log and one clock."""

    def __init__(self, base: str, token: str):
        self.base = base.rstrip("/")
        self.token = token

    def _call(self, path: str, body: dict | None = None) -> dict:
        from urllib.request import Request, urlopen

        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(self.base + path, data=data, method="POST" if data is not None else "GET")
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("X-Dock-Token", self.token)
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def raw(self) -> dict:
        return self._call("/api/live/raw")

    def append(self, events: list[Event]) -> list[str]:
        return self._call("/api/live/events", {"events": [e.to_dict() for e in events]}).get("appended", [])

    def set_offset(self, offset: float) -> None:
        self._call("/api/live/clock", {"offset_seconds": offset})

    def reset(self) -> None:
        self._call("/api/live/reset", {})


class LiveRun:
    def __init__(self, root: Path, runtime: Path | None = None, wall=_wall):
        url = os.environ.get("DOCK_LIVE_URL", "")
        self.remote = _Remote(url, os.environ.get("DOCK_WRITE_TOKEN", "")) if url else None
        self.root = Path(root)
        self.runtime = Path(runtime or os.environ.get("DOCK_RUNTIME") or self.root / "data" / "runtime")
        self.log = EventLog(self.runtime / "live.jsonl")
        self.clock_path = self.runtime / "live-clock.json"
        self.context = load_context(self.root / "data" / "samples" / "parties.json")
        self._wall = wall

    # clock -------------------------------------------------------------
    def offset(self) -> float:
        if self.remote:
            return float(self.remote.raw()["offset_seconds"])
        if not self.clock_path.exists():
            self.set_now(parse_time(START_AT))
        try:
            return float(json.loads(self.clock_path.read_text(encoding="utf-8"))["offset_seconds"])
        except (ValueError, KeyError, json.JSONDecodeError):
            return 0.0

    def now(self) -> datetime:
        return (self._wall() + timedelta(seconds=self.offset() + 0.5)).replace(microsecond=0)

    def set_now(self, moment: datetime) -> None:
        offset = (moment - self._wall()).total_seconds()
        self.set_offset(offset)

    def set_offset(self, offset: float) -> None:
        if self.remote:
            self.remote.set_offset(offset)
            return
        self.runtime.mkdir(parents=True, exist_ok=True)
        tmp = self.clock_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"offset_seconds": offset}), encoding="utf-8")
        tmp.replace(self.clock_path)

    def advance(self, minutes: float) -> None:
        self.set_now(self.now() + timedelta(minutes=minutes))

    # log ---------------------------------------------------------------
    def read(self) -> list[Event]:
        if self.remote:
            from dock_events.model import event_from_dict

            return [event_from_dict(obj) for obj in self.remote.raw()["events"]]
        return self.log.read()

    def append(self, events: list[Event]) -> list[Event]:
        if self.remote:
            ids = set(self.remote.append(events))
            return [event for event in events if event.event_id in ids]
        return list(self.log.append(events).appended)

    def raw(self) -> dict:
        return {"events": [event.to_dict() for event in self.read()], "offset_seconds": self.offset()}

    def reset(self) -> None:
        if self.remote:
            self.remote.reset()
            return
        self.runtime.mkdir(parents=True, exist_ok=True)
        if self.log.path.exists():
            stamp = _wall().strftime("%Y%m%dT%H%M%S")
            self.log.path.rename(self.runtime / f"live-{stamp}.jsonl.bak")
        self.set_now(parse_time(START_AT))

    def has(self, event_type: str) -> bool:
        return any(event.type == event_type for event in self.read())

    # facts the voice agent and the web both write ----------------------
    def driver_report(self, text: str, *, channel: str = "sms") -> list[Event]:
        load = self.context["load"]
        stamp = format_time(self.now())
        events = normalize_message(
            text,
            load_id=load["load_id"],
            party_id=load["driver_party_id"],
            role="driver",
            channel=channel,
            occurred_at=stamp,
            context=self.context,
            recorded_at=stamp,
        )
        if self.has("arrived"):
            events = [event for event in events if event.type != "arrived"]
            if not events:
                raise ValueError("Luis is already checked in. Report a delay, unload started, or unload done.")
        return self.append(events)

    def driver_status(self, status: str, *, detail: str = "", channel: str = "voice") -> list[Event]:
        """Structured path for the voice agent: status is arrived, waiting, unload_started, or unload_done."""
        load = self.context["load"]
        stamp = format_time(self.now())
        actor = Actor(role="driver", party_id=load["driver_party_id"], channel=channel)
        out: list[Event] = []

        def make(kind: str, payload: dict) -> Event:
            return Event(
                event_id=f"evt-{kind[:8]}-{uuid.uuid4().hex[:12]}",
                type=kind,
                occurred_at=stamp,
                recorded_at=stamp,
                load_id=load["load_id"],
                actor=actor,
                payload=payload,
                source="dock-voice" if channel == "voice" else "dock-intake",
            )

        door = load.get("door", "door 4")
        if status in ("arrived", "waiting"):
            if not self.has("arrived"):
                out.append(make("arrived", arrived_payload(self.context)))
            reason = "door_occupied" if "occup" in detail.lower() else "receiver_not_ready"
            out.append(make("delay_reported", {"reason": reason, "detail": detail.strip() or "They are not ready to unload."}))
        elif status in ("unload_started", "unload_done"):
            if not self.has("arrived"):
                out.append(make("arrived", arrived_payload(self.context)))
            out.append(make(status, {"door": door}))
        else:
            raise ValueError(f"unknown driver status {status}")
        return self.append(out)

    def heads_up_by_voice(self, *, call_id: str, to_role: str, body: str, reply: str, summary: dict) -> list[Event]:
        """The outbound heads-up, delivered on an inbound call. Logs notice_sent (voice) and call_result."""
        load = self.context["load"]
        party = next(p for p in self.context["parties"] if p["role"] == to_role)
        stamp = format_time(self.now())
        slug = "".join(ch for ch in call_id if ch.isalnum() or ch in "-_")[:40] or uuid.uuid4().hex[:12]
        actor = Actor(role="system", party_id="dock-voice", channel="voice")
        events: list[Event] = []
        if summary.get("phase") in ("warning", "accruing", "closed"):
            events.append(
                Event(
                    event_id=f"ntc-voice-{slug}",
                    type="notice_sent",
                    occurred_at=stamp,
                    recorded_at=stamp,
                    load_id=load["load_id"],
                    actor=actor,
                    payload={
                        "channel": "voice",
                        "to_party_id": party["party_id"],
                        "to_role": to_role,
                        "to_name": party["contact"],
                        "body": body,
                        "estimated_charge_usd": summary["estimated_charge_usd"],
                        "phase": summary["phase"],
                        "provider": "guava",
                        "delivery_status": "spoken",
                    },
                    source="dock-voice",
                )
            )
        events.append(
            Event(
                event_id=f"call-voice-{slug}",
                type="call_result",
                occurred_at=stamp,
                recorded_at=stamp,
                load_id=load["load_id"],
                actor=actor,
                payload={
                    "goal": f"{to_role}_heads_up",
                    "outcome": "reached",
                    "to_party_id": party["party_id"],
                    "to_name": party["contact"],
                    "to_role": to_role,
                    "summary": (reply.strip() or "Heard the heads-up.")[:400],
                },
                source="dock-voice",
            )
        )
        return self.append(events)


class LiveDesk(Desk):
    """The same Desk projection, fed from the shared log and the shared clock on every read."""

    def __init__(self, run: LiveRun):
        super().__init__(run.context, [])
        self.run = run
        self.note = "Live. Call the Dock line or text as the driver; every view reads the same log."

    def _sync(self) -> None:
        with self._lock:
            self._base = self.run.read()
            self._extra = []
            self.as_of = self.run.now()

    def snapshot(self) -> dict:
        self._sync()
        snap = super().snapshot()
        snap["mode"] = "live"
        snap["banner"] = "Live desk. Fictional load. Every view reads data/runtime/live.jsonl."
        snap["presets"] = list(LIVE_PRESETS)
        snap["driver_prompts"] = list(LIVE_PROMPTS)
        snap["active_preset"] = None
        snap["agent_number"] = os.environ.get("GUAVA_AGENT_NUMBER", "")
        snap["clock_local"] = format_local(format_time(self.as_of), self._zone())
        snap["heads_up"] = {role: heads_up_text(snap, role) for role in ("shipper", "consignee", "broker")}
        return snap

    def reset(self) -> None:
        self.run.reset()
        self.note = "New live run. Clock back to 2:04 PM ET, log archived."

    def jump(self, as_of: str) -> None:
        self.run.set_now(parse_time(as_of))
        self.note = f"Demo clock moved to {format_local(as_of, self._zone())}."

    def jump_preset(self, preset_id: str) -> None:
        if preset_id == "plus15":
            self.run.advance(15)
            self.note = "Demo clock +15 min."
            return
        clock = self._clock()
        if clock is None:
            raise ValueError("No arrival yet. Call in as the driver (or log a driver SMS) first.")
        free_end = parse_time(clock["free_time_ends_at"])
        if preset_id == "warning":
            target = free_end - timedelta(minutes=self.policy.warn_minutes)
        elif preset_id == "accruing":
            target = free_end + timedelta(minutes=15)
        else:
            raise ValueError(f"unknown preset {preset_id}")
        if target > self.run.now():
            self.run.set_now(target)
        self.note = f"Demo clock at {format_local(format_time(self.run.now()), self._zone())}."

    def report_driver(self, text: str) -> None:
        events = self.run.driver_report(text, channel="sms")
        self.note = "Logged " + ", ".join(event.type for event in events) + " from driver SMS."

    def _clock(self) -> dict | None:
        from dock_clock.tick import replay_clock

        facts = [event for event in self.run.read() if parse_time(event.occurred_at) <= self.run.now()]
        for event in replay_clock(facts, as_of=self.run.now(), policy=self.policy):
            if event.type == "clock_started":
                return event.payload
        return None


def heads_up_text(snap: dict, role: str) -> str:
    """What Dock would have said on the outbound call. Rules in code, not in a prompt.

    Once the clock has a charge_risk mark, the spoken script is dock-notify's compose_pair, so the call and
    the SMS say the same thing. Before the first mark (plenty of free time) Dock gives a plain status."""
    if role in ("shipper", "consignee"):
        spoken = _notify_script(snap, role)
        if spoken:
            return spoken
    s = snap["summary"]
    load = snap["load"]
    if s["phase"] == "not_started":
        return (
            f"Load {load['load_id']} for {load['facility']}: the driver has not checked in yet, "
            "so no detention clock is running."
        )
    events = [row["event"] for row in snap["events"]]
    arrived = next((e for e in events if e["type"] == "arrived"), None)
    since = ""
    if arrived:
        since = f" since {format_local(arrived['occurred_at'], load['timezone'])}"
    door = load.get("door", "the door")
    who = "Red Kettle's driver, Luis,"
    where = f"your {door}" if role == "consignee" else f"Harbor and Rye {door}"
    start = "If you start the unload" if role == "consignee" else "If the unload starts"
    if s["phase"] in ("running", "warning"):
        return (
            f"Heads-up on load {load['load_id']}, {load['reference']}. {who} has been waiting at "
            f"{where}{since}. Free time ends at {s['free_time_ends_local']}, "
            f"{s['remaining_free_minutes']} minutes from now. The detention estimate so far is "
            f"${s['estimated_charge_usd']}. {start} before {s['free_time_ends_local']}, it stays at zero."
        )
    if s["phase"] == "accruing":
        return (
            f"Heads-up on load {load['load_id']}. Free time ended at {s['free_time_ends_local']} and the trailer at "
            f"{door} is still closed. ${s['estimated_charge_usd']} is on the trail, "
            f"and it goes up ${_step(snap)} every {snap['policy']['increment_minutes']} minutes until the unload starts."
        )
    return (
        f"Update on load {load['load_id']}. The unload started and the clock stopped. "
        f"The trail supports ${s['estimated_charge_usd']} of detention. This is not an invoice."
    )


def _notify_script(snap: dict, role: str) -> str | None:
    from dock_events.model import event_from_dict
    from dock_notify.compose import compose_pair

    events = [event_from_dict(row["event"]) for row in snap["events"]]
    arrived = next((e for e in events if e.type == "arrived"), None)
    risks = [e for e in events if e.type == "charge_risk"]
    if arrived is None or not risks:
        return None
    charge = max(risks, key=lambda e: (e.occurred_at, e.event_id))
    try:
        _sms, spoken = compose_pair(arrived.payload, charge, role)
    except (ValueError, KeyError):
        return None
    return spoken


def _step(snap: dict) -> str:
    from decimal import Decimal

    rate = Decimal(snap["policy"]["rate_usd_per_hour"])
    step = rate * Decimal(snap["policy"]["increment_minutes"]) / Decimal(60)
    return f"{step.quantize(Decimal('0.01')):.2f}"
