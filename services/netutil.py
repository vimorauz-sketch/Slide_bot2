"""
The visitor's IP address behind a hosting proxy (Railway, nginx).

The first X-Forwarded-For value is whatever the visitor sent, so it must never decide a lock or a
rate limit: with a new made-up value on every request, "5 wrong passwords -> locked" and the Mini App
rate limit would never trigger. A proxy appends the address it saw to the END of X-Forwarded-For
(Railway's edge and the Caddy server in deploy/ both do), so the value is taken from the end.
X-Real-IP is not used: Caddy passes a visitor's own X-Real-IP through unchanged.
TRUSTED_PROXY_HOPS (default 1) says how many proxies in front of the bot append to X-Forwarded-For;
0 ignores the proxy headers (the bot is reached directly).
"""
from __future__ import annotations

import os


def _hops() -> int:
    try:
        return max(0, int(os.getenv("TRUSTED_PROXY_HOPS", "1")))
    except ValueError:
        return 1


def client_ip(request) -> str:
    hops = _hops()
    if hops:
        chain = [p.strip() for p in (request.headers.get("X-Forwarded-For") or "").split(",") if p.strip()]
        if chain:
            return chain[-hops] if len(chain) >= hops else chain[0]
    return request.remote or "?"
