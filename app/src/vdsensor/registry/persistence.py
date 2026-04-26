"""Background loop: persist every ERP1, decode against the device's EEP, publish to MQTT.

The loop is *single*: subscribing to the controller's fan-out twice would mean
two separate decode paths, which is wasted work. By doing DB write + MQTT
publish in one shot we keep retries simple and the codebase tight.
"""

from __future__ import annotations

import asyncio
import json
import logging

from ..eep import DecodedPoint, decode, has_decoder
from ..mqtt import MqttBridge
from ..transport import Controller
from .db import Database
from .devices import get_device, mark_seen
from .telegrams import write_telegram

logger = logging.getLogger(__name__)


async def persistence_loop(
    controller: Controller,
    db: Database,
    mqtt: MqttBridge | None = None,
) -> None:
    try:
        async with controller.subscribe(maxsize=512) as q:
            while True:
                erp1 = await q.get()
                points = await _persist_one(db, erp1)
                if mqtt is not None and points:
                    try:
                        await mqtt.publish_state(erp1.sender_id, points)
                        await mqtt.publish_raw(erp1.sender_id, erp1.payload.hex())
                    except Exception as e:
                        logger.warning("mqtt publish failed: %s", e)
    except asyncio.CancelledError:
        return


async def _persist_one(db: Database, erp1) -> list[DecodedPoint] | None:
    """Write one telegram to SQLite + return decoded points for known devices."""
    decoded: list[DecodedPoint] | None = None
    decoded_json: str | None = None
    try:
        async with db.session() as s, s.begin():
            device = await get_device(s, erp1.sender_id)
            if device and has_decoder(device.eep):
                try:
                    decoded = decode(device.eep, erp1)
                    decoded_json = json.dumps(
                        {p.key: _encode(p.value) for p in decoded},
                        separators=(",", ":"),
                    )
                except Exception as e:
                    logger.warning("decode failed for %s/%s: %s",
                                   device.eep, erp1.sender_id, e)
                    decoded = None
            await write_telegram(s, erp1, decoded_json=decoded_json)
            if device is not None:
                await mark_seen(s, erp1.sender_id)
    except Exception as e:
        logger.warning("persistence write failed: %s", e)
    return decoded


def _encode(v: object) -> object:
    if isinstance(v, bool | int | float | str):
        return v
    return str(v)
