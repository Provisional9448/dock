"""dock-proof: pass events through, append claim_drafted, and write the markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dock_events.model import dump_jsonl, load_jsonl

from dock_proof.render import claim_event, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dock-proof",
        description="Write a detention trail. Stdout stays JSONL unless you pass --print.",
    )
    parser.add_argument("--load", required=True, help="Load id to render.")
    parser.add_argument("--out", help="Write the markdown document to this path.")
    parser.add_argument(
        "--print",
        dest="print_markdown",
        action="store_true",
        help="Write markdown to stdout instead of JSONL. Skips the claim_drafted event.",
    )
    args = parser.parse_args(argv)
    try:
        events = load_jsonl(sys.stdin.read())
        markdown = render_markdown(events, args.load)
        if args.out:
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(markdown, encoding="utf-8")
            print(f"dock-proof: wrote {path}", file=sys.stderr)
        if args.print_markdown:
            sys.stdout.write(markdown)
            return 0
        claim = claim_event(events, args.load)
        if any(event.event_id == claim.event_id for event in events):
            sys.stdout.write(dump_jsonl(events))
        else:
            sys.stdout.write(dump_jsonl([*events, claim]))
    except (ValueError, OSError) as exc:
        print(f"dock-proof: {exc}", file=sys.stderr)
        return 1
    return 0
