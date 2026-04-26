"""EEP A5-02-05 — Temperature sensor, range 0..40 °C.

4BS payload layout (DB3, DB2, DB1, DB0):
  DB3 = unused
  DB2 = unused
  DB1 = temperature byte; linear 255 → 0 °C, 0 → 40 °C  (note the inversion)
  DB0 = bit 3 = LRN (0 teach-in, 1 data); bit 1 ignored at decode time
"""

from __future__ import annotations

from ...esp3.radio import Erp1
from ..decoder import DecodedPoint


def decode(erp1: Erp1) -> list[DecodedPoint]:
    if len(erp1.payload) < 4:
        return []
    db1 = erp1.payload[2]
    temp_c = round(40.0 - (db1 / 255.0) * 40.0, 1)
    return [DecodedPoint("temperature", temp_c, "°C", "temperature", "measurement")]
