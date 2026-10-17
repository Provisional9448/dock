"""Stdlib HTTP server. The desk is the app; this file only carries JSON and one page."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dock_web.desk import Desk

STATIC = Path(__file__).resolve().parent / "static" / "index.html"


class DockServer(ThreadingHTTPServer):
    desk: Desk


class Handler(BaseHTTPRequestHandler):
    server: DockServer

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/favicon.ico":
            self._bytes(204, b"", "image/x-icon")
            return
        if path in ("/", "/index.html"):
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


def serve(desk: Desk, host: str, port: int) -> DockServer:
    server = DockServer((host, port), Handler)
    server.desk = desk
    return server
