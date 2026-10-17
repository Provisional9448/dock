"""Goals, checklists, and rules. The opening line is filled from events, not invented."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from dock_events.model import Actor, Event
from dock_events.timeutil import format_local, format_time

RULES = (
    "State the free-time end from the event. Do not invent a time.",
    "Quote estimated_charge_usd only when the phase is accruing or closed.",
    "When the estimate is still 0.00, say it is zero and say when it starts.",
    "Do not threaten collections, a legal claim, or the relationship.",
    "On voicemail, leave the load id, the free-time end, and the callback number, then stop.",
    "Do not discuss lumper, cargo claims, rate confirmation, or other accessorials.",
)


@dataclass(frozen=True)
class Goal:
    goal_id: str
    objective: str
    checklist: tuple[dict[str, object], ...]


RECEIVER_DELAY = Goal(
    goal_id="receiver_delay",
    objective="Get a commit time for when the receiver will start the unload.",
    checklist=(
        {
            "key": "reached",
            "field_type": "multiple_choice",
            "choices": ["yes", "voicemail", "wrong_person"],
            "description": "Whether the dock contact is actually on the line",
        },
        {
            "key": "commit_time",
            "field_type": "text",
            "description": "When they say unload will start, in their words",
        },
        {
            "key": "blocker",
            "field_type": "text",
            "description": "What is in the way, if they named it",
        },
    ),
)

GOALS = {RECEIVER_DELAY.goal_id: RECEIVER_DELAY}


def build_plan(events: list[Event], goal_id: str = "receiver_delay") -> dict:
    try:
        goal = GOALS[goal_id]
    except KeyError as exc:
        raise ValueError(f"unknown goal {goal_id}") from exc
    arrived = _latest(events, "arrived")
    if arrived is None:
        raise ValueError("need an arrived event before planning a call")
    charge = _latest(events, "charge_risk")
    clock = _latest(events, "clock_started")
    snap = arrived.payload
    zone = snap["timezone"]
    if charge is not None:
        free_end = charge.payload["free_time_ends_at"]
        phase = charge.payload["phase"]
        estimate = charge.payload["estimated_charge_usd"]
        how = charge.payload["how_to_avoid"]
    elif clock is not None:
        free_end = clock.payload["free_time_ends_at"]
        phase = "running"
        estimate = "0.00"
        how = f"Start the unload before {format_local(free_end, zone)}."
    else:
        raise ValueError("need a clock_started or charge_risk event before planning a call")
    opening = _opening(snap, arrived, zone, free_end, phase, estimate)
    return {
        "goal": goal.goal_id,
        "objective": goal.objective,
        "opening": opening,
        "checklist": [dict(item) for item in goal.checklist],
        "rules": list(RULES),
        "instruction": instruction_for(phase, estimate, free_end, zone),
        "variables": {
            "load_id": arrived.load_id,
            "driver_name": snap["driver_name"],
            "facility": snap["facility"],
            "phase": phase,
            "estimated_charge_usd": estimate,
            "free_time_ends_at": free_end,
            "how_to_avoid": how,
            "contact_name": snap.get("consignee_contact") or snap["consignee_name"],
        },
        "guava": {
            "entrypoint": "agent.call_phone",
            "from_number_env": "GUAVA_AGENT_NUMBER",
            "to_number": snap["consignee_phone"],
            "test_with": ["agent.chat", "agent.roleplay"],
            "docs": "https://goguava.ai/docs/coding-agent-starter.md",
        },
    }


def instruction_for(phase: str, estimate: str, free_end: str, zone: str) -> str:
    when = format_local(free_end, zone)
    if phase in ("accruing", "closed"):
        return (
            f"Tell them the trail currently supports ${estimate}. "
            f"Free time ended {when}. Ask when unload will start. Then stop talking."
        )
    if phase == "warning":
        return (
            f"Tell them the estimate is still $0.00 and free time ends {when}. "
            "Ask when unload will start. Do not quote a dollar figure above zero."
        )
    return f"Tell them free time ends {when} and the estimate is still $0.00. Ask when unload will start."


def simulate_result(plan: dict, *, load_id: str, occurred_at: str, to_party_id: str) -> Event:
    """A call_result that records a dry run. No dial tone."""
    slug = "".join(ch for ch in load_id.lower() if ch.isalnum())[:24]
    return Event(
        event_id=f"call-dry-{slug}",
        type="call_result",
        occurred_at=occurred_at,
        recorded_at=format_time(datetime.now(timezone.utc)),
        load_id=load_id,
        actor=Actor(role="system", party_id="dock-call", channel="system"),
        payload={
            "goal": plan["goal"],
            "outcome": "dry_run",
            "to_party_id": to_party_id,
            "to_name": plan["variables"]["contact_name"],
            "to_role": "consignee",
            "summary": (
                f"Dry run. No call was placed. Opening line was ready for goal {plan['goal']}."
            ),
        },
        caused_by=None,
        source="dock-call",
    )


def _opening(snap: dict, arrived: Event, zone: str, free_end: str, phase: str, estimate: str) -> str:
    since = format_local(arrived.occurred_at, zone)
    ends = format_local(free_end, zone)
    money = ""
    if phase in ("accruing", "closed"):
        money = f" The trail supports ${estimate} so far."
    elif phase == "warning":
        money = " The detention estimate is still $0.00."
    return (
        f"This is Dock calling about load {arrived.load_id} for {snap['carrier_name']}. "
        f"{snap['driver_name']} has been on site since {since}. "
        f"Free time ends at {ends}.{money} "
        "Can someone start the unload, or tell me the time they will?"
    )


def _latest(events: list[Event], event_type: str) -> Event | None:
    found = [event for event in events if event.type == event_type]
    if not found:
        return None
    return max(found, key=lambda event: event.occurred_at)


def serve_outbound(plan: dict, to_number: str) -> None:
    """Place one live call. Tests never set DOCK_CALL_MODE=live."""
    import os

    if os.environ.get("DOCK_CALL_MODE") != "live":
        raise RuntimeError(
            "Refusing to dial. Set DOCK_CALL_MODE=live after a roleplay test passes. "
            "Until then, use `dock-call plan` or agent.chat / agent.roleplay."
        )
    try:
        import guava
    except ImportError as exc:
        raise RuntimeError("Install the voice SDK with: uv add guava-sdk") from exc

    agent = guava.Agent(name="Dock", organization="Dock", purpose=plan["objective"])

    @agent.on_call_start
    def on_call_start(call: guava.Call) -> None:
        call.reach_person(contact_full_name=plan["variables"]["contact_name"])

    @agent.on_reach_person
    def on_reach_person(call: guava.Call, outcome: str) -> None:
        if outcome != "available":
            call.hangup(f"Leave this voicemail: {plan['opening']}")
            return
        call.add_info("detention", plan["variables"])
        call.set_task(
            plan["goal"],
            objective=plan["objective"],
            checklist=[guava.Field(**field) for field in plan["checklist"]],
        )

    agent.call_phone(
        from_number=os.environ["GUAVA_AGENT_NUMBER"],
        to_number=to_number,
        variables=plan["variables"],
    )
