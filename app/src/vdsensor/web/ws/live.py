"""/ws/live — pushes ERP1 telegrams to the live inspector page.

Envelope (JSON, one message per ERP1):

    {"type": "telegram",
     "ts":   "2026-04-26T14:01:23.456Z",
     "payload": {
        "rorg":      "0xa5",
        "sender":    "0x12345672",
        "status":    "0x00",
        "dbm":       -65,
        "payload":   "0000800a"
     }}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..deps import get_controller

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await ws.accept()
    controller = get_controller()
    async with controller.subscribe(maxsize=128) as q:
        try:
            while True:
                erp1 = await q.get()
                msg = {
                    "type": "telegram",
                    "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "payload": {
                        "rorg": f"0x{erp1.rorg:02x}",
                        "sender": f"0x{erp1.sender_id:08x}",
                        "status": f"0x{erp1.status:02x}",
                        "dbm": erp1.dbm,
                        "payload": erp1.payload.hex(),
                    },
                }
                await ws.send_json(msg)
        except WebSocketDisconnect:
            return
        except (asyncio.CancelledError, Exception) as e:
            logger.warning("/ws/live error: %s", e)
            try:
                await ws.close()
            except Exception:
                pass
