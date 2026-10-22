"""
TezCheck merchant API (https://tezcheck.uz, API: https://api.tezcheck.uz/api/merchant/v1).

Flow used by the bot:
  1. POST /bills            one bill per order -> payment_url (sent to the customer as a button)
  2. customer pays with Click or Payme on TezCheck's page
  3. TezCheck POSTs a signed webhook (payment.succeeded …) to /payments/tezcheck/webhook;
     POST /bills/{bill} is the "ask" side (the "✅ Tekshirish" button and the reconciliation loop)
  4. paid AND (livemode or test payments allowed) -> the order is PAID and the files are sent.

Amounts in the API are tiyin (1 so'm = 100 tiyin). Every request carries the API key
(Authorization: Bearer) and the cash desk code (X-Cash-Desk-Code); requests can also be signed
with HMAC-SHA256 (TEZCHECK_SIGN_REQUESTS) and bills are created with an Idempotency-Key, so a
retried request never makes a second bill.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.tezcheck.uz/api/merchant/v1"
TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)
SIGNATURE_WINDOW = 300  # seconds, both for our requests and for incoming webhooks


class TezCheckError(Exception):
    def __init__(self, status: int, code: str, message: str = "", retryable: bool = False, request_id: str = ""):
        super().__init__(f"{status} {code}: {message} (request_id={request_id})")
        self.status, self.code, self.message, self.retryable, self.request_id = status, code, message, retryable, request_id


def is_configured() -> bool:
    return bool((settings.TEZCHECK_API_KEY or "").strip() and (settings.TEZCHECK_CASH_DESK_CODE or "").strip())


def to_minor(som: int) -> int:
    return int(round(som)) * 100


def from_minor(minor: Optional[int]) -> Optional[int]:
    return None if minor is None else int(minor) // 100


def sign_request(api_key: str, method: str, path_and_query: str, body: bytes, timestamp: Optional[int] = None) -> Dict[str, str]:
    """X-TezCheck-Timestamp / X-TezCheck-Signature for one request:
    HMAC-SHA256(api_key, "{timestamp}.{METHOD}.{path+query}.{sha256_hex(body)}")."""
    ts = str(int(timestamp if timestamp is not None else time.time()))
    msg = f"{ts}.{method.upper()}.{path_and_query}.{hashlib.sha256(body or b'').hexdigest()}"
    sig = hmac.new(api_key.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {"X-TezCheck-Timestamp": ts, "X-TezCheck-Signature": f"v1={sig}"}


class TezCheckClient:
    def __init__(self, api_key: str = "", cash_desk_code: str = "", base_url: str = "", sign: Optional[bool] = None,
                 session: Optional[aiohttp.ClientSession] = None):
        self.api_key = (api_key or settings.TEZCHECK_API_KEY or "").strip()
        self.cash_desk_code = (cash_desk_code or settings.TEZCHECK_CASH_DESK_CODE or "").strip()
        self.base_url = (base_url or settings.TEZCHECK_API_URL or API_BASE).rstrip("/")
        self.sign = settings.TEZCHECK_SIGN_REQUESTS if sign is None else sign
        self._session = session

    # ------------------------------------------------------------------ transport
    async def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None, *,
                       desk: bool = True, idempotency_key: str = "", auth: bool = True) -> Dict[str, Any]:
        url = self.base_url + path
        body = b"" if payload is None and method == "GET" else json.dumps(payload or {}, ensure_ascii=False).encode()
        headers = {"Accept": "application/json"}
        if method != "GET":
            headers["Content-Type"] = "application/json"
        if auth:
            headers["Authorization"] = f"Bearer {self.api_key}"
            if desk and self.cash_desk_code:
                headers["X-Cash-Desk-Code"] = self.cash_desk_code
            if self.sign:
                headers.update(sign_request(self.api_key, method, urlsplit(url).path, body))
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:128]
        own = self._session is None
        session = self._session or aiohttp.ClientSession(timeout=TIMEOUT)
        try:
            async with session.request(method, url, data=body if method != "GET" else None, headers=headers) as r:
                text = await r.text()
                try:
                    data = json.loads(text) if text else {}
                except ValueError:
                    data = {}
                if r.status >= 400:
                    err = (data or {}).get("error") or {}
                    raise TezCheckError(r.status, err.get("code", f"http.{r.status}"), err.get("message", text[:200]),
                                        bool(err.get("retryable", r.status >= 500 or r.status == 429)),
                                        err.get("request_id") or r.headers.get("X-Request-Id", ""))
                return data
        finally:
            if own:
                await session.close()

    # ------------------------------------------------------------------ endpoints
    async def health(self) -> bool:
        try:
            data = await self._request("GET", "/health", auth=False)
            return (data.get("data") or {}).get("status") == "ok"
        except Exception:  # noqa: BLE001
            return False

    async def me(self) -> Dict[str, Any]:
        return (await self._request("GET", "/me")).get("data") or {}

    async def cash_desks(self) -> List[Dict[str, Any]]:
        return (await self._request("POST", "/cash-desks", {}, desk=False)).get("data") or []

    async def create_bill(self, amount_som: int, title: str, external_reference: str, *, description: str = "",
                          return_url: str = "", idempotency_key: str = "") -> Dict[str, Any]:
        """Returns {"bill": {...}, "payment_url": "..."} (payment_url is given only once: store it)."""
        payload: Dict[str, Any] = {"amount_minor": to_minor(amount_som), "title": title[:191] if len(title) >= 2 else "Buyurtma",
                                   "external_reference": external_reference[:128]}
        if description:
            payload["description"] = description[:2000]
        if return_url:
            payload["return_url"] = return_url[:255]
        providers = [p.strip() for p in (settings.TEZCHECK_PROVIDERS or "").split(",") if p.strip()]
        if providers:
            payload["allowed_provider_codes"] = providers[:10]
        return (await self._request("POST", "/bills", payload,
                                    idempotency_key=idempotency_key or f"order-{external_reference}")).get("data") or {}

    async def get_bill(self, bill_id: str) -> Dict[str, Any]:
        """{"bill": {..., "paid", "livemode", "environment"}, "payment": {...} | null}"""
        return (await self._request("POST", f"/bills/{bill_id}", {})).get("data") or {}

    async def cancel_bill(self, bill_id: str, reason: str = "") -> Dict[str, Any]:
        return (await self._request("POST", f"/bills/{bill_id}/cancel", {"reason": reason[:191]} if reason else {},
                                    idempotency_key=f"cancel-{bill_id}")).get("data") or {}

    async def reissue_bill(self, bill_id: str, attempt: int = 1) -> Dict[str, Any]:
        return (await self._request("POST", f"/bills/{bill_id}/reissue", {},
                                    idempotency_key=f"reissue-{bill_id}-{attempt}")).get("data") or {}

    async def transactions(self, limit: int = 25, cursor: str = "", state: Any = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"limit": max(1, min(200, int(limit)))}
        if cursor:
            payload["cursor"] = cursor
        if state:
            payload["state"] = state
        return await self._request("POST", "/transactions", payload)

    async def stats(self) -> Dict[str, Any]:
        return (await self._request("POST", "/stats", {})).get("data") or {}

    async def balance(self) -> Dict[str, Any]:
        return await self._request("POST", "/balance", {})

    async def payment_methods(self) -> List[Dict[str, Any]]:
        return (await self._request("POST", "/payment-methods", {})).get("data") or []


# ---------------------------------------------------------------------- results
@dataclass
class BillStatus:
    paid: bool
    real_money: bool          # livemode / environment == "live"
    state: str                # bill state
    payment_state: str        # payment state ("succeeded", "processing", "failed", …) or ""
    amount: Optional[int]     # so'm paid
    fee: Optional[int]
    provider: str
    unknown: bool             # outcome not known yet: never cancel, never charge again
    problem: str

    @property
    def accepted(self) -> bool:
        """Paid with real money (or a test payment while TEZCHECK_ACCEPT_TEST is on)."""
        return self.paid and (self.real_money or settings.TEZCHECK_ACCEPT_TEST)


def parse_bill(data: Dict[str, Any]) -> BillStatus:
    bill = data.get("bill") or {}
    pay = data.get("payment") or {}
    problem = pay.get("problem") or {}
    env = bill.get("environment") or pay.get("environment")
    return BillStatus(
        paid=bool(bill.get("paid")),
        real_money=bool(bill.get("livemode") or pay.get("livemode")) and env != "test",
        state=str(bill.get("state") or ""),
        payment_state=str(pay.get("state") or ""),
        amount=from_minor(pay.get("amount_minor") if pay else None),
        fee=from_minor(pay.get("fee_minor") if pay else None),
        provider=str(pay.get("provider_code") or ""),
        unknown=bool(problem.get("unknown_reason")) if problem else False,
        problem=str(problem.get("category") or problem.get("unknown_reason") or ""),
    )


# ---------------------------------------------------------------------- webhooks
def verify_webhook(raw_body: bytes, timestamp: str, delivery_id: str, signature_header: str,
                   secret: str = "", now: Optional[float] = None) -> bool:
    """X-Checkout-Signature check: HMAC-SHA256(secret, "{timestamp}.{delivery_id}.{raw_body}").
    The header may carry several "v1=…" values (during a secret rotation): any one may match.
    Requests older/newer than 5 minutes are rejected (a captured request cannot be replayed)."""
    secret = secret or settings.TEZCHECK_WEBHOOK_SECRET or ""
    if not secret or not timestamp or not signature_header:
        return False
    try:
        if abs((now if now is not None else time.time()) - int(timestamp)) > SIGNATURE_WINDOW:
            return False
    except ValueError:
        return False
    expected = "v1=" + hmac.new(secret.encode(), f"{timestamp}.{delivery_id}.".encode() + raw_body,
                                hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, c.strip()) for c in signature_header.split(",") if c.strip().startswith("v1="))
