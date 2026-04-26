"""Validate the CRC8 table + crc8() against worked examples from ESP3 §3.2."""

from vdsensor.esp3.crc8 import crc8


def test_crc8_empty_is_zero() -> None:
    assert crc8(b"") == 0


def test_crc8_co_wr_reset_header() -> None:
    # ESP3 v1.58 §3.2.3 CO_WR_RESET: header 00 01 00 05 → CRC8H = 0x70
    assert crc8(bytes.fromhex("00010005")) == 0x70


def test_crc8_co_wr_reset_data() -> None:
    # Same example: data 02 → CRC8D = 0x0E
    assert crc8(bytes.fromhex("02")) == 0x0E


def test_crc8_co_rd_idbase_data() -> None:
    # §3.2.4 CO_RD_IDBASE: data 08 → CRC8D = 0x38
    assert crc8(bytes.fromhex("08")) == 0x38


def test_crc8_idbase_response_data() -> None:
    # §3.2.4 response: data 00 FF 80 00 00 → CRC8D = 0xDA
    assert crc8(bytes.fromhex("00FF800000")) == 0xDA


def test_crc8_radio_erp1_vld_header() -> None:
    # §3.2.1 RADIO_ERP1 VLD: header 00 0F 07 01 → CRC8H = 0x2B
    assert crc8(bytes.fromhex("000F0701")) == 0x2B
