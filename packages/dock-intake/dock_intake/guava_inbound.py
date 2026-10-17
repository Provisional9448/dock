"""Shape of a Guava inbound expert. Importing this module does not import guava.

The live entrypoint is serve(). Tests call normalize_message() and never reach it.
Docs: https://goguava.ai/docs/coding-agent-starter.md
"""

from __future__ import annotations

import os
from typing import Any

from dock_intake.normalize import normalize_message


PURPOSE = "Log a driver's arrival and whether the receiver is ready to unload."


def serve(context: dict[str, Any]) -> None:
    """Listen on GUAVA_AGENT_NUMBER. Blocks. Run it in the background."""
    if os.environ.get("DOCK_CALL_MODE") != "live":
        raise RuntimeError("Refusing to listen. Set DOCK_CALL_MODE=live and install guava-sdk first.")
    try:
        import guava
        from guava import logging_utils
    except ImportError as exc:
        raise RuntimeError("Install the voice SDK with: uv add guava-sdk") from exc

    agent = guava.Agent(
        name="Dock",
        organization="Dock",
        purpose=PURPOSE,
    )

    @agent.on_call_start
    def on_call_start(call: guava.Call) -> None:
        call.set_task(
            "driver_report",
            objective="Learn whether the driver has arrived and whether unload has started.",
            checklist=[
                guava.Field(key="load_id", field_type="text", description="Load or PO number"),
                guava.Field(key="report", field_type="text", description="What the driver is seeing at the dock"),
            ],
        )

    @agent.on_task_complete("driver_report")
    def on_report(call: guava.Call) -> None:
        # A real expert appends these events to the shared log. This starter
        # stops at the normalized events so the handler stays inspectable.
        normalize_message(
            str(call.get_field("report")),
            load_id=str(call.get_field("load_id")),
            party_id="pty_driver",
            role="driver",
            channel="voice",
            occurred_at=_now(),
            context=context,
        )
        call.hangup("Tell the driver the free-time clock is noted and the shipper will be told.")

    logging_utils.configure_logging()
    agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])


def _now() -> str:
    from datetime import datetime, timezone

    from dock_events.timeutil import format_time

    return format_time(datetime.now(timezone.utc))
