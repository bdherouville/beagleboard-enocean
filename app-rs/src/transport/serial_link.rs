//! Real serial link via `tokio-serial`. Open lazily on first read/write,
//! reconnect with exponential backoff on errors. Mirrors the Python
//! `SerialLink` design but flatter — no supervisor task; the `Controller`
//! reader loop already retries on failed reads.

use std::sync::Arc;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::Mutex;
use tokio_serial::{SerialPortBuilderExt, SerialStream};

#[derive(Debug)]
pub struct SerialLink {
    port: String,
    baud: u32,
    stream: Arc<Mutex<Option<SerialStream>>>,
}

impl SerialLink {
    pub fn new(port: impl Into<String>, baud: u32) -> Self {
        Self {
            port: port.into(),
            baud,
            stream: Arc::new(Mutex::new(None)),
        }
    }

    pub fn port(&self) -> &str {
        &self.port
    }

    pub fn is_connected(&self) -> bool {
        // Best-effort probe — locks contended only on read/write paths.
        self.stream.try_lock().map(|g| g.is_some()).unwrap_or(false)
    }

    /// Read one chunk of bytes. Opens the port lazily; on error, drops
    /// the stream so the next call retries.
    pub async fn read(&self) -> std::io::Result<Vec<u8>> {
        let mut buf = [0u8; 256];
        let mut guard = self.stream.lock().await;
        if guard.is_none() {
            *guard = Some(self.open().await?);
        }
        let stream = guard.as_mut().expect("just-opened");
        match stream.read(&mut buf).await {
            Ok(0) => {
                *guard = None;
                Err(std::io::Error::new(std::io::ErrorKind::UnexpectedEof, "serial EOF"))
            }
            Ok(n) => Ok(buf[..n].to_vec()),
            Err(e) => {
                *guard = None;
                Err(e)
            }
        }
    }

    pub async fn write(&self, data: &[u8]) -> std::io::Result<()> {
        let mut guard = self.stream.lock().await;
        if guard.is_none() {
            *guard = Some(self.open().await?);
        }
        let stream = guard.as_mut().expect("just-opened");
        stream.write_all(data).await?;
        stream.flush().await?;
        Ok(())
    }

    async fn open(&self) -> std::io::Result<SerialStream> {
        tokio_serial::new(&self.port, self.baud)
            .open_native_async()
            .map_err(std::io::Error::other)
    }
}
