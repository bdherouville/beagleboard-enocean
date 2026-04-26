"""MQTT URL parsing + HA discovery payload shape."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vdsensor.eep import DecodedPoint
from vdsensor.mqtt import Topics, build_discovery_payloads, parse_mqtt_url, sender_hex
from vdsensor.registry.models import Device


def test_parse_mqtt_url_full() -> None:
    cfg = parse_mqtt_url("mqtt://alice:s3cret@broker.lan:1883")
    assert cfg.host == "broker.lan"
    assert cfg.port == 1883
    assert cfg.username == "alice"
    assert cfg.password == "s3cret"
    assert cfg.tls is False


def test_parse_mqtt_url_default_port() -> None:
    assert parse_mqtt_url("mqtt://broker").port == 1883
    assert parse_mqtt_url("mqtts://broker").port == 8883
    assert parse_mqtt_url("mqtts://broker").tls is True


def test_parse_mqtt_url_rejects_unknown_scheme() -> None:
    with pytest.raises(ValueError):
        parse_mqtt_url("http://broker")


def test_sender_hex_lowercase_zero_padded() -> None:
    assert sender_hex(0x0180A1B2) == "0180a1b2"
    assert sender_hex(0xFF) == "000000ff"


def _office() -> Device:
    return Device(
        sender_id=0x0180A1B2,
        eep="A5-02-05",
        label="Office",
        paired_at=datetime.now(UTC).replace(tzinfo=None),
        last_seen=None,
        notes=None,
    )


def test_discovery_topic_and_payload_for_a5_02_05() -> None:
    points = [DecodedPoint("temperature", 21.3, "°C", "temperature", "measurement")]
    entries = build_discovery_payloads(_office(), points, Topics())
    assert len(entries) == 1
    e = entries[0]
    assert e.component == "sensor"
    assert e.topic == "homeassistant/sensor/vdsensor_0180a1b2/temperature/config"
    p = e.payload
    assert p["unique_id"] == "vdsensor_0180a1b2_temperature"
    assert p["state_topic"] == "vdsensor/devices/0180a1b2/state"
    assert p["unit_of_measurement"] == "°C"
    assert p["device_class"] == "temperature"
    assert p["state_class"] == "measurement"
    assert p["availability_topic"] == "vdsensor/status"
    assert "vdsensor_0180a1b2" in p["device"]["identifiers"]


def test_discovery_picks_binary_sensor_for_bool_points() -> None:
    points = [DecodedPoint("contact", True, None, "door", None)]
    entries = build_discovery_payloads(_office(), points, Topics())
    assert entries[0].component == "binary_sensor"
    assert entries[0].topic.startswith("homeassistant/binary_sensor/")
    # Binary sensor needs explicit payload_on/off so the templated value matches.
    assert entries[0].payload["payload_on"] == "True"
    assert entries[0].payload["payload_off"] == "False"


def test_discovery_emits_one_entry_per_point() -> None:
    points = [
        DecodedPoint("temperature", 0.0, "°C", "temperature", "measurement"),
        DecodedPoint("humidity", 0.0, "%", "humidity", "measurement"),
    ]
    entries = build_discovery_payloads(_office(), points, Topics())
    assert {e.payload["unique_id"] for e in entries} == {
        "vdsensor_0180a1b2_temperature",
        "vdsensor_0180a1b2_humidity",
    }
