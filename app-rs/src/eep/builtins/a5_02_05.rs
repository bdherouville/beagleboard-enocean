//! EEP A5-02-05 — Temperature sensor, range 0..40 °C.
//!
//! 4BS payload (DB3, DB2, DB1, DB0):
//!   DB3 = unused
//!   DB2 = unused
//!   DB1 = temperature byte; linear 255 → 0 °C, 0 → 40 °C  (inverted)
//!   DB0 = bit 3 = LRN (0 teach-in, 1 data); bit 1 ignored at decode time

use crate::eep::DecodedPoint;
use crate::esp3::radio::Erp1;

pub fn decode(erp1: &Erp1) -> Vec<DecodedPoint> {
    if erp1.payload.len() < 4 {
        return Vec::new();
    }
    let db1 = erp1.payload[2];
    let temp_c = ((40.0 - (db1 as f64 / 255.0) * 40.0) * 10.0).round() / 10.0;
    vec![
        DecodedPoint::new("temperature", temp_c)
            .unit("°C")
            .device_class("temperature")
            .state_class("measurement"),
    ]
}
