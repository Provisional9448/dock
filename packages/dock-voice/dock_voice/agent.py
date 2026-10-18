"""The Guava agent. One inbound number; the caller picks a role.

- Driver: arrival / delay / unload -> events appended to the shared log; dock-clock runs on read.
- Shipper or receiver: the outbound heads-up, delivered inbound. Dock reads the clock now and speaks it;
  logs notice_sent (channel voice) and call_result.
- Broker: the clock and what the trail supports.

Every handler reads LiveDesk.snapshot() at the moment it runs, so the numbers are live mid-call.
"""

from __future__ import annotations

import logging

from dock_web.live import LiveDesk, LiveRun

from dock_voice.script import DRIVER_STATUS, answer_question, driver_reply, pick_role, pick_status

log = logging.getLogger("dock-voice")

DISCLOSURE = "Hi, this is Dock, an automated AI assistant for detention on load L L 8 8 4 2 1. This call may be recorded for the load trail."


def save_call_later(call_id: str, role: str, delay: float = 15.0) -> None:
    """Pull the transcript and WAV for a finished call into demo/calls/ (for the video). Best effort."""
    import os
    import shutil
    import subprocess
    import threading
    import time
    from datetime import datetime
    from pathlib import Path

    out = Path(os.environ.get("DOCK_DEMO_DIR", "demo")) / "calls"
    cli = shutil.which("guava") or os.path.expanduser("~/.local/bin/guava")

    def work() -> None:
        time.sleep(delay)
        out.mkdir(parents=True, exist_ok=True)
        stem = out / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{role}-{call_id[:16]}"
        for attempt in range(6):
            text = subprocess.run([cli, "conversations", "transcript", call_id], capture_output=True, text=True)
            if text.returncode == 0 and text.stdout.strip():
                stem.with_suffix(".txt").write_text(text.stdout, encoding="utf-8")
                break
            time.sleep(10)
        subprocess.run([cli, "conversations", "recording", call_id, "-o", str(stem.with_suffix(".wav"))], capture_output=True)
        log.info("saved call %s to %s.*", call_id, stem)

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
            "Ortega, truck 1841, Red Kettle Freight. The broker is Lantern Lane Logistics. Drivers call to check in "
            "and report delays. Shippers, consignees (the receiving DC), and brokers call to hear the live detention clock. Keep every "
            "answer short. Never invent numbers; use only what Dock's tools return. Callers chase: 'any update?', "
            "'please confirm', 'tell me when it's unloading'. Answer with the current clock every time. A detention "
            "amount is an estimate until the client agrees to it: never call it a bill or an invoice."
        ),
        pronunciations={"LL-88421": "L L 8 8 4 2 1"},
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
                    question="Are you the driver, the shipper, the consignee (the receiving DC), or the broker?",
                )
            ],
        )

    @agent.on_question
    def on_question(call: guava.Call, question: str) -> str:
        return answer_question(desk.snapshot(), question)

    @agent.on_task_complete("who")
    def on_who(call: guava.Call) -> None:
        role = pick_role(call.get_field("role"))
        call.set_variable("role", role)
        log.info("caller role %s", role)
        if role == "driver":
            call.set_task(
                "driver_report",
                objective="Log what the driver is seeing at the dock. Be quick; he is in the cab.",
                checklist=[
                    guava.Field(
                        key="status",
                        field_type="multiple_choice",
                        choices=list(DRIVER_STATUS),
                        question="Are you checking in and waiting, still waiting, or has the unload started or finished?",
                    ),
                    guava.Field(
                        key="detail",
                        field_type="text",
                        question="What is holding you up, for example the door is occupied? Skip this if the unload started.",
                        required=False,
                    ),
                ],
            )
            return
        snap = desk.snapshot()
        if role in ("shipper", "consignee"):
            heads_up = snap["heads_up"]["shipper" if role == "shipper" else "consignee"]
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
                guava.Say(snap["heads_up"]["broker"] + " " + snap["summary"]["detail"]),
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
        status = pick_status(call.get_field("status"))
        detail = str(call.get_field("detail") or "")
        try:
            events = run.driver_status(status, detail=detail, channel="voice")
            log.info("driver logged %s", [e.type for e in events])
        except ValueError as exc:
            log.warning("driver report rejected: %s", exc)
        call.hangup(driver_reply(desk.snapshot(), status))

    @agent.on_task_complete("heads_up")
    def on_heads_up(call: guava.Call) -> None:
        role = call.get_variable("role", "shipper")
        to_role = "shipper" if role == "shipper" else "consignee"
        snap = desk.snapshot()
        body = call.get_variable("heads_up", snap["heads_up"][to_role])
        plan = str(call.get_field("plan") or "")
        run.heads_up_by_voice(call_id=str(call.id), to_role=to_role, body=body, reply=plan, summary=snap["summary"])
        call.hangup("Thank them. Say the heads-up and their answer are on the load trail with a timestamp. Say goodbye.")

    @agent.on_session_end
    def on_session_end(call: guava.Call, ended) -> None:
        log.info("call %s ended: %s", call.id, getattr(ended, "termination_reason", ended))
        save_call_later(str(call.id), getattr(call, "get_variable", lambda *_: None)("role", None) or "caller")

    @agent.on_task_complete("broker")
    def on_broker(call: guava.Call) -> None:
        call.hangup("Say the proof pack is on the broker desk, it is not an invoice, and goodbye.")

    return agent
