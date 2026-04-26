"""Build Home Assistant MQTT-discovery `config` payloads from EEP DecodedPoints.

Each DecodedPoint maps to one HA entity. Topic shape and payload follow
https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery .

The chosen `component` is:
  - bool DecodedPoint with device_class set       → binary_sensor
  - any other numeric/string DecodedPoint         → sensor
"""

from __future__ import annotations

from dataclasses import dataclass

from ..eep import DecodedPoint
from ..registry.models import Device
from .topics import Topics, sender_hex


@dataclass(frozen=True)
class DiscoveryEntry:
    component: str
    topic: str
    payload: dict


def _component_for(point: DecodedPoint) -> str:
    if isinstance(point.value, bool):
        return "binary_sensor"
    return "sensor"


def _device_block(device: Device) -> dict:
    return {
        "identifiers": [f"vdsensor_{sender_hex(device.sender_id)}"],
        "name": f"{device.label} ({device.eep})",
        "manufacturer": "EnOcean",
        "model": device.eep,
        "via_device": "vdsensor_gateway",
    }


def build_discovery_payloads(
    device: Device, points: list[DecodedPoint], topics: Topics
) -> list[DiscoveryEntry]:
    entries: list[DiscoveryEntry] = []
    state_topic = topics.device_state(device.sender_id)
    avail_topic = topics.status()
    dev_block = _device_block(device)
    sid_hex = sender_hex(device.sender_id)

    for p in points:
        component = _component_for(p)
        config: dict = {
            "name": f"{device.label} {p.key}".strip(),
            "unique_id": f"vdsensor_{sid_hex}_{p.key}",
            "state_topic": state_topic,
            "value_template": "{{ value_json." + p.key + " }}",
            "availability_topic": avail_topic,
            "payload_available": "online",
            "payload_not_available": "offline",
            "device": dev_block,
        }
        if p.unit is not None:
            config["unit_of_measurement"] = p.unit
        if p.device_class is not None:
            config["device_class"] = p.device_class
        if p.state_class is not None:
            config["state_class"] = p.state_class
        if component == "binary_sensor":
            # HA binary_sensor wants a literal payload_on/payload_off pair, since
            # JSON `true`/`false` after value_template render as the strings True/False.
            config["payload_on"] = "True"
            config["payload_off"] = "False"

        entries.append(DiscoveryEntry(
            component=component,
            topic=topics.ha_config(component, device.sender_id, p.key),
            payload=config,
        ))
    return entries
