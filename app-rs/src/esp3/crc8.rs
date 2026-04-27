//! CRC8 over the ESP3 polynomial G(x) = x^8 + x^2 + x + 1 (0x07).
//!
//! Table copied verbatim from ESP3 v1.58 §3.3. Header CRC and data CRC use
//! the same calculation; both seed at 0x00 and fold each byte through the
//! table.

/// Compute CRC8 over `data` (seed 0x00, polynomial 0x07).
///
/// Stub for R1.red — Haiku fills in the lookup table + loop.
pub fn crc8(_data: &[u8]) -> u8 {
    unimplemented!("crc8 — implemented by R1.green")
}
