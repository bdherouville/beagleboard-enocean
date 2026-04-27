//! COMMON_COMMAND builders and response parsers.
//! Port of `app/tests/test_common_command.py`.

mod common;
use common::hex;

use vdsensor::esp3::common_command as cc;
use vdsensor::esp3::framing::{FrameDecoder, encode_frame};
use vdsensor::esp3::response::parse_response;
use vdsensor::esp3::{CommonCommand, PacketType, ReturnCode};

#[test]
fn test_cmd_co_wr_reset_matches_spec() {
    // ESP3 §3.2.3 — exact bytes from the worked example.
    assert_eq!(cc::cmd_co_wr_reset(), hex("550001000570020E"));
}

#[test]
fn test_cmd_co_rd_idbase_matches_spec() {
    // ESP3 §3.2.4 — exact bytes from the worked example.
    assert_eq!(cc::cmd_co_rd_idbase(), hex("5500010005700838"));
}

#[test]
fn test_cmd_co_rd_version_decodes_correctly() {
    let raw = cc::cmd_co_rd_version();
    let mut dec = FrameDecoder::new();
    let frames = dec.feed(&raw);
    assert_eq!(frames[0].packet_type, PacketType::CommonCommand as u8);
    assert_eq!(frames[0].data, vec![CommonCommand::CoRdVersion as u8]);
}

#[test]
fn test_cmd_co_wr_learnmode_layout() {
    let raw = cc::cmd_co_wr_learnmode(true, 60_000, 0xFF);
    let mut dec = FrameDecoder::new();
    let frames = dec.feed(&raw);
    assert_eq!(frames[0].packet_type, PacketType::CommonCommand as u8);
    // data: cmd(0x17) | enable(0x01) | timeout BE(60000=0xEA60)
    assert_eq!(
        frames[0].data,
        vec![CommonCommand::CoWrLearnmode as u8, 0x01, 0x00, 0x00, 0xEA, 0x60]
    );
    assert_eq!(frames[0].opt, vec![0xFF]);
}

#[test]
fn test_parse_idbase_response_from_spec_example() {
    // §3.2.4 response: 5 data bytes (00 FF800000), no opt → remaining_writes default 0xFF
    let raw = hex("5500050002CE00FF800000DA");
    let mut dec = FrameDecoder::new();
    let frames = dec.feed(&raw);
    let resp = parse_response(&frames[0]).expect("parse");
    let info = cc::parse_idbase_response(&resp).expect("parse idbase");
    assert_eq!(resp.return_code, ReturnCode::RetOk as u8);
    assert_eq!(info.base_id, 0xFF800000);
    assert_eq!(info.remaining_writes, 0xFF);
}

#[test]
fn test_parse_idbase_response_with_remaining_writes_in_opt() {
    // Same response but with the (newer) opt byte = 0x05 remaining writes.
    let raw = encode_frame(PacketType::Response as u8, &hex("00FF800000"), &[0x05]).unwrap();
    let mut dec = FrameDecoder::new();
    let frames = dec.feed(&raw);
    let info = cc::parse_idbase_response(&parse_response(&frames[0]).unwrap()).unwrap();
    assert_eq!(info.remaining_writes, 0x05);
}

#[test]
fn test_parse_version_response_round_trip() {
    let mut payload = Vec::new();
    payload.push(ReturnCode::RetOk as u8);
    payload.extend_from_slice(&[2, 6, 0, 5]); // app version 2.6.0.5
    payload.extend_from_slice(&[1, 22, 0, 0]); // api version 1.22.0.0
    payload.extend_from_slice(&0x01234567u32.to_be_bytes()); // EURID
    payload.extend_from_slice(&0x00000001u32.to_be_bytes()); // device version
    payload.extend_from_slice(b"GATEWAYCTRLR\0\0\0\0"); // 16-byte ASCII

    let raw = encode_frame(PacketType::Response as u8, &payload, &[]).unwrap();
    let mut dec = FrameDecoder::new();
    let frames = dec.feed(&raw);
    let info = cc::parse_version_response(&parse_response(&frames[0]).unwrap()).unwrap();
    assert_eq!(info.app_version, [2, 6, 0, 5]);
    assert_eq!(info.api_version, [1, 22, 0, 0]);
    assert_eq!(info.chip_id, 0x01234567);
    assert_eq!(info.chip_version, 0x00000001);
    assert_eq!(info.description, "GATEWAYCTRLR");
}
