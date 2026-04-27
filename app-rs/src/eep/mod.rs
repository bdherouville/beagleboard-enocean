//! EEP — EnOcean Equipment Profile decoders.
//!
//! The decoder dispatch is a simple `match` on the profile id (`"RR-FF-TT"`),
//! avoiding a global registry. Each builtin is its own module; the public
//! [`decode`] entry point picks the right one.

pub mod builtins;
pub mod catalog;
pub mod decoder;

pub use catalog::{KNOWN_PROFILES, ProfileInfo, get_profile};
pub use decoder::{DecodedPoint, DecodedValue, decode, has_decoder};
