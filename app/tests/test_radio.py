"""ERP1 parse/build round-trips and teach-in detection."""

import pytest

from vdsensor.esp3.framing import FrameDecoder
from vdsensor.esp3.radio import (
    Erp1,
    build_erp1,
    is_1bs_teach_in,
    is_4bs_teach_in,
    parse_erp1,
)


def test_parse_erp1_vld_from_spec_example() -> None:
    # ESP3 §3.2.1: VLD with 10 payload bytes, sender 0x008035C4, status 0x00,
    # opt sub_tel=3, dest=0xFFFFFFFF, dbm=0x4D=77 → -77, security=0
    raw = bytes.fromhex(
        "55 00 0F 07 01 2B"
        " D2 DD DD DD DD DD DD DD DD DD 00 80 35 C4 00"
        " 03 FF FF FF FF 4D 00"
        " 36".replace(" ", "")
    )
    frame = next(iter(FrameDecoder().feed(raw)))
    erp1 = parse_erp1(frame)
    assert erp1.rorg == 0xD2
    # After RORG (D2): 9 payload bytes (DD×9) | sender_id (00 80 35 C4) | status (00)
    assert erp1.payload == bytes.fromhex("DD" * 9)
    assert erp1.sender_id == 0x008035C4
    assert erp1.status == 0x00
    assert erp1.sub_tel == 3
    assert erp1.destination_id == 0xFFFFFFFF
    assert erp1.dbm == -0x4D
    assert erp1.security_level == 0


@pytest.mark.parametrize(
    "rorg,payload",
    [
        (0xF6, b"\x50"),                         # RPS, 1 data byte
        (0xD5, b"\x08"),                         # 1BS, 1 data byte (LRN bit set = data tel)
        (0xA5, b"\x01\x02\x03\x08"),             # 4BS, 4 data bytes (LRN bit set)
    ],
)
def test_build_then_parse_round_trip(rorg: int, payload: bytes) -> None:
    raw = build_erp1(rorg, payload, sender_id=0x01020304, status=0x30)
    frame = next(iter(FrameDecoder().feed(raw)))
    erp1 = parse_erp1(frame)
    assert erp1.rorg == rorg
    assert erp1.payload == payload
    assert erp1.sender_id == 0x01020304
    assert erp1.status == 0x30
    # build_erp1 always emits opt → dbm is surfaced as -0xFF (the "send" sentinel)
    assert erp1.dbm == -0xFF
    assert erp1.destination_id == 0xFFFFFFFF


def test_4bs_teach_in_detection() -> None:
    teach = Erp1(rorg=0xA5, payload=b"\x00\x00\x00\x00", sender_id=1, status=0)
    data = Erp1(rorg=0xA5, payload=b"\x00\x00\x00\x08", sender_id=1, status=0)
    assert is_4bs_teach_in(teach) is True
    assert is_4bs_teach_in(data) is False


def test_1bs_teach_in_detection() -> None:
    teach = Erp1(rorg=0xD5, payload=b"\x00", sender_id=1, status=0)
    data = Erp1(rorg=0xD5, payload=b"\x08", sender_id=1, status=0)
    assert is_1bs_teach_in(teach) is True
    assert is_1bs_teach_in(data) is False


def test_4bs_teach_in_only_on_correct_rorg() -> None:
    # An RPS or 1BS frame must not be classified as 4BS teach-in even if its
    # payload happens to look like one.
    assert is_4bs_teach_in(Erp1(rorg=0xF6, payload=b"\x00", sender_id=1, status=0)) is False
