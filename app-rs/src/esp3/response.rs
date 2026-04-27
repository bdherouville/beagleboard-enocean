//! RESPONSE (packet type 0x02) parser (§2.2).

use super::framing::Frame;
use super::{ParseError, PacketType, ReturnCode};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Response {
    pub return_code: u8,
    /// Extra response bytes after the return code.
    pub payload: Vec<u8>,
    pub opt: Vec<u8>,
}

impl Response {
    pub fn ok(&self) -> bool {
        self.return_code == ReturnCode::RetOk as u8
    }
}

/// Parse a RESPONSE frame.
///
pub fn parse_response(frame: &Frame) -> Result<Response, ParseError> {
    if frame.packet_type != PacketType::Response as u8 {
        return Err(ParseError::WrongPacketType {
            expected: PacketType::Response as u8,
            actual: frame.packet_type,
        });
    }
    if frame.data.is_empty() {
        return Err(ParseError::EmptyData);
    }
    Ok(Response {
        return_code: frame.data[0],
        payload: frame.data[1..].to_vec(),
        opt: frame.opt.clone(),
    })
}
