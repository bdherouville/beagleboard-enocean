"""/ws/pair — pushes pairing candidates while a learn window is open."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..deps import get_pairing

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/pair")
async def pair(ws: WebSocket) -> None:
    await ws.accept()
    pairing = get_pairing()
    sub = pairing.subscribe()
    try:
        async with sub as iterator:
            async for cand in iterator:
                await ws.send_json({
                    "type": "learn_candidate",
                    "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    "payload": {
                        "sender": f"0x{cand.sender_id:08x}",
                        "rorg": f"0x{cand.rorg:02x}",
                        "status": f"0x{cand.status:02x}",
                        "dbm": cand.dbm,
                        "payload": cand.payload_hex,
                    },
                })
    except WebSocketDisconnect:
        return
    except Exception as e:
        logger.warning("/ws/pair error: %s", e)
        try:
            await ws.close()
        except Exception:
            pass
