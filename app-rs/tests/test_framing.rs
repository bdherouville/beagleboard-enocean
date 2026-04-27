//! ESP3 framing — encode against §3.2 examples, then exercise the decoder.
//! Port of `app/tests/test_framing.py`.

mod common;
use common::hex;

use vdsensor::esp3::framing::{FrameDecoder, encode_frame};
use vdsensor::esp3::PacketType;

// Worked examples from ESP3 v1.58 §3.2 (full frames, sync byte first)
fn co_wr_reset_frame() -> Vec<u8> {
    hex("55 00 01 00 05 70 02 0E")
}
fn co_rd_idbase_frame() -> Vec<u8> {
    hex("55 00 01 00 05 70 08 38")
}
fn idbase_response_frame() -> Vec<u8> {
    hex("55 00 05 00 02 CE 00 FF 80 00 00 DA")
}
fn erp1_vld_frame() -> Vec<u8> {
    hex(
        "55 00 0F 07 01 2B \
           D2 DD DD DD DD DD DD DD DD DD 00 80 35 C4 00 \
           03 FF FF FF FF 4D 00 \
           36",
    )
}

#[test]
fn test_encode_co_wr_reset_matches_spec() {
    let out = encode_frame(PacketType::CommonCommand as u8, &[0x02], &[]).unwrap();
    assert_eq!(out, co_wr_reset_frame());
}

#[test]
fn test_encode_co_rd_idbase_matches_spec() {
    let out = encode_frame(PacketType::CommonCommand as u8, &[0x08], &[]).unwrap();
    assert_eq!(out, co_rd_idbase_frame());
}

#[test]
fn test_encode_response_matches_spec() {
    // §3.2.4 response: 5 data bytes, no opt.
    let out = encode_frame(PacketType::Response as u8, &hex("00FF800000"), &[]).unwrap();
    assert_eq!(out, idbase_response_frame());
}

#[test]
fn test_decoder_decodes_each_spec_frame() {
    let mut dec = FrameDecoder::new();
    let mut blob = Vec::new();
    blob.extend(co_wr_reset_frame());
    blob.extend(co_rd_idbase_frame());
    blob.extend(idbase_response_frame());
    blob.extend(erp1_vld_frame());
    let frames = dec.feed(&blob);
    let types: Vec<u8> = frames.iter().map(|f| f.packet_type).collect();
    assert_eq!(
        types,
        vec![
            PacketType::CommonCommand as u8,
            PacketType::CommonCommand as u8,
            PacketType::Response as u8,
            PacketType::RadioErp1 as u8,
        ]
    );
    assert_eq!(frames[3].opt, hex("03FFFFFFFF4D00"));
}

#[test]
fn test_decoder_handles_split_chunks() {
    let mut dec = FrameDecoder::new();
    let mut out = Vec::new();
    for b in co_rd_idbase_frame() {
        out.extend(dec.feed(&[b]));
    }
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].packet_type, PacketType::CommonCommand as u8);
    assert_eq!(out[0].data, vec![0x08]);
}

#[test]
fn test_decoder_resyncs_past_garbage() {
    let mut dec = FrameDecoder::new();
    let junk: Vec<u8> = vec![0xFF, 0x00, 0x55, 0x55, 0xAA];
    let mut blob = junk;
    blob.extend(co_wr_reset_frame());
    let frames = dec.feed(&blob);
    assert_eq!(frames.len(), 1);
    assert_eq!(frames[0].data, vec![0x02]);
}

#[test]
fn test_decoder_resyncs_past_bad_header_crc() {
    let mut bad = co_wr_reset_frame();
    bad[5] ^= 0xFF; // wreck CRC8H
    let mut dec = FrameDecoder::new();
    let mut blob = bad;
    blob.extend(co_rd_idbase_frame());
    let frames = dec.feed(&blob);
    assert_eq!(frames.len(), 1);
    assert_eq!(frames[0].data, vec![0x08]);
}

#[test]
fn test_decoder_resyncs_past_bad_data_crc() {
    let mut bad = co_rd_idbase_frame();
    let last = bad.len() - 1;
    bad[last] ^= 0xFF; // wreck CRC8D
    let mut dec = FrameDecoder::new();
    let mut blob = bad;
    blob.extend(co_wr_reset_frame());
    let frames = dec.feed(&blob);
    assert_eq!(frames.len(), 1);
    assert_eq!(frames[0].data, vec![0x02]);
}

#[test]
fn test_encode_rejects_oversize_data() {
    let big = vec![0u8; 1 << 16];
    assert!(encode_frame(PacketType::RadioErp1 as u8, &big, &[]).is_err());
}
