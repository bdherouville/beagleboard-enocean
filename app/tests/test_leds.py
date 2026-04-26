"""LED state, blink scheduling, and Controller hooks (NullLeds + fake link)."""

from __future__ import annotations

import asyncio

import pytest

from vdsensor.esp3 import common_command as cc
from vdsensor.esp3.framing import encode_frame
from vdsensor.esp3.packets import PacketType, ReturnCode
from vdsensor.esp3.radio import build_erp1
from vdsensor.hardware import Color, NullLeds, build_leds
from vdsensor.transport import Controller, FakeSerialLink


@pytest.fixture
def leds() -> NullLeds:
    return NullLeds({Color.GREEN: 67, Color.ORANGE: 68, Color.RED: 66})


async def test_set_toggles_state(leds: NullLeds) -> None:
    assert leds.state() == {Color.GREEN: False, Color.ORANGE: False, Color.RED: False}
    await leds.set(Color.GREEN, True)
    assert leds.state()[Color.GREEN] is True
    await leds.set(Color.GREEN, False)
    assert leds.state()[Color.GREEN] is False


async def test_blink_returns_to_off(leds: NullLeds) -> None:
    await leds.blink(Color.RED, duration_ms=20)
    assert leds.state()[Color.RED] is True          # immediately after blink
    await asyncio.sleep(0.06)                        # let the off-task fire
    assert leds.state()[Color.RED] is False


async def test_blink_unknown_color_is_noop() -> None:
    leds = NullLeds({Color.GREEN: 67})
    await leds.set(Color.RED, True)                  # not in gpios → ignored
    assert leds.state() == {Color.GREEN: False}


def test_build_leds_dispatches_by_kind() -> None:
    g = {Color.GREEN: 67}
    assert build_leds("none", g).__class__.__name__ == "NullLeds"
    assert build_leds("sysfs", g).__class__.__name__ == "SysfsLeds"
    with pytest.raises(ValueError):
        build_leds("bogus", g)


async def test_controller_blinks_green_on_request_and_orange_on_erp1(
    leds: NullLeds,
) -> None:
    """End-to-end: a fake link with a real Controller — TX→green, RX→orange."""
    controller = Controller(FakeSerialLink(telegram_period=0.05), leds=leds)
    async with controller.run():
        # request() sends a frame and waits for a synthetic RESPONSE.
        await controller.read_version()
        # request() blinks green; assert the off-task hasn't yet expired.
        # (blink_tx default duration is 80 ms, so within 10 ms it's still on.)
        assert leds.state()[Color.GREEN] is True

        # Wait until the FakeSerialLink emits at least one ERP1 (period=0.05 s).
        async with controller.subscribe() as q:
            async with asyncio.timeout(0.5):
                await q.get()
        # Orange is blinked from a fire-and-forget task; give it a moment.
        await asyncio.sleep(0)
        assert leds.state()[Color.ORANGE] is True


async def test_controller_blinks_red_on_response_error(leds: NullLeds) -> None:
    """If the chip replies with anything other than RET_OK, red flashes."""
    link = FakeSerialLink()

    # Replace the fake link's normal CO_RD_VERSION reply with an error response.
    err_frame = encode_frame(PacketType.RESPONSE, bytes((ReturnCode.RET_NOT_SUPPORTED,)))

    original_write = link.write

    async def write_intercepting(data: bytes) -> None:
        # Drop anything the controller sends, queue an error response back.
        link._out.put_nowait(err_frame)
        # Don't call original_write — we don't want the canned OK reply.
        _ = original_write

    link.write = write_intercepting                  # type: ignore[method-assign]

    controller = Controller(link, leds=leds)
    async with controller.run():
        resp = await controller.request(cc.cmd_co_rd_version())
        assert resp.return_code == ReturnCode.RET_NOT_SUPPORTED
        await asyncio.sleep(0)
        assert leds.state()[Color.RED] is True


async def test_build_erp1_rx_path(leds: NullLeds) -> None:
    """Manually feed an ERP1 frame into Controller's decoder and confirm orange blinks."""
    link = FakeSerialLink()
    erp1_bytes = build_erp1(0xA5, b"\x00\x00\x80\x08", sender_id=0x1234, status=0)
    link._out.put_nowait(erp1_bytes)

    controller = Controller(link, leds=leds)
    async with controller.run():
        async with controller.subscribe() as q:
            async with asyncio.timeout(0.5):
                got = await q.get()
        assert got.sender_id == 0x1234
        await asyncio.sleep(0)
        assert leds.state()[Color.ORANGE] is True
