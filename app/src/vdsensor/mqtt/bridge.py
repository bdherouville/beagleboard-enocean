"""MQTT bridge: keeps a connection open, pushes decoded state, drives HA discovery.

Design choices:
  - Connection lifetime is a context manager (`run()`) keyed off `aiomqtt.Client`.
  - Outgoing commands are queued; the bridge task drains the queue and re-publishes
    on reconnect. This way, callers (pair/assign, persistence loop) never block on
    a flaky network.
  - LWT publishes "offline" to <prefix>/status with retain=True; on connect we
    publish "online" so HA flips entities back to available.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

import aiomqtt

from ..eep import DecodedPoint
from ..registry.models import Device
from .ha_discovery import build_discovery_payloads
from .topics import Topics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int = 1883
    username: str | None = None
    password: str | None = None
    tls: bool = False


def parse_mqtt_url(url: str) -> MqttConfig:
    """Parse mqtt://user:pass@host:port (or mqtts://) into an MqttConfig."""
    u = urlparse(url)
    if u.scheme not in ("mqtt", "mqtts"):
        raise ValueError(f"unsupported scheme {u.scheme!r}; expected mqtt or mqtts")
    host = u.hostname
    if not host:
        raise ValueError(f"no host in mqtt url: {url!r}")
    return MqttConfig(
        host=host,
        port=u.port or (8883 if u.scheme == "mqtts" else 1883),
        username=u.username,
        password=u.password,
        tls=u.scheme == "mqtts",
    )


@dataclass
class _PendingPublish:
    topic: str
    payload: str
    retain: bool = False
    qos: int = 0


class MqttBridge:
    def __init__(self, config: MqttConfig, topics: Topics) -> None:
        self._config = config
        self._topics = topics
        self._queue: asyncio.Queue[_PendingPublish | None] = asyncio.Queue(maxsize=2048)
        self._task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @asynccontextmanager
    async def run(self) -> AsyncIterator[MqttBridge]:
        self._task = asyncio.create_task(self._loop(), name="mqtt-bridge")
        try:
            yield self
        finally:
            await self._queue.put(None)             # poison pill
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    # --- public publish surface --------------------------------------------

    async def publish_state(
        self, sender_id: int, points: list[DecodedPoint]
    ) -> None:
        body = {p.key: _encode_value(p.value) for p in points}
        await self._enqueue(
            self._topics.device_state(sender_id),
            json.dumps(body, separators=(",", ":")),
            retain=True,
            qos=1,
        )

    async def publish_raw(self, sender_id: int, hex_payload: str) -> None:
        await self._enqueue(
            self._topics.device_raw(sender_id), hex_payload, retain=False, qos=0
        )

    async def publish_discovery(
        self, device: Device, points: list[DecodedPoint]
    ) -> None:
        for entry in build_discovery_payloads(device, points, self._topics):
            await self._enqueue(
                entry.topic,
                json.dumps(entry.payload, separators=(",", ":")),
                retain=True,
                qos=1,
            )

    async def clear_discovery(
        self, device: Device, points: list[DecodedPoint]
    ) -> None:
        """Publish empty retained payloads so HA forgets the entities."""
        for entry in build_discovery_payloads(device, points, self._topics):
            await self._enqueue(entry.topic, "", retain=True, qos=1)
        # Also clear the state topic so old values disappear.
        await self._enqueue(self._topics.device_state(device.sender_id), "", retain=True, qos=1)

    # --- internals ---------------------------------------------------------

    async def _enqueue(self, topic: str, payload: str, retain: bool, qos: int) -> None:
        try:
            self._queue.put_nowait(_PendingPublish(topic, payload, retain, qos))
        except asyncio.QueueFull:
            logger.warning("mqtt queue full; dropping publish to %s", topic)

    async def _loop(self) -> None:
        backoff = 1.0
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self._config.host,
                    port=self._config.port,
                    username=self._config.username,
                    password=self._config.password,
                    tls_params=aiomqtt.TLSParameters() if self._config.tls else None,
                    will=aiomqtt.Will(self._topics.status(), "offline", retain=True, qos=1),
                ) as client:
                    self._connected.set()
                    backoff = 1.0
                    await client.publish(self._topics.status(), "online", retain=True, qos=1)
                    logger.info("mqtt connected: %s:%d", self._config.host, self._config.port)
                    while True:
                        msg = await self._queue.get()
                        if msg is None:
                            return
                        await client.publish(msg.topic, msg.payload, retain=msg.retain, qos=msg.qos)
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._connected.clear()
                logger.warning("mqtt loop error (%s); retry in %.1fs", e, backoff)
                try:
                    async with asyncio.timeout(backoff):
                        await asyncio.sleep(backoff)
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)


def _encode_value(v: object) -> object:
    """Coerce DecodedPoint values into JSON-friendly primitives."""
    if isinstance(v, bool | int | float | str):
        return v
    return str(v)
