//! ESP3 transport layer: serial / fake link + Controller orchestration.
//!
//! `Controller` is the only thing that touches the link. It spawns a
//! reader task that fans out RADIO_ERP1 frames via a `broadcast` channel,
//! fulfils outstanding `request()` futures on RESPONSE frames, and forwards
//! EVENT frames to event subscribers.

pub mod controller;
pub mod fake;
pub mod link;
pub mod serial_link;

pub use controller::{Controller, ControllerError, GatewayInfo};
pub use fake::FakeLink;
pub use link::LinkKind;
pub use serial_link::SerialLink;
