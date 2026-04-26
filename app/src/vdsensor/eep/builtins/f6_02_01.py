"""EEP F6-02-01 — Light & blind, 2 rocker switches (RPS).

RPS has only 1 data byte + a status byte. The interpretation depends on the
T21 (status bit 5) and NU (status bit 4) flags:

  NU=1  → "rocker action" event; data byte encodes which rocker + which side.
  NU=0  → "energy bow released" event; treat as a release.

For v1 we surface a coarse `action` string and the raw 8-bit code so HA users
can build automations against it. A rocker is *not* a sensor in HA's sense; it
is exposed as `device_automation` triggers in M4's discovery layer.
"""

from __future__ import annotations

from ...esp3.radio import Erp1
from ..decoder import DecodedPoint

_ACTIONS = {
    0x10: "AI",   # rocker A, lower (I)
    0x30: "A0",   # rocker A, upper (0)
    0x50: "BI",   # rocker B, lower
    0x70: "B0",   # rocker B, upper
}


def decode(erp1: Erp1) -> list[DecodedPoint]:
    if not erp1.payload:
        return []
    db0 = erp1.payload[0]
    nu = (erp1.status >> 4) & 0x01
    if nu == 0:
        action = "released"
    else:
        action = _ACTIONS.get(db0 & 0xF0, f"raw_{db0:02x}")
    return [
        DecodedPoint("action", action, None, None, None),
        DecodedPoint("raw", f"0x{db0:02x}", None, None, None),
    ]
