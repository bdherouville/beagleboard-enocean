//! EVENT (packet type 0x04) parser (§2.4).

use super::framing::Frame;
use super::{ParseError, PacketType};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Event {
    pub event_code: u8,
    pub payload: Vec<u8>,
    pub opt: Vec<u8>,
}

/// Parse an EVENT frame.
///
pub fn parse_event(frame: &Frame) -> Result<Event, ParseError> {
    if frame.packet_type != PacketType::Event as u8 {
        return Err(ParseError::WrongPacketType {
            expected: PacketType::Event as u8,
            actual: frame.packet_type,
        });
    }
    if frame.data.is_empty() {
        return Err(ParseError::EmptyData);
    }
    Ok(Event {
        event_code: frame.data[0],
        payload: frame.data[1..].to_vec(),
        opt: frame.opt.clone(),
    })
}
