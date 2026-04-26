"""Link Protocol — what `Controller` needs from the underlying transport.

Both `SerialLink` (real UART) and `FakeSerialLink` (synthetic source for dev
iteration without hardware) satisfy this surface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Protocol


class Link(Protocol):
    @property
    def port(self) -> str: ...

    @property
    def is_connected(self) -> bool: ...

    def run(self) -> AbstractAsyncContextManager[Link]:
        """Open the link, keep it open, close on exit."""
        ...

    async def read(self) -> bytes:
        """Block until at least one byte is available, then return a chunk."""
        ...

    async def write(self, data: bytes) -> None:
        """Send a complete ESP3 frame."""
        ...


# Re-export AsyncIterator just to silence a lint warning if a downstream module
# wants to type a generator using this Protocol.
__all__ = ["Link", "AsyncIterator"]
