from dock_call.plan import build_plan, serve_outbound
from dock_clock.policy import policy_from_context
from dock_clock.tick import replay_clock
from dock_events.context import load_context
from dock_events.model import load_jsonl
from dock_events.timeutil import parse_time
from dock_intake.normalize import classify, normalize_message
from dock_notify.compose import apply_notices
from dock_notify.provider import GuavaSmsProvider, LogProvider, TwilioProvider
from dock_proof.render import render_markdown

import pytest

AS_OF_END = parse_time("2026-10-17T22:05:00Z")


def _context(sample_dir):
    return load_context(sample_dir / "parties.json")


def _raw(sample_dir):
    return load_jsonl((sample_dir / "harbor-rye.raw.jsonl").read_text(encoding="utf-8"))


def test_one_text_can_arrive_and_report_a_delay(sample_dir):
    context = _context(sample_dir)
    assert classify("Checked in at receiving 2:06. No doors open, they said wait in the truck, maybe 40 min.") == [
        "arrived",
        "delay_reported",
    ]
    events = normalize_message(
        "Checked in at receiving 2:06. No doors open, they said wait in the truck, maybe 40 min.",
        load_id="LL-88421",
        party_id="pty_luis",
        role="driver",
        channel="sms",
        occurred_at="2026-10-17T18:10:00Z",
        context=context,
    )
    assert [event.type for event in events] == ["arrived", "delay_reported"]
    assert events[1].payload["reason"] == "no_door_available"


def test_unrecognized_driver_text_is_an_error(sample_dir):
    with pytest.raises(ValueError, match="could not classify"):
        normalize_message(
            "hello?",
            load_id="LL-88421",
            party_id="pty_luis",
            role="driver",
            channel="sms",
            occurred_at="2026-10-17T18:10:00Z",
            context=_context(sample_dir),
        )


def test_heads_up_quotes_zero_then_the_accrual(sample_dir):
    context = _context(sample_dir)
    clocked = replay_clock(_raw(sample_dir), as_of=AS_OF_END, policy=policy_from_context(context))
    noticed = apply_notices(clocked, provider=LogProvider())
    notices = [event for event in noticed if event.type == "notice_sent"]
    assert len(notices) == 6
    again = apply_notices(noticed, provider=LogProvider())
    assert len(again) == len(noticed)
    warning = next(event for event in notices if event.payload["phase"] == "warning" and event.payload["to_role"] == "shipper")
    assert "Not an invoice." in warning.payload["body"]
    assert "$0.00" in warning.payload["body"]
    assert "Dan Okonkwo" in warning.payload["body"]
    accruing = next(event for event in notices if event.payload["phase"] == "accruing" and event.payload["to_role"] == "shipper")
    assert "$18.75" in accruing.payload["body"]
    assert "Dan Okonkwo" in accruing.payload["body"]
    # payer-only: the shipper pays on LL-88421 (fictional terms), so the consignee gets no money heads-up
    assert not any(event.payload["to_role"] == "consignee" for event in notices)
    broker = next(event for event in notices if event.payload["phase"] == "accruing" and event.payload["to_role"] == "broker")
    assert "The shipper pays on this load; Red Kettle Freight invoices." in broker.payload["body"]
    assert "The timestamped record backs the carrier's invoice." in broker.payload["body"]
    assert accruing.payload["delivery_status"] == "logged"


def test_sms_providers_do_not_transmit():
    from dock_notify.provider import OutboundMessage
    from pathlib import Path

    message = OutboundMessage("sms", "+15555550121", "Priya Shah", "consignee", "hi", "LL-88421")
    assert TwilioProvider().send(message).status == "stubbed"
    assert GuavaSmsProvider().send(message).status == "stubbed"
    import dock_notify.provider as provider

    text = Path(provider.__file__).read_text(encoding="utf-8")
    assert "urlopen" not in text
    assert "requests" not in text


def test_call_plan_quotes_money_only_after_free_time(sample_dir):
    context = _context(sample_dir)
    policy = policy_from_context(context)
    warning_at = parse_time("2026-10-17T19:36:00Z")
    accruing_at = parse_time("2026-10-17T20:21:00Z")
    warned = replay_clock(_raw(sample_dir), as_of=warning_at, policy=policy)
    warning_plan = build_plan(warned)
    assert warning_plan["guava"]["test_with"] == ["agent.chat", "agent.roleplay"]
    assert "$0.00" in warning_plan["opening"]
    assert "$18.75" not in warning_plan["opening"]
    assert "Do not threaten" in " ".join(warning_plan["rules"])
    accrued = replay_clock(_raw(sample_dir), as_of=accruing_at, policy=policy)
    accrued_plan = build_plan(accrued)
    assert "$18.75" in accrued_plan["opening"]
    assert accrued_plan["variables"]["contact_name"] == "Priya Shah"
    assert accrued_plan["guava"]["to_number"] == "+15555550121"


def test_live_dial_is_gated():
    with pytest.raises(RuntimeError, match="Refusing to dial"):
        serve_outbound({"objective": "Get a commit time.", "goal": "receiver_delay", "variables": {}, "checklist": []}, "+15555550121")


def test_proof_is_a_trail_not_an_invoice(sample_dir):
    context = _context(sample_dir)
    clocked = replay_clock(_raw(sample_dir), as_of=AS_OF_END, policy=policy_from_context(context))
    noticed = apply_notices(clocked)
    markdown = render_markdown(noticed, "LL-88421")
    assert "This is not an invoice." in markdown
    assert "$56.25" in markdown
    assert "Priya said door 4 is still occupied" in markdown
    assert "Dan Okonkwo" in markdown
    early = replay_clock(_raw(sample_dir), as_of=parse_time("2026-10-17T18:10:00Z"), policy=policy_from_context(context))
    early_doc = render_markdown(early, "LL-88421")
    assert "No detention estimate yet." in early_doc
    assert "$56.25" not in early_doc
