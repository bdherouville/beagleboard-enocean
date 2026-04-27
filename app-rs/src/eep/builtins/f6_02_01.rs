//! EEP F6-02-01 — Light & Blind, 2 rocker switches (RPS / PTM200).
//!
//! Status byte:
//!   bit 5 (T21) = 1 (PTM200)
//!   bit 4 (NU)  = 1 → "N message": DB0 encodes which rocker(s) and direction
//!                 0 → "U message": typically a release event, DB0 = 0
//!
//! When NU = 1, DB0 layout:
//!   bits 7-5  R1   action of first rocker (0=AI, 1=AO, 2=BI, 3=BO)
//!   bit  4    EB   energy-bow / press flag (1 = pressed)
//!   bits 3-1  R2   second rocker action (only meaningful if SA=1)
//!   bit  0    SA   second-action flag (1 = R2 valid, 0 = ignore R2)

use crate::eep::DecodedPoint;
use crate::esp3::radio::Erp1;

const R_ACTIONS: [&str; 4] = ["AI", "AO", "BI", "BO"];

fn rocker_of(action: &str) -> &'static str {
    match action {
        "AI" | "AO" => "A",
        "BI" | "BO" => "B",
        _ => "",
    }
}

pub fn decode(erp1: &Erp1) -> Vec<DecodedPoint> {
    if erp1.payload.is_empty() {
        return Vec::new();
    }
    let db0 = erp1.payload[0];
    let nu = (erp1.status >> 4) & 0x01;

    if nu == 0 {
        return vec![
            DecodedPoint::new("action", "released"),
            DecodedPoint::new("button", ""),
            DecodedPoint::new("rocker", ""),
            DecodedPoint::new("second_button", ""),
        ];
    }

    let r1 = (db0 >> 5) & 0x07;
    let energy_bow = (db0 >> 4) & 0x01;
    let button: String = if (r1 as usize) < R_ACTIONS.len() {
        R_ACTIONS[r1 as usize].to_string()
    } else {
        format!("R1_{r1}")
    };
    let rocker = rocker_of(&button);
    let action = if energy_bow != 0 { "pressed" } else { "released" };

    let sa = db0 & 0x01;
    let second: String = if sa != 0 {
        let r2 = (db0 >> 1) & 0x07;
        if (r2 as usize) < R_ACTIONS.len() {
            R_ACTIONS[r2 as usize].to_string()
        } else {
            format!("R2_{r2}")
        }
    } else {
        "".to_string()
    };

    vec![
        DecodedPoint::new("action", action),
        DecodedPoint::new("button", button),
        DecodedPoint::new("rocker", rocker),
        DecodedPoint::new("second_button", second),
    ]
}
