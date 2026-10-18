"""dock-voice serve | chat | roleplay <driver|driver-update|shipper|consignee|broker>

serve     listen on GUAVA_AGENT_NUMBER (inbound only; outbound is never dialed)
chat      text chat with the agent in the terminal (no phone)
roleplay  an LLM plays the caller; prints the transcript and the events it logged
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROLEPLAYS = {
    "driver": (
        "Open with exactly: 'Driver. Hi, this is Luis with Red Kettle Freight, load LL-88421. I checked in at the Harbor and Rye receiving window at 2:06, and Dana the clerk told me to wait in my truck, maybe 40 minutes.' You are Luis Ortega, a truck driver for Red Kettle Freight, truck 1841, on load LL-88421 at Harbor and Rye "
        "Grocery DC. You checked in at the receiving window at 2:06 PM. Dana at the window said no doors are open, "
        "wait in your truck, they'll call you, maybe 40 minutes. You are calling Dock so your check-in time and what "
        "they told you are on the record. You do not need directions. Say you're the driver. When asked, say you "
        "checked in at 2:06, Dana at receiving told you, and what she said. One short sentence per turn. Do not "
        "hang up until the agent says goodbye."
    ),
    "driver-update": (
        "You are Luis Ortega, the driver on load LL-88421, calling Dock back. You are still waiting at Harbor and "
        "Rye. Dana at receiving just said another 20 minutes. Say you're the driver, that you're still waiting, "
        "and what Dana said. One short sentence per turn. When asked if there is anything else, say no, that is it. Do not hang up until the agent says goodbye."
    ),
    "shipper": (
        "You are Sam Okonkwo at Northwind Orchards, the shipper on load LL-88421; on this load the shipper pays "
        "detention. Answer one short sentence per turn. When asked who you are, say you're the shipper. Listen. "
        "When asked what you'll do, say you'll call Harbor and Rye now and push them to start unloading within 20 "
        "minutes. When asked if there is anything else, say no, that is it. Do not hang up until the agent says goodbye."
    ),
    "consignee": (
        "You are Priya Shah at Harbor and Rye Grocery DC, the consignee on load LL-88421. One short sentence per "
        "turn. When asked who you are, say you're the receiver. Listen. When asked for a door and time, say door 4, "
        "you'll start unloading at 2:50. When asked if there is anything else, say no. Do not hang up until the agent says goodbye."
    ),
    "broker": (
        "You are Alex Kim at Lantern Lane Logistics, the broker on load LL-88421. Say you're the broker and ask "
        "where the load stands for your customer. One short sentence per turn. Say yes to the record. When asked "
        "if there is anything else, say no. Do not hang up until the agent says goodbye."
    ),
}


def _root() -> Path:
    from dock_web.cli import _repo_root

    return _repo_root()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dock-voice")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sub.add_parser("chat")
    rp = sub.add_parser("roleplay")
    rp.add_argument("who", choices=sorted(ROLEPLAYS))
    args = parser.parse_args(argv)

    from guava import logging_utils

    from dock_web.live import LiveRun
    from dock_voice.agent import build_agent

    run = LiveRun(_root())
    agent = build_agent(run)
    logging_utils.configure_logging()
    if args.cmd == "serve":
        number = os.environ.get("GUAVA_AGENT_NUMBER")
        if not number:
            print("dock-voice: set GUAVA_AGENT_NUMBER (see `guava numbers list`)", file=sys.stderr)
            return 2
        print(f"dock-voice: listening on {number}. Inbound only.", file=sys.stderr, flush=True)
        agent.listen_phone(number)
        return 0
    if args.cmd == "chat":
        agent.chat()
        return 0
    before = {event.event_id for event in run.read()}
    session = agent.roleplay(ROLEPLAYS[args.who])
    print(session.get_transcript())
    print("--- events logged ---")
    for event in run.read():
        if event.event_id not in before:
            print(event.type, event.occurred_at, event.payload.get("detail") or event.payload.get("summary") or "")
    print("termination:", session.termination_reason)
    return 0
