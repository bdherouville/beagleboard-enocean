"""Per-EEP decoder smoke tests + catalog/decoder roundtrip."""

from __future__ import annotations

from vdsensor.eep import decode, has_decoder
from vdsensor.eep.catalog import KNOWN_PROFILES
from vdsensor.esp3.radio import Erp1


def _erp1(rorg: int, payload: bytes) -> Erp1:
    return Erp1(rorg=rorg, payload=payload, sender_id=0xAA, status=0)


def test_every_known_profile_has_a_decoder() -> None:
    for pid in KNOWN_PROFILES:
        assert has_decoder(pid), f"no decoder registered for {pid}"


def test_a5_02_05_temperature_endpoints() -> None:
    # DB1 = 0xFF → 0 °C ; DB1 = 0x00 → 40 °C ; DB1 = 0x80 → ~19.9 °C
    points = decode("A5-02-05", _erp1(0xA5, b"\x00\x00\xFF\x08"))
    assert points[0].key == "temperature"
    assert points[0].value == 0.0
    points = decode("A5-02-05", _erp1(0xA5, b"\x00\x00\x00\x08"))
    assert points[0].value == 40.0


def test_a5_04_01_temp_and_humidity() -> None:
    # DB3=100 (50% RH), DB2=125 (≈20°C), DB1=0, DB0=0x08 (data)
    points = decode("A5-04-01", _erp1(0xA5, b"\x64\x7D\x00\x08"))
    assert {p.key for p in points} == {"temperature", "humidity"}
    by_key = {p.key: p.value for p in points}
    assert by_key["humidity"] == 50.0
    assert by_key["temperature"] == 20.0


def test_a5_07_01_pir_motion_threshold() -> None:
    # DB1 < 128 → no motion; >= 128 → motion
    no_motion = decode("A5-07-01", _erp1(0xA5, b"\xFA\x00\x00\x08"))
    motion = decode("A5-07-01", _erp1(0xA5, b"\xFA\x00\x80\x08"))
    assert {p.key: p.value for p in no_motion}["motion"] is False
    assert {p.key: p.value for p in motion}["motion"] is True


def test_a5_09_04_co2_decode() -> None:
    # DB2=0x32 (=50) → 500 ppm
    points = decode("A5-09-04", _erp1(0xA5, b"\x00\x32\x80\x08"))
    by_key = {p.key: p.value for p in points}
    assert by_key["co2"] == 500


def test_d5_00_01_contact_open_closed() -> None:
    open_pts = decode("D5-00-01", _erp1(0xD5, b"\x08"))         # bit 0 = 0
    closed_pts = decode("D5-00-01", _erp1(0xD5, b"\x09"))       # bit 0 = 1
    assert open_pts[0].value is False
    assert closed_pts[0].value is True


def _f6(db0: int, status: int) -> Erp1:
    return Erp1(rorg=0xF6, payload=bytes((db0,)), sender_id=1, status=status)


def test_f6_02_01_release_when_nu_zero() -> None:
    rel = {p.key: p.value for p in decode("F6-02-01", _f6(0x00, 0x20))}
    assert rel["action"] == "released"
    assert rel["button"] == ""
    assert rel["rocker"] == ""


def test_f6_02_01_press_AI() -> None:
    # status NU=1 (0x30 = T21+NU), DB0: R1=0 (AI), energy bow = 1
    pts = {p.key: p.value for p in decode("F6-02-01", _f6(0x10, 0x30))}
    assert pts["action"] == "pressed"
    assert pts["button"] == "AI"
    assert pts["rocker"] == "A"
    assert pts["second_button"] == ""


def test_f6_02_01_press_AO_BI_BO_buttons() -> None:
    # AO: R1=1, EB=1 → DB0 = 0b001_1_0000 = 0x30
    # BI: R1=2, EB=1 → DB0 = 0b010_1_0000 = 0x50
    # BO: R1=3, EB=1 → DB0 = 0b011_1_0000 = 0x70
    cases = {0x30: ("AO", "A"), 0x50: ("BI", "B"), 0x70: ("BO", "B")}
    for db0, (button, rocker) in cases.items():
        pts = {p.key: p.value for p in decode(
            "F6-02-01", Erp1(rorg=0xF6, payload=bytes((db0,)), sender_id=1, status=0x30))}
        assert pts["button"] == button
        assert pts["rocker"] == rocker
        assert pts["action"] == "pressed"


def test_f6_02_01_second_action_when_sa_set() -> None:
    # First press AI (R1=0) + simultaneous BO (R2=3) with SA=1 and EB=1.
    # DB0 = R1[7:5]=000 | EB[4]=1 | R2[3:1]=011 | SA[0]=1
    #     = 0b000_1_011_1 = 0x17
    pts = {p.key: p.value for p in decode("F6-02-01", _f6(0x17, 0x30))}
    assert pts["button"] == "AI"
    assert pts["second_button"] == "BO"
