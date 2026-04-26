"""RESPONSE (packet type 0x02) parser (§2.2)."""

from __future__ import annotations

from dataclasses import dataclass

from .framing import Frame
from .packets import PacketType, ReturnCode


@dataclass(frozen=True)
class Response:
    return_code: int
    payload: bytes                  # any extra response bytes after the return code
    opt: bytes

    @property
    def ok(self) -> bool:
        return self.return_code == ReturnCode.RET_OK


def parse_response(frame: Frame) -> Response:
    if frame.packet_type != PacketType.RESPONSE:
        raise ValueError(f"not a RESPONSE frame: type={frame.packet_type:#x}")
    if not frame.data:
        raise ValueError("RESPONSE frame has empty data")
    return Response(return_code=frame.data[0], payload=frame.data[1:], opt=frame.opt)
