"""Device list + per-device management.

HTML pages: /devices, /devices/{sender_id}.
HTMX-friendly mutation endpoints return small fragments (or 204 on delete).
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ...eep import KNOWN_PROFILES, get_profile
from ...mqtt import MqttBridge
from ...registry import Database
from ...registry.devices import (
    change_eep,
    get_device,
    list_devices,
    remove_device,
    rename_device,
)
from ...registry.telegrams import recent_for_device
from ..deps import get_database, get_mqtt, get_templates

router = APIRouter()

DatabaseDep = Annotated[Database, Depends(get_database)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]
MqttDep = Annotated[MqttBridge | None, Depends(get_mqtt)]


def _fmt_sender(sid: int) -> str:
    return f"0x{sid:08x}"


@router.get("/devices", response_class=HTMLResponse)
async def devices_index(
    request: Request, db: DatabaseDep, templates: TemplatesDep
):
    async with db.session() as s:
        rows = await list_devices(s)
    return templates.TemplateResponse(
        request,
        "devices.html",
        {"devices": rows, "fmt_sender": _fmt_sender},
    )


@router.get("/api/devices/{sender_id}/state")
async def device_state_api(sender_id: str, db: DatabaseDep) -> JSONResponse:
    """Latest decoded state for a paired device — used for live page updates."""
    sid = _parse_sender(sender_id)
    async with db.session() as s:
        dev = await get_device(s, sid)
        if dev is None:
            raise HTTPException(status_code=404, detail="device not found")
        rows = await recent_for_device(s, sid, limit=1)

    last = rows[0] if rows else None
    return JSONResponse({
        "sender_id": _fmt_sender(sid),
        "label": dev.label,
        "eep": dev.eep,
        "last_seen": dev.last_seen.isoformat() + "Z" if dev.last_seen else None,
        "last_ts": last.ts.isoformat() + "Z" if last else None,
        "last_rssi": last.rssi_dbm if last else None,
        "last_payload": last.payload_hex if last else None,
        "decoded": json.loads(last.decoded_json) if last and last.decoded_json else None,
    })


@router.get("/devices/{sender_id}", response_class=HTMLResponse)
async def device_detail(
    request: Request,
    sender_id: str,
    db: DatabaseDep,
    templates: TemplatesDep,
):
    sid = _parse_sender(sender_id)
    async with db.session() as s:
        dev = await get_device(s, sid)
        if dev is None:
            raise HTTPException(status_code=404, detail="device not found")
        recent = await recent_for_device(s, sid, limit=50)
    return templates.TemplateResponse(
        request,
        "device_detail.html",
        {
            "device": dev,
            "telegrams": recent,
            "profiles": list(KNOWN_PROFILES.values()),
            "fmt_sender": _fmt_sender,
        },
    )


@router.post("/devices/{sender_id}/rename", response_class=HTMLResponse)
async def device_rename(
    sender_id: str,
    db: DatabaseDep,
    mqtt: MqttDep,
    templates: TemplatesDep,
    request: Request,
    label: Annotated[str, Form()],
):
    sid = _parse_sender(sender_id)
    async with db.session() as s, s.begin():
        dev = await rename_device(s, sid, label.strip())
    if dev is None:
        raise HTTPException(status_code=404, detail="device not found")
    # Discovery name carries the device label; republish so HA picks it up.
    if mqtt is not None and (profile := get_profile(dev.eep)) is not None:
        await mqtt.publish_discovery(dev, list(profile.points))
    return templates.TemplateResponse(
        request, "fragments/device_row.html",
        {"device": dev, "fmt_sender": _fmt_sender},
    )


@router.post("/devices/{sender_id}/eep", response_class=HTMLResponse)
async def device_change_eep(
    sender_id: str,
    db: DatabaseDep,
    mqtt: MqttDep,
    templates: TemplatesDep,
    request: Request,
    eep: Annotated[str, Form()],
):
    new_profile = get_profile(eep)
    if new_profile is None:
        raise HTTPException(status_code=400, detail=f"unknown EEP profile: {eep}")
    sid = _parse_sender(sender_id)

    # Capture the previous profile so we can clear its discovery topics first.
    async with db.session() as s:
        prev = await get_device(s, sid)
    if prev is None:
        raise HTTPException(status_code=404, detail="device not found")
    prev_profile = get_profile(prev.eep)

    async with db.session() as s, s.begin():
        dev = await change_eep(s, sid, eep)
    assert dev is not None

    if mqtt is not None:
        if prev_profile is not None and prev_profile.profile_id != new_profile.profile_id:
            await mqtt.clear_discovery(prev, list(prev_profile.points))
        await mqtt.publish_discovery(dev, list(new_profile.points))

    return templates.TemplateResponse(
        request, "fragments/device_row.html",
        {"device": dev, "fmt_sender": _fmt_sender},
    )


@router.delete("/devices/{sender_id}")
async def device_delete(sender_id: str, db: DatabaseDep, mqtt: MqttDep) -> Response:
    sid = _parse_sender(sender_id)
    # Capture the device + its profile points before deletion so we can clear MQTT.
    async with db.session() as s:
        dev = await get_device(s, sid)
    if dev is None:
        raise HTTPException(status_code=404, detail="device not found")
    profile = get_profile(dev.eep)

    async with db.session() as s, s.begin():
        await remove_device(s, sid)

    if mqtt is not None and profile is not None:
        await mqtt.clear_discovery(dev, list(profile.points))

    return Response(status_code=200, content="")


def _parse_sender(s: str) -> int:
    try:
        return int(s, 0)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid sender_id: {s}") from e
