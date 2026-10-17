"""Outbound call plans. The live Guava dial is a separate, gated function."""

__version__ = "0.1.0"

from dock_call.plan import build_plan, simulate_result

__all__ = ["build_plan", "simulate_result"]
