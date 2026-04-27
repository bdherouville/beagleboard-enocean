//! Builders + response parsers for the four COMMON_COMMAND codes used in v1.
//!
//! - CO_WR_RESET     §2.5.4  (1-byte data, no opt)
//! - CO_RD_VERSION   §2.5.5  (1-byte data, no opt) → 32-byte response payload
//! - CO_RD_IDBASE    §2.5.10 (1-byte data, no opt) → 4-byte ID + 1 opt remaining-writes
//! - CO_WR_LEARNMODE §2.5.25 (6-byte data + 1 opt channel)

use super::response::Response;
use super::ParseError;

// --- request builders ------------------------------------------------------

/// Stub for R1.red.
pub fn cmd_co_wr_reset() -> Vec<u8> {
    unimplemented!("cmd_co_wr_reset — implemented by R1.green")
}

pub fn cmd_co_rd_version() -> Vec<u8> {
    unimplemented!("cmd_co_rd_version — implemented by R1.green")
}

pub fn cmd_co_rd_idbase() -> Vec<u8> {
    unimplemented!("cmd_co_rd_idbase — implemented by R1.green")
}

/// Toggle the chip's classic learn mode (§2.5.25).
///
/// `timeout_ms = 0` lets the chip use its default 60 s window.
/// `channel = 0xFF` (next relative) is the safe default for non-channel-aware devices.
pub fn cmd_co_wr_learnmode(_enable: bool, _timeout_ms: u32, _channel: u8) -> Vec<u8> {
    unimplemented!("cmd_co_wr_learnmode — implemented by R1.green")
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
pub fn parse_version_response(_resp: &Response) -> Result<VersionInfo, ParseError> {
    unimplemented!("parse_version_response — implemented by R1.green")
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IdBaseInfo {
    pub base_id: u32,
    /// 0..0xFE remaining writes; 0xFF = unlimited / not advertised.
    pub remaining_writes: u8,
}

pub fn parse_idbase_response(_resp: &Response) -> Result<IdBaseInfo, ParseError> {
    unimplemented!("parse_idbase_response — implemented by R1.green")
}
