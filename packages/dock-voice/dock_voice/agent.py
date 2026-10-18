"""The Guava agent. One inbound number; the caller picks a role.

- Driver: he already checked in at the receiving window and was told to wait. Dock logs the check-in time
  and the receiver's promise (who said it, what, how long), reads back the free-time end, and later logs
  "still waiting, another 20" or "they started unloading at 4:48". Dock never gives directions.
- Shipper or receiver: the outbound heads-up, delivered inbound. Dock reads the clock now and speaks it;
  logs notice_sent (channel voice) and call_result.
- Broker: the clock and what the trail supports.

Every handler reads LiveDesk.snapshot() at the moment it runs, so the numbers are live mid-call.
"""

from __future__ import annotations

import logging

from dock_web.live import LiveDesk, LiveRun

from dock_voice.record import promise_events, receiver_promise, log_receiver, build_driver_events, local_snapshot, post_later, queue_notices
from dock_voice.script import (
    DRIVER_STATUS,
    answer_question,
    driver_readback,
    parse_clock,
    parse_minutes,
    pick_role,
    broker_brief,
    caller_party,
    consignee_brief,
    greeting,
    goodbye_line,
    payer_role,
    pick_status,
    promise_readback,
    shipper_brief,
    spoken,
)

NAME_NOTE = (
    " The driver's name is Luis (said 'loo-EES'). If you hear Louise, Lewis, Louis or Luiz, it is Luis; call him Luis."
    " Say clock times like '2:06 PM Eastern', never 'ET' and never with a leading zero."
    " After the driver answers, do not say 'one moment' or 'processing'; Dock's read-back comes right away."
)

log = logging.getLogger("dock-voice")

DISCLOSURE = greeting(None)  # unknown caller; known callers get greeting(role)
STYLE = (
    " Talk like a dispatcher on the phone: short, casual, plain. Never say 'load trail', 'load record', 'logged', "
    "'timestamped', 'automated AI assistant', 'one moment' or 'processing'."
)


def fetch_call_files(call_id: str, stem, *, tries: int = 12, wait: float = 10.0, cli: str | None = None, run=None, sleep=None) -> dict:
    """Pull transcript (.txt) and audio (.wav) for a finished call from Guava, retrying until both are there.

    Guava answers 'No transcript available yet.' (exit 0) for a while after hangup, and the WAV can lag too,
    so neither counts until it has real content. Returns {"transcript": bool, "audio": bool}."""
    import os
    import re
    import shutil
    import subprocess
    import time
    from pathlib import Path

    run = run or subprocess.run
    sleep = sleep or time.sleep
    cli = cli or shutil.which("guava") or os.path.expanduser("~/.local/bin/guava")
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    txt, wav = stem.with_suffix(".txt"), stem.with_suffix(".wav")
    got = {"transcript": False, "audio": False}
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    for attempt in range(tries):
        if not got["transcript"]:
            out = run([cli, "conversations", "transcript", call_id], capture_output=True, text=True)
            text = ansi.sub("", out.stdout or "").strip()
            if out.returncode == 0 and text and "no transcript available" not in text.lower():
                txt.write_text(text + "\n", encoding="utf-8")
                got["transcript"] = True
        if not got["audio"]:
            out = run([cli, "conversations", "recording", call_id, "-o", str(wav)], capture_output=True, text=True)
            if out.returncode == 0 and wav.exists() and wav.stat().st_size > 1024:
                got["audio"] = True
            elif wav.exists() and wav.stat().st_size <= 1024:
                wav.unlink()
        if all(got.values()):
            break
        sleep(wait)
    if not got["transcript"]:
        txt.write_text("No transcript from Guava after retrying.\n", encoding="utf-8")
    log.info("call %s files: transcript=%s audio=%s (%s.*)%s", call_id, got["transcript"], got["audio"], stem,
             "" if got["audio"] else " - Guava gave no audio; get it from the caller side")
    return got


def save_call_later(call_id: str, role: str, delay: float = 15.0) -> None:
    """After hangup, save the transcript and WAV into demo/calls/ for the video. Retries ~2 minutes. Best effort."""
    import os
    import threading
    import time
    from datetime import datetime
    from pathlib import Path

    out = Path(os.environ.get("DOCK_DEMO_DIR", "demo")) / "calls"
    stem = out / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{role}-{call_id[:16]}"

    def work() -> None:
        time.sleep(delay)
        try:
            fetch_call_files(call_id, stem)
        except Exception:
            log.exception("saving call %s failed", call_id)

    threading.Thread(target=work, daemon=True).start()


def build_agent(run: LiveRun):
    import guava

    desk = LiveDesk(run)
    agent = guava.Agent(
        name="Doc",
        organization="Red Kettle Freight",
        purpose=(
            "Doc is Red Kettle Freight's automated dispatch line for one fictional freight load, LL-88421 (say '8 8 4 2 1'): 18 pallets of citrus from Northwind "
            "Orchards in Fresno to Harbor and Rye Grocery DC, door 4, in Elizabeth, New Jersey. The driver is Luis "
            "Ortega, truck 1841, Red Kettle Freight. The broker is Lantern Lane Logistics. Drivers call after they "
            "have already checked in at the receiving window, to put the check-in time and what the receiver told "
            "them on the record, and later to report a new estimate or the unload start. Dock keeps the timestamped "
            "record and warns the shipper and broker before free time runs out. Dock never gives directions or "
            "tells a driver where to go or park; the receiver does that. Shippers, consignees (the receiving DC), and brokers call to hear the live detention clock. Keep every "
            "answer short. Never invent numbers; use only what Dock's tools return. Callers chase: 'any update?', "
            "'please confirm', 'tell me when it's unloading'. Answer with the current clock every time. A detention "
            "amount is an estimate until the client agrees to it: never call it a bill or an invoice."
            + NAME_NOTE
            + STYLE
        ),
        pronunciations={"LL-88421": "L L 8 8 4 2 1", "Luis": "Loo-EES"},
    )

    @agent.on_call_start
    def on_call_start(call: guava.Call) -> None:
        """We know the caller from caller ID: greet by name and skip 'who is this'. Ask only if the number is unknown."""
        info = getattr(call, "call_info", None)
        number = getattr(info, "from_number", None)
        party = caller_party(run.context, number)
        log.info("caller %s -> %s", number, party["party_id"] if party else "unknown")
        if party:
            call.set_variable("role", party["role"])
            call.read_script(greeting(party["role"]))
            start_role(call, party["role"])
            return
        call.read_script(DISCLOSURE)
        call.set_task(
            "who",
            objective="Find out who's calling about 88421. Don't ask again if they already said.",
            checklist=[
                guava.Field(
                    key="role",
                    field_type="multiple_choice",
                    choices=["driver", "shipper", "consignee", "broker"],
                    description=(
                        "If the caller already said who they are (for example 'Driver. Hi, this is Luis', or a name: "
                        "Luis is the driver, Sam the shipper, Priya the consignee, Alex the broker), fill this in "
                        "without asking."
                    ),
                    question="Who's this, the driver, shipper, receiver, or broker?",
                )
            ],
        )

    @agent.on_question
    def on_question(call: guava.Call, question: str) -> str:
        return answer_question(desk.snapshot(), question)

    def close_call(call: guava.Call, role: str) -> None:
        """One closing line, then hang up. The SDK has no hard hangup, so the final instruction allows nothing
        else; the wrapup task also tells the model not to thank or say goodbye on its own."""
        call.set_variable("closed", True)
        call.hangup(
            f"Your only remaining words are exactly: '{goodbye_line(role)}' Then hang up immediately. "
            "Do not add thanks, 'have a safe trip', or a second goodbye."
        )

    def wrap_up(call: guava.Call, readback: str) -> None:
        """Say the read-back, then ask 'anything else?' and wait for the answer before hanging up."""
        call.set_task(
            "wrapup",
            objective=(
                "Say the line exactly as written; it ends by asking 'Anything else?'. Wait for the answer. "
                "Answer questions with Doc's numbers only, short and casual. Do not give directions. When the caller says there is "
                "nothing else, do not reply, thank, or say goodbye: Doc closes the call with one fixed line."
            ),
            checklist=[
                guava.Say(readback if readback.rstrip().endswith("Anything else?") else readback + " Anything else?"),
                guava.Field(
                    key="anything_else",
                    field_type="text",
                    description="The caller's answer to 'Anything else?'. Write 'no' if nothing else. Do not ask again.",
                ),
            ],
        )

    @agent.on_task_complete("wrapup")
    def on_wrapup(call: guava.Call) -> None:
        close_call(call, call.get_variable("role", "caller"))

    @agent.on_task_complete("who")
    def on_who(call: guava.Call) -> None:
        role = pick_role(call.get_field("role"))
        call.set_variable("role", role)
        log.info("caller role %s", role)
        start_role(call, role)

    def start_role(call: guava.Call, role: str) -> None:
        if role == "driver":
            call.set_task(
                "driver_report",
                objective=(
                    "Capture and confirm the driver's update; nothing more. Do not mention free time, dollars, or rates to "
                    "a driver: he is paid for waiting and does not pay detention. He has already checked in at the receiving window and "
                    "was told to wait; do not give directions. Fill every field you can from what he already said "
                    "and only ask for what is missing. If his first sentence gave the check-in time and what the "
                    "receiver told him, ask nothing and finish right away. Never ask who the clerk was. "
                    "Never say 'one moment' or 'processing'." + STYLE
                ),
                checklist=[
                    guava.Field(
                        key="at",
                        field_type="text",
                        description=(
                            "Clock time it happened, written like 2:06 PM: when he checked in at the receiving "
                            "window, or when the unload started or finished. For still waiting, write now."
                        ),
                        question="What time'd you check in?",
                        required=False,
                    ),
                    guava.Field(
                        key="said",
                        field_type="text",
                        description="What the receiver told him, close to his words, including any time estimate.",
                        question="What'd they tell you, how long?",
                        required=False,
                    ),
                    guava.Field(
                        key="status",
                        field_type="multiple_choice",
                        choices=list(DRIVER_STATUS),
                        description=(
                            "Infer from what he said: checked in and told to wait means 'checked in, waiting for "
                            "a door'. Ask only if it is truly unclear."
                        ),
                        question="Still waiting on a door, or are they unloading you?",
                    ),
                    guava.Field(
                        key="said_by",
                        field_type="text",
                        description=(
                            "Fill ONLY if he already named who told him (e.g. 'Dana', 'the clerk'). Never ask for it; "
                            "leave blank otherwise."
                        ),
                        required=False,
                    ),
                ],
            )
            return
        snap = desk.snapshot()
        if role == "shipper" and not call.get_variable("asked_news", False):
            call.set_variable("asked_news", True)
            call.set_task(
                "shipper_open",
                objective=(
                    "Shipper call. Doc already asked what's up; just listen. If they say what the warehouse or "
                    "receiving told them (door, time, who), write it down. If they're just checking in, write that."
                    + STYLE
                ),
                checklist=[
                    guava.Field(
                        key="news",
                        field_type="text",
                        description="What they said, close to their words, e.g. 'I called the warehouse manager, door 4 in 20 minutes' or 'any update?'.",
                        required=False,
                    )
                ],
            )
            return
        if role == "shipper":
            brief = shipper_brief(snap)
            call.set_variable("heads_up", brief)
            payer = payer_role(snap) == "shipper"
            call.set_task(
                "heads_up",
                objective=(
                    "Shipper call. Read the update exactly, then hear what they'll do. "
                    + ("They pay detention on this load."
                       if payer else "They do not pay detention on this load: status only, no money talk.")
                    + STYLE
                ),
                checklist=[
                    guava.Say(brief),
                    guava.Field(
                        key="plan",
                        field_type="text",
                        description=(
                            "What they will do, or what the warehouse / receiving told them (who said it, door, time), "
                            "close to their words."
                        ),
                        question="What do you want to do?" if payer else "Need anything else on this one?",
                        required=payer,
                    ),
                ],
            )
            return
        if role == "consignee":
            brief = consignee_brief(snap)
            call.set_variable("heads_up", brief)
            call.set_task(
                "consignee",
                objective=(
                    "Receiver call. Read the update exactly (it is what the driver reported). Then take their door "
                    "and unload time, or the time unloading started." + STYLE
                ),
                checklist=[
                    guava.Say(brief),
                    guava.Field(
                        key="door_time",
                        field_type="text",
                        description="Door and the time unloading will start or did start, e.g. 'door 4 at 2:50 PM' or 'started at 4:48'.",
                        question="What door, and when do you think you'll get him in? Or is he in already?",
                    ),
                ],
            )
            return
        call.set_task(
            "broker",
            objective="Broker call. Read the update exactly: status, exposure, and that the carrier bills off the timestamps." + STYLE,
            checklist=[
                guava.Say(broker_brief(snap)),
                guava.Field(
                    key="anything_else",
                    field_type="text",
                    question="Want me to send you the timestamps?",
                    required=False,
                ),
            ],
        )

    @agent.on_task_complete("driver_report")
    def on_driver(call: guava.Call) -> None:
        """Speak from the local clock first (no desk write on this path), then post to the desk in the background.
        6:16 PM call: the desk POST raised 403 inside this handler, so the read-back was never sent."""
        status = pick_status(call.get_field("status"))
        said = str(call.get_field("said") or "")
        readback = None
        try:
            zone = run.context["load"].get("timezone", "America/New_York")
            at = parse_clock(call.get_field("at"), run.now(), zone)
            events, record, base, now = build_driver_events(
                run,
                status,
                at=at,
                said_by=str(call.get_field("said_by") or ""),
                said=said,
                estimate_minutes=parse_minutes(said),
            )
            snap = local_snapshot(run.context, [*base, *events], now)
            readback = driver_readback(snap, record.get("status", status), record)
            if record.get("status", status) in ("arrived", "waiting"):
                events = [*events, *queue_notices(run.context, snap, now, after=events[-1].event_id)]
            post_later(run, events, "driver")
            log.info("driver read-back ready: %s", [e.type for e in events])
        except Exception:
            log.exception("driver path failed; speaking a fallback read-back")
        if not readback:
            readback = spoken(
                "Got it, Luis. Call me when they pull you in. Anything else?"
            )
        wrap_up(call, readback)

    @agent.on_task_complete("consignee")
    def on_consignee(call: guava.Call) -> None:
        answer = str(call.get_field("door_time") or "")
        zone = run.context["load"].get("timezone", "America/New_York")
        post_later(run, [], "consignee", write=lambda _e: log_receiver(run, answer, zone))
        wrap_up(call, spoken("Got it, thanks. Anything else?"))

    @agent.on_task_complete("heads_up")
    def on_heads_up(call: guava.Call) -> None:
        role = call.get_variable("role", "shipper")
        to_role = "shipper" if role == "shipper" else "consignee"
        snap = desk.snapshot()
        body = call.get_variable("heads_up", snap["heads_up"][to_role])
        plan = str(call.get_field("plan") or "")
        promise = receiver_promise(run.context, plan, run.now(), via_role=to_role) if plan else None
        if promise:
            now = run.now()
            post_later(run, promise_events(run.context, promise, now), f"{to_role} promise")
            wrap_up(call, promise_readback(promise))
            return
        post_later(
            run,
            [],
            to_role,
            write=lambda _events: run.heads_up_by_voice(
                call_id=str(call.id), to_role=to_role, body=body, reply=plan, summary=snap["summary"]
            ),
        )
        wrap_up(call, "Sounds good. Anything else?")

    @agent.on_task_complete("shipper_open")
    def on_shipper_open(call: guava.Call) -> None:
        """'I called the warehouse manager, door 4 in 20' -> receiver promise. Anything else -> the heads-up."""
        news = str(call.get_field("news") or "")
        promise = receiver_promise(run.context, news, run.now(), via_role="shipper") if news else None
        if promise:
            post_later(run, promise_events(run.context, promise, run.now()), "shipper promise")
            wrap_up(call, promise_readback(promise))
            return
        start_role(call, "shipper")

    @agent.on_session_end
    def on_session_end(call: guava.Call, ended) -> None:
        log.info("call %s ended: %s", call.id, getattr(ended, "termination_reason", ended))
        save_call_later(str(call.id), getattr(call, "get_variable", lambda *_: None)("role", None) or "caller")

    @agent.on_task_complete("broker")
    def on_broker(call: guava.Call) -> None:
        close_call(call, "broker")

    return agent
