"""Heads-up messages for shipper and consignee. Sending is a provider, and the providers here do not transmit."""

__version__ = "0.1.0"

from dock_notify.compose import apply_notices, compose_notice

__all__ = ["apply_notices", "compose_notice"]
