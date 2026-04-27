//! Transport: Controller + FakeLink integration.
//! Mirrors the Python `test_leds.py` / sniff smoke checks.

use std::time::Duration;
use tokio::time::timeout;

use vdsensor::esp3::common_command as cc;
use vdsensor::esp3::framing::encode_frame;
use vdsensor::esp3::packets::{PacketType, ReturnCode};
use vdsensor::esp3::radio::build_erp1;
use vdsensor::transport::{Controller, FakeLink, LinkKind};

#[tokio::test]
async fn fake_controller_emits_periodic_erp1_frames() {
    let link = FakeLink::new(Duration::from_millis(40));
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let mut sub = controller.subscribe();
    let erp1 = timeout(Duration::from_secs(1), sub.recv())
        .await
        .expect("erp1 within 1s")
        .expect("subscriber not closed");
    assert!(
        matches!(erp1.rorg, 0xF6 | 0xD5 | 0xA5 | 0xD2),
        "got rorg {:#x}",
        erp1.rorg
    );
}

#[tokio::test]
async fn read_version_against_fake_returns_fake_gateway() {
    let link = FakeLink::new(Duration::from_secs(60)); // no auto-emission
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let info = controller.read_version().await.expect("version ok");
    assert_eq!(info.description, "FAKE_GATEWAY");
    assert_eq!(info.chip_id, 0xFAFA_0001);
}

#[tokio::test]
async fn read_idbase_against_fake_returns_synthetic_base() {
    let link = FakeLink::new(Duration::from_secs(60));
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let info = controller.read_idbase().await.expect("idbase ok");
    assert_eq!(info.base_id, 0xFFAA_0000);
    assert_eq!(info.remaining_writes, 5);
}

#[tokio::test]
async fn set_learn_mode_returns_false_on_ret_not_supported() {
    let link = FakeLink::new(Duration::from_secs(60));
    link.set_learnmode_reply(ReturnCode::RetNotSupported).await;
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let accepted = controller.set_learn_mode(true, 5_000).await.expect("no error raised");
    assert!(!accepted, "RET_NOT_SUPPORTED → returns Ok(false)");
}

#[tokio::test]
async fn set_learn_mode_returns_true_on_ret_ok() {
    let link = FakeLink::new(Duration::from_secs(60));
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let accepted = controller.set_learn_mode(true, 5_000).await.expect("ok");
    assert!(accepted);
    assert!(controller.info().await.learn_mode);
}

#[tokio::test]
async fn injected_erp1_frame_reaches_subscribers() {
    let link = FakeLink::new(Duration::from_secs(60));
    let raw = build_erp1(0xA5, &[0x11, 0x22, 0x33, 0x08], 0xDEAD_BEEF, 0).unwrap();
    let injection = link.clone_inject_handle();
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let mut sub = controller.subscribe();
    injection.send(raw).await.expect("inject");

    let erp1 = timeout(Duration::from_secs(1), sub.recv())
        .await
        .expect("got frame")
        .expect("subscriber alive");
    assert_eq!(erp1.sender_id, 0xDEAD_BEEF);
    assert_eq!(erp1.payload, vec![0x11, 0x22, 0x33, 0x08]);
}

#[tokio::test]
async fn bad_return_code_propagates_as_error() {
    let link = FakeLink::new(Duration::from_secs(60));
    // Hijack: replace the canned learnmode reply with RET_ERROR.
    link.set_learnmode_reply(ReturnCode::RetError).await;
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let result = controller.set_learn_mode(true, 5_000).await;
    assert!(result.is_err(), "RET_ERROR must surface as ControllerError");
}

// Smoke check that an arbitrary RESPONSE frame reaches an in-flight request().
#[tokio::test]
async fn request_round_trip_against_synthetic_response() {
    let link = FakeLink::new(Duration::from_secs(60));
    let controller = Controller::new(LinkKind::Fake(link));
    controller.start().await;
    let resp = controller
        .request(cc::cmd_co_wr_reset(), Duration::from_secs(1))
        .await
        .expect("response within deadline");
    assert!(resp.ok());
    // Frame echo: encoded version of the canned RET_OK payload.
    let expect = encode_frame(PacketType::Response as u8, &[ReturnCode::RetOk as u8], &[]).unwrap();
    let _ = expect; // not asserting bytes — we trust the framing tests
}
