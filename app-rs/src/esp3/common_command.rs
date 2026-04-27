//! Builders + response parsers for the four COMMON_COMMAND codes used in v1.
//!
//! - CO_WR_RESET     §2.5.4  (1-byte data, no opt)
//! - CO_RD_VERSION   §2.5.5  (1-byte data, no opt) → 32-byte response payload
//! - CO_RD_IDBASE    §2.5.10 (1-byte data, no opt) → 4-byte ID + 1 opt remaining-writes
//! - CO_WR_LEARNMODE §2.5.25 (6-byte data + 1 opt channel)

use super::framing::encode_frame;
use super::response::Response;
use super::{CommonCommand, PacketType, ParseError};

// --- request builders ------------------------------------------------------

pub fn cmd_co_wr_reset() -> Vec<u8> {
    encode_frame(
        PacketType::CommonCommand as u8,
        &[CommonCommand::CoWrReset as u8],
        &[],
    )
    .expect("valid frame")
}

pub fn cmd_co_rd_version() -> Vec<u8> {
    encode_frame(
        PacketType::CommonCommand as u8,
        &[CommonCommand::CoRdVersion as u8],
        &[],
    )
    .expect("valid frame")
}

pub fn cmd_co_rd_idbase() -> Vec<u8> {
    encode_frame(
        PacketType::CommonCommand as u8,
        &[CommonCommand::CoRdIdbase as u8],
        &[],
    )
    .expect("valid frame")
}

/// Toggle the chip's classic learn mode (§2.5.25).
///
/// `timeout_ms = 0` lets the chip use its default 60 s window.
/// `channel = 0xFF` (next relative) is the safe default for non-channel-aware devices.
pub fn cmd_co_wr_learnmode(enable: bool, timeout_ms: u32, channel: u8) -> Vec<u8> {
    let data = [
        &[CommonCommand::CoWrLearnmode as u8][..],
        &[if enable { 0x01 } else { 0x00 }][..],
        &timeout_ms.to_be_bytes()[..],
    ]
    .concat();
    let opt = [channel];
    encode_frame(PacketType::CommonCommand as u8, &data, &opt).expect("valid frame")
}

// --- response parsers (caller knows which command preceded) ----------------

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VersionInfo {
    /// `(main, beta, alpha, build)`.
    pub app_version: [u8; 4],
    pub api_version: [u8; 4],
    /// EURID (32-bit chip identifier).
    pub chip_id: u32,
    pub chip_version: u32,
    /// 16-byte ASCII description, null-trimmed.
    pub description: String,
}

/// Decode the 32-byte payload returned after a CO_RD_VERSION request.
pub fn parse_version_response(resp: &Response) -> Result<VersionInfo, ParseError> {
    if resp.payload.len() < 32 {
        return Err(ParseError::DataTooShort {
            got: resp.payload.len(),
            min: 32,
        });
    }
    let p = &resp.payload;
    let app_version = [p[0], p[1], p[2], p[3]];
    let api_version = [p[4], p[5], p[6], p[7]];
    let chip_id = u32::from_be_bytes([p[8], p[9], p[10], p[11]]);
    let chip_version = u32::from_be_bytes([p[12], p[13], p[14], p[15]]);
    let desc_bytes = &p[16..32];
    let null_pos = desc_bytes.iter().position(|&b| b == 0).unwrap_or(32 - 16);
    let description =
        String::from_utf8_lossy(&desc_bytes[..null_pos]).into_owned();

    Ok(VersionInfo {
        app_version,
        api_version,
        chip_id,
        chip_version,
        description,
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IdBaseInfo {
    pub base_id: u32,
    /// 0..0xFE remaining writes; 0xFF = unlimited / not advertised.
    pub remaining_writes: u8,
}

pub fn parse_idbase_response(resp: &Response) -> Result<IdBaseInfo, ParseError> {
    if resp.payload.len() < 4 {
        return Err(ParseError::DataTooShort {
            got: resp.payload.len(),
            min: 4,
        });
    }
    let base_id = u32::from_be_bytes([
        resp.payload[0],
        resp.payload[1],
        resp.payload[2],
        resp.payload[3],
    ]);
    let remaining_writes = if !resp.opt.is_empty() {
        resp.opt[0]
    } else {
        0xFF
    };

    Ok(IdBaseInfo {
        base_id,
        remaining_writes,
    })
}
