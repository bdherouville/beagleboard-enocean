//! ESP3 frame encoder + streaming decoder.
//!
//! Layout (§1.7 / §3.4.1):
//!
//! ```text
//! | 0x55 | DataLen[2 BE] | OptLen[1] | Type[1] | CRC8H | Data | OptData | CRC8D |
//! ```
//!
//! CRC8H is computed over the 4 header bytes; CRC8D over `Data || OptData`.

use super::crc8::crc8;
use super::{EncodeError, HEADER_LENGTH, SYNC_BYTE};
use std::collections::VecDeque;

/// A successfully decoded ESP3 frame.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    pub packet_type: u8,
    pub data: Vec<u8>,
    pub opt: Vec<u8>,
}

/// Encode an ESP3 frame ready for the wire (§3.4.3).
pub fn encode_frame(packet_type: u8, data: &[u8], opt: &[u8]) -> Result<Vec<u8>, EncodeError> {
    let data_len = data.len();
    let opt_len = opt.len();

    if data_len > 0xFFFF {
        return Err(EncodeError::DataTooLong(data_len));
    }
    if opt_len > 0xFF {
        return Err(EncodeError::OptTooLong(opt_len));
    }

    let header = [
        (data_len >> 8) as u8,
        (data_len & 0xFF) as u8,
        opt_len as u8,
        packet_type,
    ];

    let header_crc = crc8(&header);
    let body = [data, opt].concat();
    let body_crc = crc8(&body);

    let mut result = Vec::with_capacity(1 + HEADER_LENGTH + 1 + body.len() + 1);
    result.push(SYNC_BYTE);
    result.extend_from_slice(&header);
    result.push(header_crc);
    result.extend_from_slice(&body);
    result.push(body_crc);

    Ok(result)
}

/// Streaming decoder. Feed arbitrary chunks; emits complete frames.
///
/// Resync behaviour per §3.4.2: on any CRC mismatch we drop the candidate
/// sync byte and search forward for the next 0x55.
#[derive(Debug, Default)]
pub struct FrameDecoder {
    buf: VecDeque<u8>,
}

impl FrameDecoder {
    pub fn new() -> Self {
        Self::default()
    }

    /// Push `chunk` into the buffer; return every complete frame extracted.
    pub fn feed(&mut self, chunk: &[u8]) -> Vec<Frame> {
        self.buf.extend(chunk);
        let mut frames = Vec::new();

        loop {
            // Drop until the next sync byte.
            while !self.buf.is_empty() && self.buf[0] != SYNC_BYTE {
                self.buf.pop_front();
            }

            if self.buf.len() < 1 + HEADER_LENGTH + 1 {
                break; // need more header bytes
            }

            // Extract header
            let header = [
                self.buf[1],
                self.buf[2],
                self.buf[3],
                self.buf[4],
            ];

            // Validate header CRC
            if crc8(&header) != self.buf[5] {
                self.buf.pop_front(); // drop sync, retry
                continue;
            }

            let data_len = ((header[0] as usize) << 8) | (header[1] as usize);
            let opt_len = header[2] as usize;
            let packet_type = header[3];
            let body_len = data_len + opt_len;
            let total = 1 + HEADER_LENGTH + 1 + body_len + 1;

            if self.buf.len() < total {
                break; // need more body bytes
            }

            // Extract body and validate CRC
            let body_start = 1 + HEADER_LENGTH + 1;
            let body = self.buf
                .iter()
                .skip(body_start)
                .take(body_len)
                .copied()
                .collect::<Vec<u8>>();

            if crc8(&body) != self.buf[total - 1] {
                self.buf.pop_front(); // drop sync, retry
                continue;
            }

            // Frame is valid; remove it from buffer
            for _ in 0..total {
                self.buf.pop_front();
            }

            frames.push(Frame {
                packet_type,
                data: body[..data_len].to_vec(),
                opt: body[data_len..].to_vec(),
            });
        }

        frames
    }
}
