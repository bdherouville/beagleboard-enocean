"""Clock-sync gate.

The BeagleBone Black has no battery-backed RTC: at first boot, `time.time()`
sits at the kernel's compiled-in epoch (often around 2000-01-01) until NTP
catches up. Pairing or last-seen timestamps stamped before sync are wrong —
sometimes by 25 years — and surface in HA / SQLite as garbage.

`wait_for_clock_sync()` blocks startup until the clock has plausibly synced,
then returns. If NTP is broken on the host, we log a warning and proceed
rather than refusing to start; a service that runs is more useful than one
that won't boot, and the timestamps just need a one-time `UPDATE` later.

The threshold is configurable but defaults to 2020-01-01 — anything below
that is unmistakably pre-sync.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

# 2020-01-01 00:00:00 UTC. Anything earlier is pre-NTP-sync on a freshly-booted BBB.
DEFAULT_MIN_EPOCH = 1577836800


async def wait_for_clock_sync(
    *, min_epoch: int = DEFAULT_MIN_EPOCH, timeout_s: float = 30.0,
    poll_interval_s: float = 0.5,
) -> bool:
    """Return True if the clock is plausibly synced before `timeout_s` elapses.

    On True, downstream code can stamp `paired_at` / `last_seen` and trust them.
    On False, the caller may proceed but should annotate timestamps as suspect
    (or just log a warning; v1 does the latter).
    """
    if time.time() >= min_epoch:
        logger.debug("clock already synced (now=%d, min=%d)", int(time.time()), min_epoch)
        return True

    logger.info(
        "waiting up to %.1fs for clock sync (current=%d, min=%d)",
        timeout_s, int(time.time()), min_epoch,
    )
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        await asyncio.sleep(poll_interval_s)
        if time.time() >= min_epoch:
            elapsed = time.monotonic() - start
            logger.info("clock sync detected after %.2fs", elapsed)
            return True

    logger.warning(
        "clock did not sync within %.1fs (still %d) — proceeding with possibly wrong timestamps",
        timeout_s, int(time.time()),
    )
    return False
