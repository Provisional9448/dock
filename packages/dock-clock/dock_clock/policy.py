"""The numbers on a load. Hourly detention and daily demurrage use the same shape."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class DetentionPolicy:
    free_minutes: int = 120
    warn_minutes: int = 30
    rate_usd_per_hour: Decimal = Decimal("75.00")
    increment_minutes: int = 15
    stop_on: str = "unload_started"

    def __post_init__(self) -> None:
        if self.free_minutes < 0 or self.warn_minutes < 0 or self.increment_minutes <= 0:
            raise ValueError("policy minutes must be non-negative, and the step must be positive")
        if self.rate_usd_per_hour < 0:
            raise ValueError("rate cannot be negative")
        if self.stop_on not in ("unload_started", "unload_done"):
            raise ValueError("stop_on must be unload_started or unload_done")

    @property
    def rate_text(self) -> str:
        return f"{self.rate_usd_per_hour.quantize(Decimal('0.01')):.2f}"


def policy_from_context(context: dict[str, Any]) -> DetentionPolicy:
    raw = context.get("policy") or {}
    return DetentionPolicy(
        free_minutes=int(raw.get("free_minutes", 120)),
        warn_minutes=int(raw.get("warn_minutes", 30)),
        rate_usd_per_hour=Decimal(str(raw.get("rate_usd_per_hour", "75.00"))),
        increment_minutes=int(raw.get("increment_minutes", 15)),
        stop_on=str(raw.get("stop_on", "unload_started")),
    )
