"""dock-live: drive the live desk from a terminal. Same files the web and the voice line use.

  dock-live reset                 new run, clock at 2:04 PM ET, old log archived
  dock-live status                one line: clock, stamp, headline
  dock-live jump warning|accruing|plus15|+MIN
  dock-live driver "They started unloading."
  dock-live replay [--pause 4]    scripted scenario for the video (no phone needed)
"""

from __future__ import annotations

import argparse
import time
from datetime import timedelta

from dock_events.timeutil import parse_time
from dock_web.live import LiveDesk, LiveRun


def _status(desk: LiveDesk) -> str:
    snap = desk.snapshot()
    s = snap["summary"]
    return f"{snap['clock_local']}  {s['stamp']}  {s['headline']}  (${s['estimated_charge_usd']})"


def replay(run: LiveRun, pause: float = 4.0, say=print) -> None:
    desk = LiveDesk(run)
    run.reset()

    def beat(text: str) -> None:
        say(f"[{_status(desk)}] {text}")
        time.sleep(pause)

    beat("New run. Waiting for the driver.")
    run.set_now(parse_time("2026-10-17T18:06:00Z"))
    run.driver_status("arrived", detail="Door 4 is occupied. They are not ready to unload.", channel="voice")
    beat("Driver call: Luis checked in at door 4; door occupied. Clock started.")
    desk.jump_preset("warning")
    beat("30 minutes of free time left. dock-notify composed the heads-ups.")
    snap = desk.snapshot()
    run.heads_up_by_voice(
        call_id="replay-sam",
        to_role="shipper",
        body=snap["heads_up"]["shipper"],
        reply="Sam said he will call Harbor and Rye now and push for an unload within 20 minutes.",
        summary=snap["summary"],
    )
    beat("Shipper call-in (the outbound heads-up, shown inbound): Sam heard it and committed.")
    run.advance(4)
    snap = desk.snapshot()
    run.heads_up_by_voice(
        call_id="replay-priya",
        to_role="consignee",
        body=snap["heads_up"]["consignee"],
        reply="Priya said door 4 is still occupied and they can start in about 40 minutes.",
        summary=snap["summary"],
    )
    beat("Consignee call-in: Priya asked for about 40 minutes.")
    desk.jump_preset("accruing")
    beat("15 minutes past free time. Accruing.")
    run.advance(27)
    run.driver_report("They started unloading.", channel="sms")
    beat("Driver SMS: unload started. Clock stopped.")
    say(f"[{_status(desk)}] Done. Open the Broker column for the proof pack.")


def main(argv: list[str] | None = None) -> int:
    from dock_web.cli import _repo_root

    parser = argparse.ArgumentParser(prog="dock-live")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("reset")
    sub.add_parser("status")
    j = sub.add_parser("jump")
    j.add_argument("to")
    d = sub.add_parser("driver")
    d.add_argument("text")
    r = sub.add_parser("replay")
    r.add_argument("--pause", type=float, default=4.0)
    args = parser.parse_args(argv)
    run = LiveRun(_repo_root())
    desk = LiveDesk(run)
    if args.cmd == "reset":
        desk.reset()
    elif args.cmd == "jump":
        if args.to.startswith("+"):
            run.advance(float(args.to[1:]))
        else:
            desk.jump_preset(args.to)
    elif args.cmd == "driver":
        desk.report_driver(args.text)
    elif args.cmd == "replay":
        replay(run, pause=args.pause)
        return 0
    print(_status(desk))
    return 0
