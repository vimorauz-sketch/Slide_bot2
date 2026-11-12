"""
Tells the admins in Telegram when something goes wrong, so nobody has to watch the server logs.

Every log record of level ERROR or higher (a failed build, a payment that could not be checked, an
unhandled exception) is sent to the admins' chats. The same message is sent at most once per
REPEAT_AFTER seconds and at most BURST messages go out per minute, so a storm of errors cannot
flood the admins or hit Telegram's limits. Turn it off with ADMIN_ALERTS=0.
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import time
from typing import Dict, Optional

REPEAT_AFTER = 30 * 60
BURST = 4
MAX_LEN = 1500
# expected noise that needs no human
IGNORE = ("terminated by other getupdates", "bot was blocked by the user", "query is too old",
          "message is not modified", "server disconnected", "flood control")

_queue: Optional[asyncio.Queue] = None
_seen: Dict[str, float] = {}
_sent_times: list = []


class _Handler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if _queue is None or record.name.startswith("services.admin_alerts"):
            return
        try:
            text = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                text += f"\n{type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
            if any(k in text.lower() for k in IGNORE):
                return
            key = f"{record.name}:{record.getMessage()[:120]}"
            now = time.time()
            if now - _seen.get(key, 0) < REPEAT_AFTER:
                return
            _seen[key] = now
            if len(_seen) > 500:
                for k in [k for k, t in _seen.items() if now - t > REPEAT_AFTER]:
                    _seen.pop(k, None)
            _queue.put_nowait((record.levelname, record.name, text[:MAX_LEN]))
        except Exception:  # noqa: BLE001 - logging must never raise
            pass


async def _worker(bot) -> None:
    from services import runtime
    while True:
        level, name, text = await _queue.get()
        now = time.time()
        _sent_times[:] = [t for t in _sent_times if now - t < 60]
        if len(_sent_times) >= BURST:
            continue                     # too many in a minute: the rest stay in the server log
        _sent_times.append(now)
        body = f"🚨 <b>{html.escape(level)}</b> · <code>{html.escape(name)}</code>\n\n{html.escape(text)}"
        for admin in sorted(runtime.admin_ids()):
            try:
                await bot.send_message(admin, body, parse_mode="HTML", disable_notification=level != "CRITICAL")
            except Exception:  # noqa: BLE001 - an admin who never opened the bot
                pass


def install(bot) -> Optional[asyncio.Task]:
    """Starts sending ERROR records to the admins. Returns the background task (None when turned off)."""
    global _queue
    if os.getenv("ADMIN_ALERTS", "1") == "0":
        return None
    _queue = asyncio.Queue(maxsize=100)
    handler = _Handler(level=logging.ERROR)
    root = logging.getLogger()
    if not any(isinstance(h, _Handler) for h in root.handlers):
        root.addHandler(handler)
    return asyncio.ensure_future(_worker(bot))
