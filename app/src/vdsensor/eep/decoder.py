"""EEP decode interface — DecodedPoint + lookup-and-call dispatch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..esp3.radio import Erp1


@dataclass(frozen=True)
class DecodedPoint:
    key: str                    # stable machine-readable name (e.g. "temperature")
    value: float | int | bool | str
    unit: str | None = None
    device_class: str | None = None      # Home Assistant device_class
    state_class: str | None = None       # Home Assistant state_class


Decoder = Callable[[Erp1], list[DecodedPoint]]


# Filled in by builtins.__init__ via register().
_DECODERS: dict[str, Decoder] = {}


def register(profile_id: str, decoder: Decoder) -> None:
    _DECODERS[profile_id.upper()] = decoder


def decode(profile_id: str, erp1: Erp1) -> list[DecodedPoint]:
    """Decode `erp1` according to `profile_id` (e.g. "A5-02-05").

    Raises KeyError if no decoder is registered for that profile.
    """
    return _DECODERS[profile_id.upper()](erp1)


def has_decoder(profile_id: str) -> bool:
    return profile_id.upper() in _DECODERS
