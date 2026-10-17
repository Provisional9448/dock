"""SMS and voice heads-up go through a provider. This starter never opens a socket."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OutboundMessage:
    channel: str
    to_number: str
    to_name: str
    to_role: str
    body: str
    load_id: str


@dataclass(frozen=True)
class Receipt:
    provider: str
    status: str
    detail: str


class Notifier(Protocol):
    name: str

    def send(self, message: OutboundMessage) -> Receipt: ...


class LogProvider:
    """Default. Records the message on the event. Nothing is sent."""

    name = "log"

    def send(self, message: OutboundMessage) -> Receipt:
        return Receipt(
            provider=self.name,
            status="logged",
            detail="Stored on the event. No SMS or call was placed.",
        )


class TwilioProvider:
    """Stub. Guava's own docs now include SMS; Twilio stays available as the other adapter.

    send() does not read TWILIO_AUTH_TOKEN and does not call Twilio.
    """

    name = "twilio"

    def send(self, message: OutboundMessage) -> Receipt:
        return Receipt(
            provider=self.name,
            status="stubbed",
            detail=(
                "Twilio adapter is a stub in this starter. "
                f"Would have sent {len(message.body)} characters to {message.to_number}. "
                "No HTTP request was made."
            ),
        )


class GuavaSmsProvider:
    """Stub mapping onto guava.Client.send_sms / next_sms.

    The hackathon brief treated Guava as voice-only. As of the docs fetched on
    2026-10-17, Guava documents SMS: client.send_sms(from_number, to_number, message)
    and client.next_sms(from_number, to_number, timeout=...). Dock still keeps SMS
    behind this interface. This method does not import guava and does not send.
    """

    name = "guava"

    def send(self, message: OutboundMessage) -> Receipt:
        return Receipt(
            provider=self.name,
            status="stubbed",
            detail=(
                "Guava SMS adapter is a stub. A live version would call "
                "guava.Client.send_sms(from_number=GUAVA_AGENT_NUMBER, "
                f"to_number={message.to_number!r}, message=...). Nothing was sent."
            ),
        )


def provider_from_env() -> Notifier:
    name = os.environ.get("SMS_PROVIDER", "log")
    if name == "log":
        return LogProvider()
    if name == "twilio":
        return TwilioProvider()
    if name == "guava":
        return GuavaSmsProvider()
    raise ValueError(f"unknown SMS_PROVIDER {name!r}")
