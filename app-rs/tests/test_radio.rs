//! ERP1 parse/build round-trips and teach-in detection.
//! Port of `app/tests/test_radio.py`.

mod common;
use common::hex;

use vdsensor::esp3::framing::FrameDecoder;
use vdsensor::esp3::radio::{Erp1, build_erp1, is_1bs_teach_in, is_4bs_teach_in, parse_erp1};

#[test]
fn test_parse_erp1_vld_from_spec_example() {
    // ESP3 §3.2.1: VLD with 9 payload bytes (DD×9), sender 0x008035C4, status 0x00,
    // opt sub_tel=3, dest=0xFFFFFFFF, dbm=0x4D=77 → -77, security=0
    let raw = hex(
        "55 00 0F 07 01 2B \
           D2 DD DD DD DD DD DD DD DD DD 00 80 35 C4 00 \
           03 FF FF FF FF 4D 00 \
           36",
    );
    let mut dec = FrameDecoder::new();
    let frames = dec.feed(&raw);
    let erp1 = parse_erp1(&frames[0]).expect("parse ok");
    assert_eq!(erp1.rorg, 0xD2);
    // After RORG (D2): 9 payload bytes (DD×9) | sender_id (00 80 35 C4) | status (00)
    assert_eq!(erp1.payload, vec![0xDD; 9]);
    assert_eq!(erp1.sender_id, 0x008035C4);
    assert_eq!(erp1.status, 0x00);
    assert_eq!(erp1.sub_tel, Some(3));
    assert_eq!(erp1.destination_id, Some(0xFFFFFFFF));
    assert_eq!(erp1.dbm, Some(-0x4D));
    assert_eq!(erp1.security_level, Some(0));
}

#[test]
fn test_build_then_parse_round_trip_rps() {
    round_trip(0xF6, &[0x50]);
}

#[test]
fn test_build_then_parse_round_trip_1bs() {
    round_trip(0xD5, &[0x08]);
}

#[test]
fn test_build_then_parse_round_trip_4bs() {
    round_trip(0xA5, &[0x01, 0x02, 0x03, 0x08]);
}

fn round_trip(rorg: u8, payload: &[u8]) {
    let raw = build_erp1(rorg, payload, 0x01020304, 0x30).expect("build");
    let mut dec = FrameDecoder::new();
    let frames = dec.feed(&raw);
    let erp1 = parse_erp1(&frames[0]).expect("parse");
    assert_eq!(erp1.rorg, rorg);
    assert_eq!(erp1.payload, payload);
    assert_eq!(erp1.sender_id, 0x01020304);
    assert_eq!(erp1.status, 0x30);
    // build_erp1 always emits opt → dbm is surfaced as -0xFF (the "send" sentinel)
    assert_eq!(erp1.dbm, Some(-0xFF));
    assert_eq!(erp1.destination_id, Some(0xFFFFFFFF));
}

fn erp1(rorg: u8, payload: &[u8]) -> Erp1 {
    Erp1 {
        rorg,
        payload: payload.to_vec(),
        sender_id: 1,
        status: 0,
        sub_tel: None,
        destination_id: None,
        dbm: None,
        security_level: None,
    }
}

#[test]
fn test_4bs_teach_in_detection() {
    let teach = erp1(0xA5, &[0x00, 0x00, 0x00, 0x00]);
    let data = erp1(0xA5, &[0x00, 0x00, 0x00, 0x08]);
    assert!(is_4bs_teach_in(&teach));
    assert!(!is_4bs_teach_in(&data));
}

#[test]
fn test_1bs_teach_in_detection() {
    let teach = erp1(0xD5, &[0x00]);
    let data = erp1(0xD5, &[0x08]);
    assert!(is_1bs_teach_in(&teach));
    assert!(!is_1bs_teach_in(&data));
}

#[test]
fn test_4bs_teach_in_only_on_correct_rorg() {
    // RPS or 1BS frame must not be classified as 4BS teach-in.
    assert!(!is_4bs_teach_in(&erp1(0xF6, &[0x00])));
}
