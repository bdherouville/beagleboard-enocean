//! Test helpers shared across integration tests.

pub fn hex(s: &str) -> Vec<u8> {
    let stripped: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    (0..stripped.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&stripped[i..i + 2], 16).expect("invalid hex"))
        .collect()
}
