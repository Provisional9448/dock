import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from dock_voice.replay import replay
from datetime import datetime, timezone

from dock_events.timeutil import parse_time
from dock_voice.record import log_driver
from dock_voice.script import answer_question, driver_readback, parse_clock, parse_minutes, pick_role, pick_status, spoken
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
    run.driver_status("arrived", detail="Checked in at receiving. No doors open, wait in the truck.")
    desk.jump_preset("warning")
    snap = desk.snapshot()
    assert "Free time ends 4:0" in snap["heads_up"]["shipper"] and "$0.00" in snap["heads_up"]["shipper"]
    assert "$" not in snap["heads_up"]["consignee"]  # consignee is not the payer on LL-88421: status only
    assert "carrier's invoice" in snap["heads_up"]["broker"]
    assert "Nothing owed yet" in answer_question(snap, "how much is it so far?")
    desk.jump_preset("accruing")
    assert "$18.75" in desk.snapshot()["heads_up"]["shipper"]


def test_driver_cannot_check_in_twice(run):
    run.driver_report("Checked in at receiving 2:06. No doors open, they said wait in the truck, maybe 40 min.")
    with pytest.raises(ValueError):
        run.driver_report("I'm here")


def test_role_and_status_mapping():
    assert pick_role("I'm the shipper") == "shipper"
    assert pick_role("Broker") == "broker"
    assert pick_role("this is the DC") == "consignee"
    assert pick_role("consignee") == "consignee"
    assert pick_role("Driver. Hi, this is Luis") == "driver"
    assert pick_role("Hi, this is Luis with Red Kettle") == "driver"
    assert pick_status("I'm waiting to start unloading") == "arrived"
    assert pick_status("checked in, waiting for a door") == "arrived"
    assert pick_status("they started unloading at 4:48") == "unload_started"
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
        snap = json.loads(post("/api/live/driver", {"text": "Checked in at receiving, no doors open, they said wait in the truck"}).read())
        assert snap["summary"]["phase"] == "running"
        with pytest.raises(HTTPError):
            post("/api/live/clock", {"offset_seconds": 0})
        raw = json.loads(urlopen(base + "/api/live/raw").read())
        assert len(raw["events"]) == 2
    finally:
        server.shutdown()


def _wait_for(run, count, timeout=5.0):
    """Desk writes happen off the call thread now; wait for them."""
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        events = run.read()
        if len(events) >= count:
            return events
        time.sleep(0.02)
    return run.read()


def test_agent_handlers_with_mockcall(run):
    """Handler-level tests with Guava's MockCall. Phrases come from data/samples/conversations/."""
    from guava.testing import MockCall

    from dock_voice.agent import build_agent

    try:
        agent = build_agent(run)
    except Exception as exc:  # the SDK wants Guava credentials even to build an agent
        pytest.skip(f"no Guava credentials: {exc}")
    answer = agent._on_question(MockCall(), "any update?")
    assert "hasn't checked in" in answer and "no detention clock" in answer

    run.set_now(parse_time("2026-10-17T18:05:30Z"))  # caller is a minute ahead of the demo clock
    driver = MockCall()
    driver.set_field("role", "driver")
    agent._on_task_complete_handlers["who"](driver)
    driver.set_field("status", "checked in, waiting for a door")
    driver.set_field("at", "2:06 PM")
    driver.set_field("said_by", "Dana at the receiving window")
    driver.set_field("said", "no doors open, wait in your truck, we'll call you, maybe 40 minutes")
    agent._on_task_complete_handlers["driver_report"](driver)
    events = _wait_for(run, 4)
    assert [e.type for e in events][:2] == ["arrived", "delay_reported"]
    assert events[0].occurred_at == "2026-10-17T18:06:00Z"
    assert "Dana at the receiving window said" in events[1].payload["detail"]
    # read back, then "Anything else?" and wait: no hangup yet
    assert "wrapup" in agent._on_task_complete_handlers
    assert not any("hang up" in str(getattr(c, "instruction", "")) for c in driver._command_queue)
    readback = driver_readback(LiveDesk(run).snapshot(), "arrived", {
        "at_local": "2:06 PM ET", "said_by": "Dana at the receiving window", "said": "x",
        "estimate_minutes": 40, "eta_local": "2:46 PM ET"})
    assert readback.startswith("Okay, you checked in at 2:06 and Dana")
    assert " ET" not in readback and "$" not in readback and "free time" not in readback.lower()
    agent._on_task_complete_handlers["wrapup"](driver)
    assert "hang up" in driver._command_queue[-1].instruction

    LiveDesk(run).jump_preset("warning")
    assert "Nothing owed yet" in agent._on_question(MockCall(), "please confirm the detention amount")
    shipper = MockCall()
    shipper.set_field("role", "shipper")
    agent._on_task_complete_handlers["who"](shipper)
    shipper.set_field("plan", "I'll call the DC, let me know when it's unloading")
    agent._on_task_complete_handlers["heads_up"](shipper)
    kinds = [e.type for e in _wait_for(run, 6)]
    assert kinds[-2:] == ["notice_sent", "call_result"]
    assert run.read()[-2].payload["channel"] == "voice"


def test_driver_call_flow_check_in_update_unload(run):
    """Luis: checked in 2:06, told ~40 min; calls back 'another 20'; then 'they started unloading at 4:48'."""
    zone = "America/New_York"
    run.set_now(parse_time("2026-10-17T18:08:00Z"))
    events, rec = log_driver(
        run, "arrived", at=parse_clock("2:06", run.now(), zone),
        said_by="Dana at receiving", said="no doors open, wait in your truck, maybe 40 minutes",
        estimate_minutes=parse_minutes("maybe 40 minutes"),
    )
    assert [e.type for e in events] == ["arrived", "delay_reported"]
    assert events[0].occurred_at == "2026-10-17T18:06:00Z" and events[0].recorded_at == "2026-10-17T18:08:00Z"
    assert rec["at_local"] == "2:06 PM ET" and rec["eta_local"] == "2:46 PM ET"
    snap = LiveDesk(run).snapshot()
    assert snap["summary"]["free_time_ends_local"].startswith("4:06")
    reply = driver_readback(snap, rec["status"], rec)
    assert "checked in at 2:06" in reply and "Dana at receiving said" in reply and "$" not in reply

    run.set_now(parse_time("2026-10-17T19:30:00Z"))
    events, rec = log_driver(run, "waiting", said_by="Dana", said="another 20", estimate_minutes=parse_minutes("another 20"))
    assert [e.type for e in events] == ["delay_reported"]
    assert events[0].payload["reason"] == "still_waiting" and rec["eta_local"] == "3:50 PM ET"

    run.set_now(parse_time("2026-10-17T20:55:00Z"))
    events, rec = log_driver(run, "unload_started", at=parse_clock("they started unloading at 4:48", run.now(), zone))
    assert events[0].type == "unload_started" and events[0].occurred_at == "2026-10-17T20:48:00Z"
    assert LiveDesk(run).snapshot()["summary"]["estimated_charge_usd"] == "56.25"


def test_time_and_estimate_parsing():
    now = datetime(2026, 10, 17, 18, 8, tzinfo=timezone.utc)
    zone = "America/New_York"
    assert parse_clock("2:06", now, zone) == parse_time("2026-10-17T18:06:00Z")
    assert parse_clock("at 2:06 p.m.", now, zone) == parse_time("2026-10-17T18:06:00Z")
    assert parse_clock("ten minutes ago", now, zone) == parse_time("2026-10-17T17:58:00Z")
    assert parse_clock("I don't know", now, zone) is None
    assert parse_minutes("no doors, wait in your truck, maybe 40 minutes") == 40
    assert parse_minutes("they said another 20") == 20
    assert parse_minutes("half an hour") == 30
    assert parse_minutes("we'll call you") is None


def test_spoken_text_and_remaining_time(run):
    assert spoken("Free time ends 4:06 PM ET. Estimate $0.00.") == "Free time ends 4:06 PM Eastern. Estimate zero dollars."
    run.set_now(parse_time("2026-10-17T18:08:00Z"))
    log_driver(run, "arrived", at=parse_time("2026-10-17T18:06:00Z"))
    snap = LiveDesk(run).snapshot()
    assert snap["summary"]["remaining_free_minutes"] == 118
    answer = answer_question(snap, "how much so far?")
    assert "1 hour 58 minutes from now" in answer and "$75 an hour" in answer and " ET" not in answer


def test_unload_without_check_in_does_not_close_the_clock(run):
    """Real call 6:10 PM: an unload_started before any arrival closed the clock, so the line said '0 minutes'."""
    run.set_now(parse_time("2026-10-17T18:05:00Z"))
    events, rec = log_driver(run, "unload_started")
    assert [e.type for e in events] == ["arrived", "delay_reported"] and rec["status"] == "arrived"
    snap = LiveDesk(run).snapshot()
    assert snap["summary"]["phase"] == "running" and snap["summary"]["remaining_free_minutes"] == 120


def test_driver_readback_survives_desk_403(tmp_path, monkeypatch):
    """Live-path failure, 6:16 PM PT call: the remote desk answered the event POST (and the clock catch-up)
    with HTTP 403 because DOCK_WRITE_TOKEN differed. The handler raised, the read-back was never sent, and
    the agent stalled on 'one moment'. Now the read-back is spoken from the local clock and the write is
    spooled in the background."""
    import time
    from urllib.error import HTTPError

    from guava.testing import MockCall

    from dock_voice.agent import build_agent

    monkeypatch.delenv("DOCK_LIVE_URL", raising=False)
    monkeypatch.setenv("DOCK_SPOOL", str(tmp_path / "spool.jsonl"))

    class Forbidden(LiveRun):
        def append(self, events):
            raise HTTPError("https://desk/api/live/events", 403, "Forbidden", None, None)

        def set_now(self, moment):
            if getattr(self, "_ready", False):
                raise HTTPError("https://desk/api/live/clock", 403, "Forbidden", None, None)
            super().set_now(moment)

    run = Forbidden(ROOT, runtime=tmp_path)
    run.set_now(parse_time("2026-10-17T18:05:30Z"))
    run._ready = True
    try:
        agent = build_agent(run)
    except Exception as exc:
        pytest.skip(f"no Guava credentials: {exc}")
    call = MockCall()
    call.set_field("role", "driver")
    agent._on_task_complete_handlers["who"](call)
    call.set_field("status", "checked in, waiting for a door")
    call.set_field("at", "2:06")
    call.set_field("said_by", "the receiving clerk")
    call.set_field("said", "wait in the truck, maybe 40 minutes")
    started = time.monotonic()
    agent._on_task_complete_handlers["driver_report"](call)
    assert time.monotonic() - started < 3
    said = " ".join(str(getattr(c, "script", "")) + str(getattr(c, "instruction", "")) + str(getattr(c, "task", "")) + repr(c) for c in call._command_queue)
    assert "Okay, you checked in at 2:06" in said and "$75" not in said
    assert "Anything else?" in said
    for _ in range(100):
        spool = tmp_path / "spool.jsonl"
        if spool.exists() and len(spool.read_text().splitlines()) >= 4:
            break
        time.sleep(0.05)
    spooled = [json.loads(line)["type"] for line in (tmp_path / "spool.jsonl").read_text().splitlines()]
    assert spooled == ["arrived", "delay_reported", "call_result", "call_result"]


def test_caller_name_near_matches():
    from dock_voice.agent import NAME_NOTE

    for heard in ("Louise", "Lewis", "Louis", "Luiz"):
        assert heard in NAME_NOTE
    assert "Eastern" in NAME_NOTE and "never 'ET'" in NAME_NOTE


def test_call_files_retry_until_guava_has_them(tmp_path):
    """6:10 and 6:16 calls saved only 'No transcript available yet.' and no WAV: the first answer was taken."""
    from types import SimpleNamespace

    from dock_voice.agent import fetch_call_files

    calls = {"transcript": 0, "recording": 0}

    def fake_run(cmd, **_kw):
        kind = cmd[2]
        calls[kind] += 1
        if kind == "transcript":
            text = "No transcript available yet." if calls[kind] < 3 else "0:00 AGENT Hi, this is Dock"
            return SimpleNamespace(returncode=0, stdout=text)
        if calls[kind] >= 2:
            Path(cmd[-1]).write_bytes(b"RIFF" + b"\0" * 4096)
            return SimpleNamespace(returncode=0, stdout="Saved")
        return SimpleNamespace(returncode=1, stdout="")

    got = fetch_call_files("abc123", tmp_path / "call", cli="guava", run=fake_run, sleep=lambda _s: None)
    assert got == {"transcript": True, "audio": True}
    assert "Hi, this is Dock" in (tmp_path / "call.txt").read_text()
    assert (tmp_path / "call.wav").stat().st_size > 1024


def test_parse_clock_spoken_digits():
    now = datetime(2026, 10, 17, 18, 8, tzinfo=timezone.utc)
    assert parse_clock("I checked in at 206", now, "America/New_York") == parse_time("2026-10-17T18:06:00Z")


def test_spoken_polish_name_zero_and_steps(run):
    from dock_voice.script import goodbye_line

    assert spoken("Thanks, Louise. Checked in at 02:06 PM ET.") == "Thanks, Luis. Checked in at 2:06 PM Eastern."
    assert goodbye_line("driver") == "Thanks Luis. Bye."
    assert goodbye_line("shipper") == "Thanks Dan. Bye." and "load record" not in goodbye_line("broker")
    run.set_now(parse_time("2026-10-17T18:08:00Z"))
    log_driver(run, "arrived", at=parse_time("2026-10-17T18:06:00Z"))
    from dock_voice.script import shipper_brief

    text = shipper_brief(LiveDesk(run).snapshot())
    assert "$75 an hour" in text and "billed" not in text and "02:" not in text


def test_wrapup_says_goodbye_once_with_luis(run):
    from guava.testing import MockCall

    from dock_voice.agent import build_agent

    try:
        agent = build_agent(run)
    except Exception as exc:
        pytest.skip(f"no Guava credentials: {exc}")
    call = MockCall()
    call.set_variable("role", "driver")
    agent._on_task_complete_handlers["wrapup"](call)
    final = call._command_queue[-1].instruction
    assert "Thanks Luis. Bye." in final
    assert "Do not add thanks" in final and final.count("Bye.") == 1


def test_take3_read_back_is_short_and_clerk_is_never_asked(run):
    """Take 3: Doc asked 'who was the clerk?' after the opening line already had the time and the 40 minutes,
    and the read-back ran ~30 s. The read-back is now a few short sentences ending in 'Anything else?'."""
    from guava.testing import MockCall

    from dock_voice.agent import build_agent

    run.set_now(parse_time("2026-10-17T18:08:00Z"))
    log_driver(run, "arrived", at=parse_time("2026-10-17T18:06:00Z"))
    rec = {"at_local": "2:06 PM ET", "said_by": "Dana", "said": "wait in the truck, maybe 40 minutes",
           "estimate_minutes": 40, "eta_local": "2:46 PM ET"}
    text = driver_readback(LiveDesk(run).snapshot(), "arrived", rec)
    assert text.startswith("Okay, you checked in at 2:06") and text.endswith("Anything else?")
    assert len(text.split()) <= 45, len(text.split())
    assert "02:" not in text and "Louise" not in text
    try:
        agent = build_agent(run)
    except Exception as exc:
        pytest.skip(f"no Guava credentials: {exc}")
    call = MockCall()
    call.set_field("role", "driver")
    agent._on_task_complete_handlers["who"](call)
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand")
    dumped = task.model_dump_json()
    assert "Never ask who the clerk was" in dumped
    assert "Who told you" not in dumped


def test_mirror_to_second_desk_is_best_effort(run, tmp_path, monkeypatch):
    from dock_voice.record import build_driver_events, mirror, post_later

    monkeypatch.setenv("DOCK_WRITE_TOKEN", "t0k")
    other = LiveRun(ROOT, runtime=tmp_path / "railway")
    server = serve(Desk.from_repo(ROOT), "127.0.0.1", 0, live=LiveDesk(other), home="live")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("DOCK_MIRROR_URL", f"http://127.0.0.1:{server.server_address[1]}")
        run.set_now(parse_time("2026-10-17T18:08:00Z"))
        events, _rec, _base, _now = build_driver_events(run, "arrived", at=parse_time("2026-10-17T18:06:00Z"))
        post_later(run, events, "driver").join(5)
        assert [e.type for e in run.read()] == ["arrived", "delay_reported"]
        assert [e.type for e in other.read()] == ["arrived", "delay_reported"]
        assert LiveDesk(other).snapshot()["summary"]["phase"] == "running"
        monkeypatch.setenv("DOCK_MIRROR_URL", "http://127.0.0.1:9")  # nothing listening
        assert mirror(run, events) is False  # logged, never raised
    finally:
        server.shutdown()


def _checked_in(run):
    run.set_now(parse_time("2026-10-17T18:08:00Z"))
    log_driver(run, "arrived", at=parse_time("2026-10-17T18:06:00Z"), said_by="Dana",
               said="wait in the truck, about 40 minutes", estimate_minutes=40)
    return LiveDesk(run).snapshot()


def test_role_driver_no_money(run):
    snap = _checked_in(run)
    text = driver_readback(snap, "arrived", {"at_local": "2:06 PM ET", "said_by": "Dana",
                                             "said": "wait in the truck, about 40 minutes"})
    assert text == ("Okay, you checked in at 2:06 and Dana said wait in the truck, about 40 minutes. "
                    "Give me a call when they start unloading. Anything else?")


def test_role_shipper_payer_gets_cutoff_cost_and_action(run):
    from dock_voice.script import payer_role, shipper_brief

    snap = _checked_in(run)
    assert payer_role(snap) == "shipper"  # fictional per-load terms in parties.json
    text = shipper_brief(snap)
    # situation, free-time end, rate, ask them to check in, we'll call back if charges start
    assert text == ("Luis is waiting for a door at Harbor and Rye. He checked in at 2:06; they told him about 40 "
                    "minutes. Free time ends at 4:06. After that, detention is $75 an hour. Could you check in with "
                    "Harbor and Rye? If they give you a time, let me know. I'll call you if charges start.")
    assert "Eastern" not in text and "from now" not in text
    assert "Could you check in with Harbor and Rye?" in text and text.endswith("I'll call you if charges start.")
    assert "Dock will bill" not in text


def test_role_consignee_status_only_when_not_payer(run):
    from dock_voice.script import consignee_brief

    snap = _checked_in(run)
    text = consignee_brief(snap)
    assert text.startswith("Luis from Red Kettle checked in at your receiving window at 2:06 and is waiting for a door.")
    assert "wait in the truck, about 40 minutes" in text and "$" not in text
    snap["load"]["payer_role"] = "consignee"
    assert "$75 an hour" in consignee_brief(snap)
    from dock_voice.script import shipper_brief
    assert "$" not in shipper_brief(snap)


def test_role_broker_status_exposure_and_carrier_invoices(run):
    from dock_voice.script import broker_brief

    text = broker_brief(_checked_in(run))
    assert text.startswith("Luis is waiting for a door at Harbor and Rye.") and "$75 an hour" in text
    assert "The shipper pays detention on this load, and Red Kettle will invoice from our timestamps." in text
    assert "Dock will bill" not in text


def test_consignee_unload_time_logged(run):
    from dock_voice.record import log_receiver

    _checked_in(run)
    run.set_now(parse_time("2026-10-17T20:55:00Z"))
    (event,) = log_receiver(run, "door 4, we started unloading at 4:48", "America/New_York")
    assert event.type == "unload_started" and event.occurred_at == "2026-10-17T20:48:00Z"
    assert event.actor.role == "consignee"


def test_driver_update_queues_payer_call_and_broker_message(run):
    from dock_voice.record import build_driver_events, local_snapshot, queue_notices

    run.set_now(parse_time("2026-10-17T18:08:00Z"))
    events, _rec, base, now = build_driver_events(run, "arrived", at=parse_time("2026-10-17T18:06:00Z"))
    snap = local_snapshot(run.context, [*base, *events], now)
    notes = queue_notices(run.context, snap, now, after=events[-1].event_id)
    run.append([*events, *notes])
    payer, broker = notes
    assert payer.payload["to_role"] == "shipper" and payer.payload["outcome"] == "dry_run"
    assert payer.payload["summary"].startswith("Heads-up call to shipper (outbound disabled in demo): ")
    assert "Free time ends at 4:06" in payer.payload["summary"]
    assert broker.payload["to_role"] == "broker" and broker.actor.channel == "sms"
    assert broker.payload["summary"].startswith("Message to broker") and "Red Kettle will invoice from our timestamps" in broker.payload["summary"]
    rows = [row["event"] for row in LiveDesk(run).snapshot()["events"]]
    assert sum(1 for r in rows if r["type"] == "call_result") == 2


def test_shipper_call_back_logs_receiver_promise_and_messages_broker(run):
    """Anthony 6:50 PM: the shipper calls the warehouse, then calls Dock back with what they said."""
    from guava.testing import MockCall

    from dock_voice.agent import build_agent

    _checked_in(run)
    run.set_now(parse_time("2026-10-17T18:10:00Z"))
    try:
        agent = build_agent(run)
    except Exception as exc:
        pytest.skip(f"no Guava credentials: {exc}")
    call = MockCall()
    call.set_field("role", "shipper")
    agent._on_task_complete_handlers["who"](call)
    call.set_field("news", "I called the warehouse manager and they'll have him in door 4 in 20 minutes")
    agent._on_task_complete_handlers["shipper_open"](call)
    said = " ".join(repr(c) for c in call._command_queue)
    assert "Thanks. So the warehouse manager says door 4 by 2:30. I'll pass that on to Lantern Lane. Anything else?" in said
    events = _wait_for(run, 4)
    promise, broker = [e for e in events if e.type == "call_result"][-2:]
    assert promise.payload["goal"] == "receiver_promise" and promise.occurred_at == "2026-10-17T18:10:00Z"
    assert "warehouse manager said door 4 by 2:30 PM ET" in promise.payload["summary"]
    assert "Dan Okonkwo (shipper)" in promise.payload["summary"]
    assert broker.payload["to_role"] == "broker" and "carrier's invoice" in broker.payload["summary"]


def test_caller_id_known_numbers_skip_the_role_question(run, monkeypatch):
    """Anthony 6:53 PM: we know the caller from the number. AgentLine's demo phone is Luis unless
    DOCK_CALLER_ROLE says otherwise; party phones map to their party; unknown numbers get 'Who's this?'."""
    from dock_voice.script import caller_party, greeting

    ctx = run.context
    assert caller_party(ctx, "+12053516709", env={})["contact"] == "Luis Ortega"
    assert caller_party(ctx, "(205) 351-6709", env={"DOCK_CALLER_ROLE": "shipper"})["contact"] == "Dan Okonkwo"
    assert caller_party(ctx, "+15555550141", env={})["role"] == "broker"
    assert caller_party(ctx, "+15555550151", env={})["role"] == "driver"  # carrier dispatch -> driver path
    assert caller_party(ctx, "+14155550000", env={}) is None and caller_party(ctx, None, env={}) is None
    assert greeting("driver").startswith("Hi Luis, it's Doc") and "automated" in greeting("driver") and "recorded" in greeting("driver")
    assert greeting(None).endswith("Who am I speaking with?")

    from guava.testing import MockCall
    from guava.types.call_info import PSTNCallInfo

    from dock_voice.agent import build_agent

    monkeypatch.delenv("DOCK_CALLER_ROLE", raising=False)
    try:
        agent = build_agent(run)
    except Exception as exc:
        pytest.skip(f"no Guava credentials: {exc}")
    call = MockCall(call_info=PSTNCallInfo(from_number="+12053516709", to_number="+12402125485"))
    agent._on_call_start(call)
    said = " ".join(repr(c) for c in call._command_queue)
    assert "Hi Luis, it's Doc" in said and "driver_report" in said and "Who am I speaking" not in said

    monkeypatch.setenv("DOCK_CALLER_ROLE", "shipper")
    call = MockCall(call_info=PSTNCallInfo(from_number="+12053516709", to_number="+12402125485"))
    agent._on_call_start(call)
    said = " ".join(repr(c) for c in call._command_queue)
    assert "Hi Dan, it's Doc" in said and "shipper_open" in said

    call = MockCall(call_info=PSTNCallInfo(from_number="+14155550000", to_number="+12402125485"))
    agent._on_call_start(call)
    said = " ".join(repr(c) for c in call._command_queue)
    assert "Who am I speaking with?" in said and "'who'" in said


def test_lines_sound_like_a_dispatcher(run):
    """No 'load record', 'load trail', 'Logged', or 'automated AI assistant' in anything the line says."""
    from dock_voice import agent as agent_mod
    from dock_voice.script import broker_brief, consignee_brief, driver_readback, goodbye_line, greeting, shipper_brief

    snap = _checked_in(run)
    lines = [greeting(r) for r in (None, "driver", "shipper", "consignee", "broker")]
    lines += [shipper_brief(snap), consignee_brief(snap), broker_brief(snap), agent_mod.DISCLOSURE]
    lines += [driver_readback(snap, s, {"at_local": "2:06 PM ET", "said": "about 40"}) for s in ("arrived", "waiting", "unload_started", "unload_done")]
    lines += [goodbye_line(r) for r in ("driver", "shipper", "consignee", "broker")]
    for line in lines:
        low = line.lower()
        for banned in ("load record", "load trail", "logged", "automated ai assistant", "timestamped record", "one moment"):
            assert banned not in low, (banned, line)
        assert len(line) < 330, line
