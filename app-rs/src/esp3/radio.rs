//! RADIO_ERP1 (packet type 0x01) parser/builder.
//!
//! Per §2.1.1 the Data field carries:
//!
//! ```text
//! | RORG | DB(N..0) | SenderID[4 BE] | Status |
//! ```
//!
//! and OptData (when present): `| SubTelNum | DestID[4 BE] | dBm | SecLvl |`.

use super::framing::Frame;
use super::{EncodeError, ParseError};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Erp1 {
    pub rorg: u8,
    /// DB(N..0) — bytes between RORG and SenderID.
    pub payload: Vec<u8>,
    pub sender_id: u32,
    pub status: u8,
    pub sub_tel: Option<u8>,
    pub destination_id: Option<u32>,
    /// Negative dBm; ESP3 wire field is `u8` of `|dBm|`, parser surfaces it negative.
    pub dbm: Option<i16>,
    pub security_level: Option<u8>,
}

/// Parse an ERP1 frame.
///
/// Stub for R1.red.
pub fn parse_erp1(_frame: &Frame) -> Result<Erp1, ParseError> {
    unimplemented!("parse_erp1 — implemented by R1.green")
}

/// Build a TX-ready ERP1 frame as raw bytes (sync + header + … + CRCs).
///
/// Defaults match `build_erp1` in the Python implementation:
/// `sub_tel = 3`, `destination_id = 0xFFFF_FFFF`, `dbm = 0xFF` (the "send case"
/// sentinel per §2.1.1), `security_level = 0`.
///
/// Stub for R1.red.
pub fn build_erp1(
    _rorg: u8,
    _payload: &[u8],
    _sender_id: u32,
    _status: u8,
) -> Result<Vec<u8>, EncodeError> {
    unimplemented!("build_erp1 — implemented by R1.green")
}

/// 4BS teach-in: DB0 bit 3 cleared (§EEP A5 convention).
pub fn is_4bs_teach_in(_erp1: &Erp1) -> bool {
    unimplemented!("is_4bs_teach_in — implemented by R1.green")
}

/// 1BS teach-in: DB0 bit 3 cleared (§EEP D5).
pub fn is_1bs_teach_in(_erp1: &Erp1) -> bool {
    unimplemented!("is_1bs_teach_in — implemented by R1.green")
}
