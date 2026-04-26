"""RADIO_ERP1 (packet type 0x01) parser/builder.

Per §2.1.1 the Data field carries:

    | RORG | DB(N..0) | SenderID[4 BE] | Status |

and the OptData field carries (when present, §2.1.1):

    | SubTelNum | DestinationID[4 BE] | dBm (uint8) | SecurityLevel |
"""

from __future__ import annotations

from dataclasses import dataclass

from .framing import Frame, encode_frame
from .packets import PacketType


@dataclass(frozen=True)
class Erp1:
    rorg: int
    payload: bytes                  # data bytes between RORG and SenderID (DB(N..0))
    sender_id: int                  # 32-bit big-endian
    status: int

    sub_tel: int | None = None
    destination_id: int | None = None
    dbm: int | None = None          # negative dBm (per §2.1.1: u8 of |dBm|)
    security_level: int | None = None


def parse_erp1(frame: Frame) -> Erp1:
    if frame.packet_type != PacketType.RADIO_ERP1:
        raise ValueError(f"not an ERP1 frame: type={frame.packet_type:#x}")
    if len(frame.data) < 1 + 4 + 1:
        raise ValueError(f"ERP1 data too short: {len(frame.data)} bytes")

    rorg = frame.data[0]
    payload = frame.data[1:-5]
    sender_id = int.from_bytes(frame.data[-5:-1], "big")
    status = frame.data[-1]

    sub_tel = destination_id = dbm = security = None
    opt = frame.opt
    if len(opt) >= 7:
        sub_tel = opt[0]
        destination_id = int.from_bytes(opt[1:5], "big")
        # ESP3 reports the absolute value; surface it as a negative dBm so
        # downstream code does not have to remember the convention.
        dbm = -opt[5]
        security = opt[6]

    return Erp1(
        rorg=rorg,
        payload=payload,
        sender_id=sender_id,
        status=status,
        sub_tel=sub_tel,
        destination_id=destination_id,
        dbm=dbm,
        security_level=security,
    )


def build_erp1(
    rorg: int,
    payload: bytes,
    sender_id: int,
    status: int = 0,
    *,
    sub_tel: int = 3,
    destination_id: int = 0xFFFFFFFF,
    dbm: int = 0xFF,                # 0xFF = "send case" per §2.1.1
    security_level: int = 0,
) -> bytes:
    """Build a TX-ready ERP1 frame as raw bytes (sync + header + … + CRCs)."""
    if not 0 <= sender_id <= 0xFFFFFFFF:
        raise ValueError(f"sender_id out of range: {sender_id:#x}")
    if not 0 <= destination_id <= 0xFFFFFFFF:
        raise ValueError(f"destination_id out of range: {destination_id:#x}")

    data = (
        bytes((rorg,))
        + payload
        + sender_id.to_bytes(4, "big")
        + bytes((status,))
    )
    opt = (
        bytes((sub_tel,))
        + destination_id.to_bytes(4, "big")
        + bytes((dbm & 0xFF, security_level & 0xFF))
    )
    return encode_frame(PacketType.RADIO_ERP1, data, opt)


# RORG-specific helpers ------------------------------------------------------

def is_4bs_teach_in(erp1: Erp1) -> bool:
    """4BS teach-in is signalled by LRN bit (DB0 bit 3) being 0 (§EEP A5)."""
    if erp1.rorg != 0xA5 or len(erp1.payload) < 4:
        return False
    return (erp1.payload[3] & 0x08) == 0


def is_1bs_teach_in(erp1: Erp1) -> bool:
    """1BS teach-in: DB0 bit 3 = 0 (§EEP D5)."""
    if erp1.rorg != 0xD5 or len(erp1.payload) < 1:
        return False
    return (erp1.payload[0] & 0x08) == 0
