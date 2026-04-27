//! Container entry-point. Settings-driven; assembles Controller, DB, MQTT,
//! and the axum app, then runs forever. Currently a stub during the Rust
//! migration — modules land milestone by milestone.

use vdsensor::esp3;

fn main() {
    println!(
        "vdsensor (rust) — stub main. esp3 sync byte = 0x{:02x}",
        esp3::SYNC_BYTE
    );
}
