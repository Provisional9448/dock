"""Rules in code for a tracking ask. No network, no clock, no clock math."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

_URL = re.compile(r"https?://[^\s<>\]\)\"']+")
_CONTAINER = re.compile(r"\b[A-Z]{4}\d{7}\b", re.IGNORECASE)
_PRO_CODE = re.compile(r"\b[A-Z]{2,8}-PRO-\d+\b", re.IGNORECASE)
_PRO_LABELED = re.compile(r"\bPRO[\s:#-]+([A-Z0-9]+(?:-[A-Z0-9]+)*)\b", re.IGNORECASE)
_BOL_CODE = re.compile(r"\b[A-Z]{2,8}-BOL-\d+\b", re.IGNORECASE)
_BOL_LABELED = re.compile(r"\bBOL[\s:#-]+([A-Z0-9]+(?:-[A-Z0-9]+)*)\b", re.IGNORECASE)
_PO = re.compile(r"\bPO-\d+\b", re.IGNORECASE)
_LOAD = re.compile(r"\bLL-\d+\b", re.IGNORECASE)
_LOAD_LABELED = re.compile(r"\bload(?:\s+id)?[\s:#-]+([A-Z]{1,6}-\d+)\b", re.IGNORECASE)
_PLATE = re.compile(
    r"\b(?:plate|plates|placa|placas|license plate)\s*[#:]?\s*([A-Z0-9]{2,8}(?:-[A-Z0-9]{1,8})*)\b",
    re.IGNORECASE,
)
_ROLE = re.compile(
    r"(?:this is|i am|i'm|im|soy|habla)\s+(?:the\s+|el\s+|la\s+)?([A-Za-zÁÉÍÓÚáéíóúñ]+)"
    r"|^(shipper|consignee|broker|carrier|driver|conductor|chofer|embarcador|transportista)\b"
    r"|\b(shipper|consignee|broker|carrier|driver)\s+here\b"
    r"|\bfrom the\s+(shipper|consignee|broker|carrier|driver)\b",
    re.IGNORECASE | re.MULTILINE,
)
_SAME = re.compile(
    r"mismas instrucciones|same instructions|same as before|igual que antes|lo mismo que antes"
    r"|use again the link|usa (?:otra vez )?el link|usar el link",
    re.IGNORECASE,
)
_DOC = re.compile(
    r"\b(?:send|resend|need|m[aá]ndame|env[ií]a(?:me)?|following up)\b.{0,50}\b(?:pod|paperwork|proof of delivery|documento|bol photo)\b"
    r"|\bsigned pod\b"
    r"|\bbol photo\b"
    r"|\b(?:pod|paperwork)\b.{0,40}\b(?:please|pls|resend|full page|scan)\b",
    re.IGNORECASE | re.DOTALL,
)
_DRIVER = re.compile(
    r"\b(?:llegu[eé]|estoy en|en puerta|esperando|ya cargando|cargado|vac[ií]o|checked in|check-in|i'm here|i am here|im here|at the gate|ya empezaron)\b",
    re.IGNORECASE,
)
_STATUS = re.compile(
    r"\b(?:status|estatus|where is|where'?s|d[oó]nde est[aá]|any update|what time|is there a problem|confirm status)\b"
    r"|^\s*\?\s*$",
    re.IGNORECASE,
)
_TRACK = re.compile(
    r"\b(?:track|tracking|keep track|rastre\w*|sigu[ea]|follow|av[ií]same|tell me|let me know|report)\b",
    re.IGNORECASE,
)
_ARRIVE = re.compile(
    r"(?:tell me (?:once|when)|let me know when|av[ií]same cuando|cuando|when)\s+"
    r"(?:[^\s.]+\s+){0,6}?"
    r"(?:gets to|reaches|arrives?(?:\s+at|\s+in)?|llegue a|llega a)\s+"
    r"(.+)",
    re.IGNORECASE,
)
_LEAVE = re.compile(
    r"(?:tell me when|let me know when|av[ií]same cuando|cuando|when)\s+"
    r"(?:(?:it(?:'s| is)?|the (?:unit|truck|container|shipment)|el cami[oó]n|la unidad)\s+)?"
    r"(?:is\s+|gets\s+)?"
    r"(?:out of|leaves|leave|salga del|sale del|salga de|sale de)\s+"
    r"(?:the\s+|el\s+|la\s+)?"
    r"(.+)",
    re.IGNORECASE,
)
_EVERY = re.compile(
    r"(?:every|each|cada)\s+(\d+|one|una|un|two|dos|three|tres|four|cuatro)\s*(?:hours|hrs|horas)\b",
    re.IGNORECASE,
)
_NUM = {
    "one": 1,
    "una": 1,
    "un": 1,
    "two": 2,
    "dos": 2,
    "three": 3,
    "tres": 3,
    "four": 4,
    "cuatro": 4,
}
_ROLE_MAP = {
    "shipper": "shipper",
    "embarcador": "shipper",
    "consignee": "consignee",
    "consignatario": "consignee",
    "destinatario": "consignee",
    "broker": "broker",
    "carrier": "carrier",
    "transportista": "carrier",
    "driver": "driver",
    "conductor": "driver",
    "chofer": "driver",
}


@dataclass(frozen=True)
class Identifier:
    kind: str
    value: str


@dataclass(frozen=True)
class Condition:
    """When to speak up. One trigger: arrive_at, leave_terminal, or interval_hours."""

    trigger: str
    city: str | None = None
    place: str | None = None
    interval_hours: int | None = None


@dataclass(frozen=True)
class TrackRequest:
    role: str | None
    kind: str | None
    value: str | None
    intent: str
    identifiers: tuple[Identifier, ...]
    condition: Condition | None
    same_instructions: bool
    text: str

    def to_dict(self) -> dict:
        condition = None
        if self.condition is not None:
            condition = {
                "trigger": self.condition.trigger,
                "city": self.condition.city,
                "place": self.condition.place,
                "interval_hours": self.condition.interval_hours,
            }
        return {
            "role": self.role,
            "kind": self.kind,
            "value": self.value,
            "intent": self.intent,
            "same_instructions": self.same_instructions,
            "identifiers": [{"kind": item.kind, "value": item.value} for item in self.identifiers],
            "condition": condition,
            "text": self.text,
        }


def parse_request(text: str) -> TrackRequest:
    """One free-text ask from a shipper, consignee, broker, carrier, or driver."""
    raw = " ".join(text.split())
    if not raw:
        raise ValueError("could not read a tracking request")
    identifiers = _identifiers(text)
    condition = _condition(text)
    same = _SAME.search(text) is not None
    intent = _intent(text, condition=condition, same=same, has_id=bool(identifiers))
    kind = identifiers[0].kind if identifiers else None
    value = identifiers[0].value if identifiers else None
    return TrackRequest(
        role=_role(text),
        kind=kind,
        value=value,
        intent=intent,
        identifiers=identifiers,
        condition=condition,
        same_instructions=same,
        text=raw,
    )


def carry_forward(previous: TrackRequest, current: TrackRequest) -> TrackRequest:
    """'Same instructions' keeps the earlier condition and adds whatever is new."""
    if not current.same_instructions or current.condition is not None:
        return current
    return TrackRequest(
        role=current.role or previous.role,
        kind=current.kind,
        value=current.value,
        intent=current.intent,
        identifiers=current.identifiers or previous.identifiers,
        condition=previous.condition,
        same_instructions=True,
        text=current.text,
    )


def _role(text: str) -> str | None:
    match = _ROLE.search(text)
    if match is None:
        return None
    word = next(group for group in match.groups() if group).lower()
    return _ROLE_MAP.get(word)


def _intent(text: str, *, condition: Condition | None, same: bool, has_id: bool) -> str:
    if _DOC.search(text):
        return "doc_request"
    if condition is not None:
        return "track"
    if same:
        return "same_instructions"
    if _DRIVER.search(text) and _STATUS.search(text) is None:
        return "driver_report"
    if _STATUS.search(text):
        return "status"
    if _TRACK.search(text) or has_id:
        return "track"
    raise ValueError("could not read a tracking request")


def _condition(text: str) -> Condition | None:
    found: list[tuple[int, Condition]] = []
    leave = _LEAVE.search(text)
    if leave is not None:
        place = _clip(leave.group(1))
        if place:
            found.append((leave.start(), Condition(trigger="leave_terminal", place=place)))
    arrive = _ARRIVE.search(text)
    if arrive is not None:
        place = _clip(arrive.group(1))
        if place:
            found.append(
                (
                    arrive.start(),
                    Condition(trigger="arrive_at", city=_city(place), place=place),
                )
            )
    every = _EVERY.search(text)
    if every is not None:
        found.append((every.start(), Condition(trigger="interval_hours", interval_hours=_hours(every.group(1)))))
    if not found:
        return None
    found.sort(key=lambda item: item[0])
    return found[0][1]


def _hours(token: str) -> int:
    if token.isdigit():
        return int(token)
    return _NUM[token.lower()]


def _clip(raw: str) -> str:
    cut = re.split(r"\s+(?:send|and send|so)\b|[?\n]|[.,]", raw.strip(), maxsplit=1, flags=re.IGNORECASE)[0]
    return " ".join(cut.strip(" .,;:").split())


def _city(place: str) -> str | None:
    match = re.search(r"\bin\s+([A-Za-z][A-Za-z.'-]{1,40})\s*$", place)
    if match:
        return match.group(1)
    words = place.split()
    if len(words) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z.'-]{1,40}", words[0]):
        return words[0]
    return None


def _identifiers(text: str) -> tuple[Identifier, ...]:
    found: list[tuple[int, int, Identifier]] = []
    spans: list[tuple[int, int]] = []
    for match in _URL.finditer(text):
        url = match.group(0).rstrip(".,);>")
        found.append((match.start(), 0, Identifier(_url_kind(url), url)))
        for offset, ident in enumerate(_ids_in_url(url), start=1):
            found.append((match.start(), offset, ident))
        spans.append((match.start(), match.end()))
    scanners: tuple[tuple[re.Pattern[str], str, int], ...] = (
        (_CONTAINER, "container", 0),
        (_PRO_CODE, "pro", 0),
        (_PRO_LABELED, "pro", 1),
        (_BOL_CODE, "bol", 0),
        (_BOL_LABELED, "bol", 1),
        (_PO, "po", 0),
        (_LOAD, "load_id", 0),
        (_LOAD_LABELED, "load_id", 1),
        (_PLATE, "plate", 1),
    )
    for pattern, kind, group in scanners:
        for match in pattern.finditer(text):
            if _inside(match.start(), spans):
                continue
            value = match.group(group).upper()
            if not any(ch.isdigit() for ch in value):
                continue
            found.append((match.start(), 0, Identifier(kind, value)))
    found.sort(key=lambda item: (item[0], item[1]))
    seen: set[tuple[str, str]] = set()
    ordered: list[Identifier] = []
    for _, _, ident in found:
        key = (ident.kind, ident.value if ident.kind in ("url", "gps_share_link") else ident.value.upper())
        if key in seen:
            continue
        seen.add(key)
        ordered.append(ident)
    return tuple(ordered)


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _url_kind(url: str) -> str:
    low = url.lower()
    if "/fleet/live" in low or "/gps" in low or "share=" in low:
        return "gps_share_link"
    return "url"


def _ids_in_url(url: str) -> list[Identifier]:
    found: list[Identifier] = []
    query = parse_qs(urlsplit(url).query)
    for key, kind in (("pro", "pro"), ("bol", "bol"), ("po", "po")):
        values = query.get(key) or []
        if values and values[0].strip() and any(ch.isdigit() for ch in values[0]):
            found.append(Identifier(kind, values[0].strip().upper()))
    for match in _CONTAINER.finditer(url):
        found.append(Identifier("container", match.group(0).upper()))
    for match in _PRO_CODE.finditer(url):
        found.append(Identifier("pro", match.group(0).upper()))
    for match in _BOL_CODE.finditer(url):
        found.append(Identifier("bol", match.group(0).upper()))
    return found
