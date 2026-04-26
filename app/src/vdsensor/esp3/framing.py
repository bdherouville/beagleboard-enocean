"""ESP3 frame encoder + streaming decoder.

Layout (§1.7 / §3.4.1):

    | 0x55 | DataLen[2 BE] | OptLen[1] | Type[1] | CRC8H | Data | OptData | CRC8D |

CRC8H is computed over the 4 header bytes; CRC8D over Data || OptData. Both use
the same polynomial (see crc8.py).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass

from .crc8 import crc8
from .packets import HEADER_LENGTH, SYNC_BYTE


@dataclass(frozen=True)
class Frame:
    """A successfully decoded ESP3 frame."""

    packet_type: int
    data: bytes
    opt: bytes


def encode_frame(packet_type: int, data: bytes, opt: bytes = b"") -> bytes:
    """Encode an ESP3 frame ready for the wire.

    Mirrors the structure described in §3.4.3. Caller supplies packet_type and
    payload; this function fills in lengths and both CRCs.
    """
    if not 0 <= packet_type <= 0xFF:
        raise ValueError(f"packet_type out of range: {packet_type:#x}")
    data_len = len(data)
    opt_len = len(opt)
    if data_len > 0xFFFF:
        raise ValueError(f"data too long: {data_len} bytes (max 65535)")
    if opt_len > 0xFF:
        raise ValueError(f"opt too long: {opt_len} bytes (max 255)")

    header = bytes((data_len >> 8, data_len & 0xFF, opt_len, packet_type))
    body = data + opt
    return bytes((SYNC_BYTE,)) + header + bytes((crc8(header),)) + body + bytes((crc8(body),))


class FrameDecoder:
    """Streaming decoder. Feed arbitrary chunks; yields complete frames.

    Implements the resynchronisation behaviour specified in §3.4.2: on a header
    CRC mismatch we discard the candidate sync byte and try again from the next
    byte in the buffer; on a data CRC mismatch we likewise drop the sync byte
    that started the bad frame.
    """

    def __init__(self) -> None:
        self._buf: deque[int] = deque()

    def feed(self, chunk: bytes) -> Iterator[Frame]:
        self._buf.extend(chunk)
        while True:
            # Drop until the next sync byte.
            while self._buf and self._buf[0] != SYNC_BYTE:
                self._buf.popleft()
            if len(self._buf) < 1 + HEADER_LENGTH + 1:
                return                          # need more header bytes

            b = list(self._buf)
            header = bytes(b[1 : 1 + HEADER_LENGTH])
            if crc8(header) != b[1 + HEADER_LENGTH]:
                self._buf.popleft()             # bogus header — drop sync, retry
                continue

            data_len = (header[0] << 8) | header[1]
            opt_len = header[2]
            packet_type = header[3]
            body_len = data_len + opt_len
            total = 1 + HEADER_LENGTH + 1 + body_len + 1
            if len(self._buf) < total:
                return                          # need more body bytes

            body = bytes(b[1 + HEADER_LENGTH + 1 : 1 + HEADER_LENGTH + 1 + body_len])
            if crc8(body) != b[total - 1]:
                self._buf.popleft()             # bad data CRC — drop sync, retry
                continue

            for _ in range(total):
                self._buf.popleft()
            yield Frame(packet_type=packet_type, data=body[:data_len], opt=body[data_len:])
