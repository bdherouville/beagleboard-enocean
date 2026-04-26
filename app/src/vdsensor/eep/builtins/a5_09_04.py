"""EEP A5-09-04 — CO₂ + temperature + humidity.

DB3 = humidity     (0..200 ⇒ 0..100 %RH)
DB2 = CO₂          (0..255 ⇒ 0..2550 ppm)
DB1 = temperature  (0..255 ⇒ 0..51 °C)
DB0 = flags + LRN bit (b1=H_Sen, b2=T_Sen, b3=LRN)

Variants exist; this is the most common revision shipped with current sensors.
"""

from __future__ import annotations

from ...esp3.radio import Erp1
from ..decoder import DecodedPoint


def decode(erp1: Erp1) -> list[DecodedPoint]:
    if len(erp1.payload) < 4:
        return []
    db3, db2, db1 = erp1.payload[0], erp1.payload[1], erp1.payload[2]
    humidity = round((db3 / 200.0) * 100.0, 1)
    co2 = round(db2 * 10.0, 0)
    temp_c = round((db1 / 255.0) * 51.0, 1)
    return [
        DecodedPoint("co2", int(co2), "ppm", "carbon_dioxide", "measurement"),
        DecodedPoint("temperature", temp_c, "°C", "temperature", "measurement"),
        DecodedPoint("humidity", humidity, "%", "humidity", "measurement"),
    ]
