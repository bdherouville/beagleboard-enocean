"""Runtime configuration via env vars (VDSENSOR_*)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VDSENSOR_", env_file=".env", extra="ignore")

    serial_port: str = Field(default="/dev/ttyO4")
    serial_baud: int = Field(default=57600)
    fake: bool = Field(default=False)

    db_path: str = Field(default="/data/vdsensor.db")
    telegram_ring_size: int = Field(default=10_000)

    http_host: str = Field(default="0.0.0.0")
    http_port: int = Field(default=8080)

    mqtt_url: str | None = Field(default=None)
    mqtt_prefix: str = Field(default="vdsensor")
    ha_discovery_prefix: str = Field(default="homeassistant")

    # Status LEDs on the EnOcean daughter-board.
    leds_backend: str = Field(default="sysfs")     # "sysfs" or "none"
    led_green_gpio: int = Field(default=67)
    led_orange_gpio: int = Field(default=68)
    led_red_gpio: int = Field(default=66)

    # Clock-sync gate. The BBB has no RTC; without this, paired_at can be
    # stamped before NTP catches up.
    clock_sync_timeout_s: float = Field(default=30.0)

    @property
    def db_url(self) -> str:
        if self.db_path == ":memory:":
            return "sqlite+aiosqlite:///:memory:"
        return f"sqlite+aiosqlite:///{self.db_path}"
