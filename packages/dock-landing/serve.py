"""Serve the Dock landing page on 0.0.0.0:$PORT.

Railway injects PORT. Default is 8080. Stdlib only: no login, no upstream calls.
"""

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
        sys.stderr.write("dock-landing: " + (fmt % args) + "\n")


def bind_port() -> int:
    raw = os.environ.get("PORT", "8080")
    try:
        port = int(raw)
    except ValueError:
        sys.stderr.write(f"dock-landing: PORT must be an integer, got {raw!r}\n")
        raise SystemExit(1)
    if not 0 < port < 65536:
        sys.stderr.write(f"dock-landing: PORT out of range: {port}\n")
        raise SystemExit(1)
    return port


def main() -> None:
    port = bind_port()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write(f"dock-landing: http://0.0.0.0:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
