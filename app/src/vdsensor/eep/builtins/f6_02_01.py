"""EEP F6-02-01 — Light & Blind, 2 rocker switches (RPS/PTM200).

Decoding follows the standard PTM200 telegram convention:

  Status byte:
    bit 5 (T21) = 1 (PTM200)
    bit 4 (NU)  = 1 → "N message": DB0 encodes which rocker(s) and direction
                  0 → "U message": typically a release event, DB0 = 0

  When NU=1, DB0 layout:
    bits 7-5  R1   action of first rocker (0=AI, 1=AO, 2=BI, 3=BO)
    bit  4    EB   energy-bow / press flag (1 = pressed)
    bits 3-1  R2   second rocker action (only meaningful if SA=1)
    bit  0    SA   second-action flag (1 = R2 valid, 0 = ignore R2)

We surface four points so HA automations can match on whichever feels
natural:

    action          "pressed" | "released"
    button          "AI" | "AO" | "BI" | "BO" | ""    (empty on release)
    rocker          "A"  | "B"  | ""
    second_button   second simultaneous press, "" if SA=0
"""

from __future__ import annotations

from ...esp3.radio import Erp1
from ..decoder import DecodedPoint

_R_ACTIONS: dict[int, str] = {0: "AI", 1: "AO", 2: "BI", 3: "BO"}
_ROCKER_OF: dict[str, str] = {"AI": "A", "AO": "A", "BI": "B", "BO": "B"}


def decode(erp1: Erp1) -> list[DecodedPoint]:
    if not erp1.payload:
        return []

    db0 = erp1.payload[0]
    nu = (erp1.status >> 4) & 0x01

    if nu == 0:
        # U-message — treat as a release event (PTM200 emits DB0=0 on release).
        return [
            DecodedPoint("action", "released"),
            DecodedPoint("button", ""),
            DecodedPoint("rocker", ""),
            DecodedPoint("second_button", ""),
        ]

    # NU=1 — N-message. Decode the first action.
    r1 = (db0 >> 5) & 0x07
    energy_bow = (db0 >> 4) & 0x01
    button = _R_ACTIONS.get(r1, f"R1_{r1}")
    rocker = _ROCKER_OF.get(button, "")
    action = "pressed" if energy_bow else "released"

    sa = db0 & 0x01
    second = ""
    if sa:
        r2 = (db0 >> 1) & 0x07
        second = _R_ACTIONS.get(r2, f"R2_{r2}")

    return [
        DecodedPoint("action", action),
        DecodedPoint("button", button),
        DecodedPoint("rocker", rocker),
        DecodedPoint("second_button", second),
    ]
