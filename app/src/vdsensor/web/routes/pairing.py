"""Pairing wizard routes.

Flow:
    1. GET  /pair                      → wizard shell (open WS + start button)
    2. POST /pair/start                → kick off learn-mode window
    3. WS   /ws/pair  (in ws/pair.py)  → server pushes Candidate JSON envelopes
    4. POST /pair/assign               → user picked a candidate + EEP + label
    5. POST /pair/cancel               → user gave up
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ...eep import KNOWN_PROFILES, get_profile
from ...mqtt import MqttBridge
from ...registry import Database
from ...registry.devices import get_device
from ...registry.pairing import PairingService
from ..deps import get_database, get_mqtt, get_pairing, get_templates

router = APIRouter()

PairingDep = Annotated[PairingService, Depends(get_pairing)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]
DatabaseDep = Annotated[Database, Depends(get_database)]
MqttDep = Annotated[MqttBridge | None, Depends(get_mqtt)]


@router.get("/pair", response_class=HTMLResponse)
async def pair_page(
    request: Request,
    pairing: PairingDep,
    templates: TemplatesDep,
):
    return templates.TemplateResponse(
        request,
        "pair.html",
        {"state": pairing.state.value, "profiles": list(KNOWN_PROFILES.values())},
    )


@router.post("/pair/start")
async def pair_start(
    pairing: PairingDep,
    timeout_ms: Annotated[int, Form()] = 60_000,
) -> JSONResponse:
    try:
        await pairing.start(timeout_ms=timeout_ms)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return JSONResponse({"state": pairing.state.value, "timeout_ms": timeout_ms})


@router.post("/pair/assign")
async def pair_assign(
    pairing: PairingDep,
    db: DatabaseDep,
    mqtt: MqttDep,
    sender_id: Annotated[str, Form()],
    eep: Annotated[str, Form()],
    label: Annotated[str, Form()],
) -> JSONResponse:
    try:
        sid = int(sender_id, 0)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid sender_id: {sender_id}") from e
    profile = get_profile(eep)
    if profile is None:
        raise HTTPException(status_code=400, detail=f"unknown EEP profile: {eep}")

    # If the device already exists with a different EEP, snapshot its old
    # profile so we can clear the stale HA discovery topics afterwards.
    async with db.session() as s:
        prev = await get_device(s, sid)
    prev_profile = get_profile(prev.eep) if prev is not None else None
    eep_changed = prev is not None and prev.eep != eep

    try:
        created = await pairing.assign(sid, eep, label.strip())
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    if mqtt is not None:
        if eep_changed and prev is not None and prev_profile is not None:
            await mqtt.clear_discovery(prev, list(prev_profile.points))
        async with db.session() as s:
            device = await get_device(s, sid)
        if device is not None:
            await mqtt.publish_discovery(device, list(profile.points))

    return JSONResponse({
        "ok": True,
        "created": created,
        "sender_id": f"0x{sid:08x}",
        "eep": eep,
        "label": label,
    })


@router.post("/pair/cancel")
async def pair_cancel(pairing: PairingDep) -> JSONResponse:
    await pairing.cancel()
    return JSONResponse({"state": pairing.state.value})
