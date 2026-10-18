"""dock-voice serve | chat | roleplay <driver|shipper|broker>

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
        "You are Luis Ortega, a truck driver for Red Kettle Freight, truck 1841, on load LL-88421. You just arrived at "
        "Harbor and Rye door 4 and they are not ready to unload because the door is occupied. Say you're the driver, "
        "that you have arrived and are waiting, and that the door is occupied. Hang up once the agent confirms."
    ),
    "shipper": (
        "You are Sam Okonkwo at Northwind Orchards, the shipper on load LL-88421. You're calling to check on your "
        "load. Say you're the shipper. Listen to the heads-up. Ask how much it is so far. Then say you will call "
        "Harbor and Rye now and push them to start the unload within 20 minutes. Hang up once the agent wraps up."
    ),
    "broker": (
        "You are Alex Kim at Lantern Lane Logistics, the broker on load LL-88421. Say you're the broker and ask "
        "what the trail supports. Say no thanks to anything else and hang up."
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
