import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from dock_voice.replay import replay
from dock_voice.script import answer_question, pick_role, pick_status
from dock_web.desk import Desk
from dock_web.live import LiveDesk, LiveRun
from dock_web.server import serve

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCK_LIVE_URL", raising=False)
    return LiveRun(ROOT, runtime=tmp_path)


def test_replay_matches_sample_numbers(run):
    replay(run, pause=0, say=lambda _line: None)
    snap = LiveDesk(run).snapshot()
    assert snap["summary"]["phase"] == "closed"
    assert snap["summary"]["estimated_charge_usd"] == "56.25"
    kinds = [row["event"]["type"] for row in snap["events"]]
    assert "call_result" in kinds and "unload_started" in kinds
    voice = [row for row in snap["events"] if row["event"]["type"] == "notice_sent" and row["event"]["payload"]["channel"] == "voice"]
    assert voice and voice[0]["event"]["payload"]["estimated_charge_usd"] == "0.00"


def test_heads_up_and_questions_read_the_clock(run):
    desk = LiveDesk(run)
    assert "has not checked in" in desk.snapshot()["heads_up"]["shipper"]
    run.driver_status("arrived", detail="Door 4 is occupied.")
    desk.jump_preset("warning")
    snap = desk.snapshot()
    assert "30 minutes from now" in snap["heads_up"]["shipper"]
    assert "$0.00" in answer_question(snap, "how much is it so far?")
    desk.jump_preset("accruing")
    assert "$18.75 is on the trail" in desk.snapshot()["heads_up"]["shipper"]


def test_driver_cannot_check_in_twice(run):
    run.driver_report("I'm at Harbor and Rye door 4. They are not ready to unload.")
    with pytest.raises(ValueError):
        run.driver_report("I'm here")


def test_role_and_status_mapping():
    assert pick_role("I'm the shipper") == "shipper"
    assert pick_role("Broker") == "broker"
    assert pick_role("this is the DC") == "receiver"
    assert pick_status("unload started") == "unload_started"
    assert pick_status("we're done, empty") == "unload_done"


def test_live_routes_and_write_token(run, sample_dir, monkeypatch):
    monkeypatch.setenv("DOCK_WRITE_TOKEN", "test-token")
    server = serve(Desk.from_repo(ROOT), "127.0.0.1", 0, live=LiveDesk(run), home="live")
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        assert b"live detention desk" in urlopen(base + "/").read()
        post = lambda path, body, token=None: urlopen(Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **({"X-Dock-Token": token} if token else {})}))
        snap = json.loads(post("/api/live/driver", {"text": "I'm at door 4, they are not ready"}).read())
        assert snap["summary"]["phase"] == "running"
        with pytest.raises(HTTPError):
            post("/api/live/clock", {"offset_seconds": 0})
        raw = json.loads(urlopen(base + "/api/live/raw").read())
        assert len(raw["events"]) == 2
    finally:
        server.shutdown()
