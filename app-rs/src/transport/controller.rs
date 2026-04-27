//! ESP3 controller: the only thing that touches the link.
//!
//! Owns a `FrameDecoder`, dispatches incoming frames to:
//! - the `oneshot` of an in-flight RESPONSE round-trip,
//! - the `broadcast` channel of RADIO_ERP1 telegrams,
//! - the `broadcast` channel of EVENT frames.

use std::sync::Arc;
use std::time::Duration;
use tokio::sync::{Mutex, broadcast, oneshot};
use tokio::task::JoinHandle;
use tokio::time::timeout;
use tracing::{debug, info, warn};

use crate::esp3::common_command::{self as cc, IdBaseInfo, VersionInfo};
use crate::esp3::events::{Event, parse_event};
use crate::esp3::framing::{Frame, FrameDecoder};
use crate::esp3::packets::{PacketType, ReturnCode};
use crate::esp3::radio::{Erp1, parse_erp1};
use crate::esp3::response::{Response, parse_response};
use crate::transport::LinkKind;

const ERP1_BROADCAST_CAP: usize = 256;
const EVENT_BROADCAST_CAP: usize = 64;

#[derive(Debug, thiserror::Error)]
pub enum ControllerError {
    #[error("CO_WR_RESET / CO_RD_* / CO_WR_LEARNMODE returned RET_* != OK: {0:#x}")]
    BadReturnCode(u8),
    #[error("response timeout")]
    Timeout,
    #[error("transport: {0}")]
    Io(#[from] std::io::Error),
    #[error("parse: {0}")]
    Parse(#[from] crate::esp3::ParseError),
    #[error("encode: {0}")]
    Encode(#[from] crate::esp3::EncodeError),
}

#[derive(Debug, Clone, Default)]
pub struct GatewayInfo {
    pub version: Option<VersionInfo>,
    pub idbase: Option<IdBaseInfo>,
    pub learn_mode: bool,
}

pub struct Controller {
    link: Arc<LinkKind>,
    erp1_tx: broadcast::Sender<Erp1>,
    event_tx: broadcast::Sender<Event>,
    pending: Arc<Mutex<Option<oneshot::Sender<Response>>>>,
    info: Arc<Mutex<GatewayInfo>>,
    reader_task: Mutex<Option<JoinHandle<()>>>,
    tx_lock: Mutex<()>,
}

impl Controller {
    pub fn new(link: LinkKind) -> Arc<Self> {
        let (erp1_tx, _) = broadcast::channel(ERP1_BROADCAST_CAP);
        let (event_tx, _) = broadcast::channel(EVENT_BROADCAST_CAP);
        Arc::new(Self {
            link: Arc::new(link),
            erp1_tx,
            event_tx,
            pending: Arc::new(Mutex::new(None)),
            info: Arc::new(Mutex::new(GatewayInfo::default())),
            reader_task: Mutex::new(None),
            tx_lock: Mutex::new(()),
        })
    }

    pub fn port(&self) -> &str {
        self.link.port()
    }

    pub async fn info(&self) -> GatewayInfo {
        self.info.lock().await.clone()
    }

    /// Spawn the reader loop. Cancelled when the returned `JoinHandle` is dropped.
    pub async fn start(self: &Arc<Self>) {
        let me = Arc::clone(self);
        let handle = tokio::spawn(async move {
            me.reader_loop().await;
        });
        *self.reader_task.lock().await = Some(handle);
    }

    pub async fn stop(&self) {
        if let Some(h) = self.reader_task.lock().await.take() {
            h.abort();
        }
    }

    /// Subscribe to the ERP1 fan-out. Returns a fresh receiver that only
    /// sees frames that arrive *after* this call.
    pub fn subscribe(&self) -> broadcast::Receiver<Erp1> {
        self.erp1_tx.subscribe()
    }

    pub fn subscribe_events(&self) -> broadcast::Receiver<Event> {
        self.event_tx.subscribe()
    }

    /// Send a pre-encoded ESP3 frame and await the next RESPONSE.
    pub async fn request(
        &self,
        frame: Vec<u8>,
        deadline: Duration,
    ) -> Result<Response, ControllerError> {
        let _tx_guard = self.tx_lock.lock().await;
        let (resp_tx, resp_rx) = oneshot::channel();
        *self.pending.lock().await = Some(resp_tx);
        self.link.write(&frame).await?;
        match timeout(deadline, resp_rx).await {
            Ok(Ok(resp)) => Ok(resp),
            Ok(Err(_)) => Err(ControllerError::Timeout), // sender dropped
            Err(_) => {
                *self.pending.lock().await = None;
                Err(ControllerError::Timeout)
            }
        }
    }

    pub async fn reset(&self) -> Result<Response, ControllerError> {
        self.request(cc::cmd_co_wr_reset(), Duration::from_secs(1)).await
    }

    pub async fn read_version(&self) -> Result<VersionInfo, ControllerError> {
        let resp = self
            .request(cc::cmd_co_rd_version(), Duration::from_secs(1))
            .await?;
        if !resp.ok() {
            return Err(ControllerError::BadReturnCode(resp.return_code));
        }
        let info = cc::parse_version_response(&resp)?;
        self.info.lock().await.version = Some(info.clone());
        Ok(info)
    }

    pub async fn read_idbase(&self) -> Result<IdBaseInfo, ControllerError> {
        let resp = self
            .request(cc::cmd_co_rd_idbase(), Duration::from_secs(1))
            .await?;
        if !resp.ok() {
            return Err(ControllerError::BadReturnCode(resp.return_code));
        }
        let info = cc::parse_idbase_response(&resp)?;
        self.info.lock().await.idbase = Some(info.clone());
        Ok(info)
    }

    /// Best-effort: returns `Ok(true)` if the chip accepted, `Ok(false)` if
    /// it returned RET_NOT_SUPPORTED (older firmware — classic teach-in
    /// works passively regardless), `Err` for any other return code.
    pub async fn set_learn_mode(
        &self,
        enable: bool,
        timeout_ms: u32,
    ) -> Result<bool, ControllerError> {
        let resp = self
            .request(
                cc::cmd_co_wr_learnmode(enable, timeout_ms, 0xFF),
                Duration::from_secs(1),
            )
            .await?;
        if resp.ok() {
            self.info.lock().await.learn_mode = enable;
            return Ok(true);
        }
        if resp.return_code == ReturnCode::RetNotSupported as u8 {
            info!(
                "CO_WR_LEARNMODE({}) not supported by this chip — \
                classic teach-in still works passively",
                enable
            );
            return Ok(false);
        }
        Err(ControllerError::BadReturnCode(resp.return_code))
    }

    // --- internals ---------------------------------------------------------

    async fn reader_loop(self: Arc<Self>) {
        let mut decoder = FrameDecoder::new();
        loop {
            let chunk = match self.link.read().await {
                Ok(b) => b,
                Err(e) => {
                    warn!("link read error: {e}; backing off");
                    tokio::time::sleep(Duration::from_millis(500)).await;
                    continue;
                }
            };
            for frame in decoder.feed(&chunk) {
                self.dispatch(frame).await;
            }
        }
    }

    async fn dispatch(&self, frame: Frame) {
        if frame.packet_type == PacketType::Response as u8 {
            match parse_response(&frame) {
                Ok(resp) => {
                    if let Some(tx) = self.pending.lock().await.take() {
                        let _ = tx.send(resp);
                    } else {
                        debug!("orphan RESPONSE (no caller awaiting)");
                    }
                }
                Err(e) => warn!("malformed RESPONSE: {e}"),
            }
            return;
        }
        if frame.packet_type == PacketType::RadioErp1 as u8 {
            match parse_erp1(&frame) {
                Ok(erp1) => {
                    let _ = self.erp1_tx.send(erp1);
                }
                Err(e) => warn!("malformed ERP1: {e}"),
            }
            return;
        }
        if frame.packet_type == PacketType::Event as u8 {
            match parse_event(&frame) {
                Ok(ev) => {
                    let _ = self.event_tx.send(ev);
                }
                Err(e) => warn!("malformed EVENT: {e}"),
            }
            return;
        }
        debug!(
            "unhandled packet type {:#x} ({} data, {} opt)",
            frame.packet_type,
            frame.data.len(),
            frame.opt.len()
        );
    }
}

// Re-export `cc` here just so tests don't have to import the crate root.
#[allow(unused_imports)]
pub use crate::esp3::common_command;
