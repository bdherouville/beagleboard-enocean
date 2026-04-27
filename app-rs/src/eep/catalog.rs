//! EEP catalog — labels + canonical point schema per profile.
//!
//! The pairing wizard reads `known_profiles()` to populate its dropdown.
//! The MQTT discovery layer reads `ProfileInfo::points` to publish HA
//! `config` payloads at pair-time, before any real telegram has been seen.
//!
//! Each profile's `points` carries placeholder values whose *type* matters
//! (bool → HA binary_sensor; numeric → HA sensor); the actual values come
//! from the runtime decoder.

use std::sync::OnceLock;

use crate::eep::decoder::DecodedPoint;

#[derive(Debug, Clone)]
pub struct ProfileInfo {
    pub profile_id: &'static str,
    pub label: &'static str,
    pub rorg: u8,
    pub points: Vec<DecodedPoint>,
}

static PROFILES: OnceLock<Vec<ProfileInfo>> = OnceLock::new();

/// Return every profile the catalog knows about.
#[allow(non_snake_case)]
pub fn KNOWN_PROFILES() -> &'static [ProfileInfo] {
    PROFILES.get_or_init(build).as_slice()
}

fn build() -> Vec<ProfileInfo> {
    vec![
        ProfileInfo {
            profile_id: "A5-02-05",
            label: "Temperature 0..40 °C",
            rorg: 0xA5,
            points: vec![DecodedPoint::new("temperature", 0.0_f64)
                .unit("°C")
                .device_class("temperature")
                .state_class("measurement")],
        },
        ProfileInfo {
            profile_id: "A5-04-01",
            label: "Temperature + Humidity",
            rorg: 0xA5,
            points: vec![
                DecodedPoint::new("temperature", 0.0_f64)
                    .unit("°C")
                    .device_class("temperature")
                    .state_class("measurement"),
                DecodedPoint::new("humidity", 0.0_f64)
                    .unit("%")
                    .device_class("humidity")
                    .state_class("measurement"),
            ],
        },
        ProfileInfo {
            profile_id: "A5-07-01",
            label: "PIR occupancy",
            rorg: 0xA5,
            points: vec![
                DecodedPoint::new("motion", false).device_class("motion"),
                DecodedPoint::new("voltage", 0.0_f64)
                    .unit("V")
                    .device_class("voltage")
                    .state_class("measurement"),
            ],
        },
        ProfileInfo {
            profile_id: "A5-09-04",
            label: "CO₂ + temperature + humidity",
            rorg: 0xA5,
            points: vec![
                DecodedPoint::new("co2", 0_i64)
                    .unit("ppm")
                    .device_class("carbon_dioxide")
                    .state_class("measurement"),
                DecodedPoint::new("temperature", 0.0_f64)
                    .unit("°C")
                    .device_class("temperature")
                    .state_class("measurement"),
                DecodedPoint::new("humidity", 0.0_f64)
                    .unit("%")
                    .device_class("humidity")
                    .state_class("measurement"),
            ],
        },
        ProfileInfo {
            profile_id: "F6-02-01",
            label: "Rocker switch (2-channel)",
            rorg: 0xF6,
            points: vec![
                DecodedPoint::new("action", "released"),
                DecodedPoint::new("button", ""),
                DecodedPoint::new("rocker", ""),
                DecodedPoint::new("second_button", ""),
            ],
        },
        ProfileInfo {
            profile_id: "D5-00-01",
            label: "1BS magnet contact",
            rorg: 0xD5,
            points: vec![DecodedPoint::new("contact", false).device_class("door")],
        },
    ]
}

pub fn get_profile(profile_id: &str) -> Option<&'static ProfileInfo> {
    let want = profile_id.to_ascii_uppercase();
    KNOWN_PROFILES().iter().find(|p| p.profile_id == want)
}
