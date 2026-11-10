"""
Dashboard sign-in.

  * One-time link: /admin in the bot -> https://<domain>/admin/login/tg?t=<token> (10 minutes, once).
    Only the token's SHA-256 is stored, so a database leak does not leak working links.
  * Login + password (ADMIN_LOGIN / ADMIN_PASSWORD), 5 wrong tries from one address -> 15 minutes locked;
    more than GLOBAL_MAX_FAILS wrong tries from all addresses together in 15 minutes -> password sign-in
    pauses for 15 minutes (someone is guessing from many addresses; the Telegram link still works).

A session is a signed cookie (HMAC-SHA256 with ADMIN_SECRET; without it, with a random key the bot makes
once and keeps in the database — never with BOT_TOKEN, so a leaked bot token does not open the dashboard):
HttpOnly, SameSite=Lax, Secure on HTTPS, 12 hours. Every form carries a CSRF token derived from
the session, and every POST is checked.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from aiohttp import web

from config import settings

COOKIE = "sl_admin"
SESSION_HOURS = 12
TOKEN_MINUTES = 10
MAX_FAILS = 5
LOCK_SECONDS = 15 * 60

GLOBAL_MAX_FAILS = 30
MAX_TRACKED = 10000

_fails: Dict[str, Tuple[int, float]] = {}
_recent_fails: list = []          # times of wrong tries from every address (last LOCK_SECONDS)
_global_lock_until = 0.0


SECRET_KEY = "admin_session_secret"
_generated_secret: bytes = b""


async def init_secret() -> None:
    """Called at start: loads (or makes once) the random session key used when ADMIN_SECRET is empty."""
    global _generated_secret
    if (settings.ADMIN_SECRET or "").strip():
        return
    from database.connection import AsyncSessionLocal
    from database import repository
    async with AsyncSessionLocal() as session:
        value = await repository.get_setting(session, SECRET_KEY, "")
        if len(value) < 32:
            value = secrets.token_hex(32)
            await repository.set_setting(session, SECRET_KEY, value)
    _generated_secret = value.encode()


def _secret() -> bytes:
    if (settings.ADMIN_SECRET or "").strip():
        return settings.ADMIN_SECRET.strip().encode()
    if _generated_secret:
        return _generated_secret
    # before init_secret() ran (tests, tools): a per-process random key — sessions simply do not survive it
    return _process_secret


_process_secret = secrets.token_bytes(32)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_session(label: str, tg_id: int = 0, hours: int = SESSION_HOURS) -> str:
    payload = _b64(json.dumps({"u": label[:64], "id": int(tg_id or 0), "exp": int(time.time()) + hours * 3600},
                              separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_session(value: str) -> Optional[Dict]:
    try:
        payload, sig = (value or "").split(".", 1)
        good = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(good, sig):
            return None
        data = json.loads(_unb64(payload))
        if int(data.get("exp", 0)) < time.time():
            return None
        if data.get("id"):
            from services import runtime
            if not runtime.is_admin(data["id"]):  # removed from the admin list: the session ends
                return None
        return data
    except Exception:  # noqa: BLE001
        return None


def current(request: web.Request) -> Optional[Dict]:
    return read_session(request.cookies.get(COOKIE, ""))


def csrf_token(request: web.Request) -> str:
    raw = request.cookies.get(COOKIE, "")
    return hmac.new(_secret(), ("csrf:" + raw).encode(), hashlib.sha256).hexdigest()[:32]


def check_csrf(request: web.Request, form) -> bool:
    sent = str(form.get("csrf", "")) or request.headers.get("X-CSRF-Token", "")
    return bool(sent) and hmac.compare_digest(sent, csrf_token(request))


def set_cookie(request: web.Request, response: web.StreamResponse, value: str) -> None:
    secure = request.secure or request.headers.get("X-Forwarded-Proto", "") == "https"
    response.set_cookie(COOKIE, value, max_age=SESSION_HOURS * 3600, httponly=True, secure=secure,
                        samesite="Lax", path="/admin")


def client_ip(request: web.Request) -> str:
    """The visitor's address as the hosting proxy saw it. Never the first X-Forwarded-For value: the
    visitor writes that one himself (see services/netutil.py)."""
    from services.netutil import client_ip as _ip
    return _ip(request)


# ---------------------------------------------------------------------- password
def password_enabled() -> bool:
    return bool((settings.ADMIN_PASSWORD or "").strip())


def locked_for(ip: str) -> int:
    now = time.time()
    n, until = _fails.get(ip, (0, 0.0))
    mine = max(0, int(until - now)) if n >= MAX_FAILS else 0
    return max(mine, max(0, int(_global_lock_until - now)))


def _note_failure(ip: str) -> None:
    global _global_lock_until
    now = time.time()
    n, _ = _fails.get(ip, (0, 0.0))
    n += 1
    _fails[ip] = (n, now + LOCK_SECONDS if n >= MAX_FAILS else 0.0)
    _recent_fails.append(now)
    while _recent_fails and now - _recent_fails[0] > LOCK_SECONDS:
        _recent_fails.pop(0)
    if len(_recent_fails) > GLOBAL_MAX_FAILS:
        _global_lock_until = now + LOCK_SECONDS
        _recent_fails.clear()
    if len(_fails) > MAX_TRACKED:
        # forget only what no longer matters: addresses that are not locked right now. Locked
        # addresses stay locked even when someone floods the table with new ones.
        for key, (cnt, until) in list(_fails.items()):
            if cnt < MAX_FAILS or until <= now:
                _fails.pop(key, None)


def check_password(ip: str, login: str, password: str) -> bool:
    if not password_enabled() or locked_for(ip):
        return False
    ok = hmac.compare_digest((login or "").strip().encode(), (settings.ADMIN_LOGIN or "admin").strip().encode()) & \
        hmac.compare_digest((password or "").encode(), settings.ADMIN_PASSWORD.strip().encode())
    if ok:
        _fails.pop(ip, None)
        return True
    _note_failure(ip)
    return False


# ---------------------------------------------------------------------- one-time links
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_login_token(admin_id: int) -> str:
    from database.connection import AsyncSessionLocal
    from database.models import AdminToken
    token = secrets.token_urlsafe(32)
    async with AsyncSessionLocal() as session:
        session.add(AdminToken(token_hash=_hash(token), admin_id=int(admin_id),
                               expires_at=datetime.utcnow() + timedelta(minutes=TOKEN_MINUTES)))
        await session.commit()
    return token


async def use_login_token(token: str) -> Optional[int]:
    """The admin's Telegram id if the link is valid (and burns it), else None."""
    from sqlalchemy import update
    from database.connection import AsyncSessionLocal
    from database.models import AdminToken
    if not token or len(token) > 100:
        return None
    h = _hash(token)
    async with AsyncSessionLocal() as session:
        row = await session.get(AdminToken, h)
        if not row or row.used_at is not None or row.expires_at < datetime.utcnow():
            return None
        res = await session.execute(update(AdminToken).where(AdminToken.token_hash == h, AdminToken.used_at.is_(None))
                                    .values(used_at=datetime.utcnow()))
        await session.commit()
        if not res.rowcount:
            return None
        admin_id = int(row.admin_id)
    from services import runtime
    return admin_id if runtime.is_admin(admin_id) else None


def public_base_url() -> str:
    """https://<domain> of this server (from WEBAPP_URL or the hosting platform)."""
    url = (settings.WEBAPP_URL or "").strip()
    if url.startswith("https://"):
        return url.split("/webapp")[0].rstrip("/")
    dom = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RENDER_EXTERNAL_HOSTNAME") or ""
    return f"https://{dom.strip('/')}" if dom else ""
