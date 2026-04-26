"""EEP A5-04-01 — Temperature + Humidity sensor.

DB3 = humidity   (0..200 ⇒ 0..100 %RH)
DB2 = temperature (0..250 ⇒ 0..40 °C)
DB1 = unused
DB0 = LRN bit + flags
"""

from __future__ import annotations

from ...esp3.radio import Erp1
from ..decoder import DecodedPoint


def decode(erp1: Erp1) -> list[DecodedPoint]:
    if len(erp1.payload) < 4:
        return []
    db3, db2 = erp1.payload[0], erp1.payload[1]
    humidity = round((db3 / 200.0) * 100.0, 1)
    temp_c = round((db2 / 250.0) * 40.0, 1)
    return [
        DecodedPoint("temperature", temp_c, "°C", "temperature", "measurement"),
        DecodedPoint("humidity", humidity, "%", "humidity", "measurement"),
    ]
