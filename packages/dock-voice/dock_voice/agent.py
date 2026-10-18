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

from dock_voice.record import build_driver_events, local_snapshot, post_later
from dock_voice.script import (
    DRIVER_STATUS,
    answer_question,
    driver_readback,
    parse_clock,
    parse_minutes,
    pick_role,
    goodbye_line,
    pick_status,
    spoken,
)

NAME_NOTE = (
    " The driver's name is Luis (said 'loo-EES'). If you hear Louise, Lewis, Louis or Luiz, it is Luis; call him Luis."
    " Say clock times like '2:06 PM Eastern', never 'ET' and never with a leading zero."
    " After the driver answers, do not say 'one moment' or 'processing'; Dock's read-back comes right away."
)

log = logging.getLogger("dock-voice")

DISCLOSURE = "Hi, this is Dock, an automated AI assistant for detention on load L L 8 8 4 2 1. This call may be recorded for the load trail."


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
        name="Dock",
        organization="Dock",
        purpose=(
            "Dock is a detention desk for one fictional freight load, LL-88421: 18 pallets of citrus from Northwind "
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
        ),
        pronunciations={"LL-88421": "L L 8 8 4 2 1", "Luis": "Loo-EES"},
    )

    @agent.on_call_start
    def on_call_start(call: guava.Call) -> None:
        call.read_script(DISCLOSURE)
        call.set_task(
            "who",
            objective="Find out who is calling about load LL-88421.",
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
                    question="Are you the driver, the shipper, the consignee (the receiving DC), or the broker?",
                )
            ],
        )

    @agent.on_question
    def on_question(call: guava.Call, question: str) -> str:
        return answer_question(desk.snapshot(), question)

    def wrap_up(call: guava.Call, readback: str) -> None:
        """Say the read-back, then ask 'anything else?' and wait for the answer before hanging up."""
        call.set_task(
            "wrapup",
            objective=(
                "Read the record back exactly as written, then ask if there is anything else and wait for the "
                "answer. Answer questions with Dock's numbers only. Do not give directions."
            ),
            checklist=[
                guava.Say(readback),
                guava.Field(
                    key="anything_else",
                    field_type="text",
                    description="The caller's answer. Write 'no' if there is nothing else.",
                    question="Anything else?",
                ),
            ],
        )

    @agent.on_task_complete("wrapup")
    def on_wrapup(call: guava.Call) -> None:
        role = call.get_variable("role", "caller")
        call.hangup(
            f"Say exactly this once and nothing after it: '{goodbye_line(role)}' Do not say goodbye again. "
            "The driver's name is Luis, never Louise."
        )

    @agent.on_task_complete("who")
    def on_who(call: guava.Call) -> None:
        role = pick_role(call.get_field("role"))
        call.set_variable("role", role)
        log.info("caller role %s", role)
        if role == "driver":
            call.set_task(
                "driver_report",
                objective=(
                    "Put the driver's wait on the record. He has already checked in at the receiving window and "
                    "was told to wait; do not give directions. Get the time, who at the receiver told him what, "
                    "and their time estimate. For an unload start or finish, only the time is needed; skip the rest. "
                    "Be quick; he is in the cab."
                ),
                checklist=[
                    guava.Field(
                        key="status",
                        field_type="multiple_choice",
                        choices=list(DRIVER_STATUS),
                        question="Are you checked in and waiting for a door, still waiting, or has the unload started or finished?",
                    ),
                    guava.Field(
                        key="at",
                        field_type="text",
                        description=(
                            "Clock time it happened, written like 2:06 PM: when he checked in at the receiving "
                            "window, or when the unload started or finished. For still waiting, write now."
                        ),
                        question="What time did you check in at the receiving window? Or, what time did the unload start?",
                        required=False,
                    ),
                    guava.Field(
                        key="said_by",
                        field_type="text",
                        description="Who at the receiver told him, name or role, like 'Dana at the receiving window'.",
                        question="Who told you to wait?",
                        required=False,
                    ),
                    guava.Field(
                        key="said",
                        field_type="text",
                        description="What the receiver told him, close to their words, including any time estimate.",
                        question="What did they tell you, and how long did they say?",
                        required=False,
                    ),
                ],
            )
            return
        snap = desk.snapshot()
        if role in ("shipper", "consignee"):
            heads_up = snap["heads_up"]["shipper" if role == "shipper" else "consignee"]
            if snap["summary"]["phase"] in ("running", "warning"):
                rate = snap["policy"]
                heads_up += (
                    f" No charges yet; detention is ${str(rate['rate_usd_per_hour']).removesuffix('.00')} an hour after "
                    f"{snap['summary']['free_time_ends_local']}, in {rate['increment_minutes']}-minute steps."
                )
            heads_up = spoken(heads_up)
            call.set_variable("heads_up", heads_up)
            call.set_task(
                "heads_up",
                objective=(
                    "Deliver the detention heads-up that Dock would have placed as an outbound call, then ask "
                    "what they will do and when."
                ),
                checklist=[
                    guava.Say(heads_up),
                    guava.Field(
                        key="plan",
                        field_type="text",
                        question="What can you do to get the unload started, and by when?",
                    ),
                ],
            )
            return
        call.set_task(
            "broker",
            objective="Give the broker the clock and what the trail supports.",
            checklist=[
                guava.Say(spoken(snap["heads_up"]["broker"] + " " + snap["summary"]["detail"])),
                guava.Field(
                    key="anything_else",
                    field_type="text",
                    question="Do you want the proof pack sent to the broker desk?",
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
            post_later(run, events, "driver")
            snap = local_snapshot(run.context, [*base, *events], now)
            readback = driver_readback(snap, record.get("status", status), record)
            log.info("driver read-back ready: %s", [e.type for e in events])
        except Exception:
            log.exception("driver path failed; speaking a fallback read-back")
        if not readback:
            readback = spoken(
                "Thanks, Luis. I have your check-in and what the receiver told you. Free time is two hours from "
                "your check-in, then detention is $75 an hour in 15-minute steps. Dock will warn the shipper and the broker."
            )
        wrap_up(call, readback)

    @agent.on_task_complete("heads_up")
    def on_heads_up(call: guava.Call) -> None:
        role = call.get_variable("role", "shipper")
        to_role = "shipper" if role == "shipper" else "consignee"
        snap = desk.snapshot()
        body = call.get_variable("heads_up", snap["heads_up"][to_role])
        plan = str(call.get_field("plan") or "")
        post_later(
            run,
            [],
            to_role,
            write=lambda _events: run.heads_up_by_voice(
                call_id=str(call.id), to_role=to_role, body=body, reply=plan, summary=snap["summary"]
            ),
        )
        wrap_up(call, "Thanks. The heads-up and your answer are on the load record with a timestamp.")

    @agent.on_session_end
    def on_session_end(call: guava.Call, ended) -> None:
        log.info("call %s ended: %s", call.id, getattr(ended, "termination_reason", ended))
        save_call_later(str(call.id), getattr(call, "get_variable", lambda *_: None)("role", None) or "caller")

    @agent.on_task_complete("broker")
    def on_broker(call: guava.Call) -> None:
        call.hangup("Say the proof pack is on the broker desk, it is not an invoice, and goodbye.")

    return agent
