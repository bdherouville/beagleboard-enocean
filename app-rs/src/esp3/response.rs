//! RESPONSE (packet type 0x02) parser (§2.2).

use super::framing::Frame;
use super::{ParseError, ReturnCode};

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
/// Stub for R1.red.
pub fn parse_response(_frame: &Frame) -> Result<Response, ParseError> {
    unimplemented!("parse_response — implemented by R1.green")
}
