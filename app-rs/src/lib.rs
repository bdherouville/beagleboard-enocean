//! `vdsensor` library — the EnOcean ESP3 router rewritten in Rust.
//!
//! Modules land milestone-by-milestone per the migration plan; this is the
//! crate root that re-exports each as it stabilises. Test crates target
//! these `pub` paths directly.

pub mod esp3;
