//! `DecodedPoint` + the public `decode(profile_id, erp1)` dispatcher.

use crate::eep::builtins::{a5_02_05, a5_04_01, a5_07_01, a5_09_04, d5_00_01, f6_02_01};
use crate::esp3::radio::Erp1;

#[derive(Debug, Clone, PartialEq)]
pub enum DecodedValue {
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
}

impl DecodedValue {
    pub fn as_json(&self) -> serde_json::Value {
        match self {
            Self::Bool(b) => serde_json::Value::Bool(*b),
            Self::Int(i) => serde_json::Value::Number((*i).into()),
            Self::Float(f) => serde_json::Number::from_f64(*f)
                .map(serde_json::Value::Number)
                .unwrap_or(serde_json::Value::Null),
            Self::Str(s) => serde_json::Value::String(s.clone()),
        }
    }
}

impl From<bool> for DecodedValue {
    fn from(v: bool) -> Self { Self::Bool(v) }
}
impl From<i64> for DecodedValue {
    fn from(v: i64) -> Self { Self::Int(v) }
}
impl From<i32> for DecodedValue {
    fn from(v: i32) -> Self { Self::Int(v as i64) }
}
impl From<u32> for DecodedValue {
    fn from(v: u32) -> Self { Self::Int(v as i64) }
}
impl From<f64> for DecodedValue {
    fn from(v: f64) -> Self { Self::Float(v) }
}
impl From<f32> for DecodedValue {
    fn from(v: f32) -> Self { Self::Float(v as f64) }
}
impl From<&str> for DecodedValue {
    fn from(v: &str) -> Self { Self::Str(v.to_string()) }
}
impl From<String> for DecodedValue {
    fn from(v: String) -> Self { Self::Str(v) }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DecodedPoint {
    pub key: String,
    pub value: DecodedValue,
    pub unit: Option<String>,
    pub device_class: Option<String>,
    pub state_class: Option<String>,
}

impl DecodedPoint {
    /// Builder-style helper: `DecodedPoint::new("temperature", 21.3).unit("°C").device_class("temperature").state_class("measurement")`.
    pub fn new(key: impl Into<String>, value: impl Into<DecodedValue>) -> Self {
        Self {
            key: key.into(),
            value: value.into(),
            unit: None,
            device_class: None,
            state_class: None,
        }
    }

    pub fn unit(mut self, u: impl Into<String>) -> Self {
        self.unit = Some(u.into());
        self
    }

    pub fn device_class(mut self, c: impl Into<String>) -> Self {
        self.device_class = Some(c.into());
        self
    }

    pub fn state_class(mut self, c: impl Into<String>) -> Self {
        self.state_class = Some(c.into());
        self
    }
}

/// Decode `erp1` according to `profile_id` (e.g. `"A5-02-05"`).
/// Returns `None` if no decoder is registered for that profile.
pub fn decode(profile_id: &str, erp1: &Erp1) -> Option<Vec<DecodedPoint>> {
    match profile_id.to_ascii_uppercase().as_str() {
        "A5-02-05" => Some(a5_02_05::decode(erp1)),
        "A5-04-01" => Some(a5_04_01::decode(erp1)),
        "A5-07-01" => Some(a5_07_01::decode(erp1)),
        "A5-09-04" => Some(a5_09_04::decode(erp1)),
        "F6-02-01" => Some(f6_02_01::decode(erp1)),
        "D5-00-01" => Some(d5_00_01::decode(erp1)),
        _ => None,
    }
}

pub fn has_decoder(profile_id: &str) -> bool {
    matches!(
        profile_id.to_ascii_uppercase().as_str(),
        "A5-02-05" | "A5-04-01" | "A5-07-01" | "A5-09-04" | "F6-02-01" | "D5-00-01"
    )
}
