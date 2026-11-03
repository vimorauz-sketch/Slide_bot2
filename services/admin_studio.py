"""
Work the dashboard's AI studio runs in the background: test presentations and test referats in any
template (so the admin sees a new template on real content before customers do), and promo texts for
broadcasts. Jobs live in memory; their files in storage/admin_studio/<job>.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDIO_DIR = os.path.join(ROOT, "storage", "admin_studio")
MAX_JOBS = 20

STAGES = {"queued": "Navbatda", "write": "Matn yozilmoqda", "photos": "Rasmlar topilmoqda", "render": "Slaydlar chizilmoqda",
          "previews": "Fayllar tayyorlanmoqda", "done": "Tayyor", "failed": "Xato"}


@dataclass
class Job:
    id: str
    kind: str                       # deck / referat
    params: Dict[str, Any]
    admin: str = ""
    status: str = "queued"          # queued / running / done / failed
    stage: str = "queued"
    done: int = 0
    total: int = 0
    started: float = field(default_factory=time.time)
    finished: float = 0.0
    error: str = ""
    files: Dict[str, str] = field(default_factory=dict)     # pdf / pptx / docx -> path
    pictures: List[str] = field(default_factory=list)       # slide / page pictures
    task: Optional[asyncio.Task] = None

    @property
    def dir(self) -> str:
        return os.path.join(STUDIO_DIR, self.id)

    @property
    def stage_label(self) -> str:
        label = STAGES.get(self.stage, self.stage)
        return f"{label} ({self.done}/{self.total})" if self.total and self.status == "running" else label

    @property
    def seconds(self) -> int:
        return int((self.finished or time.time()) - self.started)


JOBS: Dict[str, Job] = {}


def get(job_id: str) -> Optional[Job]:
    return JOBS.get(job_id)


def recent() -> List[Job]:
    return sorted(JOBS.values(), key=lambda j: -j.started)


def start(kind: str, params: Dict[str, Any], admin: str = "") -> Job:
    job = Job(id=uuid.uuid4().hex[:12], kind=kind, params=params, admin=admin)
    JOBS[job.id] = job
    for old in sorted(JOBS.values(), key=lambda j: j.started)[:-MAX_JOBS]:
        if old.status not in ("queued", "running"):
            JOBS.pop(old.id, None)
    job.task = asyncio.ensure_future(_run(job))
    return job


async def _run(job: Job) -> None:
    from bot.handlers.create_pres import _build_slot

    async def progress(stage, done=0, total=0):
        job.stage, job.done, job.total = stage, done, total

    os.makedirs(job.dir, exist_ok=True)
    try:
        async with _build_slot():          # waits in the same queue as customers' orders
            job.status = "running"
            if job.kind == "deck":
                await _deck(job, progress)
            else:
                await _referat(job, progress)
        job.status, job.stage = "done", "done"
    except Exception as e:  # noqa: BLE001
        logger.exception("studio job %s failed", job.id)
        job.status, job.stage, job.error = "failed", "failed", str(e)[:300]
    finally:
        job.finished = time.time()


async def _deck(job: Job, progress) -> None:
    from services.presentation import build_presentation
    p = job.params
    data = {"topic": p["topic"], "subject": p.get("subject") or "Sinov", "slide_count": int(p.get("slides") or 8),
            "template_id": p["template"], "language": p.get("language") or "uz", "author_name": "SlideLab Admin",
            "institution": "SlideLab", "with_images": True}
    res = await build_presentation(data, job.dir, progress=progress, files_now=True, preview_count=1)
    job.pictures = list(res.slide_pngs)
    job.files = {k: v for k, v in (("pdf", res.pdf_path), ("pptx", res.pptx_path)) if v and os.path.exists(v)}


async def _referat(job: Job, progress) -> None:
    from services.referat import builder, render
    p = job.params
    data = {"topic": p["topic"], "subject": p.get("subject") or "Sinov", "size": p.get("size") or "short",
            "referat_template": p["template"], "language": p.get("language") or "uz", "author": "SlideLab Admin",
            "institution": "SlideLab", "level": "Universitet", "with_images": True}
    res = await builder.build_referat(data, job.dir, progress=progress)
    pics = await asyncio.to_thread(render.pdf_pages_to_images, res.pdf_path, os.path.join(job.dir, "pages"),
                                   list(range(min(res.pages, 6))), 700, "p")
    job.pictures = pics
    job.files = {k: v for k, v in (("pdf", res.pdf_path), ("docx", res.docx_path)) if v and os.path.exists(v)}


# ---------------------------------------------------------------------- promo texts
OFFLINE_TEXTS = [
    "🎉 <b>{title}</b>\n\n{brief}\n\n👉 Hoziroq sinab ko‘ring: /new",
    "✨ <b>Yangilik!</b>\n\n{brief}\n\nTaqdimot yoki referat kerakmi? Bir daqiqada tayyorlab beramiz — /start",
    "📣 Diqqat!\n\n{brief}\n\n🎁 Do‘stlaringizni taklif qiling va bepul taqdimot oling: /invite",
]


async def promo_texts(brief: str, tone: str = "friendly") -> Tuple[List[str], str]:
    """Three Telegram-ready broadcast texts (simple HTML: <b>, <i>) and the source (ai / offline)."""
    from services import ai_service
    brief = (brief or "").strip()[:800]
    client = ai_service.get_openai_client()
    if client is not None and brief:
        system = ("You write short Telegram broadcast messages in Uzbek (Latin script) for SlideLab, a bot that makes "
                  "presentations and referats with AI. Write 3 different variants (one short, one medium, one with "
                  "a clear call to action). Use only <b> and <i> HTML tags and a few fitting emojis; mention a command "
                  f"such as /new, /referat or /invite when it fits. Tone: {tone}. "
                  'Answer JSON: {"texts": ["...", "...", "..."]}')
        try:
            data = await ai_service._chat_json(client, system, brief)
            texts = [str(t).strip()[:3500] for t in (data.get("texts") or []) if str(t).strip()]
            if texts:
                return texts[:3], "ai"
        except Exception:  # noqa: BLE001
            logger.exception("AI promo texts failed")
    title = (brief.split(".")[0] or "SlideLab yangiliklari")[:60]
    return [t.format(title=title, brief=brief or "SlideLab’da yangi shablonlar paydo bo‘ldi!") for t in OFFLINE_TEXTS], "offline"
