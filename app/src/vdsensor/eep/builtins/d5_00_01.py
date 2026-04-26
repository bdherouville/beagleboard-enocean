"""EEP D5-00-01 — Single Input Contact (1BS magnet door/window sensor).

Data:  DB0 (1 byte)
  bit 0 = state           (0 = open, 1 = closed)
  bit 3 = LRN             (0 = teach-in, 1 = data telegram)
"""

from __future__ import annotations

from ...esp3.radio import Erp1
from ..decoder import DecodedPoint


def decode(erp1: Erp1) -> list[DecodedPoint]:
    if not erp1.payload:
        return []
    db0 = erp1.payload[0]
    closed = bool(db0 & 0x01)
    return [DecodedPoint("contact", closed, None, "door", None)]
