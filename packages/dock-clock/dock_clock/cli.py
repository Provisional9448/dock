"""dock-clock: events in, events plus charge risk out."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from decimal import Decimal

from dock_events.model import dump_jsonl, load_jsonl
from dock_events.timeutil import parse_time

from dock_clock.policy import DetentionPolicy
from dock_clock.tick import replay_clock, tick


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dock-clock",
        description="Read events on stdin. Write them back with clock_started and charge_risk appended.",
    )
    parser.add_argument("--as-of", required=True, help="UTC timestamp the clock is evaluated at.")
    parser.add_argument("--free-minutes", type=int, default=120)
    parser.add_argument("--warn-minutes", type=int, default=30)
    parser.add_argument("--rate-usd-per-hour", default="75.00")
    parser.add_argument("--increment-minutes", type=int, default=15)
    parser.add_argument("--stop-on", choices=("unload_started", "unload_done"), default="unload_started")
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Emit the warning, mid-accrual, and stop checkpoints up through --as-of.",
    )
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (ValueError, OSError) as exc:
        print(f"dock-clock: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    events = load_jsonl(sys.stdin.read())
    as_of = parse_time(args.as_of)
    policy = DetentionPolicy(
        free_minutes=args.free_minutes,
        warn_minutes=args.warn_minutes,
        rate_usd_per_hour=Decimal(args.rate_usd_per_hour),
        increment_minutes=args.increment_minutes,
        stop_on=args.stop_on,
    )
    if args.replay:
        produced = replay_clock(events, as_of=as_of, policy=policy)
        held = len(events) - sum(1 for event in events if parse_time(event.occurred_at) <= as_of)
    else:
        produced = [event for event in events if parse_time(event.occurred_at) <= as_of]
        produced.extend(tick(produced, as_of=as_of, policy=policy))
        held = len(events) - len([event for event in events if parse_time(event.occurred_at) <= as_of])
    if held:
        print(f"dock-clock: held back {held} events after as-of", file=sys.stderr)
    sys.stdout.write(dump_jsonl(produced))
    return 0


def parse_as_of(value: str) -> datetime:
    return parse_time(value)
