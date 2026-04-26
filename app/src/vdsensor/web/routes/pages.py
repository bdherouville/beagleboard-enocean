"""Static HTML pages: dashboard and live telegram inspector."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
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
