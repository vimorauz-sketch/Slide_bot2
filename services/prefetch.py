"""
Writing the presentation while the user is still answering questions.

As soon as everything that shapes the text is known (subject, topic, slide count, level and
class), the AI starts on the plan and the slides in the background. The remaining questions
(teacher, date, language, wishes) take the user 20-60 seconds, which is about what the AI needs,
so by the time "Create" is pressed the text is usually ready.

A job is identified by a fingerprint of the answers that change the text. When an answer changes
it (another language, extra wishes), the old job is cancelled and a new one starts; when the user
creates the deck, the job is used only if its fingerprint still matches. Names, institution, date
and the like are put on the title slide afterwards (services/presentation.refresh_title).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

from services import ai_service

logger = logging.getLogger(__name__)

TEXT_FIELDS = ("subject", "topic", "slide_count", "language", "additional_notes", "level", "course")
MAX_AGE = 30 * 60  # an abandoned job is forgotten after 30 minutes


def fingerprint(data: Dict[str, Any]) -> str:
    d = {k: str(data.get(k) or "") for k in TEXT_FIELDS}
    d["language"] = d["language"] or "uz"
    return json.dumps(d, sort_keys=True, ensure_ascii=False)


class Job:
    def __init__(self, data: Dict[str, Any]):
        self.data = dict(data)
        self.data.setdefault("language", "uz")
        self.fp = fingerprint(data)
        self.started = time.monotonic()
        self.outline: Optional[Dict[str, Any]] = None
        self.content: Optional[Dict[str, Any]] = None
        self.done = 0
        self.total = 0
        self.outline_ready = asyncio.Event()
        self.task = asyncio.ensure_future(self._run())

    async def _run(self) -> Dict[str, Any]:
        try:
            self.outline = await ai_service.generate_outline(self.data)
        finally:
            self.outline_ready.set()

        async def on_progress(done: int, total: int) -> None:
            self.done, self.total = done, total

        self.content = await ai_service.generate_presentation_content(self.data, self.outline, on_progress=on_progress)
        return self.content

    def cancel(self) -> None:
        if not self.task.done():
            self.task.cancel()


_jobs: Dict[int, Job] = {}


def _forget_old() -> None:
    now = time.monotonic()
    for uid in [u for u, j in _jobs.items() if now - j.started > MAX_AGE]:
        _jobs.pop(uid).cancel()


def _alive(job: Job) -> bool:
    if job.task.cancelled():
        return False
    return not (job.task.done() and job.task.exception() is not None)


def ensure(user_id: int, data: Dict[str, Any]) -> Job:
    """Starts writing for these answers unless the same job is already running (or done)."""
    _forget_old()
    job = _jobs.get(user_id)
    if job is not None and job.fp == fingerprint(data) and _alive(job):
        return job
    if job is not None:
        job.cancel()
    job = _jobs[user_id] = Job(data)
    logger.info("prefetch started for user %s", user_id)
    return job


def get(user_id: int, data: Dict[str, Any]) -> Optional[Job]:
    """The running/finished job if it was written for exactly these answers."""
    job = _jobs.get(user_id)
    if job is None or job.fp != fingerprint(data) or not _alive(job):
        return None
    return job


def drop(user_id: int) -> None:
    job = _jobs.pop(user_id, None)
    if job is not None:
        job.cancel()


def take(user_id: int, data: Dict[str, Any]) -> Optional[Job]:
    """Like get(), but the job is removed (it belongs to the order that is being built now)."""
    job = get(user_id, data)
    if job is not None:
        _jobs.pop(user_id, None)
    return job
