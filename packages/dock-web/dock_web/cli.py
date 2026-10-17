"""dock-web: serve the three-role desk."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dock_web.desk import Desk
from dock_web.server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dock-web", description="Serve the Dock detention desk.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--root", default=None, help="Repo root. Defaults to an ancestor that contains data/samples.")
    args = parser.parse_args(argv)
    try:
        root = Path(args.root) if args.root else _repo_root()
        desk = Desk.from_repo(root)
        httpd = serve(desk, args.host, args.port)
    except (OSError, ValueError) as exc:
        print(f"dock-web: {exc}", file=sys.stderr)
        return 1
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    print(f"Dock desk at http://{shown}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\ndock-web: stopped", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0


def _repo_root() -> Path:
    env = os.environ.get("DOCK_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "data" / "samples" / "parties.json").exists():
            return candidate
    raise FileNotFoundError("set DOCK_ROOT to the repo root")
