//! Web layer: axum router + minijinja templates + WebSocket fan-outs.
//!
//! Templates and static files are baked into the binary at compile time via
//! `include_str!` / `include_bytes!`, so the runtime image is a single static
//! ELF with no filesystem deps.

pub mod app;
pub mod state;
pub mod templates;

pub mod routes {
    pub mod pages;
}
pub mod ws {
    pub mod live;
}

pub use app::build_app;
pub use state::AppState;
