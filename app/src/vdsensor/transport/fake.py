"""FakeSerialLink — synthesises ESP3 traffic for dev iteration without hardware.

Acts like a `SerialLink` but never opens a real port. Behaviour:

  - Responds to the four COMMON_COMMANDs we emit (CO_WR_RESET, CO_RD_VERSION,
    CO_RD_IDBASE, CO_WR_LEARNMODE) with synthetic RESPONSE frames.
  - Periodically emits ERP1 telegrams rotating through RPS / 1BS / 4BS / VLD
    so the live inspector and any future EEP decoding has data to chew on.

Anything Controller doesn't recognise still gets a RET_OK so a stray cmd
doesn't deadlock `request()`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from ..esp3.framing import Frame, FrameDecoder, encode_frame
from ..esp3.packets import CommonCommand, PacketType, ReturnCode
from ..esp3.radio import build_erp1
from .link import Link

logger = logging.getLogger(__name__)


def _resp_ok(opt: bytes = b"") -> bytes:
    return encode_frame(PacketType.RESPONSE, bytes((ReturnCode.RET_OK,)), opt)


def _resp_version() -> bytes:
    payload = (
        bytes((ReturnCode.RET_OK,))
        + bytes((9, 9, 9, 9))                   # app version
        + bytes((9, 9, 9, 9))                   # api version
        + (0xFAFA0001).to_bytes(4, "big")       # chip id
        + (0x00000001).to_bytes(4, "big")       # device version
        + b"FAKE_GATEWAY\x00\x00\x00\x00"       # 16 bytes ASCII
    )
    return encode_frame(PacketType.RESPONSE, payload)


def _resp_idbase() -> bytes:
    # Base ID inside the spec-permitted range, 5 remaining writes.
    return encode_frame(
        PacketType.RESPONSE,
        bytes((ReturnCode.RET_OK,)) + (0xFFAA0000).to_bytes(4, "big"),
        opt=bytes((5,)),
    )


# Rotating telegram fixtures — one per RORG family we care about in v1.
_ROTATION: list[tuple[int, bytes, int, int]] = [
    # rorg,  payload,                sender_id,    status
    (0xF6, b"\x50",                   0x12345670, 0x30),  # RPS rocker
    (0xD5, b"\x09",                   0x12345671, 0x00),  # 1BS contact (LRN=1, closed)
    (0xA5, b"\x00\x00\x80\x08",       0x12345672, 0x00),  # 4BS data telegram
    (0xD2, b"\x01\x02\x03",           0x12345673, 0x00),  # VLD
]


class FakeSerialLink:
    """Drop-in replacement for SerialLink that talks to itself."""

    def __init__(self, telegram_period: float = 1.0) -> None:
        self._period = telegram_period
        self._port = "fake://"
        self._connected = asyncio.Event()
        self._out: asyncio.Queue[bytes] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._tx_decoder = FrameDecoder()       # decodes whatever the controller writes

    @property
    def port(self) -> str:
        return self._port

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @asynccontextmanager
    async def run(self) -> AsyncIterator[Link]:
        self._connected.set()
        self._task = asyncio.create_task(self._emit_loop(), name="fake-emit")
        try:
            yield self
        finally:
            if self._task is not None:
                self._task.cancel()
                try:
                    await self._task
                except (asyncio.CancelledError, Exception):
                    pass
            self._connected.clear()

    async def read(self) -> bytes:
        return await self._out.get()

    async def write(self, data: bytes) -> None:
        # The controller writes complete frames, but be defensive: feed and respond
        # to whatever frames arrive.
        for frame in self._tx_decoder.feed(data):
            self._out.put_nowait(self._respond(frame))

    # ---- internals --------------------------------------------------------

    def _respond(self, frame: Frame) -> bytes:
        if frame.packet_type == PacketType.COMMON_COMMAND and frame.data:
            cmd = frame.data[0]
            if cmd == CommonCommand.CO_RD_VERSION:
                return _resp_version()
            if cmd == CommonCommand.CO_RD_IDBASE:
                return _resp_idbase()
            # CO_WR_RESET / CO_WR_LEARNMODE / anything else → just OK
            return _resp_ok()
        # Non-command frames (e.g. RADIO_ERP1 we sent ourselves) — ignore.
        logger.debug("fake: ignoring outbound frame type=%#x", frame.packet_type)
        return _resp_ok()

    async def _emit_loop(self) -> None:
        i = 0
        while True:
            await asyncio.sleep(self._period)
            rorg, payload, sender_id, status = _ROTATION[i % len(_ROTATION)]
            try:
                self._out.put_nowait(
                    build_erp1(rorg, payload, sender_id=sender_id, status=status)
                )
            except asyncio.QueueFull:
                pass
            i += 1
