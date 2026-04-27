"""Pairing wizard session — at most one active at a time.

Lifecycle:

    PairingService.start(timeout_ms)   --(spawns a task that opens the learn
                                          window on the Controller)-->
    PairingService.assign(sender_id, eep, label)   --(persists Device, signals
                                                      the task to exit)-->
    PairingService.cancel()             --(signals task to exit immediately)-->

While the task is alive, it pulls ERP1 telegrams from the learn window. Each
telegram that *looks* like a teach-in (4BS/1BS LRN-bit cleared, or any RPS) is
broadcast to subscribers as a candidate. Duplicates per sender_id are
suppressed so the UI sees one row per device.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum

from ..esp3.radio import Erp1, is_1bs_teach_in, is_4bs_teach_in
from ..transport import Controller
from .db import Database
from .devices import upsert_device

logger = logging.getLogger(__name__)


class PairingState(StrEnum):
    IDLE = "idle"
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class Candidate:
    sender_id: int
    rorg: int
    payload_hex: str
    status: int
    dbm: int | None


def is_teach_in_candidate(erp1: Erp1) -> bool:
    """A telegram is a candidate if its RORG implies teach-in.

    - 4BS / 1BS: LRN bit cleared (per the EEP convention).
    - RPS: no LRN bit, so any RPS frame inside the open window is a candidate;
      the user is in pairing mode by intent.
    """
    if erp1.rorg == 0xA5:
        return is_4bs_teach_in(erp1)
    if erp1.rorg == 0xD5:
        return is_1bs_teach_in(erp1)
    if erp1.rorg == 0xF6:
        return True
    return False


class PairingService:
    def __init__(self, controller: Controller, db: Database) -> None:
        self._controller = controller
        self._db = db
        self._lock = asyncio.Lock()
        self._state = PairingState.IDLE
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._candidate_subs: set[asyncio.Queue[Candidate]] = set()
        self._seen: set[int] = set()                # dedupe candidates by sender_id

    @property
    def state(self) -> PairingState:
        return self._state

    async def start(self, timeout_ms: int = 60_000) -> None:
        async with self._lock:
            if self._state == PairingState.OPEN:
                raise RuntimeError("a pairing session is already in progress")
            self._stop_event = asyncio.Event()
            self._seen.clear()
            self._state = PairingState.OPEN
            self._task = asyncio.create_task(
                self._run_window(timeout_ms), name="pairing-window"
            )

    async def assign(self, sender_id: int, eep: str, label: str) -> bool:
        """Pair / re-pair a device. Returns True if newly inserted, False if updated."""
        async with self._lock:
            if self._state != PairingState.OPEN:
                raise RuntimeError("no pairing session is active")
            async with self._db.session() as s, s.begin():
                _, created = await upsert_device(s, sender_id=sender_id, eep=eep, label=label)
            self._stop_event.set()                  # let the window task exit cleanly
            return created

    async def cancel(self) -> None:
        async with self._lock:
            if self._state != PairingState.OPEN:
                return
            self._stop_event.set()

    def subscribe(self, *, maxsize: int = 32) -> _CandidateSubscription:
        return _CandidateSubscription(self._candidate_subs, asyncio.Queue(maxsize=maxsize))

    # ---- internals --------------------------------------------------------

    async def _run_window(self, timeout_ms: int) -> None:
        try:
            async with self._controller.open_learn_window(timeout_ms) as q:
                while not self._stop_event.is_set():
                    get_task = asyncio.create_task(q.get())
                    stop_task = asyncio.create_task(self._stop_event.wait())
                    done, pending = await asyncio.wait(
                        {get_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in pending:
                        t.cancel()
                    if get_task not in done:
                        break
                    erp1: Erp1 = get_task.result()
                    if not is_teach_in_candidate(erp1):
                        continue
                    if erp1.sender_id in self._seen:
                        continue
                    self._seen.add(erp1.sender_id)
                    cand = Candidate(
                        sender_id=erp1.sender_id,
                        rorg=erp1.rorg,
                        payload_hex=erp1.payload.hex(),
                        status=erp1.status,
                        dbm=erp1.dbm,
                    )
                    for sub_q in list(self._candidate_subs):
                        try:
                            sub_q.put_nowait(cand)
                        except asyncio.QueueFull:
                            pass
        except Exception as e:
            logger.warning("pairing window task error: %s", e)
        finally:
            self._state = PairingState.CLOSED


@dataclass
class _CandidateSubscription:
    _registry: set[asyncio.Queue[Candidate]]
    queue: asyncio.Queue[Candidate]

    async def __aenter__(self) -> AsyncIterator[Candidate]:
        self._registry.add(self.queue)
        return self._iter()

    async def __aexit__(self, *exc: object) -> None:
        self._registry.discard(self.queue)

    async def _iter(self) -> AsyncIterator[Candidate]:
        while True:
            yield await self.queue.get()
