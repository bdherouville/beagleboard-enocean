//! ESP3 codec — EnOcean Serial Protocol 3, v1.58.
//!
//! Numeric codes carry a `§x.y.z` reference to the spec PDF kept in the
//! repo root. Modules:
//!
//! - [`crc8`]            — CRC8 over polynomial 0x07, table from §3.3
//! - [`packets`]         — packet-type / return-code / event-code / common-command enums
//! - [`framing`]         — encode_frame + streaming FrameDecoder
//! - [`radio`]           — RADIO_ERP1 (0x01) parse + build
//! - [`response`]        — RESPONSE (0x02) parse
//! - [`events`]          — EVENT (0x04) parse
//! - [`common_command`]  — COMMON_COMMAND builders + response decoders

pub mod crc8;
pub mod packets;
pub mod framing;
pub mod radio;
pub mod response;
pub mod events;
pub mod common_command;

pub use packets::{
    SYNC_BYTE, HEADER_LENGTH, PacketType, ReturnCode, EventCode, CommonCommand,
};

/// Errors returned by parse functions across this module.
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum ParseError {
    #[error("wrong packet type: expected {expected:#x}, got {actual:#x}")]
    WrongPacketType { expected: u8, actual: u8 },
    #[error("data too short: got {got} bytes, need at least {min}")]
    DataTooShort { got: usize, min: usize },
    #[error("empty data field")]
    EmptyData,
}

/// Errors returned by encoding functions.
#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum EncodeError {
    #[error("data too long: {0} bytes (max 65535)")]
    DataTooLong(usize),
    #[error("opt too long: {0} bytes (max 255)")]
    OptTooLong(usize),
    #[error("value out of range: {0}")]
    OutOfRange(String),
}
