//! EEP A5-04-01 — Temperature + Humidity sensor.
//!
//! DB3 = humidity   (0..200 ⇒ 0..100 %RH)
//! DB2 = temperature (0..250 ⇒ 0..40 °C)
//! DB1 = unused
//! DB0 = LRN bit + flags

use crate::eep::DecodedPoint;
use crate::esp3::radio::Erp1;

pub fn decode(erp1: &Erp1) -> Vec<DecodedPoint> {
    if erp1.payload.len() < 4 {
        return Vec::new();
    }
    let db3 = erp1.payload[0];
    let db2 = erp1.payload[1];
    let humidity = ((db3 as f64 / 200.0) * 100.0 * 10.0).round() / 10.0;
    let temp_c = ((db2 as f64 / 250.0) * 40.0 * 10.0).round() / 10.0;
    vec![
        DecodedPoint::new("temperature", temp_c)
            .unit("°C")
            .device_class("temperature")
            .state_class("measurement"),
        DecodedPoint::new("humidity", humidity)
            .unit("%")
            .device_class("humidity")
            .state_class("measurement"),
    ]
}
