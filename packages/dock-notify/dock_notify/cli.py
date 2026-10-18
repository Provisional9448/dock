"""dock-notify: pass events through and append notice_sent lines."""

from __future__ import annotations

import argparse
import sys

from dock_events.model import dump_jsonl, load_jsonl

from dock_notify.compose import apply_notices
from dock_notify.provider import provider_from_env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dock-notify",
        description=(
            "Append notice_sent for each charge_risk. "
            "The body is the SMS. The voice field is the spoken script. "
            "The default provider only logs."
        ),
    )
    parser.add_argument(
        "--audiences",
        default="",
        help="Comma-separated roles. Default: the load's payer (shipper or consignee) plus the broker.",
    )
    args = parser.parse_args(argv)
    try:
        events = load_jsonl(sys.stdin.read())
        audiences = tuple(part.strip() for part in args.audiences.split(",") if part.strip()) or None
        produced = apply_notices(events, audiences=audiences, provider=provider_from_env())
    except (ValueError, OSError) as exc:
        print(f"dock-notify: {exc}", file=sys.stderr)
        return 1
    added = len(produced) - len(events)
    print(f"dock-notify: composed {added} heads-up events", file=sys.stderr)
    sys.stdout.write(dump_jsonl(produced))
    return 0
