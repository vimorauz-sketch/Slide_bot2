"""
Wizard state (aiogram FSM) that survives a restart or a redeploy.

aiogram's MemoryStorage forgets every half-filled order when the bot restarts. This storage keeps
the state in memory as before (same objects, same speed) and also writes it to the database table
fsm_states, so after a restart a user continues where they stopped. The data must be JSON (the
wizards store text, numbers, lists and dicts); anything else is written as text. Rows untouched
for KEEP_DAYS are deleted at start.
"""
from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Mapping, Optional

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import delete

from database.connection import AsyncSessionLocal
from database.models import FsmState

logger = logging.getLogger(__name__)
KEEP_DAYS = 7


def _key(key: StorageKey) -> str:
    return ":".join(str(x) for x in (key.bot_id, key.chat_id, key.user_id, key.thread_id or "",
                                    key.business_connection_id or "", key.destiny))[:255]


class DbStorage(BaseStorage):
    def __init__(self) -> None:
        self._mem: Dict[str, Dict[str, Any]] = {}     # key -> {"state": str|None, "data": dict}

    async def _load(self, k: str) -> Dict[str, Any]:
        entry = self._mem.get(k)
        if entry is not None:
            return entry
        if len(self._mem) > 50000:   # the database has everything: memory only keeps recent users
            self._mem.clear()
        entry = {"state": None, "data": {}}
        try:
            async with AsyncSessionLocal() as s:
                row = await s.get(FsmState, k)
            if row is not None:
                entry = {"state": row.state, "data": json.loads(row.data or "{}")}
        except Exception:  # noqa: BLE001 - an empty state is better than a broken update
            logger.exception("FSM state %s could not be read", k)
        self._mem[k] = entry
        return entry

    async def _save(self, k: str, entry: Dict[str, Any]) -> None:
        try:
            async with AsyncSessionLocal() as s:
                if entry["state"] is None and not entry["data"]:
                    await s.execute(delete(FsmState).where(FsmState.key == k))
                else:
                    await s.merge(FsmState(key=k, state=entry["state"], updated_at=datetime.utcnow(),
                                           data=json.dumps(entry["data"], ensure_ascii=False, default=str)))
                await s.commit()
        except Exception:  # noqa: BLE001 - the state still works in memory until the next restart
            logger.exception("FSM state %s could not be saved", k)
        if entry["state"] is None and not entry["data"]:
            self._mem.pop(k, None)

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        k = _key(key)
        entry = await self._load(k)
        entry["state"] = state.state if isinstance(state, State) else state
        await self._save(k, entry)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        return (await self._load(_key(key)))["state"]

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError(f"Data must be a dict, got {type(data).__name__}")
        k = _key(key)
        entry = await self._load(k)
        entry["data"] = copy.copy(dict(data))
        await self._save(k, entry)

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        return copy.copy((await self._load(_key(key)))["data"])

    async def get_value(self, storage_key: StorageKey, dict_key: str, default: Optional[Any] = None) -> Optional[Any]:
        return copy.copy((await self._load(_key(storage_key)))["data"].get(dict_key, default))

    async def close(self) -> None:
        self._mem.clear()


async def cleanup_old() -> int:
    """Deletes wizard states nobody touched for KEEP_DAYS."""
    try:
        async with AsyncSessionLocal() as s:
            res = await s.execute(delete(FsmState).where(FsmState.updated_at < datetime.utcnow() - timedelta(days=KEEP_DAYS)))
            await s.commit()
            return int(res.rowcount or 0)
    except Exception:  # noqa: BLE001
        logger.exception("old FSM states could not be deleted")
        return 0


__all__ = ["DbStorage", "cleanup_old"]
