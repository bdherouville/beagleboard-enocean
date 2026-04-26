"""All MQTT topic strings live here so renames are one-line patches."""

from __future__ import annotations

from dataclasses import dataclass


def sender_hex(sender_id: int) -> str:
    return f"{sender_id & 0xFFFFFFFF:08x}"


@dataclass(frozen=True)
class Topics:
    prefix: str = "vdsensor"
    ha_prefix: str = "homeassistant"

    # --- own namespace --------------------------------------------------

    def status(self) -> str:
        """LWT topic: 'online' on connect, 'offline' on disconnect."""
        return f"{self.prefix}/status"

    def gateway_state(self) -> str:
        return f"{self.prefix}/gateway/state"

    def device_state(self, sender_id: int) -> str:
        return f"{self.prefix}/devices/{sender_hex(sender_id)}/state"

    def device_raw(self, sender_id: int) -> str:
        return f"{self.prefix}/devices/{sender_hex(sender_id)}/raw"

    # --- HA discovery ---------------------------------------------------

    def ha_config(self, component: str, sender_id: int, key: str) -> str:
        return f"{self.ha_prefix}/{component}/vdsensor_{sender_hex(sender_id)}/{key}/config"
