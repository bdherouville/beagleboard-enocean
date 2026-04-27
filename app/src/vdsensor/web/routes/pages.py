"""Static HTML pages: dashboard and live telegram inspector."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ...hardware.leds import ALLOWED_TEST_GPIOS, drive_test_gpio
from ...transport import Controller
from ..deps import get_controller, get_templates

router = APIRouter()

ControllerDep = Annotated[Controller, Depends(get_controller)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, controller: ControllerDep, templates: TemplatesDep):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"info": controller.info, "port": controller.link.port},
    )


@router.get("/telegrams", response_class=HTMLResponse)
async def telegrams(request: Request, templates: TemplatesDep):
    return templates.TemplateResponse(request, "telegrams.html", {})


@router.get("/api/leds")
async def leds_api(controller: ControllerDep) -> JSONResponse:
    """Current state + GPIO mapping of the daughter-board LEDs."""
    leds = controller.leds
    state = leds.state()
    gpios = leds.gpios
    return JSONResponse({
        "state": {color.value: bool(on) for color, on in state.items()},
        "gpios": {color.value: gpio for color, gpio in gpios.items()},
        "test_gpios": sorted(ALLOWED_TEST_GPIOS),
    })


@router.post("/api/leds/test")
async def leds_test(
    gpio: Annotated[int, Form()],
    duration_ms: Annotated[int, Form()] = 5000,
) -> JSONResponse:
    """Drive a single GPIO high for `duration_ms`, then low.

    Used from the dashboard "Identify LED" panel: click a GPIO button, watch
    which physical colour lights up, set VDSENSOR_LED_<COLOR>_GPIO accordingly.
    """
    if gpio not in ALLOWED_TEST_GPIOS:
        raise HTTPException(
            status_code=400,
            detail=f"gpio {gpio} not in {sorted(ALLOWED_TEST_GPIOS)}",
        )
    duration_ms = max(100, min(duration_ms, 10_000))    # clamp to 0.1..10 s
    asyncio.create_task(drive_test_gpio(gpio, duration_ms=duration_ms),
                        name=f"led-test-{gpio}")
    return JSONResponse({"gpio": gpio, "duration_ms": duration_ms, "ok": True})
