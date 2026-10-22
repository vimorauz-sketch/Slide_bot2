"""
Dashboard sign-in.

  * One-time link: /admin in the bot -> https://<domain>/admin/login/tg?t=<token> (10 minutes, once).
    Only the token's SHA-256 is stored, so a database leak does not leak working links.
  * Login + password (ADMIN_LOGIN / ADMIN_PASSWORD), 5 wrong tries from one address -> 15 minutes locked.

A session is a signed cookie (HMAC-SHA256 with ADMIN_SECRET, or a key derived from BOT_TOKEN):
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

_fails: Dict[str, Tuple[int, float]] = {}


def _secret() -> bytes:
    if (settings.ADMIN_SECRET or "").strip():
        return settings.ADMIN_SECRET.strip().encode()
    return hashlib.sha256(("slidelab-admin:" + (settings.BOT_TOKEN or "")).encode()).digest()


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
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote or "?")


# ---------------------------------------------------------------------- password
def password_enabled() -> bool:
    return bool((settings.ADMIN_PASSWORD or "").strip())


def locked_for(ip: str) -> int:
    n, until = _fails.get(ip, (0, 0.0))
    return max(0, int(until - time.time())) if n >= MAX_FAILS else 0


def check_password(ip: str, login: str, password: str) -> bool:
    if not password_enabled() or locked_for(ip):
        return False
    ok = hmac.compare_digest((login or "").strip().encode(), (settings.ADMIN_LOGIN or "admin").strip().encode()) & \
        hmac.compare_digest((password or "").encode(), settings.ADMIN_PASSWORD.strip().encode())
    if ok:
        _fails.pop(ip, None)
        return True
    n, _ = _fails.get(ip, (0, 0.0))
    n += 1
    _fails[ip] = (n, time.time() + LOCK_SECONDS if n >= MAX_FAILS else 0.0)
    if len(_fails) > 10000:
        _fails.clear()
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
