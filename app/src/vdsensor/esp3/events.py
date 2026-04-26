"""EVENT (packet type 0x04) parser (§2.4)."""

from __future__ import annotations

from dataclasses import dataclass

from .framing import Frame
from .packets import PacketType


@dataclass(frozen=True)
class Event:
    event_code: int
    payload: bytes                  # data bytes after the event code
    opt: bytes


def parse_event(frame: Frame) -> Event:
    if frame.packet_type != PacketType.EVENT:
        raise ValueError(f"not an EVENT frame: type={frame.packet_type:#x}")
    if not frame.data:
        raise ValueError("EVENT frame has empty data")
    return Event(event_code=frame.data[0], payload=frame.data[1:], opt=frame.opt)
