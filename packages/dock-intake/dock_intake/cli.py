"""dock-intake: one JSON object per line in, Dock events out."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dock_events.context import load_context
from dock_events.model import dump_jsonl

from dock_intake.normalize import normalize_message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dock-intake",
        description="Normalize driver SMS or voice text into Dock events.",
    )
    parser.add_argument("--context", required=True, help="Path to parties JSON.")
    args = parser.parse_args(argv)
    try:
        context = load_context(Path(args.context))
        events = []
        for number, raw in enumerate(sys.stdin.read().splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {number}: {exc.msg}") from exc
            events.extend(
                normalize_message(
                    message["text"],
                    load_id=message["load_id"],
                    party_id=message["party_id"],
                    role=message["role"],
                    channel=message["channel"],
                    occurred_at=message["occurred_at"],
                    context=context,
                    recorded_at=message.get("recorded_at"),
                )
            )
    except (ValueError, KeyError, OSError) as exc:
        print(f"dock-intake: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(dump_jsonl(events))
    return 0
