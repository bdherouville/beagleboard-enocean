//! ESP3 frame encoder + streaming decoder.
//!
//! Layout (§1.7 / §3.4.1):
//!
//! ```text
//! | 0x55 | DataLen[2 BE] | OptLen[1] | Type[1] | CRC8H | Data | OptData | CRC8D |
//! ```
//!
//! CRC8H is computed over the 4 header bytes; CRC8D over `Data || OptData`.

use super::EncodeError;

/// A successfully decoded ESP3 frame.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    pub packet_type: u8,
    pub data: Vec<u8>,
    pub opt: Vec<u8>,
}

/// Encode an ESP3 frame ready for the wire (§3.4.3).
///
/// Stub for R1.red.
pub fn encode_frame(_packet_type: u8, _data: &[u8], _opt: &[u8]) -> Result<Vec<u8>, EncodeError> {
    unimplemented!("encode_frame — implemented by R1.green")
}

/// Streaming decoder. Feed arbitrary chunks; emits complete frames.
///
/// Resync behaviour per §3.4.2: on any CRC mismatch we drop the candidate
/// sync byte and search forward for the next 0x55.
#[derive(Debug, Default)]
pub struct FrameDecoder {
    _buf: std::collections::VecDeque<u8>,
}

impl FrameDecoder {
    pub fn new() -> Self {
        Self::default()
    }

    /// Push `chunk` into the buffer; return every complete frame extracted.
    ///
    /// Stub for R1.red.
    pub fn feed(&mut self, _chunk: &[u8]) -> Vec<Frame> {
        unimplemented!("FrameDecoder::feed — implemented by R1.green")
    }
}
