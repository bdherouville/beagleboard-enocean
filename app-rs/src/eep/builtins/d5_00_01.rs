//! EEP D5-00-01 — 1BS magnet contact (door/window sensor).
//!
//! Data: DB0 (1 byte)
//!   bit 0 = state (0 = open, 1 = closed)
//!   bit 3 = LRN   (0 = teach-in, 1 = data telegram)

use crate::eep::DecodedPoint;
use crate::esp3::radio::Erp1;

pub fn decode(erp1: &Erp1) -> Vec<DecodedPoint> {
    if erp1.payload.is_empty() {
        return Vec::new();
    }
    let db0 = erp1.payload[0];
    let closed = (db0 & 0x01) != 0;
    vec![DecodedPoint::new("contact", closed).device_class("door")]
}
