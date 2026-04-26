"""Builders + response parsers for the four COMMON_COMMAND codes used in v1.

Only what we actually need on the request path is exposed:

  - CO_WR_RESET     §2.5.4  (1-byte data, no opt)
  - CO_RD_VERSION   §2.5.5  (1-byte data, no opt) → 32-byte response payload
  - CO_RD_IDBASE    §2.5.10 (1-byte data, no opt) → 4-byte ID + 1 opt remaining-writes
  - CO_WR_LEARNMODE §2.5.25 (6-byte data + 1 opt channel)
"""

from __future__ import annotations

from dataclasses import dataclass

from .framing import encode_frame
from .packets import CommonCommand, PacketType
from .response import Response

# --- request builders -------------------------------------------------------


def cmd_co_wr_reset() -> bytes:
    return encode_frame(PacketType.COMMON_COMMAND, bytes((CommonCommand.CO_WR_RESET,)))


def cmd_co_rd_version() -> bytes:
    return encode_frame(PacketType.COMMON_COMMAND, bytes((CommonCommand.CO_RD_VERSION,)))


def cmd_co_rd_idbase() -> bytes:
    return encode_frame(PacketType.COMMON_COMMAND, bytes((CommonCommand.CO_RD_IDBASE,)))


def cmd_co_wr_learnmode(enable: bool, timeout_ms: int = 60_000, channel: int = 0xFF) -> bytes:
    """Toggle the chip's classic learn mode (§2.5.25).

    timeout_ms = 0 lets the chip use its default 60 s window.
    channel    = 0xFF (next relative) is the safe default for non-channel-aware devices.
    """
    if not 0 <= timeout_ms <= 0xFFFFFFFF:
        raise ValueError(f"timeout_ms out of range: {timeout_ms}")
    data = (
        bytes((CommonCommand.CO_WR_LEARNMODE, 0x01 if enable else 0x00))
        + timeout_ms.to_bytes(4, "big")
    )
    opt = bytes((channel & 0xFF,))
    return encode_frame(PacketType.COMMON_COMMAND, data, opt)


# --- response parsers (called only when caller knows which command preceded) -


@dataclass(frozen=True)
class VersionInfo:
    app_version: tuple[int, int, int, int]      # main, beta, alpha, build
    api_version: tuple[int, int, int, int]
    chip_id: int                                # EURID
    chip_version: int
    description: str                            # 16-byte ASCII, null-trimmed


def parse_version_response(resp: Response) -> VersionInfo:
    """Decode the 32-byte payload returned after a CO_RD_VERSION request."""
    p = resp.payload
    if len(p) < 32:
        raise ValueError(f"CO_RD_VERSION response payload too short: {len(p)}")
    return VersionInfo(
        app_version=tuple(p[0:4]),              # type: ignore[arg-type]
        api_version=tuple(p[4:8]),              # type: ignore[arg-type]
        chip_id=int.from_bytes(p[8:12], "big"),
        chip_version=int.from_bytes(p[12:16], "big"),
        description=p[16:32].split(b"\x00", 1)[0].decode("ascii", "replace"),
    )


@dataclass(frozen=True)
class IdBaseInfo:
    base_id: int                                # 32-bit base address
    remaining_writes: int                       # 0..0xFE; 0xFF = unlimited


def parse_idbase_response(resp: Response) -> IdBaseInfo:
    """Decode the response to CO_RD_IDBASE (§2.5.10)."""
    if len(resp.payload) < 4:
        raise ValueError(f"CO_RD_IDBASE response payload too short: {len(resp.payload)}")
    base = int.from_bytes(resp.payload[:4], "big")
    remaining = resp.opt[0] if resp.opt else 0xFF
    return IdBaseInfo(base_id=base, remaining_writes=remaining)
