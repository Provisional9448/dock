"""dock-call: plan on stdout, or pass events through with a dry-run call_result."""

from __future__ import annotations

import argparse
import json
import sys

from dock_events.model import dump_jsonl, load_jsonl

from dock_call.plan import GOALS, build_plan, simulate_result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dock-call", description="Plan a scripted outbound call.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    goals = sub.add_parser("goals", help="List goal ids.")
    goals.set_defaults(func=_goals)

    plan = sub.add_parser("plan", help="Read events on stdin. Write a call plan as JSON.")
    plan.add_argument("--goal", default="receiver_delay")
    plan.set_defaults(func=_plan)

    simulate = sub.add_parser("simulate", help="Pass events through and append a dry-run call_result.")
    simulate.add_argument("--goal", default="receiver_delay")
    simulate.add_argument("--as-of", required=True)
    simulate.set_defaults(func=_simulate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"dock-call: {exc}", file=sys.stderr)
        return 1


def _goals(_args: argparse.Namespace) -> int:
    for goal_id in GOALS:
        print(goal_id)
    return 0


def _plan(args: argparse.Namespace) -> int:
    plan = build_plan(load_jsonl(sys.stdin.read()), args.goal)
    json.dump(plan, sys.stdout, indent=2)
    sys.stdout.write("\n")
    print("dock-call: plan only, no call placed", file=sys.stderr)
    return 0


def _simulate(args: argparse.Namespace) -> int:
    events = load_jsonl(sys.stdin.read())
    plan = build_plan(events, args.goal)
    load_id = plan["variables"]["load_id"]
    arrived = next(event for event in events if event.type == "arrived" and event.load_id == load_id)
    result = simulate_result(
        plan,
        load_id=load_id,
        occurred_at=args.as_of,
        to_party_id=arrived.payload["consignee_party_id"],
    )
    sys.stdout.write(dump_jsonl([*events, result]))
    print("dock-call: dry run appended, no call placed", file=sys.stderr)
    return 0
