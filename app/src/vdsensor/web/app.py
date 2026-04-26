"""FastAPI app factory.

Owns the Controller + Database + MQTT bridge + persistence loop + PairingService
lifespan so that all background tasks come up together with the HTTP server.
A failed chip probe does not abort startup — the dashboard surfaces "no
gateway" and the live page keeps working as soon as telegrams flow.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..mqtt import MqttBridge, Topics, parse_mqtt_url
from ..registry import Database
from ..registry.pairing import PairingService
from ..registry.persistence import persistence_loop
from ..transport import Controller
from .deps import (
    set_controller,
    set_database,
    set_mqtt,
    set_pairing,
    set_templates,
)
from .routes.devices import router as devices_router
from .routes.pages import router as pages_router
from .routes.pairing import router as pairing_router
from .ws.live import router as live_router
from .ws.pair import router as pair_ws_router

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
TEMPLATES_DIR = _HERE / "templates"
STATIC_DIR = _HERE / "static"


def build_app(
    controller: Controller,
    *,
    db_url: str = "sqlite+aiosqlite:///:memory:",
    telegram_ring_size: int = 10_000,
    mqtt_url: str | None = None,
    mqtt_prefix: str = "vdsensor",
    ha_discovery_prefix: str = "homeassistant",
) -> FastAPI:
    db = Database(db_url, telegram_ring_size=telegram_ring_size)
    pairing = PairingService(controller, db)

    bridge: MqttBridge | None = None
    if mqtt_url is not None:
        bridge = MqttBridge(parse_mqtt_url(mqtt_url),
                            Topics(prefix=mqtt_prefix, ha_prefix=ha_discovery_prefix))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(controller.run())
            await stack.enter_async_context(db.run())
            if bridge is not None:
                await stack.enter_async_context(bridge.run())

            try:
                await controller.read_version()
                await controller.read_idbase()
                logger.info("gateway probed: %s", controller.info)
            except Exception as e:
                logger.warning("gateway probe failed: %s", e)

            persist = asyncio.create_task(
                persistence_loop(controller, db, bridge), name="persistence"
            )
            try:
                yield
            finally:
                persist.cancel()
                try:
                    await persist
                except (asyncio.CancelledError, Exception):
                    pass

    app = FastAPI(title="vdsensor", lifespan=lifespan)
    set_controller(controller)
    set_database(db)
    set_pairing(pairing)
    set_mqtt(bridge)
    set_templates(Jinja2Templates(directory=str(TEMPLATES_DIR)))

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(pages_router)
    app.include_router(devices_router)
    app.include_router(pairing_router)
    app.include_router(live_router)
    app.include_router(pair_ws_router)
    return app
