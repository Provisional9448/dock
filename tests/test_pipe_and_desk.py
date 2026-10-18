import json
import threading
from urllib.request import Request, urlopen

from dock_call.cli import main as call_main
from dock_clock.cli import main as clock_main
from dock_events.cli import main as events_main
from dock_events.model import load_jsonl
from dock_notify.cli import main as notify_main
from dock_proof.cli import main as proof_main
from dock_web.desk import Desk
from dock_web.server import serve

from helpers import run_cli


def test_cli_pipe_matches_sample_trail(sample_dir, tmp_path):
    code, raw, _err = run_cli(events_main, ["cat", str(sample_dir / "harbor-rye.raw.jsonl")])
    assert code == 0
    code, clocked, err = run_cli(
        clock_main,
        ["--replay", "--as-of", "2026-10-17T22:05:00Z"],
        raw,
    )
    assert code == 0, err
    code, noticed, err = run_cli(notify_main, [], clocked)
    assert code == 0, err
    trail = load_jsonl((sample_dir / "harbor-rye.trail.jsonl").read_text(encoding="utf-8"))
    assert [event.event_id for event in load_jsonl(noticed)] == [event.event_id for event in trail]
    out = tmp_path / "trail.md"
    code, piped, err = run_cli(proof_main, ["--load", "LL-88421", "--out", str(out), "--print"], noticed)
    assert code == 0, err
    assert "$56.25" in out.read_text(encoding="utf-8")
    assert "$56.25" in piped
    code, plan_text, err = run_cli(call_main, ["plan"], clocked)
    assert code == 0, err
    plan = json.loads(plan_text)
    assert plan["goal"] == "receiver_delay"
    assert "no call placed" in err


def test_desk_presets_and_driver_sms(root):
    desk = Desk.from_repo(root)
    arrived = desk.snapshot()
    assert arrived["summary"]["phase"] == "running"
    assert arrived["summary"]["headline"] == "1h 56m free"
    assert arrived["summary"]["estimated_charge_usd"] == "0.00"
    desk.jump_preset("warning")
    warning = desk.snapshot()
    assert warning["summary"]["phase"] == "warning"
    assert warning["summary"]["estimated_charge_usd"] == "0.00"
    assert any(row["event"]["type"] == "notice_sent" for row in warning["events"])
    desk.jump_preset("accruing")
    accruing = desk.snapshot()
    assert accruing["summary"]["estimated_charge_usd"] == "18.75"
    assert any(row["event"]["type"] == "call_result" for row in accruing["events"])
    desk.jump_preset("unloaded")
    closed = desk.snapshot()
    assert closed["summary"]["phase"] == "closed"
    assert closed["summary"]["estimated_charge_usd"] == "56.25"
    assert "$56.25" in closed["proof_markdown"]
    desk.reset()
    desk.report_driver("Still waiting. They said another 20.")
    reported = desk.snapshot()
    assert any(row["event"]["type"] == "delay_reported" and row["event"]["source"] == "dock-intake" for row in reported["events"])


def test_http_desk_roundtrip(root):
    desk = Desk.from_repo(root)
    httpd = serve(desk, "127.0.0.1", 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{port}/") as response:
            page = response.read().decode("utf-8")
        assert "Detention prevention" in page
        request = Request(
            f"http://127.0.0.1:{port}/api/as-of",
            data=json.dumps({"preset": "unloaded"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            payload = json.load(response)
        assert payload["summary"]["estimated_charge_usd"] == "56.25"
        bad = Request(
            f"http://127.0.0.1:{port}/api/driver",
            data=json.dumps({"text": "hello?"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(bad)
        except Exception as exc:
            assert exc.code == 400
        else:
            raise AssertionError("expected a 400")
    finally:
        httpd.shutdown()
        httpd.server_close()
