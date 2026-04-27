//! Validate the CRC8 table + `crc8()` against worked examples from ESP3 §3.2.
//! Direct port of `app/tests/test_crc8.py`.

use vdsensor::esp3::crc8::crc8;

fn hex(s: &str) -> Vec<u8> {
    let stripped: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    (0..stripped.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&stripped[i..i + 2], 16).expect("invalid hex"))
        .collect()
}

#[test]
fn test_crc8_empty_is_zero() {
    assert_eq!(crc8(b""), 0);
}

#[test]
fn test_crc8_co_wr_reset_header() {
    // §3.2.3 CO_WR_RESET: header 00 01 00 05 → CRC8H = 0x70
    assert_eq!(crc8(&hex("00010005")), 0x70);
}

#[test]
fn test_crc8_co_wr_reset_data() {
    // Same example: data 02 → CRC8D = 0x0E
    assert_eq!(crc8(&hex("02")), 0x0E);
}

#[test]
fn test_crc8_co_rd_idbase_data() {
    // §3.2.4 CO_RD_IDBASE: data 08 → CRC8D = 0x38
    assert_eq!(crc8(&hex("08")), 0x38);
}

#[test]
fn test_crc8_idbase_response_data() {
    // §3.2.4 response: data 00 FF 80 00 00 → CRC8D = 0xDA
    assert_eq!(crc8(&hex("00FF800000")), 0xDA);
}

#[test]
fn test_crc8_radio_erp1_vld_header() {
    // §3.2.1 RADIO_ERP1 VLD: header 00 0F 07 01 → CRC8H = 0x2B
    assert_eq!(crc8(&hex("000F0701")), 0x2B);
}
