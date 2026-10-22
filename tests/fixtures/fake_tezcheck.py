"""A small in-process imitation of the TezCheck merchant API (only what the bot uses),
following the documented request/response shapes."""
import hashlib
import hmac
import json
import time

from aiohttp import web

API_KEY = "aps_TESTKEY0000000000"
DESK = "cdk_TESTDESK000000000000000090001"
WEBHOOK_SECRET = "wbs_TESTSECRET"


class FakeTezCheck:
    def __init__(self):
        self.bills = {}
        self.requests = []
        self.idem = {}
        self.require_signature = False

    def app(self) -> web.Application:
        app = web.Application()
        p = "/api/merchant/v1"
        app.router.add_get(p + "/health", self.health)
        app.router.add_get(p + "/me", self.me)
        app.router.add_post(p + "/bills", self.create_bill)
        app.router.add_post(p + "/bills/{bill}", self.get_bill)
        app.router.add_post(p + "/bills/{bill}/cancel", self.cancel)
        app.router.add_post(p + "/transactions", self.transactions)
        app.router.add_post(p + "/stats", self.stats)
        app.router.add_post(p + "/balance", self.balance)
        return app

    def _err(self, status, code):
        return web.json_response({"error": {"code": code, "message": code, "status": status,
                                            "request_id": "req_test", "retryable": status >= 500}}, status=status)

    async def _auth(self, request, desk=True):
        body = await request.read()
        self.requests.append({"path": request.path, "headers": dict(request.headers), "body": body})
        if request.headers.get("Authorization") != f"Bearer {API_KEY}":
            return self._err(401, "auth.unauthenticated")
        if desk and request.headers.get("X-Cash-Desk-Code") != DESK:
            return self._err(404, "resource.not_found")
        if self.require_signature or request.headers.get("X-TezCheck-Signature"):
            ts = request.headers.get("X-TezCheck-Timestamp", "")
            msg = f"{ts}.{request.method}.{request.path}.{hashlib.sha256(body).hexdigest()}"
            good = "v1=" + hmac.new(API_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
            if request.headers.get("X-TezCheck-Signature") != good:
                return self._err(401, "request.signature_invalid")
        return None

    async def health(self, request):
        return web.json_response({"data": {"status": "ok"}})

    async def me(self, request):
        if (e := await self._auth(request)):
            return e
        return web.json_response({"data": {"organization": {"id": "90010", "display_name": "Test"},
                                           "cash_desk": {"code": DESK, "id": "90001", "name": "Veb kassa", "currency": "UZS"},
                                           "api_client": {"name": "Backend", "token_hint": API_KEY[:12],
                                                          "signed_requests_required": False, "request_signed": False}}})

    async def create_bill(self, request):
        if (e := await self._auth(request)):
            return e
        body = json.loads(self.requests[-1]["body"])
        key = request.headers.get("Idempotency-Key")
        if key and key in self.idem:
            return web.json_response(self.idem[key], status=201, headers={"Idempotent-Replayed": "true"})
        if body.get("amount_minor", 0) < 100000:
            return self._err(422, "payment_link.amount_out_of_range")
        bid = f"link_TEST{len(self.bills) + 1:04d}"
        self.bills[bid] = {"id": bid, "reference": f"BILL-{bid}", "amount_minor": body["amount_minor"], "currency": "UZS",
                           "title": body["title"], "external_reference": body.get("external_reference"),
                           "state": "active", "available_until": "2099-01-01T00:00:00+00:00",
                           "paid": False, "livemode": False, "environment": None, "payment": None}
        out = {"data": {"bill": {k: v for k, v in self.bills[bid].items() if k not in ("paid", "payment", "livemode", "environment")},
                        "payment_url": f"https://pay.tezcheck.uz/pay/plk_{bid}"}}
        if key:
            self.idem[key] = out
        return web.json_response(out, status=201)

    def pay(self, bid, environment="live", amount_minor=None, state="succeeded", unknown=False):
        b = self.bills[bid]
        paid = state == "succeeded"
        b.update(paid=paid, livemode=environment == "live", environment=environment,
                 state="exhausted" if paid else "active")
        b["payment"] = {"id": f"pay_{bid}", "reference": f"PAY-{bid}", "state": state,
                        "amount_minor": amount_minor or b["amount_minor"], "fee_minor": 3500 if paid else 0,
                        "net_minor": (amount_minor or b["amount_minor"]) - (3500 if paid else 0), "currency": "UZS",
                        "livemode": environment == "live", "environment": environment, "provider_code": "payme",
                        "problem": {"category": None, "unknown_reason": "provider_timeout"} if unknown else None}

    async def get_bill(self, request):
        if (e := await self._auth(request)):
            return e
        b = self.bills.get(request.match_info["bill"])
        if not b:
            return self._err(404, "resource.not_found")
        bill = {k: v for k, v in b.items() if k != "payment"}
        return web.json_response({"data": {"bill": bill, "payment": b["payment"], "payment_url": None}})

    async def cancel(self, request):
        if (e := await self._auth(request)):
            return e
        b = self.bills.get(request.match_info["bill"])
        if not b:
            return self._err(404, "resource.not_found")
        if b["paid"]:
            return self._err(409, "resource.state_invalid")
        b["state"] = "revoked"
        return web.json_response({"data": {"bill": b, "cancelled": True, "cancelled_at": "2026-10-22T00:00:00+00:00"}})

    async def transactions(self, request):
        if (e := await self._auth(request)):
            return e
        rows = [dict(b["payment"], external_reference=b["external_reference"], created_at="2026-10-22T00:00:00+00:00",
                     succeeded_at="2026-10-22T00:01:00+00:00")
                for b in self.bills.values() if b.get("payment")]
        return web.json_response({"data": rows, "meta": {"limit": 25, "has_more": False, "next_cursor": None}})

    async def stats(self, request):
        if (e := await self._auth(request)):
            return e
        paid = [b for b in self.bills.values() if b["paid"]]
        block = {"count": len(paid), "total_minor": sum(b["amount_minor"] for b in paid), "fees_minor": 3500 * len(paid),
                 "net_minor": sum(b["amount_minor"] for b in paid) - 3500 * len(paid)}
        return web.json_response({"data": {"today": block, "yesterday": block, "week": block, "month": block}})

    async def balance(self, request):
        if (e := await self._auth(request)):
            return e
        return web.json_response({"data": {"currency": "UZS", "balance": {"available_minor": None, "reserved_minor": None,
                                                                          "held_minor": 0, "pending_minor": 2450000}},
                                  "meta": {"funds_flow_model": "direct_to_merchant"}})


def signed_webhook(event: dict, secret: str = WEBHOOK_SECRET, ts: int = None, delivery: str = "whd_TEST1"):
    raw = json.dumps(event, separators=(",", ":")).encode()
    ts = str(ts if ts is not None else int(time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.{delivery}.".encode() + raw, hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Checkout-Event": event.get("type", ""),
               "X-Checkout-Event-Id": event.get("id", ""), "X-Checkout-Delivery": delivery,
               "X-Checkout-Timestamp": ts, "X-Checkout-Signature": f"v1={sig}"}
    return raw, headers


def paid_event(order_id: str, bill_id: str, amount_som: int, environment="live", event_id="oev_TEST1"):
    return {"id": event_id, "type": "payment.succeeded", "schema_version": 1, "mode": "test",
            "data": {"payment_id": f"pay_{bill_id}", "state": "succeeded", "previous_state": "processing",
                     "amount_minor": amount_som * 100, "currency": "UZS", "external_reference": order_id,
                     "bill_id": bill_id, "fee_minor": 3500, "net_minor": amount_som * 100 - 3500,
                     "provider_code": "click", "environment": environment, "problem": None}}
