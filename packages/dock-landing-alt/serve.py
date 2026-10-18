#!/usr/bin/env python3
"""Serve the Dock alternate landing page. Honors PORT. Binds all interfaces."""

from __future__ import annotations

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("dock-landing-alt: " + (fmt % args) + "\n")


def main() -> None:
    raw = os.environ.get("PORT", "8080")
    try:
        port = int(raw)
    except ValueError:
        sys.stderr.write(f"dock-landing-alt: PORT must be an integer, got {raw!r}\n")
        raise SystemExit(1)
    if not (0 < port < 65536):
        sys.stderr.write(f"dock-landing-alt: PORT out of range: {port}\n")
        raise SystemExit(1)
    ThreadingHTTPServer.allow_reuse_address = True
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    except OSError as exc:
        sys.stderr.write(f"dock-landing-alt: {exc}\n")
        raise SystemExit(1)
    sys.stderr.write(f"dock-landing-alt: http://0.0.0.0:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("dock-landing-alt: stopped\n")
        raise SystemExit(0)


if __name__ == "__main__":
    main()
