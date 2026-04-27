//! EEP A5-09-04 — CO₂ + temperature + humidity.
//!
//! DB3 = humidity     (0..200 ⇒ 0..100 %RH)
//! DB2 = CO₂          (0..255 ⇒ 0..2550 ppm)
//! DB1 = temperature  (0..255 ⇒ 0..51 °C)
//! DB0 = flags + LRN bit

use crate::eep::DecodedPoint;
use crate::esp3::radio::Erp1;

pub fn decode(erp1: &Erp1) -> Vec<DecodedPoint> {
    if erp1.payload.len() < 4 {
        return Vec::new();
    }
    let db3 = erp1.payload[0];
    let db2 = erp1.payload[1];
    let db1 = erp1.payload[2];
    let humidity = ((db3 as f64 / 200.0) * 100.0 * 10.0).round() / 10.0;
    let co2 = (db2 as i64) * 10;
    let temp_c = ((db1 as f64 / 255.0) * 51.0 * 10.0).round() / 10.0;
    vec![
        DecodedPoint::new("co2", co2)
            .unit("ppm")
            .device_class("carbon_dioxide")
            .state_class("measurement"),
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
