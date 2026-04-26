"""Clock-sync gate behaviour without sleeping for real seconds."""

from __future__ import annotations

import time

from vdsensor.clock import DEFAULT_MIN_EPOCH, wait_for_clock_sync


async def test_returns_true_immediately_when_already_synced() -> None:
    # The host running the test is well past 2020-01-01.
    assert time.time() >= DEFAULT_MIN_EPOCH
    ok = await wait_for_clock_sync(timeout_s=0.01)
    assert ok is True


async def test_returns_true_once_clock_advances(monkeypatch) -> None:
    """Simulate a pre-sync host whose clock catches up after a couple of polls."""
    fake_now = [1500000000]                # before DEFAULT_MIN_EPOCH

    def fake_time() -> float:
        return fake_now[0]

    monkeypatch.setattr("vdsensor.clock.time.time", fake_time)

    # On the second poll, advance the clock past the threshold.
    poll_count = [0]
    original_sleep = __import__("asyncio").sleep

    async def quick_sleep(delay: float) -> None:
        poll_count[0] += 1
        if poll_count[0] >= 2:
            fake_now[0] = DEFAULT_MIN_EPOCH + 100
        # don't actually sleep — keep the test fast
        await original_sleep(0)

    monkeypatch.setattr("vdsensor.clock.asyncio.sleep", quick_sleep)

    ok = await wait_for_clock_sync(timeout_s=10.0, poll_interval_s=0.01)
    assert ok is True


async def test_returns_false_on_timeout(monkeypatch) -> None:
    monkeypatch.setattr("vdsensor.clock.time.time", lambda: 1500000000)

    async def quick_sleep(delay: float) -> None:
        # Fast-forward monotonic by a substantial amount each tick so we
        # blow past the timeout in two iterations without real sleeping.
        pass

    monkeypatch.setattr("vdsensor.clock.asyncio.sleep", quick_sleep)
    # Tiny timeout so the loop exits fast.
    ok = await wait_for_clock_sync(timeout_s=0.05, poll_interval_s=0.01)
    assert ok is False
