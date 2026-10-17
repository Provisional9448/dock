"""Voice and SMS in. Normalized events out. No clock math in here."""

__version__ = "0.1.0"

from dock_intake.normalize import normalize_message

__all__ = ["normalize_message"]
