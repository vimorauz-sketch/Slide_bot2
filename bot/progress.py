"""
Animated progress message shown while a presentation is being made:

    🎨 Taqdimotingiz tayyorlanmoqda

    ▰▰▰▰▰▰▰▰▱▱▱▱  68%

    ✅ Reja tuzildi
    ✅ Matn yozildi (11/11)
    ◑ Rasmlar tanlanmoqda…
    ▫️ Slaydlar chiziladi

The percentage follows the real work (every finished slide moves it) and creeps forward
smoothly in between, so the bar never looks frozen. Telegram limits how often a message may be
edited, so the text is updated at most every EDIT_EVERY seconds and only when it changed.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

EDIT_EVERY = 1.6
BAR_CELLS = 12
SPIN = "◐◓◑◒"

# stage -> (start %, end %, while running, when done, still to come)
STAGES = [
    ("write", 2, 62, "AI matn yozmoqda", "Matn yozildi", "Matn yoziladi"),
    ("photos", 62, 78, "Rasmlar tanlanmoqda", "Rasmlar tanlandi", "Rasmlar tanlanadi"),
    ("render", 78, 95, "Slaydlar chizilmoqda", "Slaydlar chizildi", "Slaydlar chiziladi"),
    ("previews", 95, 99, "Namuna tayyorlanmoqda", "Namuna tayyor", "Namuna tayyorlanadi"),
]
_INDEX = {s[0]: i for i, s in enumerate(STAGES)}
REFERAT_STAGES = [
    ("write", 2, 66, "AI referat matnini yozmoqda", "Matn yozildi", "Matn yoziladi"),
    ("photos", 66, 78, "Rasmlar topilmoqda", "Rasmlar topildi", "Rasmlar topiladi"),
    ("render", 78, 96, "Word va PDF sahifalari tayyorlanmoqda", "Sahifalar tayyor", "Sahifalar tayyorlanadi"),
    ("previews", 96, 99, "Namuna tayyorlanmoqda", "Namuna tayyor", "Namuna tayyorlanadi"),
]
# how long a stage usually takes (seconds): the bar creeps towards the stage end at this pace
_EXPECTED = {"write": 35.0, "photos": 10.0, "render": 10.0, "previews": 2.0}


def bar(pct: float) -> str:
    full = int(round(max(0.0, min(100.0, pct)) / 100 * BAR_CELLS))
    return "▰" * full + "▱" * (BAR_CELLS - full)


class ProgressMessage:
    def __init__(self, message, title: str = "🎨 <b>Taqdimotingiz tayyorlanmoqda</b>", stages=None):
        self.message = message
        self.stages = stages or STAGES
        self.title = title
        self.stage = 0
        self.stage_started = time.monotonic()
        self.done = 0
        self.total = 0
        self.shown = 0.0
        self.note = ""
        self.frame = 0
        self._last_text = ""
        self._last_edit = 0.0
        self._ticker: Optional[asyncio.Task] = None
        self.finished = False

    # ------------------------------------------------------------------ state
    def target(self) -> float:
        """Where the bar should be now: real progress plus a smooth creep inside the stage."""
        name, start, end, *_ = self.stages[self.stage]
        if name == "write" and self.total:
            real = start + (end - start) * self.done / self.total
        else:
            real = start
        elapsed = time.monotonic() - self.stage_started
        creep = start + (end - start) * min(0.92, elapsed / (_EXPECTED[name] * 1.4))
        return min(end - 1, max(real, creep))

    def text(self) -> str:
        lines = [self.title, "", f"<code>{bar(self.shown)}</code>  <b>{int(self.shown)}%</b>", ""]
        for i, (name, _s, _e, running, done, later) in enumerate(self.stages):
            if self.finished or i < self.stage:
                extra = f" ({self.total}/{self.total})" if name == "write" and self.total > 1 else ""
                lines.append(f"✅ {done}{extra}")
            elif i == self.stage:
                extra = f" {self.done}/{self.total}" if name == "write" and self.total > 1 else ""
                lines.append(f"{SPIN[self.frame % len(SPIN)]} <b>{running}…</b>{extra}")
            else:
                lines.append(f"▫️ {later}")
        if self.note:
            lines += ["", self.note]
        return "\n".join(lines)

    # ------------------------------------------------------------------ updates
    async def set(self, stage: str, done: int = 0, total: int = 0) -> None:
        i = _INDEX.get(stage)
        if i is None:
            return
        if i != self.stage:
            self.stage = max(self.stage, i)
            self.stage_started = time.monotonic()
            self.note = ""
        if stage == "write" and total:
            self.done, self.total = done, total
        await self.refresh()

    async def refresh(self, force: bool = False) -> None:
        self.shown = max(self.shown, self.target()) if not self.finished else 100.0
        now = time.monotonic()
        if not force and now - self._last_edit < EDIT_EVERY:
            return
        txt = self.text()
        if txt == self._last_text:
            return
        self._last_edit = now
        self._last_text = txt
        try:
            await self.message.edit_text(txt, parse_mode="HTML")
        except Exception as e:  # noqa: BLE001 - "message is not modified", flood limits…
            logger.debug("progress edit skipped: %s", e)

    async def _tick(self) -> None:
        while not self.finished:
            await asyncio.sleep(EDIT_EVERY)
            self.frame += 1
            await self.refresh()

    def start(self) -> "ProgressMessage":
        self._ticker = asyncio.ensure_future(self._tick())
        return self

    async def finish(self) -> None:
        self.finished = True
        self.stage = len(self.stages) - 1
        if self._ticker:
            self._ticker.cancel()
        await self.refresh(force=True)

    async def stop(self) -> None:
        self.finished = True
        if self._ticker:
            self._ticker.cancel()
