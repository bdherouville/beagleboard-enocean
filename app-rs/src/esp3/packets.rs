//! ESP3 enums + protocol constants. All numeric values reference ESP3 v1.58.

/// §3.4.1 — every ESP3 frame starts with this byte.
pub const SYNC_BYTE: u8 = 0x55;

/// §1.7 — header is u16 data length + u8 opt length + u8 packet type.
pub const HEADER_LENGTH: usize = 4;

/// §1.8 / §2.x — packet-type field discriminator.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum PacketType {
    RadioErp1 = 0x01,         // §2.1
    Response = 0x02,          // §2.2
    RadioSubTel = 0x03,       // §2.3
    Event = 0x04,             // §2.4
    CommonCommand = 0x05,     // §2.5
    SmartAckCommand = 0x06,   // §2.6
    RemoteManCommand = 0x07,  // §2.7
    RadioMessage = 0x09,      // §2.8
    RadioErp2 = 0x0A,         // §2.9
    CommandAccepted = 0x0C,   // §2.10
    Radio80215_4 = 0x10,      // §2.11
    Config24Ghz = 0x11,       // §2.12
}

/// §2.2.2 — RESPONSE return codes.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ReturnCode {
    RetOk = 0x00,
    RetError = 0x01,
    RetNotSupported = 0x02,
    RetWrongParam = 0x03,
    RetOperationDenied = 0x04,
    RetLockSet = 0x05,
    RetBufferToSmall = 0x06,
    RetNoFreeBuffer = 0x07,
}

/// §2.4.2 — EVENT (0x04) event codes.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum EventCode {
    SaReclaimNotSuccessful = 0x01,
    SaConfirmLearn = 0x02,
    SaLearnAck = 0x03,
    CoReady = 0x04,
    CoEventSecuredevices = 0x05,
    CoDutycycleLimit = 0x06,
    CoTransmitFailed = 0x07,
    CoTxDone = 0x08,
    CoLrnModeDisabled = 0x09,
}

/// §2.5.2 — COMMON_COMMAND (0x05) command codes.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CommonCommand {
    CoWrSleep = 0x01,
    CoWrReset = 0x02,
    CoRdVersion = 0x03,
    CoRdSysLog = 0x04,
    CoWrIdbase = 0x07,
    CoRdIdbase = 0x08,
    CoWrLearnmode = 0x17,
    CoRdLearnmode = 0x18,
}

/// RORG (radio choice byte) — only the v1 set we decode.
pub mod rorg {
    pub const RPS: u8 = 0xF6;      // §EEP F6
    pub const ONE_BS: u8 = 0xD5;   // §EEP D5
    pub const FOUR_BS: u8 = 0xA5;  // §EEP A5
    pub const VLD: u8 = 0xD2;      // §EEP D2
    pub const UTE: u8 = 0xD4;      // §EEP D4
    pub const ADT: u8 = 0xA6;      // §EEP A6 wrapper
    pub const SIGNAL: u8 = 0xD0;
    pub const MSC: u8 = 0xD1;
}
