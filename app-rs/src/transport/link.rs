//! `LinkKind` — enum-dispatched abstraction over a real serial port and
//! a fake in-process source. Static dispatch keeps the binary small and
//! avoids `async-trait` indirection.

use crate::transport::{FakeLink, SerialLink};

#[derive(Debug)]
pub enum LinkKind {
    Serial(SerialLink),
    Fake(FakeLink),
}

impl LinkKind {
    pub fn port(&self) -> &str {
        match self {
            Self::Serial(s) => s.port(),
            Self::Fake(f) => f.port(),
        }
    }

    pub fn is_connected(&self) -> bool {
        match self {
            Self::Serial(s) => s.is_connected(),
            Self::Fake(f) => f.is_connected(),
        }
    }

    pub async fn read(&self) -> std::io::Result<Vec<u8>> {
        match self {
            Self::Serial(s) => s.read().await,
            Self::Fake(f) => f.read().await,
        }
    }

    pub async fn write(&self, data: &[u8]) -> std::io::Result<()> {
        match self {
            Self::Serial(s) => s.write(data).await,
            Self::Fake(f) => f.write(data).await,
        }
    }
}
