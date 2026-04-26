"""Static HTML pages: dashboard and live telegram inspector."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

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
    })
