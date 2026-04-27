"""Status LEDs on the EnOcean daughter-board.

The legacy Java `LedsHandler` exported four BBB GPIOs (66, 67, 68, 69 — header
pins P8.07, P8.08, P8.10, P8.09) and toggled them on activity. The board this
codebase targets has three LEDs: green, orange, red. The default mapping
matches the colour names used in the Java field labels (`EthernetGreen`,
`EthernetAmber`); the third LED maps onto the first `Usr` slot.

Override the GPIO numbers via `VDSENSOR_LED_*_GPIO` env vars if your wiring
is different — confirm with the blink-each-GPIO loop in the README.

Two implementations:

  - `SysfsLeds`: writes `/sys/class/gpio/gpio<N>/value`. Used in the container
    on the BBB. Idempotent export — survives the kernel having already exported
    a pin from a previous run.
  - `NullLeds`: no-op, but keeps state in memory so the UI can still render a
    plausible answer when running with `--fake`.

Both implement the `Leds` Protocol so `Controller` doesn't care which it has.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from enum import StrEnum
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class Color(StrEnum):
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"


# Defaults derived from the legacy Java code (see CLAUDE.md):
#   _ledEthernetGreen → 67  (P8.08)
#   _ledEthernetAmber → 68  (P8.10)  — amber ≈ orange
#   _ledUsr0          → 66  (P8.07)  — best guess for "red"
DEFAULT_GPIOS: dict[Color, int] = {
    Color.GREEN: 67,
    Color.ORANGE: 68,
    Color.RED: 66,
}


class Leds(Protocol):
    @property
    def gpios(self) -> dict[Color, int]: ...
    def state(self) -> dict[Color, bool]: ...
    async def setup(self) -> None: ...
    async def cleanup(self) -> None: ...
    async def set(self, color: Color, on: bool) -> None: ...
    async def blink(self, color: Color, duration_ms: int = 80) -> None: ...

    # Convenience semantic blinks. Default impls below; override only if the
    # hardware needs different colours for the same event.
    async def blink_tx(self) -> None: ...
    async def blink_rx(self) -> None: ...
    async def blink_error(self) -> None: ...


class _BaseLeds:
    """Shared blink scheduling. Subclasses provide `_write(color, on)`."""

    def __init__(self, gpios: dict[Color, int]) -> None:
        self._gpios = dict(gpios)
        self._state: dict[Color, bool] = {c: False for c in self._gpios}
        self._tasks: dict[Color, asyncio.Task[None]] = {}

    @property
    def gpios(self) -> dict[Color, int]:
        return dict(self._gpios)

    def state(self) -> dict[Color, bool]:
        return dict(self._state)

    async def set(self, color: Color, on: bool) -> None:
        if color not in self._gpios:
            return
        self._state[color] = on
        await self._write(color, on)

    async def blink(self, color: Color, duration_ms: int = 80) -> None:
        # Cancel any in-flight blink on the same colour so rapid bursts don't
        # accumulate trailing turn-offs that overlap the next on.
        prev = self._tasks.pop(color, None)
        if prev is not None:
            prev.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await prev

        await self.set(color, True)

        async def _off() -> None:
            try:
                await asyncio.sleep(duration_ms / 1000)
                await self.set(color, False)
            except asyncio.CancelledError:
                pass

        self._tasks[color] = asyncio.create_task(_off(), name=f"led-{color}-off")

    async def blink_tx(self) -> None:
        await self.blink(Color.GREEN)

    async def blink_rx(self) -> None:
        await self.blink(Color.ORANGE)

    async def blink_error(self) -> None:
        await self.blink(Color.RED, duration_ms=200)

    async def _write(self, color: Color, on: bool) -> None:  # noqa: ARG002
        raise NotImplementedError


class NullLeds(_BaseLeds):
    """No GPIO access. State is tracked in memory so the UI still has data."""

    async def setup(self) -> None:
        return

    async def cleanup(self) -> None:
        for t in self._tasks.values():
            t.cancel()
        self._tasks.clear()

    async def _write(self, color: Color, on: bool) -> None:
        return


class SysfsLeds(_BaseLeds):
    """Writes `/sys/class/gpio/gpio<N>/value`."""

    SYSFS = Path("/sys/class/gpio")

    async def setup(self) -> None:
        for color, n in self._gpios.items():
            try:
                self._export(n)
                self._set_direction(n, "out")
                await self._write(color, False)
            except OSError as e:
                logger.warning("LED %s (gpio%d) setup failed: %s", color, n, e)

    async def cleanup(self) -> None:
        for t in self._tasks.values():
            t.cancel()
        self._tasks.clear()
        for n in self._gpios.values():
            with suppress(OSError):
                await asyncio.to_thread((self.SYSFS / "unexport").write_text, str(n))

    async def _write(self, color: Color, on: bool) -> None:
        n = self._gpios[color]
        path = self.SYSFS / f"gpio{n}" / "value"
        try:
            await asyncio.to_thread(path.write_text, "1" if on else "0")
        except OSError as e:
            logger.debug("LED %s (gpio%d) write failed: %s", color, n, e)

    # --- sync helpers (run on a thread when called from setup) -----------

    def _export(self, n: int) -> None:
        if (self.SYSFS / f"gpio{n}").is_dir():
            return
        try:
            (self.SYSFS / "export").write_text(str(n))
        except OSError as e:
            # Already-exported races and "device or resource busy" are
            # benign — the gpio node will appear shortly.
            logger.debug("export gpio%d ignored: %s", n, e)

    def _set_direction(self, n: int, direction: str) -> None:
        try:
            (self.SYSFS / f"gpio{n}" / "direction").write_text(direction)
        except OSError as e:
            logger.debug("set direction gpio%d=%s ignored: %s", n, direction, e)


def build_leds(kind: str, gpios: dict[Color, int] | None = None) -> Leds:
    """Construct a Leds implementation by string name (`'sysfs'` or `'none'`)."""
    g = gpios or DEFAULT_GPIOS
    kind = kind.lower()
    if kind in ("none", "null", "off"):
        return NullLeds(g)
    if kind in ("sysfs", "gpio"):
        return SysfsLeds(g)
    raise ValueError(f"unknown leds backend: {kind!r}")


# --- Standalone GPIO drive helpers (for the identification test endpoint) ----

# Restrict the test endpoint to the four GPIOs the legacy Java drove. Anything
# outside this set could collide with kernel-managed pins (USR LEDs, eMMC, etc.)
# and would make the failure mode much less obvious.
ALLOWED_TEST_GPIOS: frozenset[int] = frozenset({66, 67, 68, 69})


async def drive_test_gpio(gpio: int, *, duration_ms: int = 5000) -> None:
    """Drive `gpio` high for `duration_ms`, then low. Best-effort — failures
    are logged at INFO and swallowed (the test endpoint reports success
    optimistically; the user diagnoses by watching the actual LED).
    """
    if gpio not in ALLOWED_TEST_GPIOS:
        raise ValueError(f"gpio {gpio} not in test-allowed set {sorted(ALLOWED_TEST_GPIOS)}")

    sysfs = SysfsLeds.SYSFS / f"gpio{gpio}"
    try:
        if not sysfs.is_dir():
            await asyncio.to_thread((SysfsLeds.SYSFS / "export").write_text, str(gpio))
        await asyncio.to_thread((sysfs / "direction").write_text, "out")
        await asyncio.to_thread((sysfs / "value").write_text, "1")
        try:
            await asyncio.sleep(duration_ms / 1000)
        finally:
            await asyncio.to_thread((sysfs / "value").write_text, "0")
    except OSError as e:
        logger.info("drive_test_gpio(%d) failed: %s", gpio, e)
