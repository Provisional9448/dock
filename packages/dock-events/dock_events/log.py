"""Append-only JSONL. Duplicate event ids are skipped. Lines are never rewritten."""

from __future__ import annotations

import fcntl
from dataclasses import dataclass
from pathlib import Path

from dock_events.model import Event, dumps_event, load_jsonl


@dataclass(frozen=True)
class AppendResult:
    appended: tuple[Event, ...]
    skipped_ids: tuple[str, ...]


class EventLog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def read(self) -> list[Event]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            return load_jsonl(handle.read())

    def append(self, events: list[Event]) -> AppendResult:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            existing = load_jsonl(handle.read())
            known = {event.event_id for event in existing}
            appended: list[Event] = []
            skipped: list[str] = []
            for event in events:
                if event.event_id in known:
                    skipped.append(event.event_id)
                    continue
                handle.write(dumps_event(event) + "\n")
                known.add(event.event_id)
                appended.append(event)
            handle.flush()
            return AppendResult(appended=tuple(appended), skipped_ids=tuple(skipped))
