"""Async serial link with reconnect/backoff.

Wraps pyserial-asyncio in a small, opinionated API:

    link = SerialLink(port="/dev/ttyO4", baudrate=57600)
    async with link.run():
        await link.write(frame_bytes)
        chunk = await link.read()      # arbitrary chunk; blocks until bytes arrive

`run()` keeps the port open and reconnects on errors with exponential backoff
between 1 s and 30 s. While disconnected, `read()` and `write()` await
reconnection rather than raising.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class SerialLink:
    def __init__(self, port: str, baudrate: int = 57600) -> None:
        self._port = port
        self._baudrate = baudrate
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = asyncio.Event()
        self._disconnected = asyncio.Event()         # set when we observe a drop
        self._stop = asyncio.Event()
        self._supervisor_task: asyncio.Task[None] | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def port(self) -> str:
        return self._port

    @asynccontextmanager
    async def run(self) -> AsyncIterator[SerialLink]:
        """Open the port, keep it open, reconnect on error until the context exits."""
        self._stop.clear()
        self._supervisor_task = asyncio.create_task(self._supervise(), name="serial-supervisor")
        try:
            yield self
        finally:
            self._stop.set()
            self._close_streams()
            if self._supervisor_task is not None:
                self._supervisor_task.cancel()
                try:
                    await self._supervisor_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def write(self, data: bytes) -> None:
        await self._connected.wait()
        writer = self._writer
        if writer is None:                       # connection raced away
            return
        writer.write(data)
        await writer.drain()

    async def read(self) -> bytes:
        """Wait for any available bytes (does not assume frame boundaries)."""
        while True:
            await self._connected.wait()
            reader = self._reader
            if reader is None:
                continue
            try:
                chunk = await reader.read(256)
            except (ConnectionError, OSError) as e:
                logger.warning("serial read error: %s", e)
                self._mark_disconnected()
                continue
            if chunk == b"":
                self._mark_disconnected()
                continue
            return chunk

    # --- internals ---------------------------------------------------------

    async def _supervise(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                await self._open()
                logger.info("serial open: %s @ %d", self._port, self._baudrate)
                backoff = 1.0
                # Block until either side signals: a read/write observed a drop,
                # or the caller asked us to stop.
                stop_wait = asyncio.create_task(self._stop.wait())
                drop_wait = asyncio.create_task(self._disconnected.wait())
                done, pending = await asyncio.wait(
                    {stop_wait, drop_wait}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
                self._disconnected.clear()
            except (asyncio.CancelledError, Exception) as e:
                if isinstance(e, asyncio.CancelledError):
                    raise
                logger.warning("serial open failed (%s); retry in %.1fs", e, backoff)
                self._mark_disconnected()
                try:
                    async with asyncio.timeout(backoff):
                        await self._stop.wait()
                    return                       # stop requested while we waited
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)

    async def _open(self) -> None:
        # Imported here so that unit tests that exercise other modules don't
        # need pyserial-asyncio installed.
        import serial_asyncio  # type: ignore

        self._reader, self._writer = await serial_asyncio.open_serial_connection(
            url=self._port,
            baudrate=self._baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
        )
        self._connected.set()

    def _mark_disconnected(self) -> None:
        self._connected.clear()
        self._disconnected.set()
        self._close_streams()

    def _close_streams(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
        self._reader = None
        self._writer = None
