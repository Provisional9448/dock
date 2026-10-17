"""dock-events: validate, print, and append the shared log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dock_events.log import EventLog
from dock_events.model import dump_jsonl, load_jsonl
from dock_events.schema_doc import SCHEMA


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dock-events", description="Validate and store Dock events.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    validate = sub.add_parser("validate", help="Read JSONL on stdin. Exit 1 if any line is invalid.")
    validate.set_defaults(func=_validate)

    cat = sub.add_parser("cat", help="Print a log file to stdout.")
    cat.add_argument("path")
    cat.set_defaults(func=_cat)

    append = sub.add_parser("append", help="Append stdin JSONL to a log. Duplicate ids are skipped.")
    append.add_argument("path")
    append.set_defaults(func=_append)

    schema = sub.add_parser("schema", help="Print the event JSON Schema.")
    schema.set_defaults(func=_schema)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"dock-events: {exc}", file=sys.stderr)
        return 1


def _validate(_args: argparse.Namespace) -> int:
    events = load_jsonl(sys.stdin.read())
    sys.stdout.write(dump_jsonl(events))
    print(f"dock-events: {len(events)} valid", file=sys.stderr)
    return 0


def _cat(args: argparse.Namespace) -> int:
    events = EventLog(Path(args.path)).read()
    sys.stdout.write(dump_jsonl(events))
    return 0


def _append(args: argparse.Namespace) -> int:
    events = load_jsonl(sys.stdin.read())
    result = EventLog(Path(args.path)).append(events)
    if result.skipped_ids:
        print(
            "dock-events: skipped duplicate " + ", ".join(result.skipped_ids),
            file=sys.stderr,
        )
    print(f"dock-events: appended {len(result.appended)}", file=sys.stderr)
    sys.stdout.write(dump_jsonl(result.appended))
    return 0


def _schema(_args: argparse.Namespace) -> int:
    json.dump(SCHEMA, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0
