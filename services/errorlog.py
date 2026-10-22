"""Keeps the latest errors in memory for the dashboard's "Tizim holati" page."""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Deque, Dict, List

_records: Deque[Dict] = deque(maxlen=100)


class _Handler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                msg += f" — {type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
            _records.appendleft({"at": record.created, "level": record.levelname, "where": record.name,
                                 "message": msg[:600]})
        except Exception:  # noqa: BLE001
            pass


_installed = False


def install() -> None:
    global _installed
    if not _installed:
        h = _Handler(level=logging.ERROR)
        logging.getLogger().addHandler(h)
        _installed = True


def recent(limit: int = 50) -> List[Dict]:
    return list(_records)[:limit]


def count_since(seconds: float) -> int:
    edge = time.time() - seconds
    return sum(1 for r in _records if r["at"] >= edge)
