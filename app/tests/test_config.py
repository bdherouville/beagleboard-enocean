"""Settings env-var coercion."""

from __future__ import annotations

import pytest

from vdsensor.config import Settings


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.delenv("VDSENSOR_MQTT_URL", raising=False)
    yield


def test_unset_mqtt_url_is_none() -> None:
    s = Settings(_env_file=None)
    assert s.mqtt_url is None


def test_empty_string_mqtt_url_is_treated_as_none(monkeypatch) -> None:
    """docker-compose substitutes ${VAR:-} to '' which used to crash startup."""
    monkeypatch.setenv("VDSENSOR_MQTT_URL", "")
    s = Settings(_env_file=None)
    assert s.mqtt_url is None


def test_whitespace_mqtt_url_is_treated_as_none(monkeypatch) -> None:
    monkeypatch.setenv("VDSENSOR_MQTT_URL", "   ")
    s = Settings(_env_file=None)
    assert s.mqtt_url is None


def test_real_mqtt_url_is_preserved(monkeypatch) -> None:
    monkeypatch.setenv("VDSENSOR_MQTT_URL", "mqtt://broker.lan:1883")
    s = Settings(_env_file=None)
    assert s.mqtt_url == "mqtt://broker.lan:1883"
