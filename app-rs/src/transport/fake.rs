//! `FakeLink` — synthetic ESP3 source for dev iteration without hardware.
//!
//! - Responds to the four COMMON_COMMANDs we use with synthetic RESPONSE
//!   frames (FAKE_GATEWAY identity).
//! - Periodically emits ERP1 frames rotating through RPS / 1BS / 4BS / VLD
//!   so the live inspector + EEP decode have data to chew on.

use std::io;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;
use tokio::sync::mpsc;

use crate::esp3::common_command::{self};
use crate::esp3::framing::{Frame, FrameDecoder, encode_frame};
use crate::esp3::packets::{CommonCommand, PacketType, ReturnCode};
use crate::esp3::radio::build_erp1;

/// Stub for R2.red. Implemented by R2.green.
#[derive(Debug)]
pub struct FakeLink {
    port: String,
    rx_rx: Arc<Mutex<mpsc::Receiver<Vec<u8>>>>,
    rx_tx: mpsc::Sender<Vec<u8>>,
    tx_decoder: Arc<Mutex<FrameDecoder>>,
    /// Override the chip's reply to CO_WR_LEARNMODE — used by tests to
    /// simulate older firmware that returns RET_NOT_SUPPORTED.
    learnmode_reply: Arc<Mutex<ReturnCode>>,
}

impl FakeLink {
    /// Build a fake link that emits a synthetic ERP1 frame every `period`.
    /// If `period` is zero, no automatic emission happens (tests inject manually).
    pub fn new(period: Duration) -> Self {
        let (rx_tx, rx_rx) = mpsc::channel::<Vec<u8>>(64);
        let link = Self {
            port: "fake://".to_string(),
            rx_rx: Arc::new(Mutex::new(rx_rx)),
            rx_tx: rx_tx.clone(),
            tx_decoder: Arc::new(Mutex::new(FrameDecoder::new())),
            learnmode_reply: Arc::new(Mutex::new(ReturnCode::RetOk)),
        };
        if !period.is_zero() {
            link.spawn_emitter(period);
        }
        link
    }

    pub fn port(&self) -> &str { &self.port }
    pub fn is_connected(&self) -> bool { true }

    /// Replace the canned learn-mode response (default RET_OK).
    pub async fn set_learnmode_reply(&self, code: ReturnCode) {
        *self.learnmode_reply.lock().await = code;
    }

    /// Inject a raw frame into the read queue (test hook).
    pub async fn inject(&self, bytes: Vec<u8>) {
        let _ = self.rx_tx.send(bytes).await;
    }

    /// Clone the internal sender so a test can keep injecting after the link
    /// itself has been moved into `LinkKind::Fake`.
    pub fn clone_inject_handle(&self) -> mpsc::Sender<Vec<u8>> {
        self.rx_tx.clone()
    }

    pub async fn read(&self) -> io::Result<Vec<u8>> {
        let mut guard = self.rx_rx.lock().await;
        match guard.recv().await {
            Some(bytes) => Ok(bytes),
            None => Err(io::Error::other("fake link closed")),
        }
    }

    pub async fn write(&self, data: &[u8]) -> io::Result<()> {
        // Decode whatever the controller wrote, synthesise a response.
        let mut dec = self.tx_decoder.lock().await;
        let frames = dec.feed(data);
        for frame in frames {
            let response = self.respond(&frame).await;
            let _ = self.rx_tx.send(response).await;
        }
        Ok(())
    }

    async fn respond(&self, frame: &Frame) -> Vec<u8> {
        if frame.packet_type == PacketType::CommonCommand as u8 && !frame.data.is_empty() {
            let cmd = frame.data[0];
            if cmd == CommonCommand::CoRdVersion as u8 {
                return synth_version_response();
            }
            if cmd == CommonCommand::CoRdIdbase as u8 {
                return synth_idbase_response();
            }
            if cmd == CommonCommand::CoWrLearnmode as u8 {
                let code = *self.learnmode_reply.lock().await;
                return resp_only(code);
            }
            // Default: OK.
            return resp_only(ReturnCode::RetOk);
        }
        resp_only(ReturnCode::RetOk)
    }

    fn spawn_emitter(&self, period: Duration) {
        let tx = self.rx_tx.clone();
        tokio::spawn(async move {
            let rotation: [(u8, &[u8], u32, u8); 4] = [
                (0xF6, &[0x50],                 0x12345670, 0x30),
                (0xD5, &[0x09],                 0x12345671, 0x00),
                (0xA5, &[0x00, 0x00, 0x80, 0x08], 0x12345672, 0x00),
                (0xD2, &[0x01, 0x02, 0x03],     0x12345673, 0x00),
            ];
            let mut i = 0usize;
            loop {
                tokio::time::sleep(period).await;
                let (rorg, payload, sender, status) = rotation[i % rotation.len()];
                if let Ok(bytes) = build_erp1(rorg, payload, sender, status) {
                    if tx.send(bytes).await.is_err() {
                        return;
                    }
                }
                i = i.wrapping_add(1);
            }
        });
    }
}

// --- canned response bodies ------------------------------------------------

fn resp_only(code: ReturnCode) -> Vec<u8> {
    encode_frame(PacketType::Response as u8, &[code as u8], &[])
        .expect("trivially in range")
}

fn synth_version_response() -> Vec<u8> {
    let mut payload = Vec::with_capacity(33);
    payload.push(ReturnCode::RetOk as u8);
    payload.extend_from_slice(&[9, 9, 9, 9]); // app
    payload.extend_from_slice(&[9, 9, 9, 9]); // api
    payload.extend_from_slice(&0xFAFA_0001u32.to_be_bytes()); // chip id
    payload.extend_from_slice(&0x0000_0001u32.to_be_bytes()); // device version
    payload.extend_from_slice(b"FAKE_GATEWAY\0\0\0\0");      // 16-byte description
    encode_frame(PacketType::Response as u8, &payload, &[]).expect("known good")
}

fn synth_idbase_response() -> Vec<u8> {
    let mut payload = vec![ReturnCode::RetOk as u8];
    payload.extend_from_slice(&0xFFAA_0000u32.to_be_bytes());
    encode_frame(PacketType::Response as u8, &payload, &[5]).expect("known good")
}

// Silence unused-import lint when `common_command` isn't directly referenced
// at top level; the `pub use` in mod.rs is what makes the path visible.
#[allow(dead_code)]
fn _force_link() {
    let _ = common_command::cmd_co_wr_reset;
}
