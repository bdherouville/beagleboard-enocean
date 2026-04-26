"""Singletons made available to routes via FastAPI Depends.

Set once in `build_app`; routes pull the live values via `get_*`.
"""

from __future__ import annotations

from fastapi.templating import Jinja2Templates

from ..mqtt import MqttBridge
from ..registry import Database
from ..registry.pairing import PairingService
from ..transport import Controller

_controller: Controller | None = None
_database: Database | None = None
_pairing: PairingService | None = None
_templates: Jinja2Templates | None = None
_mqtt: MqttBridge | None = None


def set_controller(c: Controller) -> None:
    global _controller
    _controller = c


def set_database(d: Database) -> None:
    global _database
    _database = d


def set_pairing(p: PairingService) -> None:
    global _pairing
    _pairing = p


def set_templates(t: Jinja2Templates) -> None:
    global _templates
    _templates = t


def set_mqtt(b: MqttBridge | None) -> None:
    global _mqtt
    _mqtt = b


def get_mqtt() -> MqttBridge | None:
    return _mqtt


def get_controller() -> Controller:
    if _controller is None:
        raise RuntimeError("controller not initialised — build_app() was not called")
    return _controller


def get_database() -> Database:
    if _database is None:
        raise RuntimeError("database not initialised — build_app() was not called")
    return _database


def get_pairing() -> PairingService:
    if _pairing is None:
        raise RuntimeError("pairing service not initialised — build_app() was not called")
    return _pairing


def get_templates() -> Jinja2Templates:
    if _templates is None:
        raise RuntimeError("templates not initialised — build_app() was not called")
    return _templates
