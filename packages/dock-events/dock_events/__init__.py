"""Event schema and append-only JSONL log. The only shared contract in Dock."""

__version__ = "0.1.0"

from dock_events.model import Event, dumps_event, event_from_dict, load_jsonl, loads_event
from dock_events.timeutil import format_local, format_time, parse_time

__all__ = [
    "Event",
    "dumps_event",
    "event_from_dict",
    "format_local",
    "format_time",
    "load_jsonl",
    "loads_event",
    "parse_time",
]
