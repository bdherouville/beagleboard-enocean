"""EEP catalog — labels + canonical point schema per profile.

The pairing wizard reads `KNOWN_PROFILES` to populate its dropdown. The MQTT
discovery layer reads `ProfileInfo.points` to publish HA `config` payloads at
pair-time, before any real telegram has been seen.

Each profile's `points` carries placeholder values whose *type* matters (bool
→ HA binary_sensor; numeric → HA sensor); the actual values come from the
runtime decoder.
"""

from __future__ import annotations

from dataclasses import dataclass

from .decoder import DecodedPoint


@dataclass(frozen=True)
class ProfileInfo:
    profile_id: str          # canonical "RR-FF-TT"
    label: str               # human-readable name
    rorg: int
    points: tuple[DecodedPoint, ...]


KNOWN_PROFILES: dict[str, ProfileInfo] = {p.profile_id: p for p in [
    ProfileInfo(
        "A5-02-05", "Temperature 0..40 °C", 0xA5,
        (DecodedPoint("temperature", 0.0, "°C", "temperature", "measurement"),),
    ),
    ProfileInfo(
        "A5-04-01", "Temperature + Humidity", 0xA5,
        (
            DecodedPoint("temperature", 0.0, "°C", "temperature", "measurement"),
            DecodedPoint("humidity", 0.0, "%", "humidity", "measurement"),
        ),
    ),
    ProfileInfo(
        "A5-07-01", "PIR occupancy", 0xA5,
        (
            DecodedPoint("motion", False, None, "motion", None),
            DecodedPoint("voltage", 0.0, "V", "voltage", "measurement"),
        ),
    ),
    ProfileInfo(
        "A5-09-04", "CO₂ + temperature + humidity", 0xA5,
        (
            DecodedPoint("co2", 0, "ppm", "carbon_dioxide", "measurement"),
            DecodedPoint("temperature", 0.0, "°C", "temperature", "measurement"),
            DecodedPoint("humidity", 0.0, "%", "humidity", "measurement"),
        ),
    ),
    ProfileInfo(
        "F6-02-01", "Rocker switch (2-channel)", 0xF6,
        (
            DecodedPoint("action", "released"),
            DecodedPoint("button", ""),
            DecodedPoint("rocker", ""),
            DecodedPoint("second_button", ""),
        ),
    ),
    ProfileInfo(
        "D5-00-01", "1BS magnet contact", 0xD5,
        (DecodedPoint("contact", False, None, "door", None),),
    ),
]}


def get_profile(profile_id: str) -> ProfileInfo | None:
    return KNOWN_PROFILES.get(profile_id.upper())
