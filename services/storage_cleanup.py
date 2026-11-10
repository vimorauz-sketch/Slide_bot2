"""
Keeps the server's disk from filling up.

Every order writes its pictures, PDF and PPTX/DOCX to storage/<random id>/. The order's content is also
saved in the database (content_json), and services/payment/orders.order_files() rebuilds the files
from it when they are missing — so an old order folder can be deleted safely. A folder is deleted
when it is older than STORAGE_KEEP_DAYS (default 3) and either no order uses it or the order that uses
it has its content in the database. The admin studio's test outputs go after the same time.
Runs at start and then every 6 hours.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import time
from typing import Dict, Set

from sqlalchemy import select

from database.connection import AsyncSessionLocal
from database.models import PresentationOrder

logger = logging.getLogger(__name__)

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage")
EVERY = 6 * 3600
_ORDER_DIR = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def keep_days() -> float:
    try:
        return max(1.0, float(os.getenv("STORAGE_KEEP_DAYS", "3")))
    except ValueError:
        return 3.0


def _age_days(path: str, now: float) -> float:
    try:
        return (now - os.path.getmtime(path)) / 86400
    except OSError:
        return 0.0


async def _folders_in_use() -> Dict[str, bool]:
    """storage folder name -> True when the order that uses it can be rebuilt from the database."""
    out: Dict[str, bool] = {}
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PresentationOrder.id, PresentationOrder.pdf_path, PresentationOrder.pptx_path,
                                       PresentationOrder.content_json.isnot(None)))).all()
    for oid, pdf, pptx, has_content in rows:
        names: Set[str] = {str(oid)}
        for p in (pdf, pptx):
            if p:
                names.add(os.path.basename(os.path.dirname(p)))
        for n in names:
            out[n] = out.get(n, True) and bool(has_content)
    return out


async def run_once(root: str = ROOT) -> int:
    """Deletes old order folders; returns how many were deleted."""
    if not os.path.isdir(root):
        return 0
    now, limit = time.time(), keep_days()
    old = [n for n in os.listdir(root)
           if _ORDER_DIR.match(n) and os.path.isdir(os.path.join(root, n)) and _age_days(os.path.join(root, n), now) > limit]
    studio = os.path.join(root, "admin_studio")
    old_studio = [os.path.join(studio, n) for n in (os.listdir(studio) if os.path.isdir(studio) else [])
                  if _age_days(os.path.join(studio, n), now) > limit]
    if not old and not old_studio:
        return 0
    used = await _folders_in_use() if old else {}
    removed = 0
    for n in old:
        if n in used and not used[n]:
            continue                      # an order without saved content still needs its files
        shutil.rmtree(os.path.join(root, n), ignore_errors=True)
        removed += 1
    for path in old_studio:
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
    if removed:
        logger.info("storage cleanup: %d old folder(s) deleted", removed)
    return removed


async def loop() -> None:
    await asyncio.sleep(120)
    while True:
        try:
            await run_once()
        except Exception:  # noqa: BLE001
            logger.exception("storage cleanup failed")
        await asyncio.sleep(EVERY)
