"""ESP3 controller: the only thing that touches the serial port.

Owns a FrameDecoder, dispatches incoming frames to:
  - the awaiter of an in-flight COMMAND/RESPONSE round-trip,
  - subscribers to the radio-telegram fan-out (`subscribe()`),
  - subscribers to gateway events (`subscribe_events()`).

Exposes `request()` to send a COMMON_COMMAND/RADIO_ERP1 and await its RESPONSE,
and `open_learn_window()` for the pairing wizard.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from ..esp3 import common_command as cc
from ..esp3.events import Event, parse_event
from ..esp3.framing import Frame, FrameDecoder, encode_frame
from ..esp3.packets import EventCode, PacketType
from ..esp3.radio import Erp1, parse_erp1
from ..esp3.response import Response, parse_response
from .link import Link
from .serial_link import SerialLink

logger = logging.getLogger(__name__)


class CommandTimeout(RuntimeError):
    """A request was sent but no RESPONSE arrived within the deadline."""


@dataclass
class GatewayInfo:
    version: cc.VersionInfo | None = None
    idbase: cc.IdBaseInfo | None = None
    learn_mode: bool = False


class Controller:
    def __init__(self, link: Link) -> None:
        self._link = link
        self._decoder = FrameDecoder()
        self._reader_task: asyncio.Task[None] | None = None
        self._tx_lock = asyncio.Lock()
        self._pending_response: asyncio.Future[Response] | None = None
        self._erp1_subs: set[asyncio.Queue[Erp1]] = set()
        self._event_subs: set[asyncio.Queue[Event]] = set()
        self._info = GatewayInfo()

    @classmethod
    def from_serial(cls, port: str, baudrate: int = 57600) -> Controller:
        return cls(SerialLink(port=port, baudrate=baudrate))

    @property
    def link(self) -> Link:
        return self._link

    @property
    def info(self) -> GatewayInfo:
        return self._info

    @asynccontextmanager
    async def run(self) -> AsyncIterator[Controller]:
        async with self._link.run():
            self._reader_task = asyncio.create_task(self._reader_loop(), name="esp3-reader")
            try:
                yield self
            finally:
                if self._reader_task is not None:
                    self._reader_task.cancel()
                    try:
                        await self._reader_task
                    except (asyncio.CancelledError, Exception):
                        pass

    # ---- public surface ---------------------------------------------------

    async def request(
        self, frame_bytes: bytes, deadline: float = 1.0
    ) -> Response:
        """Send a pre-encoded frame and await the next RESPONSE packet."""
        async with self._tx_lock:
            loop = asyncio.get_running_loop()
            self._pending_response = loop.create_future()
            await self._link.write(frame_bytes)
            try:
                async with asyncio.timeout(deadline):
                    return await self._pending_response
            except TimeoutError as e:
                raise CommandTimeout("no RESPONSE within deadline") from e
            finally:
                self._pending_response = None

    async def reset(self) -> Response:
        return await self.request(cc.cmd_co_wr_reset())

    async def read_version(self) -> cc.VersionInfo:
        resp = await self.request(cc.cmd_co_rd_version())
        if not resp.ok:
            raise RuntimeError(f"CO_RD_VERSION failed: {resp.return_code:#x}")
        info = cc.parse_version_response(resp)
        self._info.version = info
        return info

    async def read_idbase(self) -> cc.IdBaseInfo:
        resp = await self.request(cc.cmd_co_rd_idbase())
        if not resp.ok:
            raise RuntimeError(f"CO_RD_IDBASE failed: {resp.return_code:#x}")
        info = cc.parse_idbase_response(resp)
        self._info.idbase = info
        return info

    async def set_learn_mode(self, enable: bool, timeout_ms: int = 60_000) -> None:
        resp = await self.request(cc.cmd_co_wr_learnmode(enable, timeout_ms))
        if not resp.ok:
            raise RuntimeError(f"CO_WR_LEARNMODE({enable}) failed: {resp.return_code:#x}")
        self._info.learn_mode = enable

    def subscribe(self, *, maxsize: int = 256) -> _Subscription[Erp1]:
        return _Subscription(self._erp1_subs, asyncio.Queue(maxsize=maxsize))

    def subscribe_events(self, *, maxsize: int = 64) -> _Subscription[Event]:
        return _Subscription(self._event_subs, asyncio.Queue(maxsize=maxsize))

    @asynccontextmanager
    async def open_learn_window(
        self, timeout_ms: int = 60_000
    ) -> AsyncIterator[asyncio.Queue[Erp1]]:
        """Enable learn mode, yield a queue of ERP1 telegrams seen during the window.

        The window closes either when the caller exits the context, when the
        chip emits CO_LRN_MODE_DISABLED, or when `timeout_ms` elapses.
        """
        await self.set_learn_mode(True, timeout_ms)
        sub = self.subscribe()
        evsub = self.subscribe_events()

        async def _watch_close() -> None:
            try:
                async with evsub as evq:
                    while True:
                        ev = await evq.get()
                        if ev.event_code == EventCode.CO_LRN_MODE_DISABLED:
                            self._info.learn_mode = False
                            return
            except asyncio.CancelledError:
                return

        watcher = asyncio.create_task(_watch_close(), name="learnmode-watcher")
        try:
            async with sub as q:
                yield q
        finally:
            watcher.cancel()
            try:
                await watcher
            except (asyncio.CancelledError, Exception):
                pass
            try:
                await self.set_learn_mode(False, 0)
            except Exception as e:
                logger.warning("failed to stop learn mode cleanly: %s", e)

    # ---- internals --------------------------------------------------------

    async def _reader_loop(self) -> None:
        try:
            while True:
                chunk = await self._link.read()
                for frame in self._decoder.feed(chunk):
                    self._dispatch(frame)
        except asyncio.CancelledError:
            return

    def _dispatch(self, frame: Frame) -> None:
        if frame.packet_type == PacketType.RESPONSE:
            try:
                resp = parse_response(frame)
            except Exception as e:
                logger.warning("malformed RESPONSE: %s", e)
                return
            fut = self._pending_response
            if fut is not None and not fut.done():
                fut.set_result(resp)
            return

        if frame.packet_type == PacketType.RADIO_ERP1:
            try:
                erp1 = parse_erp1(frame)
            except Exception as e:
                logger.warning("malformed ERP1: %s", e)
                return
            _broadcast(self._erp1_subs, erp1)
            return

        if frame.packet_type == PacketType.EVENT:
            try:
                ev = parse_event(frame)
            except Exception as e:
                logger.warning("malformed EVENT: %s", e)
                return
            _broadcast(self._event_subs, ev)
            return

        logger.debug("unhandled packet type %#x (%d data, %d opt)",
                     frame.packet_type, len(frame.data), len(frame.opt))


# ---- subscription helper ---------------------------------------------------


@dataclass
class _Subscription[T]:
    _registry: set[asyncio.Queue[T]]
    queue: asyncio.Queue[T] = field(repr=False)

    async def __aenter__(self) -> asyncio.Queue[T]:
        self._registry.add(self.queue)
        return self.queue

    async def __aexit__(self, *exc: object) -> None:
        self._registry.discard(self.queue)


def _broadcast[T](subs: set[asyncio.Queue[T]], item: T) -> None:
    for q in list(subs):
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            # Slow consumer — drop oldest, then push. This keeps the live
            # inspector from blocking the reader loop on a stalled WebSocket.
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                pass


# Re-export so callers can `from vdsensor.transport.controller import encode_frame` if needed.
__all__ = ["Controller", "GatewayInfo", "CommandTimeout", "encode_frame"]
