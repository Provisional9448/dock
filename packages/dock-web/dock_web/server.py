"""Stdlib HTTP server. The desk is the app; this file only carries JSON and one page."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dock_web.desk import Desk

STATIC = Path(__file__).resolve().parent / "static" / "index.html"
LIVE_STATIC = Path(__file__).resolve().parent / "static" / "live.html"


class DockServer(ThreadingHTTPServer):
    desk: Desk
    live: Desk | None = None
    home: str = "sample"


class Handler(BaseHTTPRequestHandler):
    server: DockServer

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/favicon.ico":
            self._bytes(204, b"", "image/x-icon")
            return
        if path == "/" and self.server.home == "live" and self.server.live is not None:
            path = "/live"
        if path == "/live" and self.server.live is not None:
            self._bytes(200, LIVE_STATIC.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/live/raw" and self.server.live is not None:
            self._json(200, self.server.live.run.raw())
            return
        if path == "/api/live" and self.server.live is not None:
            self._json(200, self.server.live.snapshot())
            return
        if path in ("/", "/index.html", "/sample"):
            body = STATIC.read_bytes()
            self._bytes(200, body, "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self._json(200, {"ok": True})
            return
        if path == "/api/desk":
            self._json(200, self.server.desk.snapshot())
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        desk = self.server.desk
        if path in ("/api/live/events", "/api/live/clock") and self.server.live is not None:
            self._live_write(path)
            return
        if path.startswith("/api/live/") and self.server.live is not None:
            desk = self.server.live
            path = "/api/" + path[len("/api/live/"):]
        try:
            payload = self._read_json()
            if path == "/api/reset":
                desk.reset()
            elif path == "/api/as-of":
                if payload.get("preset"):
                    desk.jump_preset(str(payload["preset"]))
                elif payload.get("as_of"):
                    desk.jump(str(payload["as_of"]))
                else:
                    raise ValueError("send preset or as_of")
            elif path == "/api/driver":
                text = str(payload.get("text", "")).strip()
                if not text:
                    raise ValueError("text is empty")
                desk.report_driver(text)
            else:
                self._json(404, {"error": "not found"})
                return
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, desk.snapshot())

    def _live_write(self, path: str) -> None:
        import os

        from dock_events.model import event_from_dict

        token = os.environ.get("DOCK_WRITE_TOKEN", "")
        if not token or self.headers.get("X-Dock-Token", "") != token:
            self._json(403, {"error": "set DOCK_WRITE_TOKEN on both sides"})
            return
        run = self.server.live.run
        try:
            payload = self._read_json()
            if path == "/api/live/clock":
                run.set_offset(float(payload["offset_seconds"]))
                self._json(200, {"ok": True})
                return
            events = [event_from_dict(obj) for obj in payload.get("events", [])]
        except (ValueError, KeyError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        appended = run.append(events)
        self._json(200, {"appended": [event.event_id for event in appended]})

    def log_message(self, fmt: str, *args) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 65_536:
            raise ValueError("body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("body must be JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("body must be a JSON object")
        return parsed

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._bytes(status, body, "application/json; charset=utf-8")

    def _bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def serve(desk: Desk, host: str, port: int, live: Desk | None = None, home: str = "sample") -> DockServer:
    server = DockServer((host, port), Handler)
    server.desk = desk
    server.live = live
    server.home = home if live is not None else "sample"
    return server
