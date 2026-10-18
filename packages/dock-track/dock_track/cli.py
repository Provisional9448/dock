"""dock-track: a tracking ask on stdin, a tracking_requested event on the log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dock_events.model import dump_jsonl, event_from_dict

from dock_track.parse import parse_request
from dock_track.watch import watch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dock-track",
        description="Read a free-text tracking request and append tracking_requested.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("parse", help="Print the structured request as one JSON object.")
    watch_parser = sub.add_parser("watch", help="Append tracking_requested to a JSONL log.")
    watch_parser.add_argument("--load", required=True, help="Load id, such as LL-88421.")
    watch_parser.add_argument("--log", required=True, help="JSONL file to append.")
    watch_parser.add_argument("--at", default=None, help="occurred_at, UTC with a trailing Z.")
    watch_parser.add_argument("--role", default=None)
    watch_parser.add_argument("--party-id", default="pty_requester")
    watch_parser.add_argument("--channel", default="sms")
    args = parser.parse_args(argv)
    text = sys.stdin.read()
    try:
        if args.cmd == "parse":
            sys.stdout.write(json.dumps(parse_request(text).to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            return 0
        event = watch(
            args.load,
            Path(args.log),
            text=text,
            occurred_at=args.at,
            role=args.role,
            party_id=args.party_id,
            channel=args.channel,
        )
        event_from_dict(event.to_dict())
    except (ValueError, OSError) as exc:
        print(f"dock-track: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(dump_jsonl([event]))
    return 0
