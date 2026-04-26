"""Device CRUD on top of the SQLAlchemy session."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Device


async def add_device(
    session: AsyncSession,
    sender_id: int,
    eep: str,
    label: str,
    notes: str | None = None,
) -> Device:
    now = datetime.now(UTC).replace(tzinfo=None)
    dev = Device(sender_id=sender_id, eep=eep, label=label, paired_at=now, notes=notes)
    session.add(dev)
    await session.flush()
    return dev


async def get_device(session: AsyncSession, sender_id: int) -> Device | None:
    return await session.get(Device, sender_id)


async def list_devices(session: AsyncSession) -> list[Device]:
    res = await session.execute(select(Device).order_by(Device.label))
    return list(res.scalars())


async def rename_device(session: AsyncSession, sender_id: int, label: str) -> Device | None:
    dev = await get_device(session, sender_id)
    if dev is None:
        return None
    dev.label = label
    await session.flush()
    return dev


async def change_eep(session: AsyncSession, sender_id: int, eep: str) -> Device | None:
    dev = await get_device(session, sender_id)
    if dev is None:
        return None
    dev.eep = eep
    await session.flush()
    return dev


async def remove_device(session: AsyncSession, sender_id: int) -> bool:
    dev = await get_device(session, sender_id)
    if dev is None:
        return False
    await session.delete(dev)
    await session.flush()
    return True


async def mark_seen(session: AsyncSession, sender_id: int, when: datetime | None = None) -> bool:
    dev = await get_device(session, sender_id)
    if dev is None:
        return False
    dev.last_seen = (when or datetime.now(UTC)).replace(tzinfo=None)
    await session.flush()
    return True
