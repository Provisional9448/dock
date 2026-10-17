"""Free-time clock. One job: turn arrival and unload facts into charge risk."""

__version__ = "0.1.0"

from dock_clock.policy import DetentionPolicy
from dock_clock.tick import replay_clock, tick

__all__ = ["DetentionPolicy", "replay_clock", "tick"]
