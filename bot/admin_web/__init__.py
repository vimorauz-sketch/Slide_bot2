"""
Admin dashboard served by the bot's own web server at /admin.

Pages: Bosh sahifa (stats), Buyurtmalar, Foydalanuvchilar, To‘lovlar (TezCheck), Xabar tarqatish,
Sozlamalar, Tizim holati. Sign-in, sessions and CSRF: bot/admin_web/auth.py.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import platform
import shutil
import time
import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from aiohttp import web
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from sqlalchemy import exists, func, or_, select, update

from config import settings
from database.connection import AsyncSessionLocal, IS_POSTGRES
from database.models import AuditLog, Broadcast, PresentationOrder, User
from services import runtime
from bot.admin_web import auth, stats

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STARTED = time.time()
PAGE = 20
TZ = timedelta(hours=5)

_env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates")),
                   autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)

# ---------------------------------------------------------------------- template helpers
AVATAR_COLORS = ["#6E7BFF", "#EC4899", "#10B981", "#F59E0B", "#0EA5E9", "#8B5CF6", "#E5484D", "#14B8A6", "#64748B"]
STATUS = {
    "PAID": ("To‘langan", "c-paid"), "PREVIEW_READY": ("Namuna", "c-prev"), "CREATED": ("Namuna", "c-prev"),
    "WAITING_PAYMENT": ("To‘lov kutilmoqda", "c-wait"), "CANCELLED": ("Bekor qilingan", "c-canc"),
    "REFUNDED": ("Qaytarilgan", "c-ref"),
}
LANGS = {"uz": "O‘zbek", "ru": "Rus", "en": "Ingliz"}


def money(n) -> str:
    return stats.money(n)


def dt(value) -> str:
    if not value:
        return "—"
    return (value + TZ).strftime("%d.%m.%Y %H:%M")


def iso(value) -> str:
    if not value:
        return "—"
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        d = d.replace(tzinfo=None) - (d.utcoffset() or timedelta(0))
        return dt(d)
    except ValueError:
        return str(value)[:16]


def ago(value) -> str:
    if not value:
        return "—"
    sec = (datetime.utcnow() - value).total_seconds()
    if sec < 120:
        return "Hozir onlayn"
    if sec < 3600:
        return f"{int(sec // 60)} daqiqa oldin"
    if sec < 86400:
        return f"{int(sec // 3600)} soat oldin"
    return dt(value)


def initials(name) -> str:
    parts = [p for p in str(name or "?").replace("@", "").split() if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


def avatar_color(uid) -> str:
    try:
        return AVATAR_COLORS[int(uid) % len(AVATAR_COLORS)]
    except (TypeError, ValueError):
        return AVATAR_COLORS[0]


def status_chip(status) -> Markup:
    label, cls = STATUS.get(status or "", (status or "—", "c-canc"))
    return Markup(f'<span class="chip {cls}"><span class="dot"></span>{escape(label)}</span>')


def user_chip(u) -> Markup:
    if getattr(u, "is_blocked", False):
        return Markup('<span class="chip c-ref"><span class="dot"></span>Bloklangan</span>')
    if getattr(u, "bot_blocked", False):
        return Markup('<span class="chip c-canc"><span class="dot"></span>Botni bloklagan</span>')
    return Markup('<span class="chip c-paid"><span class="dot"></span>Faol</span>')


def pay_chip(t) -> Markup:
    state = (t or {}).get("state", "")
    cls = {"succeeded": "c-paid", "processing": "c-wait", "requires_action": "c-wait", "open": "c-prev",
           "failed": "c-ref", "canceled": "c-canc", "expired": "c-canc", "refunded": "c-ref",
           "partially_refunded": "c-ref", "disputed": "c-ref", "charged_back": "c-ref"}.get(state, "c-canc")
    label = {"succeeded": "O‘tdi", "processing": "Jarayonda", "requires_action": "Kutilmoqda", "open": "Ochiq",
             "failed": "O‘tmadi", "canceled": "Bekor", "expired": "Muddati o‘tdi", "refunded": "Qaytarildi"}.get(state, state or "—")
    if (t or {}).get("problem") and (t["problem"] or {}).get("unknown_reason"):
        cls, label = "c-wait", "Noma’lum — kutilmoqda"
    return Markup(f'<span class="chip {cls}"><span class="dot"></span>{escape(label)}</span>')


@lru_cache(maxsize=512)
def template_colors(template_id: str) -> Dict[str, str]:
    try:
        from services.deck import themes
        p = themes.get_theme(template_id or "").get("palette", {})
        return {"bg": p.get("bg", "#F1F2F8"), "fg": p.get("text", "#12153A"), "ac": p.get("primary", "#6E7BFF")}
    except Exception:  # noqa: BLE001
        return {"bg": "#F1F2F8", "fg": "#12153A", "ac": "#6E7BFF"}


@lru_cache(maxsize=512)
def template_name(template_id: str) -> str:
    if not template_id or template_id == "custom_ai":
        return "AI maxsus dizayn"
    try:
        from services.deck import themes
        t = themes.get_theme(template_id)
        return f"{int(t.get('code') or 0)} · {t.get('name', template_id)} · {t.get('color_name', '')}".strip(" ·")
    except Exception:  # noqa: BLE001
        return template_id


def thumb(o) -> Markup:
    c = template_colors(getattr(o, "template_id", "") or "")
    return Markup(
        f'<span class="thumb" aria-hidden="true" style="background:{escape(c["bg"])}">'
        f'<i style="left:6px;top:8px;width:20px;height:3px;background:{escape(c["fg"])}"></i>'
        f'<i style="left:6px;top:15px;width:14px;height:2px;background:{escape(c["fg"])};opacity:.6"></i>'
        f'<i style="right:5px;top:5px;width:14px;height:20px;border-radius:3px;background:{escape(c["ac"])}"></i></span>')


_env.globals.update(money=money, dt=dt, iso=iso, ago=ago, initials=initials, avatar_color=avatar_color,
                    status_chip=status_chip, user_chip=user_chip, pay_chip=pay_chip, thumb=thumb,
                    lang_name=lambda c: LANGS.get(c or "", c or "—"))


# ---------------------------------------------------------------------- plumbing
def _bot(request):
    from bot.webhook_app import BOT_KEY
    return request.app.get(BOT_KEY)


def _builds():
    try:
        from bot.handlers import create_pres
        sem = create_pres._build_sem
        size = create_pres._build_sem_size or runtime.get_int("max_parallel_builds", 2)
        busy = (size - sem._value) if sem is not None else 0
        return max(0, busy), int(create_pres._build_waiting), size
    except Exception:  # noqa: BLE001
        return 0, 0, 0


def _uptime() -> str:
    s = int(time.time() - STARTED)
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return f"{d} kun {h} soat" if d else f"{h} soat {m} daqiqa"


async def _nav_waiting() -> int:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(func.count()).select_from(PresentationOrder)
                                .where(PresentationOrder.status == "WAITING_PAYMENT"))).scalar() or 0


async def render(request, name: str, active: str, **ctx) -> web.Response:
    sess = request.get("admin") or {}
    building, _, _ = _builds()
    base = {
        "active": active, "csrf": auth.csrf_token(request), "admin_label": sess.get("u", "admin"),
        "maintenance": runtime.get_bool("maintenance"), "nav_waiting": await _nav_waiting(),
        "uptime": _uptime(), "building": building,
        "flash": request.query.get("ok") or request.query.get("err"), "flash_err": bool(request.query.get("err")),
        "pay_banner": _pay_banner(),
    }
    base.update(ctx)
    html = _env.get_template(name).render(**base)
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-store"})


def _pay_banner() -> str:
    from services import guard
    from services.payment.orders import payment_mode
    mode = payment_mode()
    if mode == "off":
        return ("To‘lov tizimi ulanmagan (TEZCHECK_* o‘zgaruvchilari yo‘q) — " +
                ("yangi taqdimot yaratish YOPIQ." if not guard.creation_open() else
                 "lekin taqdimot yaratish OCHIQ: AI pul sarflaydi, to‘lov olinmaydi!"))
    if mode == "demo":
        return "DEMO rejim yoqilgan (ALLOW_DEMO_PAYMENTS): «To‘lovni tasdiqlash» pulsiz tasdiqlaydi — faqat sinov uchun!"
    return ""


def redirect(path: str, ok: str = "", err: str = "") -> web.HTTPFound:
    q = {}
    if ok:
        q["ok"] = ok
    if err:
        q["err"] = err
    sep = "&" if "?" in path else "?"
    return web.HTTPFound(path + (sep + urlencode(q) if q else ""))


async def audit(request, action: str, details: str = "") -> None:
    sess = request.get("admin") or {}
    try:
        async with AsyncSessionLocal() as s:
            s.add(AuditLog(admin=str(sess.get("u", "?"))[:64], action=action[:64], details=details[:2000]))
            await s.commit()
    except Exception:  # noqa: BLE001
        logger.exception("audit write failed")


@web.middleware
async def admin_guard(request: web.Request, handler):
    path = request.path
    if not path.startswith("/admin"):
        return await handler(request)
    public = path in ("/admin/login", "/admin/login/tg")
    if not public:
        sess = auth.current(request)
        if not sess:
            if request.method == "GET":
                raise web.HTTPFound("/admin/login")
            raise web.HTTPForbidden(text="Sessiya tugagan — qayta kiring")
        request["admin"] = sess
        if request.method == "POST":
            ctype = request.content_type or ""
            form = await request.post() if ctype.startswith(("application/x-www-form-urlencoded", "multipart/")) else {}
            if not auth.check_csrf(request, form):
                raise web.HTTPForbidden(text="CSRF tekshiruvi o‘tmadi — sahifani yangilang")
            request["form"] = form
    resp = await handler(request)
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


# ---------------------------------------------------------------------- sign in
async def login_page(request: web.Request, error: str = "") -> web.Response:
    if auth.current(request):
        raise web.HTTPFound("/admin")
    bot_url = ""
    bot = _bot(request)
    if bot is not None:
        try:
            me = await bot.me()
            bot_url = f"https://t.me/{me.username}"
        except Exception:  # noqa: BLE001
            pass
    lock = auth.locked_for(auth.client_ip(request))
    if lock and not error:
        error = f"Juda ko‘p noto‘g‘ri urinish. {lock // 60 + 1} daqiqadan so‘ng qayta urinib ko‘ring."
    html = _env.get_template("login.html").render(error=error or request.query.get("err", ""), bot_url=bot_url,
                                                  password_enabled=auth.password_enabled())
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-store"})


async def login_post(request: web.Request) -> web.Response:
    form = await request.post()
    ip = auth.client_ip(request)
    if auth.locked_for(ip):
        return await login_page(request)
    if not auth.check_password(ip, str(form.get("login", "")), str(form.get("password", ""))):
        logger.warning("dashboard: wrong password from %s", ip)
        return await login_page(request, "Login yoki parol noto‘g‘ri.")
    resp = web.HTTPFound("/admin")
    auth.set_cookie(request, resp, auth.make_session(str(form.get("login", "admin")).strip() or "admin"))
    request["admin"] = {"u": str(form.get("login", "admin"))}
    await audit(request, "login", f"parol bilan, {ip}")
    raise resp


async def login_tg(request: web.Request) -> web.Response:
    admin_id = await auth.use_login_token(request.query.get("t", ""))
    if not admin_id:
        raise web.HTTPFound("/admin/login?" + urlencode({"err": "Havola eskirgan yoki allaqachon ishlatilgan. Botga /admin yuboring."}))
    name = str(admin_id)
    try:
        async with AsyncSessionLocal() as s:
            u = await s.get(User, admin_id)
            if u and (u.full_name or u.username):
                name = (u.full_name or u.username)[:40]
    except Exception:  # noqa: BLE001
        pass
    resp = web.HTTPFound("/admin")
    auth.set_cookie(request, resp, auth.make_session(name, admin_id))
    request["admin"] = {"u": name}
    await audit(request, "login", f"Telegram havola, {auth.client_ip(request)}")
    raise resp


async def logout(request: web.Request) -> web.Response:
    resp = web.HTTPFound("/admin/login")
    resp.del_cookie(auth.COOKIE, path="/admin")
    raise resp


# ---------------------------------------------------------------------- dashboard
async def dashboard(request: web.Request) -> web.Response:
    period = request.query.get("p", "7")
    s = await stats.overview(period)
    top = stats.nice_top(max(s["series"] + s["series_prev"] + [1]))
    line = stats.smooth_path(s["series"], top=top)
    peak_i = max(range(14), key=lambda i: s["series"][i])
    peak = None
    if s["series"][peak_i] > 0:
        x = 40 + peak_i * 650 / 13
        y = 220 - s["series"][peak_i] / top * 200
        peak = {"x": round(min(max(x, 92), 638), 1), "y": round(max(y, 50), 1), "t": f"{money(s['series'][peak_i])} so‘m"}
    chart = {"line": line, "prev": stats.smooth_path(s["series_prev"], top=top), "peak": peak}
    yticks = [(220 - i * 50, f"{int(top * i / 4 / 1000)}k" if top >= 4000 else str(int(top * i / 4))) for i in range(4, -1, -1)]
    xlabels = [(round(40 + i * 650 / 13), s["days"][i]) for i in range(0, 14, 2)]
    kpis = [
        {"label": "To‘lovlar", "value": money(s["payments"]), "delta": s["payments_delta"], "color": "#6E7BFF", "tint": "#EEF0FF",
         "icon": "M2 7h20v12H2zM2 11h20M6 15h4", "spark": stats.spark_path(s["spark_paid"])},
        {"label": "Yaratilgan namunalar", "value": money(s["previews"]), "delta": s["previews_delta"], "color": "#F59E0B",
         "tint": "#FEF6E4", "icon": "M4 4h16v12H4zM8 20h8M12 16v4", "spark": stats.spark_path(s["spark_previews"])},
        {"label": "Yangi foydalanuvchilar", "value": money(s["new_users"]), "delta": s["new_users_delta"], "color": "#10B981",
         "tint": "#E7F8F1", "icon": "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21c0-4 3-6 7-6s7 2 7 6M19 8v6M16 11h6",
         "spark": stats.spark_path(s["spark_users"])},
        {"label": "To‘lov kutilmoqda", "value": money(s["waiting"]), "delta": ("hozir", "flat"), "color": "#E5484D",
         "tint": "#FDECEC", "icon": "M12 8v4l3 2M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z", "spark": ""},
    ]
    import math
    C = 2 * math.pi * 70
    total = sum(s["status"].values())
    acc, donut = 0.0, []
    for key, name, color in (("PAID", "To‘langan", "#6E7BFF"), ("PREVIEW_READY", "Namuna", "#F59E0B"),
                             ("WAITING_PAYMENT", "To‘lov kutilmoqda", "#10B981"), ("CANCELLED", "Bekor / qaytarilgan", "#E5484D")):
        n = s["status"][key]
        ln = (n / total * C) if total else 0
        donut.append({"name": name, "n": n, "color": color, "dash": f"{max(0, ln - 3 if n else 0):.1f} {C:.1f}", "off": f"{-acc:.1f}"})
        acc += ln
    tmax = s["top_templates"][0][1] if s["top_templates"] else 1
    templates = [{"name": template_name(t), "n": n, "w": round(n / tmax * 100), **template_colors(t)} for t, n in s["top_templates"]]
    smax = s["top_subjects"][0][1] if s["top_subjects"] else 1
    scol = ["#6E7BFF", "#F59E0B", "#10B981", "#EC4899", "#0EA5E9", "#8B5CF6"]
    subjects = [{"name": n[:14], "n": c, "h": max(6, round(c / smax * 82)), "color": scol[i % 6]} for i, (n, c) in enumerate(s["top_subjects"])]
    fmax = max([n for _, n in s["funnel"]] + [1])
    fcol = ["#1B2150", "#6E7BFF", "#10B981"]
    funnel = [{"name": n, "n": money(c), "w": max(45, round(c / fmax * 100)), "color": fcol[i]} for i, (n, c) in enumerate(s["funnel"])]
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(PresentationOrder, User.full_name, User.username)
                                 .join(User, User.telegram_id == PresentationOrder.user_id, isouter=True)
                                 .order_by(PresentationOrder.created_at.desc()).limit(6))).all()
    recent = []
    for o, fn, un in rows:
        o.user_name = fn or (f"@{un}" if un else str(o.user_id))
        recent.append(o)
    hour = stats.local_now().hour
    greeting = "Xayrli tong" if 5 <= hour < 12 else "Xayrli kun" if hour < 18 else "Xayrli kech"
    return await render(request, "dashboard.html", "home", s=s, kpis=kpis, chart=chart, yticks=yticks, xlabels=xlabels,
                        donut=donut, donut_total=total, templates=templates, subjects=subjects, funnel=funnel,
                        recent=recent, greeting=greeting, now=stats.local_now().strftime("%d.%m.%Y %H:%M"),
                        periods=[(k, v[0]) for k, v in stats.PERIODS.items()],
                        conv_dash=f"{max(0.0, min(1.0, s['conversion'] / 100)) * 2 * math.pi * 48:.1f} 302")


# ---------------------------------------------------------------------- orders
ORDER_FILTERS = [("all", "Barchasi", None), ("prev", "Namuna", ("PREVIEW_READY", "CREATED")),
                 ("wait", "Kutilmoqda", ("WAITING_PAYMENT",)), ("paid", "To‘langan", ("PAID",)),
                 ("canc", "Bekor", ("CANCELLED", "REFUNDED"))]


def _order_conditions(f: str, q: str):
    conds = []
    statuses = dict((k, v) for k, _, v in ORDER_FILTERS).get(f)
    if statuses:
        conds.append(PresentationOrder.status.in_(statuses))
    q = (q or "").strip()
    if q:
        like = f"%{q.lstrip('@')}%"
        opts = [PresentationOrder.topic.ilike(like), PresentationOrder.subject.ilike(like),
                PresentationOrder.id.ilike(q + "%"), User.username.ilike(like), User.full_name.ilike(like)]
        if q.isdigit():
            opts.append(PresentationOrder.user_id == int(q))
        conds.append(or_(*opts))
    return conds


async def orders_page(request: web.Request) -> web.Response:
    f = request.query.get("f", "all")
    q = request.query.get("q", "")[:100]
    page = int(request.query.get("page", "1")) if request.query.get("page", "1").isdigit() else 1
    page = max(1, page)
    oid = request.query.get("o", "")
    conds = _order_conditions(f, q)
    base = select(PresentationOrder, User.full_name, User.username).join(
        User, User.telegram_id == PresentationOrder.user_id, isouter=True)
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(PresentationOrder).join(
            User, User.telegram_id == PresentationOrder.user_id, isouter=True).where(*conds))).scalar() or 0
        pages = max(1, (total + PAGE - 1) // PAGE)
        page = min(page, pages)
        rows = (await db.execute(base.where(*conds).order_by(PresentationOrder.created_at.desc())
                                 .offset((page - 1) * PAGE).limit(PAGE))).all()
        counts = {}
        for key, _, st in ORDER_FILTERS:
            cq = select(func.count()).select_from(PresentationOrder)
            if st:
                cq = cq.where(PresentationOrder.status.in_(st))
            counts[key] = (await db.execute(cq)).scalar() or 0
        month_rev = (await db.execute(select(func.coalesce(func.sum(func.coalesce(PresentationOrder.paid_amount, PresentationOrder.total_price)), 0))
                                      .where(PresentationOrder.status == "PAID",
                                             PresentationOrder.paid_at >= datetime.utcnow() - timedelta(days=30)))).scalar() or 0
        sel = sel_user = None
        if oid:
            r = (await db.execute(base.where(PresentationOrder.id == oid))).first()
            if r:
                sel, fn, un = r
                sel_user = fn or (f"@{un}" if un else str(sel.user_id))
    out = []
    for o, fn, un in rows:
        o.user_name = fn or (f"@{un}" if un else str(o.user_id))
        out.append(o)
    if sel is None and out and not oid:
        sel = out[0]
        sel_user = sel.user_name
    sel_slides = []
    if sel is not None:
        d = os.path.dirname(sel.pdf_path or sel.pptx_path or "") or os.path.join(ROOT, "storage", sel.id)
        sel_slides = [n for n in (1, 2, 3) if os.path.exists(os.path.join(d, f"slide_{n:02d}.png"))]
    qs = urlencode({k: v for k, v in (("f", f), ("q", q)) if v})
    cards = [
        {"label": "Jami buyurtma", "value": money(counts["all"]), "tint": "#EEF0FF", "color": "#6E7BFF", "icon": "M6 2h9l5 5v15H6zM14 2v6h6"},
        {"label": "To‘langan", "value": money(counts["paid"]), "tint": "#E7F8F1", "color": "#10B981", "icon": "M20 6 9 17l-5-5"},
        {"label": "To‘lov kutilmoqda", "value": money(counts["wait"]), "tint": "#FEF6E4", "color": "#F59E0B", "icon": "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z"},
        {"label": "Daromad (30 kun)", "value": money(month_rev) + " so‘m", "tint": "#F3EEFF", "color": "#8B5CF6", "icon": "M2 7h20v12H2zM2 11h20"},
    ]
    pay = "—"
    if sel is not None:
        if sel.status == "PAID":
            pay = f"{sel.paid_by or '—'}" + (f" · {sel.payment_provider}" if sel.payment_provider else "")
        elif sel.bill_id:
            pay = "TezCheck hisob chiqarilgan, kutilmoqda"
        else:
            pay = "Hali to‘lash bosilmagan"
    return await render(request, "orders.html", "orders", rows=out, total=total, page=page, pages=pages,
                        shown_from=(page - 1) * PAGE + (1 if out else 0), shown_to=(page - 1) * PAGE + len(out),
                        filters=[(k, label, money(counts[k])) for k, label, _ in ORDER_FILTERS], f=f, q=q,
                        qs=qs, base_qs=(qs + ("&" if qs else "") + f"page={page}"), cards=cards, sel=sel,
                        sel_user=sel_user, sel_slides=sel_slides,
                        sel_colors=template_colors(sel.template_id if sel else ""),
                        sel_template=template_name(sel.template_id) if sel else "", sel_payment=pay)


async def orders_csv(request: web.Request) -> web.Response:
    conds = _order_conditions(request.query.get("f", "all"), request.query.get("q", "")[:100])
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(PresentationOrder, User.full_name, User.username)
                                 .join(User, User.telegram_id == PresentationOrder.user_id, isouter=True)
                                 .where(*conds).order_by(PresentationOrder.created_at.desc()).limit(50000))).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ID", "Sana", "Telegram ID", "Username", "Ism", "Mavzu", "Fan", "Slayd", "Narx", "Holat",
                "To'langan sana", "To'lagan summa", "Komissiya", "Kim belgiladi", "Usul"])
    for o, fn, un in rows:
        def safe(v):
            v = "" if v is None else str(v)
            return "'" + v if v[:1] in ("=", "+", "-", "@") else v  # no formulas in Excel
        w.writerow([o.id, dt(o.created_at), o.user_id, safe(un), safe(fn), safe(o.topic), safe(o.subject), o.slide_count,
                    o.total_price, STATUS.get(o.status, (o.status,))[0], dt(o.paid_at) if o.paid_at else "",
                    o.paid_amount or "", o.fee_amount or "", o.paid_by or "", o.payment_provider or ""])
    await audit(request, "export", f"{len(rows)} ta buyurtma CSV")
    return web.Response(body=("﻿" + buf.getvalue()).encode("utf-8"), content_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="buyurtmalar_{stats.local_now():%Y%m%d}.csv"',
                                 "Cache-Control": "no-store"})


async def _order(oid: str) -> Optional[PresentationOrder]:
    async with AsyncSessionLocal() as db:
        return await db.get(PresentationOrder, oid)


async def order_file(request: web.Request) -> web.StreamResponse:
    from services.payment.orders import order_files
    from bot.delivery import file_name
    o = await _order(request.match_info["oid"])
    kind = request.match_info["kind"]
    if not o or kind not in ("pdf", "pptx"):
        raise web.HTTPNotFound()
    pdf, pptx = await order_files(o)
    path = pdf if kind == "pdf" else pptx
    if not path:
        raise redirect(f"/admin/orders?o={o.id}", err="Fayl topilmadi va qayta yasab bo‘lmadi (deck saqlanmagan).")
    await audit(request, "download", f"{kind} · {o.id}")
    return web.FileResponse(path, headers={"Content-Disposition": f'attachment; filename="{file_name(o.topic, kind)}"',
                                           "Cache-Control": "no-store"})


async def order_slide(request: web.Request) -> web.StreamResponse:
    o = await _order(request.match_info["oid"])
    n = request.match_info["n"]
    if not o or not n.isdigit():
        raise web.HTTPNotFound()
    d = os.path.dirname(o.pdf_path or o.pptx_path or "") or os.path.join(ROOT, "storage", o.id)
    p = os.path.join(d, f"slide_{int(n):02d}.png")
    if not os.path.exists(p):
        raise web.HTTPNotFound()
    return web.FileResponse(p, headers={"Cache-Control": "private, max-age=3600"})


async def order_action(request: web.Request) -> web.Response:
    from services.payment import orders as pay
    from bot.delivery import deliver_order
    oid, action = request.match_info["oid"], request.match_info["action"]
    o = await _order(oid)
    back = f"/admin/orders?o={oid}"
    if not o:
        raise redirect("/admin/orders", err="Buyurtma topilmadi")
    bot = _bot(request)
    if action == "mark-paid":
        if await pay.mark_paid(oid, by="ADMIN", amount=o.total_price):
            await audit(request, "mark_paid", f"{oid} · {o.total_price} so‘m")
            sent = await deliver_order(bot, oid)
            raise redirect(back, ok="To‘langan deb belgilandi" + (" va fayllar yuborildi." if sent else ". Fayllarni yuborib bo‘lmadi."))
        raise redirect(back, err="Buyurtma allaqachon to‘langan.")
    if action == "resend":
        sent = await deliver_order(bot, oid, force=True)
        await audit(request, "resend", oid)
        raise redirect(back, ok="Fayllar qayta yuborildi.") if sent else redirect(back, err="Yuborib bo‘lmadi (mijoz botni bloklagan bo‘lishi mumkin).")
    if action == "check":
        result, _ = await pay.check_bill(oid)
        if result == "paid":
            await deliver_order(bot, oid)
        await audit(request, "check", f"{oid} · {result}")
        raise redirect(back, ok={"paid": "To‘lov topildi — fayllar yuborildi.", "already": "Buyurtma allaqachon to‘langan.",
                                 "waiting": "To‘lov hali kelmagan.", "unknown": "Natija noma’lum — TezCheck tekshirmoqda.",
                                 "failed": "To‘lov o‘tmagan."}.get(result, "TezCheck javob bermadi."))
    if action == "cancel":
        if o.status == "PAID":
            raise redirect(back, err="To‘langan buyurtmani bekor qilib bo‘lmaydi (pulni TezCheck kabinetidan qaytaring).")
        note = ""
        if o.bill_id and pay.payment_mode() == "tezcheck":
            try:
                from services.payment.tezcheck import TezCheckClient
                await TezCheckClient().cancel_bill(o.bill_id, "Admin bekor qildi")
            except Exception as e:  # noqa: BLE001
                note = f" (TezCheck: {e})"
        async with AsyncSessionLocal() as db:
            await db.execute(update(PresentationOrder).where(PresentationOrder.id == oid, PresentationOrder.status != "PAID")
                             .values(status="CANCELLED"))
            await db.commit()
        await audit(request, "cancel", oid + note)
        raise redirect(back, ok="Buyurtma bekor qilindi." + note)
    raise web.HTTPNotFound()


# ---------------------------------------------------------------------- users
def _paid_exists():
    return exists().where(PresentationOrder.user_id == User.telegram_id, PresentationOrder.status == "PAID",
                          or_(PresentationOrder.paid_by.is_(None), PresentationOrder.paid_by.notin_(("TRIAL", "BONUS", "TEST"))))


def _order_exists():
    return exists().where(PresentationOrder.user_id == User.telegram_id)


USER_FILTERS = [("all", "Barchasi"), ("paid", "To‘laganlar"), ("unpaid", "To‘lamaganlar"), ("blocked", "Bloklanganlar")]


def _user_conditions(f: str, q: str):
    conds = []
    if f == "paid":
        conds.append(_paid_exists())
    elif f == "unpaid":
        conds += [_order_exists(), ~_paid_exists()]
    elif f == "blocked":
        conds.append(User.is_blocked.is_(True))
    q = (q or "").strip()
    if q:
        like = f"%{q.lstrip('@')}%"
        opts = [User.full_name.ilike(like), User.username.ilike(like)]
        if q.isdigit():
            opts.append(User.telegram_id == int(q))
        conds.append(or_(*opts))
    return conds


async def users_page(request: web.Request) -> web.Response:
    f = request.query.get("f", "all")
    q = request.query.get("q", "")[:100]
    page = int(request.query.get("page", "1")) if request.query.get("page", "1").isdigit() else 1
    uid = request.query.get("u", "")
    conds = _user_conditions(f, q)
    n_orders = select(func.count()).where(PresentationOrder.user_id == User.telegram_id).correlate(User).scalar_subquery()
    n_paid = select(func.count()).where(PresentationOrder.user_id == User.telegram_id,
                                        PresentationOrder.status == "PAID").correlate(User).scalar_subquery()
    ref = User.__table__.alias("ref")
    n_refs = select(func.count()).select_from(ref).where(ref.c.referred_by == User.telegram_id).correlate(User).scalar_subquery()
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(User).where(*conds))).scalar() or 0
        pages = max(1, (total + PAGE - 1) // PAGE)
        page = max(1, min(page, pages))
        rows = (await db.execute(select(User, n_orders, n_paid, n_refs).where(*conds)
                                 .order_by(User.created_at.desc()).offset((page - 1) * PAGE).limit(PAGE))).all()
        counts = {k: (await db.execute(select(func.count()).select_from(User).where(*_user_conditions(k, "")))).scalar() or 0
                  for k, _ in USER_FILTERS}
        today = datetime.utcnow() - timedelta(days=1)
        active = (await db.execute(select(func.count()).select_from(User).where(User.last_seen_at >= today))).scalar() or 0
        sel = None
        sel_stats = {}
        if uid.isdigit() or (not uid and rows):
            sid = int(uid) if uid.isdigit() else rows[0][0].telegram_id
            sel = await db.get(User, sid)
            if sel:
                sel_stats = {
                    "orders": (await db.execute(select(func.count()).select_from(PresentationOrder).where(PresentationOrder.user_id == sid))).scalar() or 0,
                    "paid": (await db.execute(select(func.count()).select_from(PresentationOrder).where(PresentationOrder.user_id == sid, PresentationOrder.status == "PAID"))).scalar() or 0,
                    "spent": (await db.execute(select(func.coalesce(func.sum(func.coalesce(PresentationOrder.paid_amount, PresentationOrder.total_price)), 0)).where(PresentationOrder.user_id == sid, PresentationOrder.status == "PAID"))).scalar() or 0,
                    "refs": (await db.execute(select(func.count()).select_from(User).where(User.referred_by == sid))).scalar() or 0,
                }
    from types import SimpleNamespace
    out = []
    for u, no, npd, nr in rows:  # ("orders" is a relationship on User: never assign counts to it)
        out.append(SimpleNamespace(telegram_id=u.telegram_id, full_name=u.full_name, username=u.username,
                                   language=u.language, is_blocked=u.is_blocked, bot_blocked=u.bot_blocked,
                                   orders=no, paid=npd, refs=nr))
    allc = max(1, counts["all"])
    cards = [
        {"label": "Jami foydalanuvchilar", "value": money(counts["all"]), "w": 100, "color": "#6E7BFF"},
        {"label": "Oxirgi 24 soatda faol", "value": money(active), "w": round(active / allc * 100), "color": "#10B981"},
        {"label": "Kamida 1 marta to‘lagan", "value": money(counts["paid"]), "w": round(counts["paid"] / allc * 100), "color": "#F59E0B"},
        {"label": "Bloklangan", "value": money(counts["blocked"]), "w": round(counts["blocked"] / allc * 100), "color": "#E5484D"},
    ]
    qs = urlencode({k: v for k, v in (("f", f), ("q", q)) if v})
    return await render(request, "users.html", "users", rows=out, total=total, page=page, pages=pages,
                        shown_from=(page - 1) * PAGE + (1 if out else 0), shown_to=(page - 1) * PAGE + len(out),
                        filters=[(k, label, money(counts[k])) for k, label in USER_FILTERS], f=f, q=q,
                        base_qs=(qs + ("&" if qs else "") + f"page={page}"), cards=cards, sel=sel, sel_stats=sel_stats)


async def user_action(request: web.Request) -> web.Response:
    uid = int(request.match_info["uid"])
    action = request.match_info["action"]
    form = request.get("form") or {}
    back = f"/admin/users?u={uid}"
    async with AsyncSessionLocal() as db:
        u = await db.get(User, uid)
    if not u:
        raise redirect("/admin/users", err="Foydalanuvchi topilmadi")
    if action in ("block", "unblock"):
        if action == "block" and runtime.is_admin(uid):
            raise redirect(back, err="Adminni bloklab bo‘lmaydi.")
        reason = str(form.get("reason", ""))[:200] if action == "block" else None
        async with AsyncSessionLocal() as db:
            await db.execute(update(User).where(User.telegram_id == uid).values(is_blocked=(action == "block"), blocked_reason=reason))
            await db.commit()
        runtime.set_blocked([uid], action == "block")
        await audit(request, action, f"{uid} {reason or ''}".strip())
        raise redirect(back, ok="Bloklandi — bot unga javob bermaydi." if action == "block" else "Blokdan chiqarildi.")
    if action == "balance":
        try:
            amount = int(str(form.get("amount", "0")).strip())
        except ValueError:
            raise redirect(back, err="Summa noto‘g‘ri")
        if not amount or abs(amount) > 10_000_000:
            raise redirect(back, err="Summa noto‘g‘ri")
        async with AsyncSessionLocal() as db:
            await db.execute(update(User).where(User.telegram_id == uid).values(balance=func.coalesce(User.balance, 0) + amount))
            await db.commit()
        await audit(request, "balance", f"{uid} {amount:+d}")
        raise redirect(back, ok=f"Balans {amount:+,} so‘mga o‘zgartirildi.".replace(",", " "))
    if action == "credits":
        try:
            count = int(str(form.get("count", "0")).strip())
        except ValueError:
            raise redirect(back, err="Son noto‘g‘ri")
        if not count or abs(count) > 100:
            raise redirect(back, err="Son -100 dan 100 gacha bo‘lishi kerak")
        from services import credits as _credits
        await _credits.add_bonus(uid, count)
        await audit(request, "credits", f"{uid} {count:+d}")
        if count > 0:
            try:
                await _bot(request).send_message(
                    uid, f"🎁 <b>Sizga sovg‘a!</b>\n\nAdmin sizga <b>{count} ta bepul taqdimot</b> berdi. "
                         "«🎨 Presentation yaratish» tugmasini bosing!", parse_mode="HTML")
            except Exception:  # noqa: BLE001
                pass
        raise redirect(back, ok=f"Bepul taqdimotlar: {count:+d}.")
    if action == "trial_reset":
        async with AsyncSessionLocal() as db:
            await db.execute(update(User).where(User.telegram_id == uid).values(trial_used_at=None))
            await db.commit()
        await audit(request, "trial_reset", str(uid))
        raise redirect(back, ok="Birinchi bepul taqdimot qayta berildi.")
    if action == "message":
        text = str(form.get("text", "")).strip()[:3500]
        if not text:
            raise redirect(back, err="Xabar bo‘sh")
        bot = _bot(request)
        try:
            await bot.send_message(uid, text)
        except Exception as e:  # noqa: BLE001
            raise redirect(back, err=f"Yuborilmadi: {str(e)[:120]}")
        await audit(request, "message", f"{uid}: {text[:200]}")
        raise redirect(back, ok="Xabar yuborildi.")
    raise web.HTTPNotFound()


# ---------------------------------------------------------------------- payments
_tc_cache: Dict[str, Any] = {"at": 0.0, "data": None}


async def tezcheck_summary(force: bool = False) -> Dict[str, Any]:
    from services.payment import tezcheck
    from services.payment.orders import payment_mode
    base = auth.public_base_url()
    info = {"configured": tezcheck.is_configured(), "webhook_url": (base or "https://<domeningiz>") + "/payments/tezcheck/webhook",
            "webhook_secret": bool(settings.TEZCHECK_WEBHOOK_SECRET), "accept_test": settings.TEZCHECK_ACCEPT_TEST,
            "key_hint": (settings.TEZCHECK_API_KEY[:10] + "…") if settings.TEZCHECK_API_KEY else "",
            "ok": False, "desk": "", "error": "", "status": "Ulanmagan", "mode_label": {
                "tezcheck": "TezCheck ulangan", "legacy": "Eski Click/Payme rejimi", "demo": "DEMO rejim — to‘lovsiz!",
                "off": "To‘lov tizimi ulanmagan"}.get(payment_mode(), payment_mode())}
    if not info["configured"]:
        return info
    if not force and _tc_cache["data"] and time.time() - _tc_cache["at"] < 60:
        return {**info, **_tc_cache["data"]}
    extra: Dict[str, Any] = {}
    try:
        me = await tezcheck.TezCheckClient().me()
        desk = me.get("cash_desk") or {}
        extra.update(ok=True, desk=f"{desk.get('name', '')} ({desk.get('id', '')})", status="Ishlayapti")
    except Exception as e:  # noqa: BLE001
        extra.update(ok=False, error=str(e)[:200], status="Xato")
    _tc_cache.update(at=time.time(), data=extra)
    return {**info, **extra}


async def payments_page(request: web.Request) -> web.Response:
    from services.payment import tezcheck
    tc = await tezcheck_summary()
    problems = request.query.get("problems") == "1"
    cursor = request.query.get("cursor", "")[:80]
    remote, next_cursor, tc_stats, balance = [], None, {}, {}
    if tc["configured"]:
        client = tezcheck.TezCheckClient()
        try:
            data = await client.transactions(limit=25, cursor=cursor, state="problems" if problems else None)
            remote = data.get("data") or []
            next_cursor = (data.get("meta") or {}).get("next_cursor")
            tc_stats = await client.stats()
            balance = (await client.balance()).get("data") or {}
        except Exception as e:  # noqa: BLE001
            tc["error"] = str(e)[:200]
    async with AsyncSessionLocal() as db:
        local = (await db.execute(select(PresentationOrder).where(PresentationOrder.status == "PAID")
                                  .order_by(PresentationOrder.paid_at.desc()).limit(25))).scalars().all()

    def st(key):
        d = tc_stats.get(key) or {}
        return d.get("count"), (d.get("total_minor") or 0) // 100, (d.get("net_minor") or 0) // 100
    cards = []
    for key, label in (("today", "Bugun"), ("week", "7 kun"), ("month", "30 kun")):
        c, tot, net = st(key)
        cards.append({"label": f"{label} · TezCheck", "value": f"{money(tot)} so‘m" if c is not None else "—",
                      "note": f"{c} ta to‘lov · sizga {money(net)} so‘m" if c is not None else "", "tint": "#EEF0FF",
                      "color": "#6E7BFF", "icon": "M2 7h20v12H2zM2 11h20M6 15h4"})
    bal = (balance.get("balance") or {})
    pend = bal.get("pending_minor")
    cards.append({"label": "Yo‘ldagi pul", "value": f"{money((pend or 0) // 100)} so‘m" if pend is not None else "—",
                  "note": "Bankingizga tushishi kutilmoqda" if pend else "", "tint": "#E7F8F1", "color": "#10B981",
                  "icon": "M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"})
    return await render(request, "payments.html", "payments", tc=tc, remote=remote, next_cursor=next_cursor,
                        problems=problems, local=local, cards=cards)


# ---------------------------------------------------------------------- broadcast
SEG_STYLE = {
    "all": ("#6E7BFF", "#EEF0FF", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21c0-4 3-6 7-6s7 2 7 6M17 11a3 3 0 1 0 0-6M22 21c0-3-2-5-5-5.5"),
    "unpaid": ("#F59E0B", "#FEF6E4", "M12 8v4l3 2M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z"),
    "paid": ("#10B981", "#E7F8F1", "M20 6 9 17l-5-5"),
    "idle": ("#EC4899", "#FDF2F8", "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"),
    "ru": ("#0EA5E9", "#E0F2FE", "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"),
}


async def broadcast_page(request: web.Request) -> web.Response:
    from services import broadcast as bc
    import math
    counts = await bc.segment_counts()
    segments = [(k, label, counts.get(k, 0), *SEG_STYLE[k]) for k, label in bc.SEGMENTS.items()]
    async with AsyncSessionLocal() as db:
        items = (await db.execute(select(Broadcast).order_by(Broadcast.id.desc()).limit(12))).scalars().all()
    running = set(bc.running())
    C = 2 * math.pi * 21
    history = []
    for b in items:
        done = (b.sent or 0) + (b.failed or 0) + (b.blocked or 0)
        pct = round(done / b.total * 100) if b.total else (100 if b.status == "done" else 0)
        st = {"done": ("Tugadi", "c-paid"), "sending": ("Yuborilmoqda", "c-prev"), "queued": ("Navbatda", "c-wait"),
              "stopped": ("To‘xtatildi", "c-canc"), "failed": ("Xato", "c-ref")}.get(b.status, (b.status, "c-canc"))
        history.append({"id": b.id, "title": (b.text or "").replace("\n", " ")[:60], "status": st[0], "chip": st[1],
                        "pct": pct, "dash": f"{pct / 100 * C:.1f} {C:.1f}", "running": b.id in running,
                        "color": "#10B981" if b.status == "done" else "#6E7BFF",
                        "meta": f"{money(b.sent)} / {money(b.total)} · {money(b.blocked)} bloklagan · {dt(b.created_at)}"})
    bot_username = ""
    bot = _bot(request)
    if bot is not None:
        try:
            bot_username = (await bot.me()).username
        except Exception:  # noqa: BLE001
            pass
    return await render(request, "broadcast.html", "broadcast", segments=segments, history=history,
                        any_running=bool(running), bot_username=bot_username)


async def broadcast_post(request: web.Request) -> web.Response:
    from services import broadcast as bc
    form = request.get("form") or {}
    text = str(form.get("text", "")).strip()
    segment = str(form.get("segment", "all"))
    bt = str(form.get("button_text", "")).strip()[:60]
    bu = str(form.get("button_url", "")).strip()[:250]
    if not text:
        raise redirect("/admin/broadcast", err="Xabar matni bo‘sh.")
    if bu and not bu.startswith(("https://", "http://", "t.me/", "tg://")):
        raise redirect("/admin/broadcast", err="Tugma havolasi https:// yoki t.me/ bilan boshlanishi kerak.")
    if bt and not bu:
        raise redirect("/admin/broadcast", err="Tugma uchun havola kiriting.")
    photo = form.get("photo")
    photo_path = None
    if getattr(photo, "file", None) is not None and getattr(photo, "filename", ""):
        data = photo.file.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise redirect("/admin/broadcast", err="Rasm 10 MB dan katta.")
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            im.verify()
            fmt = (im.format or "").lower()
        except Exception:  # noqa: BLE001
            raise redirect("/admin/broadcast", err="Bu rasm fayli emas.")
        if fmt not in ("jpeg", "png", "webp"):
            raise redirect("/admin/broadcast", err="Faqat JPG, PNG yoki WEBP.")
        d = os.path.join(ROOT, "storage", "broadcast")
        os.makedirs(d, exist_ok=True)
        photo_path = os.path.join(d, f"{uuid.uuid4().hex}.{'jpg' if fmt == 'jpeg' else fmt}")
        with open(photo_path, "wb") as fh:
            fh.write(data)
        if len(text) > 1024:
            raise redirect("/admin/broadcast", err="Rasm bilan yuborilganda matn 1024 belgidan oshmasligi kerak.")
    bot = _bot(request)
    sess = request.get("admin") or {}
    if str(form.get("action")) == "test":
        me_id = int(sess.get("id") or 0) or (settings.admin_id_list[0] if settings.admin_id_list else 0)
        if not me_id:
            raise redirect("/admin/broadcast", err="Sinov uchun Telegram ID topilmadi (ADMIN_IDS ni kiriting).")
        r = await bc.send_one(bot, me_id, text, photo_path, bt or None, bu or None, {})
        raise redirect("/admin/broadcast", ok="Sinov xabari sizga yuborildi — Telegram’da tekshiring.") if r == "ok" else \
            redirect("/admin/broadcast", err="Sinov xabari yuborilmadi: matndagi HTML teglarni tekshiring.")
    bid = await bc.create(text, segment, photo_path, bt, bu, int(sess.get("id") or 0) or None)
    bc.start(bot, bid)
    await audit(request, "broadcast", f"#{bid} · {segment} · {text[:120]}")
    raise redirect("/admin/broadcast", ok="Tarqatish boshlandi. Jarayon shu sahifada ko‘rinadi.")


async def broadcast_stop(request: web.Request) -> web.Response:
    from services import broadcast as bc
    bid = int(request.match_info["bid"])
    bc.stop(bid)
    await audit(request, "broadcast_stop", f"#{bid}")
    raise redirect("/admin/broadcast", ok="To‘xtatilmoqda…")


# ---------------------------------------------------------------------- settings
MODELS = [("gpt-5.6-luna", "Luna", "eng tez"), ("gpt-5.6-terra", "Terra", "muvozanat"), ("gpt-5.6-sol", "Sol", "eng aqlli")]
EFFORTS = [("low", "low — tez"), ("medium", "medium"), ("high", "high — sekin, chuqurroq"), ("default", "model sozlamasi")]
INT_FIELDS = {"price_per_slide": (1, 1_000_000), "min_slides": (3, 60), "max_slides": (3, 60),
              "max_previews_per_day": (0, 1000), "max_parallel_builds": (1, 20), "throttle_burst": (3, 100),
              "throttle_ban_minutes": (1, 1440), "max_unpaid_open": (0, 50), "daily_preview_cap": (0, 100000),
              "free_max_slides": (0, 60), "referral_bonus": (0, 20)}
ORDER_MODES = [("auto", "Avtomatik", "to‘lov ishlamasa yopiq"), ("open", "Ochiq", "har doim"), ("closed", "Yopiq", "hech kimga")]
PREFETCH_MODES = [("paid", "Faqat avval to‘laganlar uchun (tavsiya)"), ("all", "Hamma uchun — eng tez, lekin qimmat"),
                  ("off", "O‘chiq — eng arzon")]
REFERRAL_TRIGGERS = [("paid", "Do‘sti birinchi marta to‘lov qilganda (tavsiya)"),
                     ("first", "Do‘sti birinchi taqdimotini olganda (bepul ham)")]


async def _admin_rows():
    ids = sorted(runtime.admin_ids())
    names = {}
    async with AsyncSessionLocal() as db:
        for u in (await db.execute(select(User).where(User.telegram_id.in_(ids)))).scalars().all():
            names[u.telegram_id] = u.full_name or (f"@{u.username}" if u.username else str(u.telegram_id))
    fixed = set(settings.admin_id_list)
    return [{"id": i, "name": names.get(i, str(i)), "fixed": i in fixed} for i in ids]


async def settings_page(request: web.Request) -> web.Response:
    v = {k: runtime.get(k) for k in runtime.defaults()}
    v["maintenance"] = runtime.get_bool("maintenance")
    v["free_trial"] = runtime.get_bool("free_trial")
    models = list(MODELS)
    if v["ai_fast_model"] and v["ai_fast_model"] not in [m[0] for m in models]:
        models.append((v["ai_fast_model"], v["ai_fast_model"], "hozirgi"))
    from services import guard
    return await render(request, "settings.html", "settings", v=v, models=models, efforts=EFFORTS,
                        order_modes=ORDER_MODES, prefetch_modes=PREFETCH_MODES, referral_triggers=REFERRAL_TRIGGERS, creation_open=guard.creation_open(),
                        admins=await _admin_rows(), tc=await tezcheck_summary(), main_model=settings.OPENAI_MODEL)


async def settings_post(request: web.Request) -> web.Response:
    form = request.get("form") or {}
    values: Dict[str, str] = {}
    for key, (lo, hi) in INT_FIELDS.items():
        try:
            n = int(str(form.get(key, runtime.get(key))).strip())
        except ValueError:
            raise redirect("/admin/settings", err=f"«{key}» butun son bo‘lishi kerak.")
        if not lo <= n <= hi:
            raise redirect("/admin/settings", err=f"«{key}» {lo} dan {hi} gacha bo‘lishi kerak.")
        values[key] = str(n)
    if int(values["min_slides"]) > int(values["max_slides"]):
        raise redirect("/admin/settings", err="Minimum slayd maksimumdan katta bo‘lishi mumkin emas.")
    if int(values["price_per_slide"]) * int(values["min_slides"]) < 1000:
        raise redirect("/admin/settings", err="Eng kichik buyurtma 1 000 so‘mdan kam bo‘lmasligi kerak (TezCheck chegarasi).")
    values["maintenance"] = "1" if form.get("maintenance") else "0"
    values["free_trial"] = "1" if form.get("free_trial") else "0"
    if str(form.get("referral_trigger", "")) in [m[0] for m in REFERRAL_TRIGGERS]:
        values["referral_trigger"] = str(form.get("referral_trigger"))
    values["maintenance_text"] = str(form.get("maintenance_text", "")).strip()[:500] or runtime.MAINTENANCE_TEXT
    model = str(form.get("ai_fast_model", "")).strip()
    if model and (model in [m[0] for m in MODELS] or model == runtime.get("ai_fast_model")):
        values["ai_fast_model"] = model
    if str(form.get("orders_mode", "")) in [m[0] for m in ORDER_MODES]:
        values["orders_mode"] = str(form.get("orders_mode"))
    if str(form.get("prefetch_mode", "")) in [m[0] for m in PREFETCH_MODES]:
        values["prefetch_mode"] = str(form.get("prefetch_mode"))
    effort = str(form.get("ai_effort", "")).strip()
    if effort in [e[0] for e in EFFORTS]:
        values["ai_effort"] = effort
    extra = {int(x) for x in runtime.get("extra_admins").replace(" ", "").split(",") if x.isdigit()}
    for x in form.getall("remove_admin", []) if hasattr(form, "getall") else []:
        if str(x).isdigit():
            extra.discard(int(x))
    add = str(form.get("add_admin", "")).strip()
    if add:
        if not add.isdigit() or not 4 <= len(add) <= 15:
            raise redirect("/admin/settings", err="Admin Telegram ID faqat raqamlardan iborat bo‘lishi kerak.")
        extra.add(int(add))
    values["extra_admins"] = ",".join(str(i) for i in sorted(extra))
    before = {k: runtime.get(k) for k in values}
    await runtime.set_many(values)
    changed = {k: v for k, v in values.items() if before.get(k) != v}
    if changed:
        await audit(request, "settings", ", ".join(f"{k}={v[:40]}" for k, v in changed.items()))
    raise redirect("/admin/settings", ok="Saqlandi." + (" Texnik ishlar rejimi YOQILDI." if values["maintenance"] == "1" else ""))


# ---------------------------------------------------------------------- system
async def system_page(request: web.Request) -> web.Response:
    from services import errorlog, prefetch
    from services.deck.images import enabled_providers
    from services.payment.tezcheck import TezCheckClient, is_configured
    from services import ai_service
    building, waiting, size = _builds()
    banned = 0
    try:
        from bot.middlewares import throttling
        banned = throttling.banned_now()
    except Exception:  # noqa: BLE001
        pass
    jobs = sum(1 for j in prefetch._jobs.values() if not j.task.done())
    cards = [
        {"label": "Yaratilmoqda", "value": f"{building} / {size}", "tint": "#EEF0FF", "color": "#6E7BFF", "icon": "M4 4h16v12H4zM8 20h8M12 16v4"},
        {"label": "Navbatda", "value": str(waiting), "tint": "#FEF6E4", "color": "#F59E0B", "icon": "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z"},
        {"label": "Fonda yozilmoqda", "value": str(jobs), "tint": "#E7F8F1", "color": "#10B981", "icon": "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"},
        {"label": "Spam uchun bloklangan", "value": str(banned), "tint": "#FDECEC", "color": "#E5484D", "icon": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"},
    ]
    tc_ok = await TezCheckClient().health() if is_configured() else None
    try:
        disk = shutil.disk_usage(os.path.join(ROOT, "storage") if os.path.isdir(os.path.join(ROOT, "storage")) else ROOT)
        disk_s = f"{disk.free / 1e9:.1f} GB bo‘sh / {disk.total / 1e9:.1f} GB"
    except OSError:
        disk_s = "—"
    services = [
        ("Ishlash vaqti", _uptime(), None),
        ("Ma’lumotlar bazasi", "PostgreSQL" if IS_POSTGRES else "SQLite (deploy’da o‘chadi!)", IS_POSTGRES),
        ("TezCheck API", "ishlayapti" if tc_ok else ("javob bermayapti" if tc_ok is False else "ulanmagan"), tc_ok),
        ("Vebhuk imzo kaliti", "kiritilgan" if settings.TEZCHECK_WEBHOOK_SECRET else "yo‘q", bool(settings.TEZCHECK_WEBHOOK_SECRET)),
        ("AI", "kalit bor" if ai_service.get_openai_client() else "kalit yo‘q (namuna matn)", bool(ai_service.get_openai_client())),
        ("AI modeli", (runtime.get("ai_fast_model") or settings.OPENAI_MODEL) + (" → asosiy modelga o‘tilgan" if ai_service._fast_failed else ""), not ai_service._fast_failed),
        ("Foto manbalar", ", ".join(enabled_providers()) or "yo‘q (rasmli chizmalar)", bool(enabled_providers())),
        ("Texnik ishlar", "YOQILGAN" if runtime.get_bool("maintenance") else "o‘chiq", not runtime.get_bool("maintenance")),
        ("Disk (storage)", disk_s, None),
        ("Python", platform.python_version(), None),
    ]
    errors = [{"when": (datetime.utcfromtimestamp(e["at"]) + TZ).strftime("%d.%m %H:%M:%S"),
               "where": e["where"], "message": e["message"]} for e in errorlog.recent(50)]
    async with AsyncSessionLocal() as db:
        audit_rows = (await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(50))).scalars().all()
    return await render(request, "system.html", "system", cards=cards, services=services, errors=errors,
                        audit=audit_rows, now=stats.local_now().strftime("%d.%m.%Y %H:%M:%S"))


# ---------------------------------------------------------------------- wiring
def setup_admin(app: web.Application) -> None:
    app.middlewares.append(admin_guard)
    r = app.router
    r.add_get("/admin", dashboard)
    r.add_get("/admin/", dashboard)
    r.add_get("/admin/login", login_page)
    r.add_post("/admin/login", login_post)
    r.add_get("/admin/login/tg", login_tg)
    r.add_post("/admin/logout", logout)
    r.add_get("/admin/orders", orders_page)
    r.add_get("/admin/orders.csv", orders_csv)
    r.add_get("/admin/orders/{oid}/file/{kind}", order_file)
    r.add_get(r"/admin/orders/{oid}/slide/{n}", order_slide)
    r.add_post("/admin/orders/{oid}/{action}", order_action)
    r.add_get("/admin/users", users_page)
    r.add_post(r"/admin/users/{uid:\d+}/{action}", user_action)
    r.add_get("/admin/payments", payments_page)
    r.add_get("/admin/broadcast", broadcast_page)
    r.add_post("/admin/broadcast", broadcast_post)
    r.add_post(r"/admin/broadcast/{bid:\d+}/stop", broadcast_stop)
    r.add_get("/admin/settings", settings_page)
    r.add_post("/admin/settings", settings_post)
    r.add_get("/admin/system", system_page)
    app.on_startup.append(_on_startup)


async def _on_startup(app: web.Application) -> None:
    # a broadcast that was running when the server stopped cannot be resumed reliably: mark it
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(update(Broadcast).where(Broadcast.status.in_(("sending", "queued")))
                             .values(status="stopped", finished_at=datetime.utcnow()))
            await db.commit()
    except Exception:  # noqa: BLE001
        pass
