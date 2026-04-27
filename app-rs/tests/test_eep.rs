//! Per-EEP decoder smoke tests + dispatcher coverage.
//! Direct port of `app/tests/test_eep.py`.

use vdsensor::eep::catalog::KNOWN_PROFILES;
use vdsensor::eep::{DecodedValue, decode, has_decoder};
use vdsensor::esp3::radio::Erp1;

fn erp1(rorg: u8, payload: &[u8]) -> Erp1 {
    Erp1 {
        rorg,
        payload: payload.to_vec(),
        sender_id: 0xAA,
        status: 0,
        sub_tel: None,
        destination_id: None,
        dbm: None,
        security_level: None,
    }
}

fn erp1_with_status(rorg: u8, payload: &[u8], status: u8) -> Erp1 {
    let mut e = erp1(rorg, payload);
    e.status = status;
    e
}

fn lookup<'a>(points: &'a [vdsensor::eep::DecodedPoint], key: &str) -> &'a DecodedValue {
    &points
        .iter()
        .find(|p| p.key == key)
        .unwrap_or_else(|| panic!("no point named {key}"))
        .value
}

#[test]
fn test_every_known_profile_has_a_decoder() {
    for p in KNOWN_PROFILES() {
        assert!(has_decoder(p.profile_id), "no decoder for {}", p.profile_id);
    }
}

#[test]
fn test_a5_02_05_temperature_endpoints() {
    // DB1=0xFF → 0 °C ; DB1=0x00 → 40 °C
    let pts = decode("A5-02-05", &erp1(0xA5, &[0x00, 0x00, 0xFF, 0x08])).unwrap();
    assert_eq!(pts[0].key, "temperature");
    assert_eq!(*lookup(&pts, "temperature"), DecodedValue::Float(0.0));
    let pts = decode("A5-02-05", &erp1(0xA5, &[0x00, 0x00, 0x00, 0x08])).unwrap();
    assert_eq!(*lookup(&pts, "temperature"), DecodedValue::Float(40.0));
}

#[test]
fn test_a5_04_01_temp_and_humidity() {
    // DB3=100 (50% RH), DB2=125 (≈20°C), DB1=0, DB0=0x08 (data)
    let pts = decode("A5-04-01", &erp1(0xA5, &[0x64, 0x7D, 0x00, 0x08])).unwrap();
    let keys: Vec<_> = pts.iter().map(|p| p.key.clone()).collect();
    assert!(keys.contains(&"temperature".to_string()));
    assert!(keys.contains(&"humidity".to_string()));
    assert_eq!(*lookup(&pts, "humidity"), DecodedValue::Float(50.0));
    assert_eq!(*lookup(&pts, "temperature"), DecodedValue::Float(20.0));
}

#[test]
fn test_a5_07_01_pir_motion_threshold() {
    let no_motion = decode("A5-07-01", &erp1(0xA5, &[0xFA, 0x00, 0x00, 0x08])).unwrap();
    let motion = decode("A5-07-01", &erp1(0xA5, &[0xFA, 0x00, 0x80, 0x08])).unwrap();
    assert_eq!(*lookup(&no_motion, "motion"), DecodedValue::Bool(false));
    assert_eq!(*lookup(&motion, "motion"), DecodedValue::Bool(true));
}

#[test]
fn test_a5_09_04_co2_decode() {
    // DB2 = 0x32 (=50) → 500 ppm
    let pts = decode("A5-09-04", &erp1(0xA5, &[0x00, 0x32, 0x80, 0x08])).unwrap();
    assert_eq!(*lookup(&pts, "co2"), DecodedValue::Int(500));
}

#[test]
fn test_d5_00_01_contact_open_closed() {
    let open_pts = decode("D5-00-01", &erp1(0xD5, &[0x08])).unwrap();
    let closed_pts = decode("D5-00-01", &erp1(0xD5, &[0x09])).unwrap();
    assert_eq!(*lookup(&open_pts, "contact"), DecodedValue::Bool(false));
    assert_eq!(*lookup(&closed_pts, "contact"), DecodedValue::Bool(true));
}

fn f6(db0: u8, status: u8) -> Erp1 {
    erp1_with_status(0xF6, &[db0], status)
}

#[test]
fn test_f6_02_01_release_when_nu_zero() {
    let rel = decode("F6-02-01", &f6(0x00, 0x20)).unwrap();
    assert_eq!(*lookup(&rel, "action"), DecodedValue::Str("released".into()));
    assert_eq!(*lookup(&rel, "button"), DecodedValue::Str("".into()));
    assert_eq!(*lookup(&rel, "rocker"), DecodedValue::Str("".into()));
}

#[test]
fn test_f6_02_01_press_ai() {
    // status NU=1 (0x30 = T21+NU), DB0: R1=0 (AI), energy bow = 1
    let pts = decode("F6-02-01", &f6(0x10, 0x30)).unwrap();
    assert_eq!(*lookup(&pts, "action"), DecodedValue::Str("pressed".into()));
    assert_eq!(*lookup(&pts, "button"), DecodedValue::Str("AI".into()));
    assert_eq!(*lookup(&pts, "rocker"), DecodedValue::Str("A".into()));
    assert_eq!(*lookup(&pts, "second_button"), DecodedValue::Str("".into()));
}

#[test]
fn test_f6_02_01_press_ao_bi_bo_buttons() {
    // AO: R1=1, EB=1 → DB0 = 0b001_1_0000 = 0x30
    // BI: R1=2, EB=1 → DB0 = 0b010_1_0000 = 0x50
    // BO: R1=3, EB=1 → DB0 = 0b011_1_0000 = 0x70
    let cases: &[(u8, &str, &str)] =
        &[(0x30, "AO", "A"), (0x50, "BI", "B"), (0x70, "BO", "B")];
    for &(db0, button, rocker) in cases {
        let pts = decode("F6-02-01", &f6(db0, 0x30)).unwrap();
        assert_eq!(*lookup(&pts, "button"), DecodedValue::Str(button.into()));
        assert_eq!(*lookup(&pts, "rocker"), DecodedValue::Str(rocker.into()));
        assert_eq!(*lookup(&pts, "action"), DecodedValue::Str("pressed".into()));
    }
}

#[test]
fn test_f6_02_01_second_action_when_sa_set() {
    // First press AI (R1=0) + simultaneous BO (R2=3) with SA=1, EB=1.
    // DB0 = R1[7:5]=000 | EB[4]=1 | R2[3:1]=011 | SA[0]=1 = 0x17
    let pts = decode("F6-02-01", &f6(0x17, 0x30)).unwrap();
    assert_eq!(*lookup(&pts, "button"), DecodedValue::Str("AI".into()));
    assert_eq!(*lookup(&pts, "second_button"), DecodedValue::Str("BO".into()));
}
