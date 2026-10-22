"""Admin dashboard: sign-in (one-time bot link, password + lockout), sessions, CSRF, every page
renders with real data, and the actions (mark paid, block, settings, broadcast) do what they say."""
import re
from datetime import datetime, timedelta

import pytest
from aiohttp.test_utils import TestClient, TestServer

from bot.admin_web import auth
from bot.webhook_app import create_webhook_app
from database import repository
from database.models import PresentationOrder, User
from services import runtime
from tests.fixtures.telegram_fakes import FakeBot

ADMIN = 8371155553


class Bot(FakeBot):
    async def me(self):
        return type("Me", (), {"username": "SlideLabBot"})()

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": caption, "photo": photo, **kwargs})
        return type("Msg", (), {"photo": [type("P", (), {"file_id": "file123"})()]})()


@pytest.fixture
async def env(patched_handlers_db, monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.ADMIN_IDS", str(ADMIN))
    monkeypatch.setattr("config.settings.ADMIN_PASSWORD", "s3cret-pass")
    monkeypatch.setattr("config.settings.ADMIN_LOGIN", "admin")
    monkeypatch.setattr("config.settings.TEZCHECK_API_KEY", "")
    auth._fails.clear()
    db = patched_handlers_db
    now = datetime.utcnow()
    async with db() as s:
        for uid, name in ((ADMIN, "Doniyorbek"), (111, "Ali Valiyev"), (222, "Nodira K."), (333, "Spam Bot")):
            await repository.get_or_create_user(s, uid, name, name.split()[0].lower())
        for i, (uid, st) in enumerate([(111, "PAID"), (111, "PREVIEW_READY"), (222, "WAITING_PAYMENT"), (222, "PAID")]):
            o = PresentationOrder(user_id=uid, topic=f"Mavzu {i} <script>alert(1)</script>", subject="Biologiya",
                                  slide_count=10, template_id="05_nature_organic", total_price=3500, status=st,
                                  created_at=now - timedelta(hours=i),
                                  paid_at=now - timedelta(hours=i) if st == "PAID" else None,
                                  paid_amount=3500 if st == "PAID" else None, paid_by="TEZCHECK" if st == "PAID" else None,
                                  pdf_path=str(tmp_path / "presentation.pdf"))
            s.add(o)
        await s.commit()
    bot = Bot()
    client = TestClient(TestServer(create_webhook_app(bot)))
    await client.start_server()
    yield client, bot, db
    await client.close()


async def _login(client):
    token = await auth.create_login_token(ADMIN)
    r = await client.get(f"/admin/login/tg?t={token}", allow_redirects=False)
    assert r.status == 302 and r.headers["Location"] == "/admin"
    return token


async def _csrf(client, path="/admin/settings"):
    html = await (await client.get(path)).text()
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


async def test_pages_need_a_session(env):
    client, *_ = env
    for path in ("/admin", "/admin/orders", "/admin/users", "/admin/payments", "/admin/broadcast", "/admin/settings",
                 "/admin/system", "/admin/orders.csv"):
        r = await client.get(path, allow_redirects=False)
        assert r.status == 302 and r.headers["Location"] == "/admin/login", path
    assert (await client.post("/admin/settings", data={}, allow_redirects=False)).status == 403


async def test_one_time_link_works_once(env):
    client, *_ = env
    token = await _login(client)
    r = await client.get("/admin")
    assert r.status == 200 and "Bosh sahifa" in await r.text()
    client.session.cookie_jar.clear()
    r = await client.get(f"/admin/login/tg?t={token}", allow_redirects=False)
    assert "err=" in r.headers["Location"]  # burnt


async def test_link_for_a_non_admin_is_refused(env):
    client, *_ = env
    token = await auth.create_login_token(111)
    r = await client.get(f"/admin/login/tg?t={token}", allow_redirects=False)
    assert "err=" in r.headers["Location"]


async def test_password_login_and_lockout(env):
    client, *_ = env
    for _ in range(5):
        r = await client.post("/admin/login", data={"login": "admin", "password": "wrong"})
        assert "noto‘g‘ri" in await r.text()
    r = await client.post("/admin/login", data={"login": "admin", "password": "s3cret-pass"}, allow_redirects=False)
    assert r.status == 200 and "Juda ko‘p" in await r.text()   # locked even with the right password
    auth._fails.clear()
    r = await client.post("/admin/login", data={"login": "admin", "password": "s3cret-pass"}, allow_redirects=False)
    assert r.status == 302


async def test_forged_cookie_is_rejected(env):
    client, *_ = env
    payload = auth.make_session("admin").split(".")[0]
    client.session.cookie_jar.update_cookies({auth.COOKIE: payload + ".AAAA"})
    r = await client.get("/admin", allow_redirects=False)
    assert r.status == 302


async def test_every_page_renders_and_escapes_user_text(env):
    client, *_ = env
    await _login(client)
    for path in ("/admin", "/admin?p=1", "/admin?p=30", "/admin/orders", "/admin/orders?f=paid", "/admin/orders?q=Ali",
                 "/admin/users", "/admin/users?f=unpaid", "/admin/users?q=111", "/admin/payments",
                 "/admin/broadcast", "/admin/settings", "/admin/system"):
        r = await client.get(path)
        html = await r.text()
        assert r.status == 200, path
        assert "<script>alert(1)</script>" not in html, path
    html = await (await client.get("/admin")).text()
    assert "7 000" in html  # two paid orders of 3 500 so'm in the revenue


async def test_post_without_csrf_is_refused(env):
    client, *_ = env
    await _login(client)
    r = await client.post("/admin/settings", data={"price_per_slide": "1"})
    assert r.status == 403


async def test_mark_paid_delivers_and_is_audited(env, monkeypatch, tmp_path):
    client, bot, db = env
    await _login(client)
    async with db() as s:
        o = (await s.execute(__import__("sqlalchemy").select(PresentationOrder).where(
            PresentationOrder.status == "PREVIEW_READY"))).scalars().first()
    (tmp_path / "presentation.pdf").write_bytes(b"%PDF")
    (tmp_path / "presentation.pptx").write_bytes(b"PK")
    csrf = await _csrf(client, f"/admin/orders?o={o.id}")
    r = await client.post(f"/admin/orders/{o.id}/mark-paid", data={"csrf": csrf}, allow_redirects=False)
    assert r.status == 302 and "ok=" in r.headers["Location"]
    async with db() as s:
        o2 = await s.get(PresentationOrder, o.id)
    assert o2.status == "PAID" and o2.paid_by == "ADMIN"
    assert any("document" in m for m in bot.sent_messages)
    html = await (await client.get("/admin/system")).text()
    assert "mark_paid" in html


async def test_block_and_unblock_a_user(env):
    client, _, db = env
    await _login(client)
    csrf = await _csrf(client, "/admin/users?u=333")
    await client.post("/admin/users/333/block", data={"csrf": csrf, "reason": "spam"})
    assert 333 in runtime.blocked_users
    async with db() as s:
        assert (await s.get(User, 333)).is_blocked
    r = await client.post(f"/admin/users/{ADMIN}/block", data={"csrf": csrf}, allow_redirects=False)
    assert "err=" in r.headers["Location"]  # an admin cannot be blocked
    await client.post("/admin/users/333/unblock", data={"csrf": csrf})
    assert 333 not in runtime.blocked_users


async def test_settings_take_effect_at_once(env):
    client, *_ = env
    await _login(client)
    csrf = await _csrf(client)
    form = {"csrf": csrf, "price_per_slide": "400", "min_slides": "5", "max_slides": "25", "max_previews_per_day": "7",
            "max_parallel_builds": "3", "throttle_burst": "10", "throttle_ban_minutes": "10", "maintenance": "1",
            "maintenance_text": "Tez orada qaytamiz", "ai_fast_model": "gpt-5.6-terra", "ai_effort": "medium",
            "add_admin": "123456789"}
    r = await client.post("/admin/settings", data=form, allow_redirects=False)
    assert r.status == 302 and "ok=" in r.headers["Location"]
    assert runtime.get_int("price_per_slide") == 400 and runtime.get_bool("maintenance")
    assert runtime.get("ai_fast_model") == "gpt-5.6-terra" and runtime.is_admin(123456789)
    bad = dict(form, min_slides="30", max_slides="10")
    r = await client.post("/admin/settings", data=bad, allow_redirects=False)
    assert "err=" in r.headers["Location"]


async def test_broadcast_test_send_and_real_send(env):
    import asyncio
    client, bot, _ = env
    await _login(client)
    csrf = await _csrf(client, "/admin/broadcast")
    r = await client.post("/admin/broadcast", data={"csrf": csrf, "text": "<b>Salom!</b>", "segment": "all",
                                                    "action": "test"}, allow_redirects=False)
    assert "ok=" in r.headers["Location"] and bot.sent_messages[-1]["chat_id"] == ADMIN
    bot.sent_messages.clear()
    r = await client.post("/admin/broadcast", data={"csrf": csrf, "text": "Yangilik", "segment": "all",
                                                    "button_text": "Ochish", "button_url": "https://t.me/SlideLabBot",
                                                    "action": "send"}, allow_redirects=False)
    assert "ok=" in r.headers["Location"]
    for _ in range(100):
        if len(bot.sent_messages) >= 4:
            break
        await asyncio.sleep(0.05)
    assert sorted(m["chat_id"] for m in bot.sent_messages) == sorted([ADMIN, 111, 222, 333])
    assert bot.sent_messages[0]["reply_markup"].inline_keyboard[0][0].url == "https://t.me/SlideLabBot"


async def test_csv_export(env):
    client, *_ = env
    await _login(client)
    r = await client.get("/admin/orders.csv?f=paid")
    body = (await r.read()).decode("utf-8-sig")
    assert r.status == 200 and body.count("\n") == 3  # header + 2 paid orders


async def test_gate_blocks_users_and_maintenance(env):
    """The bot side: blocked users are ignored; maintenance answers everyone but admins."""
    import datetime as _dt
    from aiogram.types import Chat, Message, Update
    from aiogram.types import User as TgUser
    from bot.middlewares.gate import GateMiddleware
    gate = GateMiddleware()
    handled = []

    async def handler(event, data):
        handled.append(event)

    def upd(uid):
        return Update(update_id=1, message=Message(message_id=1, date=_dt.datetime.now(), chat=Chat(id=uid, type="private"),
                                                   from_user=TgUser(id=uid, is_bot=False, first_name="x"), text="hi"))
    runtime.set_blocked([333], True)
    await gate(handler, upd(333), {})
    assert handled == []
    runtime._values["maintenance"] = "1"
    await gate(handler, upd(111), {})
    assert handled == []
    await gate(handler, upd(ADMIN), {})
    assert len(handled) == 1
