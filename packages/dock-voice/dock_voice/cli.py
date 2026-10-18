"""dock-voice serve | chat | roleplay <driver|driver-update|shipper|shipper-callback|consignee|broker>

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
    # Doc knows the caller from caller ID (parties.json caller_ids; DOCK_CALLER_ROLE picks the role for a take),
    # so callers don't say their role; Doc greets them by name.
    "driver": (
        "You are Luis Ortega, a truck driver for Red Kettle Freight, truck 1841, on load 88421 at Harbor and Rye "
        "Grocery DC. When Doc asks how it's going, say: 'Checked in at the receiving window at 2:06. "
        "Dana said no doors, wait in the truck, maybe 40 minutes.' You do not need directions. One short sentence "
        "per turn. When asked if there is anything else, say no, that's it. Do not hang up until Doc says bye."
    ),
    "driver-update": (
        "You are Luis Ortega, the driver on load 88421, calling Doc back. When Doc asks how it's going, say: "
        "'Still waiting. Dana says another 20.' One short sentence per turn. When asked if there is anything else, "
        "say no, that's it. Do not hang up until Doc says bye."
    ),
    "shipper": (
        "You are Dan Okonkwo at Northwind Orchards, the shipper on load 88421; on this load the shipper pays "
        "detention. When Doc asks what it can do for you, say: 'Any update on my load?' Listen. When asked what you want to do, "
        "say you'll call Harbor and Rye receiving now. When asked if there is anything else, say no, that's it. "
        "Do not hang up until Doc says bye."
    ),
    "shipper-callback": (
        "You are Dan Okonkwo at Northwind Orchards, the shipper on load 88421, calling Doc back. When Doc asks "
        "what's up, say: 'I called the warehouse manager at Harbor and Rye; they'll have him in door 4 in 20 "
        "minutes.' When asked if there is anything else, say no, that's it. Do not hang up until Doc says bye."
    ),
    "consignee": (
        "You are Priya Shah at Harbor and Rye Grocery DC, the receiver on load 88421. One short sentence per turn. "
        "Listen. When asked for a door and time, say door 4, you'll get him in at 2:50. When asked if there is "
        "anything else, say no. Do not hang up until Doc says bye."
    ),
    "broker": (
        "You are Alex Kim at Lantern Lane Logistics, the broker on load 88421. When Doc asks what it can do for you, ask where "
        "the load stands. One short sentence per turn. Say yes to the timestamps. When asked if there is anything "
        "else, say no. Do not hang up until Doc says bye."
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
