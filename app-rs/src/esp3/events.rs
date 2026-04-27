//! EVENT (packet type 0x04) parser (§2.4).

use super::framing::Frame;
use super::ParseError;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Event {
    pub event_code: u8,
    pub payload: Vec<u8>,
    pub opt: Vec<u8>,
}

/// Parse an EVENT frame.
///
/// Stub for R1.red.
pub fn parse_event(_frame: &Frame) -> Result<Event, ParseError> {
    unimplemented!("parse_event — implemented by R1.green")
}
