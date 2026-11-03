"""
Dashboard pages «AI studiya» (new slide and referat templates, test decks / referats, broadcast texts)
and «Shablonlar» (every template: preview, usage, hide / show; AI templates: switch off, delete).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List
from urllib.parse import urlencode

from aiohttp import web
from sqlalchemy import func, select

from database.connection import AsyncSessionLocal
from database.models import PresentationOrder
from services import admin_studio, custom_templates as ct, runtime

TABS = [("slide", "🎨 Slayd shabloni"), ("referat", "📄 Referat shabloni"), ("test", "🧪 Sinov"), ("text", "✍️ Xabar matni")]
_LAST: Dict[str, Dict[str, Any]] = {}     # admin -> kind -> last generated drafts / texts
PAGE = 48


def _who(request) -> str:
    return str((request.get("admin") or {}).get("u", "admin"))


def _ai_on() -> bool:
    from services import ai_service
    return ai_service.get_openai_client() is not None


# ====================================================================== AI studio
async def studio_page(request: web.Request) -> web.Response:
    from bot.admin_web import render
    from services.deck import themes
    from services.referat import designs
    tab = request.query.get("tab", "slide")
    tab = tab if tab in dict(TABS) else "slide"
    last = _LAST.get(_who(request), {})
    slide = last.get("slide") or {}
    referat = last.get("referat") or {}
    slide_drafts = [d for d in (slide.get("drafts") or []) if themes.is_known_theme(d["id"])]
    referat_drafts = [d for d in (referat.get("drafts") or []) if d["id"] in designs.BY_ID]
    custom = await ct.list_all()
    slide_choices = [(t["id"], f"{t['code']} · {t['name']}") for t in themes.catalog()]
    slide_choices = [c for c in slide_choices if themes.is_custom(c[0])][::-1] + slide_choices[:60]
    referat_choices = [(t["id"], f"{t['code']} · {t['name']}") for t in designs.TEMPLATES]
    referat_choices = [c for c in referat_choices if designs.is_custom(c[0])][::-1] + referat_choices
    job = admin_studio.get(request.query.get("job", ""))
    return await render(request, "studio.html", "studio", tab=tab, tabs=TABS, ai_on=_ai_on(),
                        slide=slide, slide_drafts=slide_drafts, referat=referat, referat_drafts=referat_drafts,
                        custom=custom, jobs=admin_studio.recent()[:8], job=job, text=last.get("text") or {},
                        slide_choices=slide_choices, referat_choices=referat_choices,
                        request_kind="referat" if request.query.get("kind") == "referat" else ("deck" if request.query.get("kind") else ""),
                        template_q=request.query.get("template", "")[:64],
                        sizes=[("short", "5–7 bet"), ("medium", "8–10 bet"), ("long", "12–15 bet")],
                        examples=["Bolalar uchun kosmos mavzusida yorqin va quvnoq shablon",
                                  "Universitet himoyasi uchun qat’iy, ko‘k-oq rasmiy dizayn",
                                  "O‘zbek milliy naqshlari, atlas va oltin ranglar",
                                  "Startap pitch uchun zamonaviy qorong‘i neon uslub"],
                        rexamples=["Milliy naqshli, bordo va oltin rangli rasmiy referat",
                                   "Maktab o‘quvchilari uchun yorqin, quvnoq titul",
                                   "Texnik fanlar uchun chizma uslubidagi qat’iy dizayn"])


async def studio_generate(request: web.Request) -> web.Response:
    from bot.admin_web import audit, redirect
    kind = request.match_info["kind"]
    form = request.get("form") or {}
    prompt = str(form.get("prompt", "")).strip()[:600]
    if not prompt:
        raise redirect(f"/admin/studio?tab={kind}", err="Avval qanday shablon kerakligini yozing.")
    try:
        n = max(1, min(4, int(form.get("count") or 3)))
    except ValueError:
        n = 3
    if kind == "slide":
        choices, source = await ct.ai_slide_choices(prompt, n)
        drafts = [ct.make_slide_draft(c) for c in choices]
    elif kind == "referat":
        choices, source = await ct.ai_referat_choices(prompt, n)
        drafts = [ct.make_referat_draft(c) for c in choices]
    else:
        raise web.HTTPNotFound()
    _LAST.setdefault(_who(request), {})[kind] = {"prompt": prompt, "source": source, "drafts": drafts}
    await audit(request, "ai_studio", f"{kind}: {len(drafts)} ta qoralama · {prompt[:120]}")
    note = "" if source == "ai" else " (OpenAI kaliti yo‘q — so‘rovdagi kalit so‘zlar bo‘yicha tanlandi)"
    raise redirect(f"/admin/studio?tab={kind}", ok=f"{len(drafts)} ta variant tayyor{note}. Yoqqanini saqlang.")


def _draft(request, kind: str, did: str):
    for d in (_LAST.get(_who(request), {}).get(kind) or {}).get("drafts") or []:
        if d["id"] == did:
            return d
    return None


async def studio_publish(request: web.Request) -> web.Response:
    from bot.admin_web import audit, redirect
    kind = request.match_info["kind"]
    form = request.get("form") or {}
    d = _draft(request, kind, str(form.get("draft", "")))
    if d is None:
        raise redirect(f"/admin/studio?tab={kind}", err="Qoralama topilmadi — qaytadan yarating.")
    choice = dict(d["choice"])
    name = str(form.get("name", "")).strip()[:40]
    if name:
        choice["name"] = name
    prompt = (_LAST.get(_who(request), {}).get(kind) or {}).get("prompt", "")
    data = await ct.publish(kind, choice, prompt, _who(request))
    await audit(request, "ai_publish", f"{kind} {data['id']} · {choice['name']}")
    what = "Mini App va botda" if kind == "slide" else "referat shablonlari ro‘yxatida"
    raise redirect(f"/admin/templates?k={kind}&f=ai", ok=f"№ {data['code']} «{choice['name']}» saqlandi — endi {what} ko‘rinadi.")


async def draft_slide_preview(request: web.Request) -> web.StreamResponse:
    from services.gallery import preview_path
    path = await preview_path(request.match_info["key"], int(request.match_info["n"]))
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=3600", "Content-Type": "image/webp"})


async def draft_referat_preview(request: web.Request) -> web.StreamResponse:
    from services.referat import designs, gallery
    tid, n = request.match_info["tid"], int(request.match_info["n"])
    if tid not in designs.BY_ID or n not in gallery.PAGES:
        raise web.HTTPNotFound()
    path = await gallery.page_path(tid, n)
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=3600", "Content-Type": "image/jpeg"})


async def studio_test(request: web.Request) -> web.Response:
    from bot.admin_web import audit, redirect
    from services.deck import themes
    from services.referat import designs
    form = request.get("form") or {}
    kind = "referat" if form.get("kind") == "referat" else "deck"
    topic = str(form.get("topic", "")).strip()[:200]
    template = str(form.get("template", "")).strip()
    if not topic:
        raise redirect("/admin/studio?tab=test", err="Mavzuni yozing.")
    if kind == "deck" and not themes.is_known_theme(template):
        raise redirect("/admin/studio?tab=test", err="Slayd shablonini tanlang.")
    if kind == "referat" and template not in designs.BY_ID:
        raise redirect("/admin/studio?tab=test", err="Referat shablonini tanlang.")
    try:
        slides = max(5, min(15, int(form.get("slides") or 8)))
    except ValueError:
        slides = 8
    job = admin_studio.start(kind, {"topic": topic, "subject": str(form.get("subject", "")).strip()[:80],
                                    "template": template, "slides": slides, "size": str(form.get("size") or "short"),
                                    "language": "uz"}, _who(request))
    await audit(request, "ai_test", f"{kind} · {template} · {topic[:80]}")
    raise web.HTTPFound(f"/admin/studio?tab=test&job={job.id}")


async def job_file(request: web.Request) -> web.StreamResponse:
    from bot.delivery import file_name
    job = admin_studio.get(request.match_info["jid"])
    name = request.match_info["name"]
    if job is None:
        raise web.HTTPNotFound()
    if name.isdigit():
        i = int(name)
        if not 0 <= i < len(job.pictures):
            raise web.HTTPNotFound()
        return web.FileResponse(job.pictures[i], headers={"Cache-Control": "private, max-age=600"})
    path = job.files.get(name)
    if not path or not os.path.exists(path):
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Content-Disposition": f'attachment; filename="{file_name(job.params["topic"], name)}"'})


async def studio_text(request: web.Request) -> web.Response:
    from bot.admin_web import redirect
    form = request.get("form") or {}
    brief = str(form.get("brief", "")).strip()[:800]
    tone = str(form.get("tone", "friendly"))
    tone = tone if tone in ("friendly", "formal", "fun") else "friendly"
    if not brief:
        raise redirect("/admin/studio?tab=text", err="Xabar nima haqida bo‘lishini yozing.")
    texts, source = await admin_studio.promo_texts(brief, {"friendly": "warm and friendly", "formal": "polite and formal",
                                                          "fun": "playful and energetic"}[tone])
    _LAST.setdefault(_who(request), {})["text"] = {"brief": brief, "tone": tone, "texts": texts, "source": source}
    note = "" if source == "ai" else " (OpenAI kaliti yo‘q — tayyor andozalar)"
    raise redirect("/admin/studio?tab=text", ok=f"{len(texts)} ta variant tayyor{note}.")


# ====================================================================== templates
async def _usage(kind: str) -> Dict[str, int]:
    since = datetime.utcnow() - timedelta(days=30)
    cond = PresentationOrder.kind == "referat" if kind == "referat" else (
        (PresentationOrder.kind.is_(None)) | (PresentationOrder.kind != "referat"))
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PresentationOrder.template_id, func.count()).where(
            PresentationOrder.created_at >= since, cond).group_by(PresentationOrder.template_id))).all()
    out: Dict[str, int] = {}
    for tid, n in rows:
        base = str(tid or "").split("~")[0]
        out[base] = out.get(base, 0) + n
    return out


async def templates_page(request: web.Request) -> web.Response:
    from bot.admin_web import render
    from services.deck import themes
    from services.referat import designs
    kind = "referat" if request.query.get("k") == "referat" else "slide"
    f = request.query.get("f", "all")
    q = request.query.get("q", "").strip().lower()[:60]
    hidden = runtime.hidden_templates(kind)
    usage = await _usage(kind)
    rows = await ct.list_all(kind)
    custom = {r.id: r for r in rows}
    items: List[Dict[str, Any]] = []
    if kind == "slide":
        for t in themes.catalog():
            items.append({"id": t["id"], "code": t["code"], "name": t["name"], "sub": t.get("category", ""),
                          "ai": t["id"] in custom, "enabled": True, "pic": f"/webapp/cover/{t['id']}.webp",
                          "photo": "photo" in t["categories"]})
        for r in rows:
            if not r.enabled:
                items.append({"id": r.id, "code": r.code, "name": r.name, "sub": "AI · o‘chirilgan", "ai": True,
                              "enabled": False, "pic": "", "photo": False})
    else:
        for t in designs.TEMPLATES:
            items.append({"id": t["id"], "code": t["code"], "name": t["name"], "sub": designs.COVERS.get(t["cover"], ""),
                          "ai": t["id"] in custom, "enabled": True, "pic": f"/admin/studio/rpreview/{t['id']}_1.jpg",
                          "photo": False})
        for r in rows:
            if not r.enabled:
                items.append({"id": r.id, "code": r.code, "name": r.name, "sub": "AI · o‘chirilgan", "ai": True,
                              "enabled": False, "pic": "", "photo": False})
    for it in items:
        it["hidden"] = it["id"] in hidden
        it["used"] = usage.get(it["id"], 0)
    counts = {"all": len(items), "ai": sum(i["ai"] for i in items), "hidden": sum(i["hidden"] for i in items),
              "top": sum(1 for i in items if i["used"])}
    if f == "ai":
        items = [i for i in items if i["ai"]]
    elif f == "hidden":
        items = [i for i in items if i["hidden"]]
    elif f == "top":
        items = sorted([i for i in items if i["used"]], key=lambda i: -i["used"])
    if q:
        items = [i for i in items if q in i["name"].lower() or q == str(i["code"]) or q in i["sub"].lower()]
    try:
        page = max(1, int(request.query.get("page", "1")))
    except ValueError:
        page = 1
    pages = max(1, (len(items) + PAGE - 1) // PAGE)
    page = min(page, pages)
    shown = items[(page - 1) * PAGE: page * PAGE]
    qs = urlencode({a: b for a, b in (("k", kind), ("f", f), ("q", q)) if b})
    return await render(request, "templates.html", "templates", kind=kind, f=f, q=q, items=shown, counts=counts,
                        page=page, pages=pages, qs=qs, total=len(items), back=request.path_qs)


async def template_action(request: web.Request) -> web.Response:
    from bot.admin_web import audit, redirect
    kind = "referat" if request.match_info["kind"] == "referat" else "slide"
    tid, action = request.match_info["tid"], request.match_info["action"]
    form = request.get("form") or {}
    back = str(form.get("back") or f"/admin/templates?k={kind}")
    if not back.startswith("/admin/templates"):
        back = f"/admin/templates?k={kind}"
    if action in ("hide", "show"):
        hidden = runtime.hidden_templates(kind)
        (hidden.add if action == "hide" else hidden.discard)(tid)
        await runtime.set_many({f"hidden_{kind}_templates": ",".join(sorted(hidden))})
        await audit(request, "template_" + action, f"{kind} {tid}")
        raise redirect(back, ok=("Yashirildi — foydalanuvchilar ro‘yxatda ko‘rmaydi." if action == "hide" else "Yana ko‘rinadi."))
    if action in ("enable", "disable"):
        if not await ct.set_enabled(tid, action == "enable"):
            raise redirect(back, err="Bu AI shablon topilmadi.")
        await audit(request, "template_" + action, f"{kind} {tid}")
        raise redirect(back, ok="Yoqildi." if action == "enable" else "O‘chirildi — botda ko‘rinmaydi.")
    if action == "delete":
        if not await ct.delete(tid):
            raise redirect(back, err="Bu AI shablon topilmadi.")
        await audit(request, "template_delete", f"{kind} {tid}")
        raise redirect(back, ok="AI shablon butunlay o‘chirildi.")
    raise web.HTTPNotFound()


def setup(app: web.Application) -> None:
    r = app.router
    r.add_get("/admin/studio", studio_page)
    r.add_post(r"/admin/studio/generate/{kind:slide|referat}", studio_generate)
    r.add_post(r"/admin/studio/publish/{kind:slide|referat}", studio_publish)
    r.add_get(r"/admin/studio/preview/{key:[0-9a-z_]+}/{n:\d}.webp", draft_slide_preview)
    r.add_get(r"/admin/studio/rpreview/{tid:r[0-9a-z]+}_{n:\d}.jpg", draft_referat_preview)
    r.add_post("/admin/studio/test", studio_test)
    r.add_get(r"/admin/studio/job/{jid:[0-9a-f]+}/{name:pdf|pptx|docx|\d+}", job_file)
    r.add_post("/admin/studio/text", studio_text)
    r.add_get("/admin/templates", templates_page)
    r.add_post(r"/admin/templates/{kind:slide|referat}/{tid:[0-9A-Za-z_~-]+}/{action:hide|show|enable|disable|delete}",
               template_action)

