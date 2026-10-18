from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace

import pytest

from dock_intake.handoff import HandoffGate

CALLER = "+15555550114"
TARGET = "+15555550121"


class Call:
    def __init__(self, ident="call-1", *, number=CALLER, fail=False):
        self.id = ident
        self.call_info = SimpleNamespace(call_type="pstn", from_number=number)
        self.transfers = []
        self.fail = fail

    def transfer(self, destination, instructions):
        self.transfers.append((destination, instructions))
        if self.fail:
            raise RuntimeError("provider unavailable")


def gate(tmp_path, **overrides):
    return HandoffGate(**{**dict(mode="live", number=TARGET, available=True,
                                state_path=tmp_path / "handoff.json", now=lambda: 1000), **overrides})


@pytest.mark.parametrize("config,status", [
    ({"mode": "disabled"}, "disabled"), ({"available": False}, "unavailable"),
    ({"number": "not-a-number"}, "unavailable"), ({"state_path": None}, "unavailable"),
    ({"agent_number": TARGET}, "unavailable"),
])
def test_fail_closed_configuration(tmp_path, config, status):
    call = Call()
    assert gate(tmp_path, **config).request(call)["status"] == status
    assert call.transfers == []


def test_persistent_call_limit_cooldown_and_fixed_destination(tmp_path):
    call = Call()
    assert gate(tmp_path).request(call)["status"] == "requested"
    assert call.transfers[0][0] == TARGET
    assert "try to connect" in call.transfers[0][1]
    assert gate(tmp_path, now=lambda: 2000).request(call)["status"] == "duplicate"
    other = Call("call-2")
    assert gate(tmp_path, now=lambda: 1599).request(other)["status"] == "cooldown"
    assert other.transfers == []
    assert gate(tmp_path, now=lambda: 1600).request(other)["status"] == "requested"
    text = (tmp_path / "handoff.json").read_text()
    assert CALLER not in text and TARGET not in text and "call-1" not in text
    assert set(json.loads(text)) == {"calls", "callers"}


def test_failure_consumes_attempt_and_unknown_identity_cannot_transfer(tmp_path):
    call = Call(fail=True)
    assert gate(tmp_path).request(call)["status"] == "failed"
    assert gate(tmp_path).request(call)["status"] == "duplicate"
    assert len(call.transfers) == 1
    for anonymous in (Call(number=None), Call(ident="")):
        assert gate(tmp_path).request(anonymous)["status"] == "unavailable"
        assert anonymous.transfers == []
    browser = Call()
    browser.call_info = SimpleNamespace(call_type="webrtc", from_number=CALLER)
    assert gate(tmp_path).request(browser)["status"] == "unavailable"


def test_concurrent_instances_reserve_before_transfer(tmp_path):
    calls = [Call(f"call-{i}") for i in range(12)]
    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda call: gate(tmp_path).request(call)["status"], calls))
    assert results.count("requested") == 1
    assert results.count("cooldown") == 11
    assert sum(len(call.transfers) for call in calls) == 1


def test_corrupt_state_blocks_without_reset(tmp_path):
    path = tmp_path / "handoff.json"
    path.write_text("bad json")
    call = Call()
    assert gate(tmp_path).request(call)["status"] == "unavailable"
    assert path.read_text() == "bad json"
    assert call.transfers == []


def test_from_env_explicit_toggle(tmp_path, monkeypatch):
    for name in ("DOCK_TRANSFER_MODE", "DOCK_HUMAN_NUMBER", "DOCK_HUMAN_AVAILABLE", "DOCK_HANDOFF_STATE"):
        monkeypatch.delenv(name, raising=False)
    assert HandoffGate.from_env().request(Call())["status"] == "disabled"
    monkeypatch.setenv("DOCK_TRANSFER_MODE", "live")
    monkeypatch.setenv("DOCK_HUMAN_NUMBER", TARGET)
    monkeypatch.setenv("DOCK_HUMAN_AVAILABLE", "true")
    monkeypatch.setenv("DOCK_HANDOFF_STATE", str(tmp_path / "handoff.json"))
    monkeypatch.setenv("GUAVA_AGENT_NUMBER", "+15555550100")
    assert HandoffGate.from_env().request(Call())["status"] == "requested"


@pytest.mark.parametrize("configured_agent", ["", "+15555550199"])
def test_actual_receiving_line_cannot_transfer_to_itself(tmp_path, configured_agent):
    call = Call()
    call.call_info.to_number = TARGET
    assert gate(tmp_path, agent_number=configured_agent).request(call)["status"] == "unavailable"
    assert call.transfers == []
    assert not (tmp_path / "handoff.json").exists()
