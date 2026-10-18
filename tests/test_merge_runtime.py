"""Merge boundary: inbound evidence and legacy replay never share write surfaces."""
import json
import threading
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from dock_events.timeutil import parse_time
from dock_intake.session import InboundSession
from dock_web.desk import Desk
from dock_web.server import serve

AS_OF = "2026-10-17T20:21:00Z"


def test_runtime_cli_never_constructs_legacy_live_run(root, tmp_path, monkeypatch):
    from dock_web import cli, live

    path = tmp_path / "inbound.jsonl"
    InboundSession(root, path, parse_time(AS_OF))
    calls = []

    def forbidden(*args, **kwargs):
        pytest.fail("runtime evidence mode constructed legacy LiveRun")

    def fake_serve(desk, host, port, live=None, home="sample"):
        calls.append((desk, live))
        return SimpleNamespace(serve_forever=lambda: None, server_close=lambda: None)

    monkeypatch.setattr(live, "LiveRun", forbidden)
    monkeypatch.setattr(cli, "serve", fake_serve)
    args = ["--root", str(root), "--runtime-log", str(path), "--as-of", AS_OF]
    assert cli.main(args) == 0
    assert calls[0][1] is None
    assert calls[0][0].runtime_log == path
    with pytest.raises(SystemExit) as exc:
        cli.main([*args, "--live"])
    assert exc.value.code == 2


def test_http_observes_confirmed_shared_log_without_write_routes(root, tmp_path):
    path = tmp_path / "inbound.jsonl"
    session = InboundSession(root, path, parse_time(AS_OF))
    server = serve(Desk.from_runtime(root, path, AS_OF), "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def get_snapshot():
        with urlopen(base + "/api/desk", timeout=3) as response:
            return json.load(response)

    try:
        before = path.read_bytes()
        assert get_snapshot()["summary"]["phase"] == "accruing"
        assert path.read_bytes() == before
        saved = session.report("LL-88421", state="unloading_started", confirmed=True,
                               occurred_at=parse_time(AS_OF), detail="Observed unloading now.",
                               action_id="merge-http-report")
        accepted = path.read_bytes()
        snap = get_snapshot()
        assert snap["summary"]["phase"] == "closed"
        assert snap["summary"]["estimated_charge_usd"] == "18.75"
        assert saved["event_id"] in {row["event"]["event_id"] for row in snap["events"]}
        assert not any(row["event"]["type"] == "notice_sent" for row in snap["events"])
        assert path.read_bytes() == accepted
        for endpoint in ("driver", "reset", "as-of", "events", "clock"):
            request = Request(base + "/api/live/" + endpoint,
                              data=json.dumps({"text": "They started unloading.",
                                               "as_of": AS_OF, "events": [],
                                               "offset_seconds": 0}).encode(),
                              headers={"Content-Type": "application/json"})
            with pytest.raises(HTTPError) as exc:
                urlopen(request, timeout=3)
            assert exc.value.code == 404
            assert path.read_bytes() == accepted
        restarted = InboundSession(root, path, parse_time(AS_OF))
        assert restarted.status("LL-88421")["stage"] == "unloading_started"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_legacy_replay_cannot_change_separate_inbound_log(root, tmp_path, monkeypatch):
    from dock_voice.replay import replay
    from dock_web.live import LiveRun

    monkeypatch.delenv("DOCK_LIVE_URL", raising=False)
    inbound_path = tmp_path / "inbound" / "events.jsonl"
    session = InboundSession(root, inbound_path, parse_time(AS_OF))
    before = inbound_path.read_bytes()
    legacy = LiveRun(root, runtime=tmp_path / "legacy")
    replay(legacy, pause=0, say=lambda _: None)
    assert any(event.type == "unload_started" for event in legacy.read())
    assert inbound_path.read_bytes() == before
    assert session.status("LL-88421")["stage"] == "waiting"
    legacy.reset()
    assert inbound_path.read_bytes() == before
