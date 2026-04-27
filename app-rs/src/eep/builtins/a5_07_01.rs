//! EEP A5-07-01 — Occupancy (PIR) sensor with supply voltage.
//!
//! DB3 = supply voltage   (0..250 ⇒ 0..5.0 V)
//! DB2 = unused
//! DB1 = PIR status       (≥128 → motion detected)
//! DB0 = LRN bit

use crate::eep::DecodedPoint;
use crate::esp3::radio::Erp1;

pub fn decode(erp1: &Erp1) -> Vec<DecodedPoint> {
    if erp1.payload.len() < 4 {
        return Vec::new();
    }
    let db3 = erp1.payload[0];
    let db1 = erp1.payload[2];
    let voltage = ((db3 as f64 / 250.0) * 5.0 * 100.0).round() / 100.0;
    let motion = db1 >= 128;
    vec![
        DecodedPoint::new("motion", motion).device_class("motion"),
        DecodedPoint::new("voltage", voltage)
            .unit("V")
            .device_class("voltage")
            .state_class("measurement"),
    ]
}
