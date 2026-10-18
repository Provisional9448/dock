"""Phrasings from every party, plus the fictional WhatsApp samples."""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

from dock_clock.policy import policy_from_context
from dock_clock.tick import replay_clock
from dock_events.context import load_context
from dock_events.log import EventLog
from dock_events.model import event_from_dict, load_jsonl
from dock_events.schema_doc import SCHEMA
from dock_events.timeutil import parse_time
from dock_track.cli import main
from dock_track.parse import carry_forward, parse_request
from dock_track.watch import watch

AS_OF = parse_time("2026-10-17T22:05:00Z")
WHEN = "2026-10-13T15:04:00Z"
_MSG = re.compile(r"^\[(?P<when>[^\]]+)\]\s+(?P<who>.+?):\s*(?P<text>.+\S)\s*$")


def _messages(path: Path) -> list[tuple[str, str]]:
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _MSG.match(line)
        if match:
            found.append((match.group("who"), match.group("text")))
    return found


def _kinds(text: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in parse_request(text).identifiers:
        grouped.setdefault(item.kind, []).append(item.value)
    return grouped


def test_ten_phrasings_cover_every_party():
    phrases = [
        (
            "This is the shipper. Can you keep track of this shipment? PRO 123-456 https://example.com/track/abc",
            "shipper",
            "track",
            "pro",
            "123-456",
        ),
        (
            "Consignee here. What's the status of container ABCU1234567?",
            "consignee",
            "status",
            "container",
            "ABCU1234567",
        ),
        (
            "Broker asking. Tell me when load LL-88421 reaches Elizabeth",
            "broker",
            "track",
            "load_id",
            "LL-88421",
        ),
        (
            "Carrier dispatch. Plate ABC-1234, report every 2 hours",
            "carrier",
            "track",
            "plate",
            "ABC-1234",
        ),
        (
            "Driver. Llegué a Harbor & Rye, gate B",
            "driver",
            "driver_report",
            None,
            None,
        ),
        (
            "2 more links coming, mismas instrucciones https://example.com/fleet/live/u1841-demo?share=9MZP4",
            None,
            "same_instructions",
            "gps_share_link",
            "https://example.com/fleet/live/u1841-demo?share=9MZP4",
        ),
        (
            "Avísame cuando salga de la terminal, placa XYZ-8891",
            None,
            "track",
            "plate",
            "XYZ-8891",
        ),
        (
            "Shipper here. Need the signed POD for BOL RK-BOL-50318",
            "shipper",
            "doc_request",
            "bol",
            "RK-BOL-50318",
        ),
        (
            "Consignee here. Any update on PO-44190?",
            "consignee",
            "status",
            "po",
            "PO-44190",
        ),
        (
            "https://example.com/fleet/live/u1841-demo?share=Q4T8W tell me when it leaves Northwind yard",
            None,
            "track",
            "gps_share_link",
            "https://example.com/fleet/live/u1841-demo?share=Q4T8W",
        ),
        (
            "Soy el embarcador. Cuando llegue a Monterrey, load LL-10001",
            "shipper",
            "track",
            "load_id",
            "LL-10001",
        ),
        (
            "From the carrier. Where is PRO RK-PRO-884210?",
            "carrier",
            "status",
            "pro",
            "RK-PRO-884210",
        ),
    ]
    assert len(phrases) >= 10
    roles = set()
    intents = set()
    kinds = set()
    for text, role, intent, kind, value in phrases:
        parsed = parse_request(text)
        assert parsed.role == role
        assert parsed.intent == intent
        assert parsed.kind == kind
        assert parsed.value == value
        if role:
            roles.add(role)
        intents.add(intent)
        if kind:
            kinds.add(kind)
        for ident in parsed.identifiers:
            if ident.kind in ("url", "gps_share_link"):
                assert "example.com" in ident.value
                assert "://" in ident.value
    assert roles == {"shipper", "consignee", "broker", "carrier", "driver"}
    assert {"track", "status", "doc_request", "driver_report", "same_instructions"} <= intents
    assert {"pro", "bol", "container", "load_id", "po", "gps_share_link", "plate"} <= kinds


def test_conditions_are_arrive_leave_or_interval():
    arrive = parse_request("tell me once it gets to harbor & rye DC in Elizabeth")
    assert arrive.condition is not None
    assert arrive.condition.trigger == "arrive_at"
    assert arrive.condition.city == "Elizabeth"
    assert "harbor & rye" in arrive.condition.place

    leave = parse_request("Avísame cuando salga de la terminal")
    assert leave.condition is not None
    assert leave.condition.trigger == "leave_terminal"
    assert leave.condition.place == "terminal"

    yard = parse_request("tell me when it leaves Northwind yard")
    assert yard.condition is not None
    assert yard.condition.trigger == "leave_terminal"
    assert yard.condition.place == "Northwind yard"

    every = parse_request("send me a summary each 2 hrs")
    assert every.condition is not None
    assert every.condition.trigger == "interval_hours"
    assert every.condition.interval_hours == 2

    spanish = parse_request("reporte cada 2 horas")
    assert spanish.condition is not None
    assert spanish.condition.interval_hours == 2


def test_whatsapp_samples_match_the_fictional_threads(sample_dir):
    folder = sample_dir / "conversations"

    first = "\n".join(text for _, text in _messages(folder / "01-whatsapp-tracking-link-arrival.md"))
    opened = parse_request(first)
    assert opened.intent == "track"
    assert opened.kind == "gps_share_link"
    assert opened.value == "https://example.com/fleet/live/u1841-demo?share=7Q2KX"
    assert _kinds(first)["load_id"] == ["LL-88421"]
    assert opened.condition is not None
    assert opened.condition.trigger == "arrive_at"
    assert opened.condition.city == "Elizabeth"
    assert opened.same_instructions is False

    more_lines = [text for who, text in _messages(folder / "02-whatsapp-more-links-same-instructions.md") if who == "Sam"]
    burst = "\n".join(more_lines[:4])
    more = parse_request(burst)
    assert more.intent == "same_instructions"
    assert more.same_instructions is True
    kinds = _kinds(burst)
    assert kinds["url"] == [
        "https://example.com/track/rkfx?pro=RK-PRO-884210",
        "https://example.com/containers/ABCU1234567?view=public",
    ]
    assert "RK-PRO-884210" in kinds["pro"]
    assert kinds["container"] == ["ABCU1234567"]
    assert kinds["po"] == ["PO-44190"]
    assert kinds["bol"] == ["RK-BOL-50318"]
    assert "gps_share_link" not in kinds
    again = parse_request(more_lines[4])
    assert again.intent == "same_instructions"
    assert again.identifiers == ()
    carried = carry_forward(opened, more)
    assert carried.condition is not None
    assert carried.condition.trigger == "arrive_at"
    assert carried.condition.city == "Elizabeth"
    renewed = parse_request(more_lines[-1])
    assert renewed.kind == "url"
    assert "t=renewed" in renewed.value
    assert _kinds(more_lines[-1])["container"] == ["ABCU1234567"]

    group = "\n".join(text for _, text in _messages(folder / "03-whatsapp-group-every-2-hours.md"))
    hourly = parse_request(group)
    assert hourly.intent == "track"
    assert hourly.condition is not None
    assert hourly.condition.trigger == "interval_hours"
    assert hourly.condition.interval_hours == 2
    assert _kinds(group)["container"] == ["ABCU1234567"]
    assert _kinds(group)["gps_share_link"] == ["https://example.com/fleet/live/u1841-demo?share=9MZP4"]

    yard_lines = [text for _, text in _messages(folder / "04-whatsapp-let-me-know-when-out.md")]
    parked = parse_request("\n".join(yard_lines[:2]))
    assert parked.intent == "track"
    assert parked.kind == "gps_share_link"
    assert parked.condition is not None
    assert parked.condition.trigger == "leave_terminal"
    assert parked.condition.place == "Northwind yard"
    assert parse_request(yard_lines[2]).intent == "status"
    assert parse_request(yard_lines[3]).intent == "status"

    driver = _messages(folder / "05-thread-dispatch-driver-checkins.md")
    assert parse_request(driver[1][1]).intent == "driver_report"
    assert parse_request(driver[2][1]).intent == "driver_report"
    loaded = parse_request(driver[3][1])
    assert loaded.intent == "driver_report"
    photo_ask = parse_request(driver[4][1])
    assert photo_ask.intent == "doc_request"
    photo = parse_request(driver[5][1])
    assert photo.identifiers[0].kind == "bol"
    assert photo.identifiers[0].value == "RK-BOL-50318"
    assert parse_request(driver[-1][1]).intent == "driver_report"

    chase = _messages(folder / "07-thread-pod-paperwork-chase.md")
    pod = parse_request(chase[0][1])
    assert pod.intent == "doc_request"
    assert _kinds(chase[0][1])["load_id"] == ["LL-88421"]
    assert _kinds(chase[0][1])["po"] == ["PO-44190"]

    customer = [text for _, text in _messages(folder / "08-thread-customer-status-chase.md")]
    status = parse_request(customer[0])
    assert status.intent == "status"
    assert status.kind == "po"
    assert status.value == "PO-44190"
    assert parse_request(customer[2]).intent == "status"
    assert parse_request(customer[5]).intent == "status"

    for name in (
        "01-whatsapp-tracking-link-arrival.md",
        "02-whatsapp-more-links-same-instructions.md",
        "03-whatsapp-group-every-2-hours.md",
        "04-whatsapp-let-me-know-when-out.md",
    ):
        for _, text in _messages(folder / name):
            if "http" not in text:
                continue
            for ident in parse_request(text).identifiers:
                if ident.kind in ("url", "gps_share_link"):
                    assert ident.value.startswith("https://example.com/")


def test_watch_appends_one_tracking_requested_line(tmp_path):
    path = tmp_path / "track.jsonl"
    text = "Broker asking. Tell me when load LL-88421 reaches Elizabeth. https://example.com/fleet/live/u1841-demo?share=7Q2KX"
    first = watch("LL-88421", path, text=text, occurred_at=WHEN, party_id="pty_sam")
    second = watch("LL-88421", path, text=text, occurred_at=WHEN, party_id="pty_sam")
    assert first == second
    assert first.type == "tracking_requested"
    assert first.source == "dock-track"
    assert first.actor.role == "broker"
    assert first.actor.channel == "sms"
    assert first.payload["summary"] == "tracking requested"
    assert first.payload["intent"] == "track"
    assert first.payload["condition"]["trigger"] == "arrive_at"
    assert first.payload["condition"]["city"] == "Elizabeth"
    assert first.payload["identifier_kind"] == "load_id"
    logged = EventLog(path).read()
    assert logged == [first]
    assert event_from_dict(first.to_dict()) == first
    other = watch(
        "LL-88421",
        path,
        text="https://example.com/containers/ABCU1234567?view=public",
        occurred_at=WHEN,
    )
    assert other.event_id != first.event_id
    assert [event.event_id for event in EventLog(path).read()] == [first.event_id, other.event_id]


def test_watch_does_not_move_the_detention_clock(sample_dir, tmp_path):
    raw = load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))
    event = watch(
        "LL-88421",
        tmp_path / "track.jsonl",
        text="tell me when it leaves Northwind yard https://example.com/fleet/live/u1841-demo?share=Q4T8W",
        occurred_at="2026-10-17T18:07:00Z",
        role="shipper",
    )
    policy = policy_from_context(load_context(sample_dir / "parties.json"))
    before = replay_clock(raw, as_of=AS_OF, policy=policy)
    after = replay_clock(raw + [event], as_of=AS_OF, policy=policy)
    clock_types = ("clock_started", "charge_risk")

    def clock_ids(events):
        return [item.event_id for item in events if item.type in clock_types]

    assert clock_ids(before) == clock_ids(after)
    assert event.event_id in {item.event_id for item in after}
    assert "tracking_requested" in SCHEMA["properties"]["type"]["enum"]


def test_cli_parse_and_watch(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert main(["parse"]) == 1
    assert capsys.readouterr().err.startswith("dock-track:")

    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO("This is the shipper. PRO 123-456 https://example.com/track/abc\n"),
    )
    assert main(["parse"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["role"] == "shipper"
    assert body["intent"] == "track"
    assert body["kind"] == "pro"

    log = tmp_path / "track.jsonl"
    monkeypatch.setattr(sys, "stdin", io.StringIO("mismas instrucciones\n"))
    assert main(["watch", "--load", "LL-88421", "--log", str(log), "--at", WHEN, "--role", "broker"]) == 0
    line = load_jsonl(capsys.readouterr().out)
    assert line[0].type == "tracking_requested"
    assert line[0].payload["same_instructions"] is True
    assert EventLog(log).read() == line
