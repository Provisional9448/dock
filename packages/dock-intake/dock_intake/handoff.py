"""Explicitly enabled, fixed-destination handoff with persistent attempt limits."""
from __future__ import annotations

import fcntl
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Callable

_E164 = re.compile(r"\+[1-9][0-9]{7,14}\Z")
_MESSAGES = {
    "disabled": "Human transfer is not enabled. No one has been contacted.",
    "unavailable": "Human transfer is unavailable right now. No connection was attempted.",
    "cooldown": "A human connection was already attempted recently. I cannot retry it yet.",
    "duplicate": "A human connection was already attempted on this call. I cannot retry it.",
    "requested": "The transfer was requested; connection to a person is not confirmed.",
    "failed": "The transfer could not be requested. I cannot retry it on this call.",
}


def _result(status: str) -> dict:
    return {"status": status, "message": _MESSAGES[status]}


class HandoffGate:
    def __init__(self, *, mode: str = "disabled", number: str = "", available: bool = False,
                 state_path: Path | str | None = None, agent_number: str = "",
                 now: Callable[[], float] = time.time):
        self.mode = mode
        self.number = number
        self.available = available
        self.state_path = Path(state_path) if state_path else None
        self.agent_number = agent_number
        self.now = now

    @classmethod
    def from_env(cls) -> HandoffGate:
        return cls(mode=os.environ.get("DOCK_TRANSFER_MODE", "disabled"),
                   number=os.environ.get("DOCK_HUMAN_NUMBER", ""),
                   available=os.environ.get("DOCK_HUMAN_AVAILABLE") == "true",
                   state_path=os.environ.get("DOCK_HANDOFF_STATE"),
                   agent_number=os.environ.get("GUAVA_AGENT_NUMBER", ""))

    def request(self, call) -> dict:
        if self.mode != "live":
            return _result("disabled")
        if (not self.available or not _E164.fullmatch(self.number)
                or self.number == self.agent_number or self.state_path is None):
            return _result("unavailable")
        # SDK 0.48: Call.id and Call.call_info.PSTNCallInfo.from_number.
        # Never derive caller identity or destination from conversational fields.
        info = getattr(call, "call_info", None)
        caller = getattr(info, "from_number", None)
        # The actual receiving line wins over absent or stale environment config.
        if self.number == getattr(info, "to_number", None):
            return _result("unavailable")
        call_id = getattr(call, "id", None)
        if (getattr(info, "call_type", None) != "pstn"
                or not isinstance(caller, str) or not _E164.fullmatch(caller)
                or not isinstance(call_id, str) or not call_id.strip()):
            return _result("unavailable")
        caller_hash = sha256(caller.encode()).hexdigest()
        call_hash = sha256(call_id.encode()).hexdigest()
        try:
            reserved = self._reserve(call_hash, caller_hash)
        except (OSError, ValueError, TypeError, KeyError):
            return _result("unavailable")
        if reserved != "reserved":
            return _result(reserved)
        # A failed or interrupted request consumes the reservation; no automatic retry.
        try:
            call.transfer(self.number, instructions="Say: I'll try to connect you to a person now. Do not say the connection is complete or that a person answered.")
        except Exception:
            return _result("failed")
        return _result("requested")

    def _reserve(self, call_hash: str, caller_hash: str) -> str:
        assert self.state_path is not None
        moment = float(self.now())
        if not math.isfinite(moment):
            raise ValueError("Invalid clock")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.state_path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(fd, "r+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            raw = handle.read()
            state = json.loads(raw) if raw else {"calls": {}, "callers": {}}
            # Malformed state fails closed; never clear history to permit a retry.
            if not isinstance(state, dict) or set(state) != {"calls", "callers"}:
                raise ValueError("Invalid handoff state")
            for group in state.values():
                if not isinstance(group, dict) or any(
                    not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key)
                    or not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value) for key, value in group.items()
                ):
                    raise ValueError("Invalid handoff state")
            if call_hash in state["calls"]:
                return "duplicate"
            previous = state["callers"].get(caller_hash)
            if previous is not None and moment - previous < 600:
                return "cooldown"
            state["calls"][call_hash] = moment
            state["callers"][caller_hash] = moment
            handle.seek(0)
            json.dump(state, handle, separators=(",", ":"))
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
            return "reserved"
