"""Container entry-point: settings-driven, no argparse.

    python -m vdsensor.main

Reads VDSENSOR_* env vars (see vdsensor.config.Settings), wires up Controller
(real or fake), Database, MQTT, and the FastAPI app, then runs uvicorn.
"""

from __future__ import annotations

import asyncio
import logging

import uvicorn

from .config import Settings
from .hardware import Color, build_leds
from .transport import Controller, FakeSerialLink
from .web.app import build_app


def _make_controller(settings: Settings) -> Controller:
    gpios = {
        Color.GREEN: settings.led_green_gpio,
        Color.ORANGE: settings.led_orange_gpio,
        Color.RED: settings.led_red_gpio,
    }
    # In fake mode, default to NullLeds so we don't try to write /sys on the dev host.
    backend = "none" if settings.fake else settings.leds_backend
    leds = build_leds(backend, gpios)
    if settings.fake:
        return Controller(FakeSerialLink(), leds=leds)
    return Controller.from_serial(settings.serial_port, settings.serial_baud, leds=leds)


async def _run() -> None:
    settings = Settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    controller = _make_controller(settings)
    app = build_app(
        controller,
        db_url=settings.db_url,
        telegram_ring_size=settings.telegram_ring_size,
        mqtt_url=settings.mqtt_url,
        mqtt_prefix=settings.mqtt_prefix,
        ha_discovery_prefix=settings.ha_discovery_prefix,
    )
    config = uvicorn.Config(
        app,
        host=settings.http_host,
        port=settings.http_port,
        log_level="info",
        lifespan="on",
    )
    await uvicorn.Server(config).serve()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
