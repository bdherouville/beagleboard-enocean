"""Database lifecycle: open engine, apply schema, run periodic ringbuffer GC."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

logger = logging.getLogger(__name__)


class Database:
    """Owns the async engine + session factory + ringbuffer GC."""

    def __init__(self, url: str, *, telegram_ring_size: int = 10_000) -> None:
        self._url = url
        self._ring = telegram_ring_size
        self._engine = create_async_engine(url, future=True)
        self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)
        self._gc_task: asyncio.Task[None] | None = None

    @property
    def url(self) -> str:
        return self._url

    def session(self) -> AsyncSession:
        return self._sessionmaker()

    async def setup(self) -> None:
        """Apply schema (idempotent) and enable WAL."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            if self._url.startswith("sqlite"):
                # WAL gives us concurrent readers + a single writer with crash-safe
                # appends — what we want for a write-heavy ringbuffer.
                await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
                await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")

    @asynccontextmanager
    async def run(self) -> AsyncIterator[Database]:
        await self.setup()
        self._gc_task = asyncio.create_task(self._gc_loop(), name="telegram-gc")
        try:
            yield self
        finally:
            if self._gc_task is not None:
                self._gc_task.cancel()
                try:
                    await self._gc_task
                except (asyncio.CancelledError, Exception):
                    pass
            await self._engine.dispose()

    async def _gc_loop(self, period_s: float = 300.0) -> None:
        """Trim the telegrams table down to the configured ring size every 5 min."""
        try:
            while True:
                await asyncio.sleep(period_s)
                try:
                    async with self.session() as s, s.begin():
                        await s.execute(
                            text(
                                "DELETE FROM telegrams WHERE id NOT IN ("
                                "  SELECT id FROM telegrams ORDER BY id DESC LIMIT :n"
                                ")"
                            ),
                            {"n": self._ring},
                        )
                except Exception as e:
                    logger.warning("telegram GC failed: %s", e)
        except asyncio.CancelledError:
            return
