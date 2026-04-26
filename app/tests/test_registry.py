"""Registry CRUD + ringbuffer + pairing-candidate filter."""

from __future__ import annotations

import pytest

from vdsensor.esp3.radio import Erp1
from vdsensor.registry import Database
from vdsensor.registry.devices import (
    add_device,
    change_eep,
    get_device,
    list_devices,
    mark_seen,
    remove_device,
    rename_device,
)
from vdsensor.registry.pairing import is_teach_in_candidate
from vdsensor.registry.telegrams import recent, recent_for_device, write_telegram


@pytest.fixture
async def db() -> Database:
    d = Database("sqlite+aiosqlite:///:memory:")
    await d.setup()
    return d


async def test_device_lifecycle(db: Database) -> None:
    async with db.session() as s, s.begin():
        await add_device(s, sender_id=0x01020304, eep="A5-02-05", label="Office")

    async with db.session() as s:
        dev = await get_device(s, 0x01020304)
        assert dev is not None
        assert dev.eep == "A5-02-05"
        assert dev.label == "Office"

    async with db.session() as s, s.begin():
        await rename_device(s, 0x01020304, "Kitchen")
        await change_eep(s, 0x01020304, "A5-04-01")
        await mark_seen(s, 0x01020304)

    async with db.session() as s:
        dev = await get_device(s, 0x01020304)
        assert dev is not None
        assert dev.label == "Kitchen"
        assert dev.eep == "A5-04-01"
        assert dev.last_seen is not None

    async with db.session() as s, s.begin():
        assert await remove_device(s, 0x01020304) is True

    async with db.session() as s:
        assert await get_device(s, 0x01020304) is None


async def test_list_devices_orders_by_label(db: Database) -> None:
    async with db.session() as s, s.begin():
        await add_device(s, 0x10, "F6-02-01", "Zulu")
        await add_device(s, 0x11, "A5-02-05", "Alpha")
        await add_device(s, 0x12, "D5-00-01", "Mike")

    async with db.session() as s:
        labels = [d.label for d in await list_devices(s)]
    assert labels == ["Alpha", "Mike", "Zulu"]


async def test_telegram_persistence(db: Database) -> None:
    erp1 = Erp1(rorg=0xA5, payload=b"\x00\x00\x80\x08", sender_id=0xAABB, status=0)
    async with db.session() as s, s.begin():
        await write_telegram(s, erp1)
        await write_telegram(s, erp1)
        await write_telegram(s, erp1)

    async with db.session() as s:
        rows = await recent_for_device(s, 0xAABB, limit=10)
        assert len(rows) == 3
        assert rows[0].rorg == 0xA5
        assert rows[0].payload_hex == "00008008"
        assert (await recent(s))[0].sender_id == 0xAABB


def test_is_teach_in_candidate_rps_always() -> None:
    e = Erp1(rorg=0xF6, payload=b"\x50", sender_id=1, status=0)
    assert is_teach_in_candidate(e) is True


def test_is_teach_in_candidate_4bs_lrn_bit() -> None:
    teach = Erp1(rorg=0xA5, payload=b"\x00\x00\x00\x00", sender_id=1, status=0)
    data = Erp1(rorg=0xA5, payload=b"\x00\x00\x00\x08", sender_id=1, status=0)
    assert is_teach_in_candidate(teach) is True
    assert is_teach_in_candidate(data) is False


def test_is_teach_in_candidate_1bs_lrn_bit() -> None:
    teach = Erp1(rorg=0xD5, payload=b"\x00", sender_id=1, status=0)
    data = Erp1(rorg=0xD5, payload=b"\x08", sender_id=1, status=0)
    assert is_teach_in_candidate(teach) is True
    assert is_teach_in_candidate(data) is False


def test_is_teach_in_candidate_vld_filtered_out_in_v1() -> None:
    # v1 doesn't support UTE/D2 teach-in; bare VLD frames should not count.
    e = Erp1(rorg=0xD2, payload=b"\x01\x02", sender_id=1, status=0)
    assert is_teach_in_candidate(e) is False
