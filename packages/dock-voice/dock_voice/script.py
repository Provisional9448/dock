"""What the line says and how answers map to events. Pure functions; no guava import."""

from __future__ import annotations

ROLES = ("driver", "shipper", "consignee", "broker")

DRIVER_STATUS = {
    "arrived, waiting to unload": "arrived",
    "still waiting": "waiting",
    "unload started": "unload_started",
    "unload finished": "unload_done",
}


def pick_role(answer: object) -> str:
    text = str(answer or "").lower()
    for role in ROLES:
        if role in text:
            return role
    if any(word in text for word in ("receiver", "receiving", "dc", "warehouse", "harbor", "dock office")):
        return "consignee"
    if "carrier" in text or "dispatch" in text or "truck" in text:
        return "driver"
    return "driver"


def pick_status(answer: object) -> str:
    text = str(answer or "").lower()
    if text in DRIVER_STATUS:
        return DRIVER_STATUS[text]
    if "finish" in text or "done" in text or "empty" in text:
        return "unload_done"
    if "start" in text or "unloading" in text:
        return "unload_started"
    if "still" in text:
        return "waiting"
    return "arrived"


def driver_reply(snap: dict, status: str) -> str:
    s = snap["summary"]
    if status in ("arrived", "waiting"):
        return (
            f"Tell the driver he is logged at {snap['clock_local']}. Free time ends at {s['free_time_ends_local']}, "
            f"{s['remaining_free_minutes']} minutes from now, and the estimate is ${s['estimated_charge_usd']}. "
            "Say Dock will give the shipper and the consignee a heads-up before any charge starts. Then say goodbye."
        )
    if status == "unload_started":
        return (
            f"Tell the driver the unload start is logged at {snap['clock_local']} and the detention clock is stopped "
            f"at ${s['estimated_charge_usd']}. Then say goodbye."
        )
    return f"Tell the driver the unload is logged as finished at {snap['clock_local']}. Thank him and say goodbye."


def answer_question(snap: dict, question: str) -> str:
    """on_question: answer from the live clock, read at the moment the caller asks."""
    s = snap["summary"]
    q = question.lower()
    parts = [f"It is {snap['clock_local']} on the Dock clock."]
    if s["phase"] == "not_started":
        parts.append("The driver has not checked in yet, so no detention clock is running.")
        return " ".join(parts)
    if any(word in q for word in ("how much", "charge", "cost", "estimate", "owe", "money", "dollar")):
        parts.append(f"The detention estimate is ${s['estimated_charge_usd']}.")
    if any(word in q for word in ("when", "time", "left", "free", "long")):
        if s["phase"] in ("running", "warning"):
            parts.append(f"Free time ends at {s['free_time_ends_local']}, {s['remaining_free_minutes']} minutes from now.")
        else:
            parts.append(f"Free time ended at {s['free_time_ends_local']}.")
    parts.append(f"Status: {s['detail']} {s['how_to_avoid']}")
    rate = snap["policy"]
    parts.append(
        f"Policy: {rate['free_minutes']} minutes free, then ${rate['rate_usd_per_hour']} an hour in "
        f"{rate['increment_minutes']}-minute steps. Load {snap['load']['load_id']}, PO {snap['load']['reference']}, "
        f"{snap['load']['commodity']}, {snap['load']['facility']}."
    )
    return " ".join(parts)
