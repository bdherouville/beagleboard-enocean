//! RADIO_ERP1 (packet type 0x01) parser/builder.
//!
//! Per §2.1.1 the Data field carries:
//!
//! ```text
//! | RORG | DB(N..0) | SenderID[4 BE] | Status |
//! ```
//!
//! and OptData (when present): `| SubTelNum | DestID[4 BE] | dBm | SecLvl |`.

use super::framing::{encode_frame, Frame};
use super::{EncodeError, PacketType, ParseError};

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
pub fn parse_erp1(frame: &Frame) -> Result<Erp1, ParseError> {
    if frame.packet_type != PacketType::RadioErp1 as u8 {
        return Err(ParseError::WrongPacketType {
            expected: PacketType::RadioErp1 as u8,
            actual: frame.packet_type,
        });
    }
    if frame.data.len() < 1 + 4 + 1 {
        return Err(ParseError::DataTooShort {
            got: frame.data.len(),
            min: 6,
        });
    }

    let rorg = frame.data[0];
    let payload = frame.data[1..frame.data.len() - 5].to_vec();
    let sender_id = u32::from_be_bytes([
        frame.data[frame.data.len() - 5],
        frame.data[frame.data.len() - 4],
        frame.data[frame.data.len() - 3],
        frame.data[frame.data.len() - 2],
    ]);
    let status = frame.data[frame.data.len() - 1];

    let (sub_tel, destination_id, dbm, security_level) = if frame.opt.len() >= 7 {
        let sub_tel = frame.opt[0];
        let destination_id =
            u32::from_be_bytes([frame.opt[1], frame.opt[2], frame.opt[3], frame.opt[4]]);
        let dbm = -(frame.opt[5] as i16);
        let security_level = frame.opt[6];
        (Some(sub_tel), Some(destination_id), Some(dbm), Some(security_level))
    } else {
        (None, None, None, None)
    };

    Ok(Erp1 {
        rorg,
        payload,
        sender_id,
        status,
        sub_tel,
        destination_id,
        dbm,
        security_level,
    })
}

/// Build a TX-ready ERP1 frame as raw bytes (sync + header + … + CRCs).
///
/// Defaults match `build_erp1` in the Python implementation:
/// `sub_tel = 3`, `destination_id = 0xFFFF_FFFF`, `dbm = 0xFF` (the "send case"
/// sentinel per §2.1.1), `security_level = 0`.
///
pub fn build_erp1(
    rorg: u8,
    payload: &[u8],
    sender_id: u32,
    status: u8,
) -> Result<Vec<u8>, EncodeError> {
    let data = [
        &[rorg][..],
        payload,
        &sender_id.to_be_bytes()[..],
        &[status][..],
    ]
    .concat();

    let sub_tel = 3u8;
    let destination_id = 0xFFFFFFFFu32;
    let dbm = 0xFFu8;
    let security_level = 0u8;

    let opt = [
        &[sub_tel][..],
        &destination_id.to_be_bytes()[..],
        &[dbm, security_level][..],
    ]
    .concat();

    encode_frame(PacketType::RadioErp1 as u8, &data, &opt)
}

/// 4BS teach-in: DB0 bit 3 cleared (§EEP A5 convention).
pub fn is_4bs_teach_in(erp1: &Erp1) -> bool {
    if erp1.rorg != 0xA5 || erp1.payload.len() < 4 {
        return false;
    }
    (erp1.payload[3] & 0x08) == 0
}

/// 1BS teach-in: DB0 bit 3 cleared (§EEP D5).
pub fn is_1bs_teach_in(erp1: &Erp1) -> bool {
    if erp1.rorg != 0xD5 || erp1.payload.is_empty() {
        return false;
    }
    (erp1.payload[0] & 0x08) == 0
}
