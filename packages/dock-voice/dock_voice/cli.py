"""dock-voice serve | chat | roleplay <driver|shipper|broker>

serve     safe inbound adapter; requires DOCK_INBOUND_MODE=live
chat      legacy simulation text chat in the terminal (hosted Guava session)
roleplay  legacy simulation; an LLM plays the caller and logs simulated events
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
        "that you have arrived and are waiting, and that the door is occupied. One short sentence per turn. Do not hang up until the agent says goodbye."
    ),
    "shipper": (
        "You are Sam Okonkwo at Northwind Orchards, the shipper on load LL-88421. Answer only what the agent asks, "
        "one short sentence per turn. When asked who you are, say only that you're the shipper. Listen to the "
        "heads-up. When asked what you'll do, say you will call Harbor and Rye now and push them to start the "
        "unload within 20 minutes. Do not hang up until the agent says goodbye."
    ),
    "consignee": (
        "You are Priya Shah at Harbor and Rye Grocery DC, the consignee on load LL-88421. Answer only what the agent "
        "asks, one short sentence per turn. When asked who you are, say you're the consignee. Listen to the heads-up. "
        "When asked what you'll do, say door 4 is still occupied and you can start the unload in about 40 minutes. "
        "Do not hang up until the agent says goodbye."
    ),
    "broker": (
        "You are Alex Kim at Lantern Lane Logistics, the broker on load LL-88421. Say you're the broker and ask "
        "what the trail supports. Answer one short sentence per turn. Say no thanks to anything else. Do not hang up until the agent says goodbye."
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

    if args.cmd == "serve":
        # Route before importing Guava or constructing the legacy simulation.
        from dock_intake.inbound_cli import main as inbound_main

        root = _root()
        return inbound_main([
            "phone", "--root", str(root),
            "--log", os.environ.get("DOCK_INBOUND_LOG", str(root / "data/runtime/inbound-demo.jsonl")),
            "--as-of", os.environ.get("DOCK_INBOUND_AS_OF", "2026-10-17T19:36:00Z"),
        ])

    print("dock-voice: legacy simulation; this is not the persisted inbound demo.", file=sys.stderr)
    from guava import logging_utils

    from dock_web.live import LiveRun
    from dock_voice.agent import build_agent

    run = LiveRun(_root())
    agent = build_agent(run)
    logging_utils.configure_logging()
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
