"""MQTT bridge: keeps a connection open, pushes decoded state, drives HA discovery.

Outbound publishes go through a coalescing buffer rather than a FIFO queue:

  - **Retained** publishes (state, raw, HA discovery, status clears) keep only the
    latest payload per topic. If MQTT drops for 30 s and a sensor reports six
    values during the outage, on reconnect we publish *one* state — the most
    recent — instead of replaying the backlog. HA cares about state, not history.
  - **Non-retained** one-shots are kept FIFO and bounded; the only such topic
    we use is `vdsensor/devices/<id>/raw` (debug) so the bound is generous.

LWT publishes "offline" to `<prefix>/status` with retain=True; on connect we
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

ONESHOT_QUEUE_LIMIT = 2048


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


@dataclass(frozen=True)
class _PendingPublish:
    topic: str
    payload: str
    retain: bool
    qos: int


class MqttBridge:
    def __init__(self, config: MqttConfig, topics: Topics) -> None:
        self._config = config
        self._topics = topics
        # Retained: latest-wins per topic. Non-retained: FIFO, bounded.
        self._latest: dict[str, _PendingPublish] = {}
        self._oneshot: list[_PendingPublish] = []
        self._wakeup = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._stop = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @asynccontextmanager
    async def run(self) -> AsyncIterator[MqttBridge]:
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="mqtt-bridge")
        try:
            yield self
        finally:
            self._stop.set()
            self._wakeup.set()
            if self._task is not None:
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
        self._enqueue(
            self._topics.device_state(sender_id),
            json.dumps(body, separators=(",", ":")),
            retain=True,
            qos=1,
        )

    async def publish_raw(self, sender_id: int, hex_payload: str) -> None:
        self._enqueue(self._topics.device_raw(sender_id), hex_payload, retain=False, qos=0)

    async def publish_discovery(
        self, device: Device, points: list[DecodedPoint]
    ) -> None:
        for entry in build_discovery_payloads(device, points, self._topics):
            self._enqueue(
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
            self._enqueue(entry.topic, "", retain=True, qos=1)
        # Also clear the state topic so old values disappear.
        self._enqueue(self._topics.device_state(device.sender_id), "", retain=True, qos=1)

    # --- internals ---------------------------------------------------------

    def _enqueue(self, topic: str, payload: str, retain: bool, qos: int) -> None:
        msg = _PendingPublish(topic, payload, retain, qos)
        if retain:
            self._latest[topic] = msg                       # latest wins
        else:
            if len(self._oneshot) >= ONESHOT_QUEUE_LIMIT:
                logger.warning("mqtt one-shot queue full; dropping publish to %s", topic)
                return
            self._oneshot.append(msg)
        self._wakeup.set()

    def _drain(self) -> tuple[list[_PendingPublish], list[_PendingPublish]]:
        """Snapshot + clear the buffers atomically (single-threaded asyncio)."""
        latest = list(self._latest.values())
        self._latest = {}
        oneshot, self._oneshot = self._oneshot, []
        return latest, oneshot

    async def _loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
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
                    # On every reconnect we drain the *coalesced* buffers — so
                    # a long outage produces at most one state publish per device.
                    while not self._stop.is_set():
                        await self._wakeup.wait()
                        self._wakeup.clear()
                        latest, oneshot = self._drain()
                        for msg in oneshot:
                            await client.publish(msg.topic, msg.payload,
                                                 retain=msg.retain, qos=msg.qos)
                        for msg in latest:
                            await client.publish(msg.topic, msg.payload,
                                                 retain=msg.retain, qos=msg.qos)
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._connected.clear()
                if self._stop.is_set():
                    return
                logger.warning("mqtt loop error (%s); retry in %.1fs", e, backoff)
                try:
                    async with asyncio.timeout(backoff):
                        await self._stop.wait()
                    return                                    # stop requested
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)


def _encode_value(v: object) -> object:
    """Coerce DecodedPoint values into JSON-friendly primitives."""
    if isinstance(v, bool | int | float | str):
        return v
    return str(v)
