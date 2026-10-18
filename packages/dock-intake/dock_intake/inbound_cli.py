"""Offline facts or an explicitly enabled inbound Guava listener."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dock_events.timeutil import parse_time
from dock_intake.guava_inbound import serve
from dock_intake.session import InboundSession


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["status", "phone", "webrtc"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--log", type=Path, required=True, help="Runtime JSONL path, never the sample fixture")
    parser.add_argument("--as-of", required=True, help="Pinned fictional demo time with timezone")
    parser.add_argument("--load", default="LL-88421")
    parser.add_argument("--webrtc-code")
    args = parser.parse_args(argv)
    try:
        session = InboundSession(args.root, args.log, parse_time(args.as_of))
        if args.mode == "status":
            print(json.dumps(session.status(args.load), indent=2))
        else:
            serve(session, transport=args.mode, webrtc_code=args.webrtc_code)
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        print(f"dock-inbound: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
