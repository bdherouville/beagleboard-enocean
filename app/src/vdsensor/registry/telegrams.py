"""Telegram persistence helpers (one row per ERP1)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..esp3.radio import Erp1
from .models import Telegram


async def write_telegram(
    session: AsyncSession,
    erp1: Erp1,
    *,
    decoded_json: str | None = None,
    when: datetime | None = None,
) -> Telegram:
    row = Telegram(
        ts=(when or datetime.now(UTC)).replace(tzinfo=None),
        sender_id=erp1.sender_id,
        rorg=erp1.rorg,
        payload_hex=erp1.payload.hex(),
        status=erp1.status,
        rssi_dbm=erp1.dbm,
        decoded_json=decoded_json,
    )
    session.add(row)
    await session.flush()
    return row


async def recent_for_device(
    session: AsyncSession, sender_id: int, limit: int = 50
) -> list[Telegram]:
    res = await session.execute(
        select(Telegram)
        .where(Telegram.sender_id == sender_id)
        .order_by(Telegram.id.desc())
        .limit(limit)
    )
    return list(res.scalars())


async def recent(session: AsyncSession, limit: int = 200) -> list[Telegram]:
    res = await session.execute(
        select(Telegram).order_by(Telegram.id.desc()).limit(limit)
    )
    return list(res.scalars())
