"""EEP A5-07-01 — Occupancy (PIR) sensor with supply voltage.

DB3 = supply voltage   (0..250 ⇒ 0..5.0 V)
DB2 = unused
DB1 = PIR status       (≥128 → motion detected)
DB0 = LRN bit
"""

from __future__ import annotations

from ...esp3.radio import Erp1
from ..decoder import DecodedPoint


def decode(erp1: Erp1) -> list[DecodedPoint]:
    if len(erp1.payload) < 4:
        return []
    db3, db1 = erp1.payload[0], erp1.payload[2]
    voltage = round((db3 / 250.0) * 5.0, 2)
    motion = db1 >= 128
    return [
        DecodedPoint("motion", motion, None, "motion", None),
        DecodedPoint("voltage", voltage, "V", "voltage", "measurement"),
    ]
