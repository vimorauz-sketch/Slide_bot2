"""
aiohttp web app exposing the Click and Payme payment webhook endpoints.

Runs alongside the aiogram Telegram polling loop (see main.py) inside the same
asyncio event loop -- this is a second, independent server, not part of Telegram's
own webhook mechanism. In production, put this behind an HTTPS reverse proxy
(nginx + certbot) and register the public HTTPS URLs with Click/Payme:
  https://<your-domain>/payments/click/prepare
  https://<your-domain>/payments/click/complete
  https://<your-domain>/payments/payme

It also serves the template gallery Mini App (webapp/) at /webapp/ and its selection endpoint
/webapp/api/select. Set WEBAPP_URL=https://<your-domain>/webapp/ to enable it in the bot.
"""
import mimetypes
import json
import logging
import os
from aiohttp import web

from services.payment import click_webhook, payme_webhook

logger = logging.getLogger(__name__)


async def _parse_click_params(request: web.Request) -> dict:
    # Click's Shop API posts application/x-www-form-urlencoded data.
    data = await request.post()
    if data:
        return dict(data)
    # Tolerate a JSON body too, in case Click or a test client sends one.
    try:
        return await request.json()
    except Exception:
        return {}


async def click_prepare_handler(request: web.Request) -> web.Response:
    params = await _parse_click_params(request)
    result = await click_webhook.handle_prepare(params)
    return web.json_response(result)


async def click_complete_handler(request: web.Request) -> web.Response:
    params = await _parse_click_params(request)
    result = await click_webhook.handle_complete(params)
    return web.json_response(result)


async def payme_handler(request: web.Request) -> web.Response:
    auth_header = request.headers.get("Authorization")
    if not payme_webhook.verify_auth_header(auth_header):
        return web.json_response(
            {"jsonrpc": "2.0", "id": None, "error": {
                "code": payme_webhook.ERR_ACCESS_DENIED,
                "message": {"ru": "Access denied", "uz": "Ruxsat yo'q", "en": "Access denied"}
            }},
            status=200  # Payme expects HTTP 200 even for RPC-level errors.
        )

    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"jsonrpc": "2.0", "id": None, "error": {
                "code": payme_webhook.ERR_PARSE_ERROR,
                "message": {"ru": "Parse error", "uz": "Xatolik", "en": "Parse error"}
            }}
        )

    result = await payme_webhook.dispatch(body)
    return web.json_response(result)


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


BOT_KEY = web.AppKey("bot", object) if hasattr(web, "AppKey") else "bot"
_background: list = []  # keeps background tasks referenced
DP_KEY = web.AppKey("dp", object) if hasattr(web, "AppKey") else "dp"
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")


# Gallery images can make the server render slides: limit how fast one address may ask for them
# (a browser scrolling the gallery stays far below this, a script hammering the server does not).
_ip_limiter = None


def _check_rate(request: web.Request) -> None:
    global _ip_limiter
    if _ip_limiter is None:
        from bot.middlewares.throttling import ThrottlingMiddleware
        _ip_limiter = ThrottlingMiddleware(rate=5, burst=150, ban_seconds=120)
    ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote or "?")
    if _ip_limiter.allow(hash(ip)) is not None:
        raise web.HTTPTooManyRequests(text="Too many requests")


mimetypes.add_type("image/webp", ".webp")  # also for the static Mini App thumbnails
mimetypes.add_type("font/ttf", ".ttf")     # the Mini App's font list loads the library fonts

# Explicit type for the .webp previews: Python 3.10's mimetypes table has no .webp, so aiohttp
# would send them as application/octet-stream (some Telegram clients then show no picture).
WEBP_HEADERS = {"Cache-Control": "public, max-age=604800", "Content-Type": "image/webp"}


async def webapp_index_handler(request: web.Request) -> web.StreamResponse:
    if not request.path.endswith("/"):
        raise web.HTTPFound(request.path + "/")
    from services.gallery import cache_token

    with open(os.path.join(WEBAPP_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read().replace("__GALLERY_V__", cache_token())
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def webapp_select_handler(request: web.Request) -> web.Response:
    """The Mini App posts {"init_data", "theme"}; the signed initData proves which Telegram user chose."""
    from config import settings
    from services.webapp_auth import validate_init_data

    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)
    data = validate_init_data(str(body.get("init_data", "")), settings.BOT_TOKEN)
    if not data or not isinstance(data.get("user"), dict):
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
    bot, dp = request.app.get(BOT_KEY), request.app.get(DP_KEY)
    if bot is None or dp is None:
        return web.json_response({"ok": False, "error": "bot_unavailable"}, status=503)

    from bot.handlers.create_pres import apply_template_choice

    user_id = int(data["user"]["id"])
    state = dp.fsm.get_context(bot=bot, chat_id=user_id, user_id=user_id)
    if body.get("referat"):  # the referat templates Mini App
        from bot.handlers.referat import apply_template_choice as referat_choice
        ok = await referat_choice(bot, user_id, state, str(body["referat"]))
        return web.json_response({"ok": ok}, status=200 if ok else 404)
    style = {k: body.get(k) for k in ("font_title", "font_body", "text_color") if body.get(k)}
    ok = await apply_template_choice(bot, user_id, state, str(body.get("theme", "")), style=style)
    return web.json_response({"ok": ok}, status=200 if ok else 404)


async def webapp_preview_handler(request: web.Request) -> web.StreamResponse:
    """Preview slide n of any template/colour key (rendered once, then cached)."""
    from services.gallery import preview_path

    _check_rate(request)

    try:
        n = int(request.match_info["n"])
    except ValueError:
        raise web.HTTPNotFound()
    path = await preview_path(request.match_info["key"], n)
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers=WEBP_HEADERS)


async def diag_handler(request: web.Request) -> web.Response:
    """Mini App diagnostics: open https://<domain>/diag in a browser."""
    from config import settings
    from bot.handlers.create_pres import webapp_url

    from services import gallery
    from services.deck import images

    thumbs = os.path.join(WEBAPP_DIR, "thumbs")
    covers = os.path.join(gallery.PREVIEW_CACHE, "covers")
    info = {
        "ok": True,
        "listening_port": settings.WEBHOOK_PORT,
        "env_PORT": os.getenv("PORT", ""),
        "env_RAILWAY_PUBLIC_DOMAIN": os.getenv("RAILWAY_PUBLIC_DOMAIN", ""),
        "WEBAPP_URL_setting": settings.WEBAPP_URL,
        "webapp_url_used_by_bot": webapp_url() or "(bo'sh: Mini App tugmasi chiqmaydi)",
        "webapp_index_exists": os.path.exists(os.path.join(WEBAPP_DIR, "index.html")),
        "catalog_exists": os.path.exists(os.path.join(WEBAPP_DIR, "catalog.json")),
        "thumb_templates": len(os.listdir(thumbs)) if os.path.isdir(thumbs) else 0,
        "request_host": request.host,
        "gallery_cache": gallery.cache_token(),
        "photo_providers": images.enabled_providers(),
        "photo_covers_ready": len(os.listdir(covers)) if os.path.isdir(covers) else 0,
    }
    return web.json_response(info, dumps=lambda o: json.dumps(o, ensure_ascii=False, indent=1))


async def webapp_cover_handler(request: web.Request) -> web.StreamResponse:
    """Cover of any template/colour key (photo templates are rendered on the server)."""
    from services.gallery import cover_path

    _check_rate(request)

    path = await cover_path(request.match_info["key"])
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers=WEBP_HEADERS)


async def fonts_api_handler(request: web.Request) -> web.Response:
    """The font library and the text colours for the Mini App's design step."""
    from bot.handlers.style import COLORS
    from services.deck import fonts
    lib = []
    for e in fonts.library_fonts():
        f = e["files"][0]
        lib.append({"key": e["key"], "name": e["name"], "category": e["category"], "cyrillic": bool(e.get("cyrillic")),
                    "file": f"fonts/{e['id']}/{f['file']}", "weight": f["weight"]})
    data = {"categories": fonts.library_categories(), "fonts": lib,
            "colors": [{"emoji": em, "name": n, "hex": h} for em, n, h in COLORS]}
    return web.json_response(data, headers={"Cache-Control": "public, max-age=3600"})


async def colors_api_handler(request: web.Request) -> web.Response:
    """Text colours that stay readable on one template (key = template or template~colour)."""
    from bot.handlers.style import allowed_colors
    from services.deck import themes
    key = request.match_info["key"]
    if not themes.is_known_theme(key):
        raise web.HTTPNotFound()
    return web.json_response({"colors": [h for _, _, _, h in allowed_colors({"template_id": themes.resolve_theme_id(key)})]},
                             headers={"Cache-Control": "public, max-age=3600"})


async def styled_cover_handler(request: web.Request) -> web.StreamResponse:
    """Cover of a template in the fonts / text colour chosen in the Mini App (drawn once, then cached)."""
    from bot.handlers.style import clean_style, preview_path
    from services.deck import themes
    key = request.match_info["key"]
    if not themes.is_known_theme(key):
        raise web.HTTPNotFound()
    tid = themes.resolve_theme_id(key)
    q = request.query
    style = clean_style({"font_title": q.get("ft"), "font_body": q.get("fb"), "text_color": q.get("c")}, tid)
    if not style:
        raise web.HTTPNotFound()
    _check_rate(request)
    path = await preview_path({"template_id": tid, **style})
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "public, max-age=604800", "Content-Type": "image/jpeg"})


async def referat_index_handler(request: web.Request) -> web.StreamResponse:
    """The referat templates Mini App; the template list is put into the page."""
    if not request.path.endswith("/"):
        raise web.HTTPFound(request.path + "/")
    from services.deck import fonts
    from services.referat import designs
    catalog = [{"id": t["id"], "n": t["code"], "name": t["name"], "cover": designs.COVERS[t["cover"]],
                "heading": designs.HEADINGS[t["heading"]], "palette": t["palette"]["name"],
                "colors": [t["palette"]["accent"], t["palette"]["accent2"]],
                "fonts": fonts.family_name(t["fonts"]["title"])} for t in designs.TEMPLATES]
    with open(os.path.join(WEBAPP_DIR, "referat", "index.html"), encoding="utf-8") as f:
        html = f.read().replace("__CATALOG__", json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/"))
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def referat_page_handler(request: web.Request) -> web.StreamResponse:
    """Title page (1) or inner page (4) of a referat template."""
    from services.referat import designs, gallery as rgallery
    tid, n = request.match_info["tid"], int(request.match_info["n"])
    if tid not in designs.BY_ID or n not in rgallery.PAGES:
        raise web.HTTPNotFound()
    if not rgallery.path(tid, n):
        _check_rate(request)
    path = await rgallery.page_path(tid, n)
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "public, max-age=604800"})


async def tezcheck_webhook_handler(request: web.Request) -> web.Response:
    """TezCheck payment events (register https://<domain>/payments/tezcheck/webhook in the cabinet)."""
    import asyncio
    from services.payment import tezcheck, orders

    raw = await request.read()
    if len(raw) > 256 * 1024:
        raise web.HTTPRequestEntityTooLarge(max_size=256 * 1024, actual_size=len(raw))
    if not tezcheck.verify_webhook(raw, request.headers.get("X-Checkout-Timestamp", ""),
                                   request.headers.get("X-Checkout-Delivery", ""),
                                   request.headers.get("X-Checkout-Signature", "")):
        logger.warning("TezCheck webhook with a bad signature from %s", request.remote)
        return web.json_response({"ok": False, "error": "bad signature"}, status=401)
    try:
        event = json.loads(raw)
    except ValueError:
        return web.json_response({"ok": False, "error": "bad json"}, status=400)
    result, order_id = await orders.handle_webhook(event)
    bot = request.app.get(BOT_KEY)
    if order_id and bot is not None:
        # answer TezCheck at once (15 s limit); the files are sent in the background
        asyncio.ensure_future(_after_payment_event(bot, result, order_id))
    return web.json_response({"ok": True, "result": result})


async def _after_payment_event(bot, result: str, order_id: str) -> None:
    from bot.delivery import deliver_order
    from database import repository
    from database.connection import AsyncSessionLocal
    try:
        if result == "paid":
            await deliver_order(bot, order_id)
        elif result in ("failed", "refunded"):
            async with AsyncSessionLocal() as session:
                order = await repository.get_presentation_order(session, order_id)
            if order:
                await bot.send_message(order.user_id, "❌ To‘lov o‘tmadi. To‘lov sahifasida qaytadan urinib ko‘ring."
                                       if result == "failed" else "↩️ To‘lov qaytarildi.")
    except Exception:  # noqa: BLE001
        logger.exception("after-payment step for %s failed", order_id)


def create_webhook_app(bot=None, dp=None) -> web.Application:
    app = web.Application(client_max_size=12 * 1024 * 1024)  # broadcast photos up to 10 MB
    app[BOT_KEY], app[DP_KEY] = bot, dp
    if os.path.isdir(WEBAPP_DIR):
        app.router.add_get("/webapp", webapp_index_handler)
        app.router.add_get("/webapp/", webapp_index_handler)
        app.router.add_post("/webapp/api/select", webapp_select_handler)
        app.router.add_get(r"/webapp/preview/{key}/{n:\d+}.webp", webapp_preview_handler)
        app.router.add_get(r"/webapp/cover/{key}.webp", webapp_cover_handler)
        app.router.add_get("/webapp/api/fonts", fonts_api_handler)
        app.router.add_get(r"/webapp/api/colors/{key}", colors_api_handler)
        app.router.add_get(r"/webapp/styled/{key}.jpg", styled_cover_handler)
        from services.deck.fonts import _LIB_DIR
        if os.path.isdir(_LIB_DIR):  # font files for the Mini App's font list (before the /webapp/ static route)
            app.router.add_static("/webapp/fonts/", str(_LIB_DIR), show_index=False)
        app.router.add_get("/webapp/referat", referat_index_handler)
        app.router.add_get("/webapp/referat/", referat_index_handler)
        app.router.add_get(r"/webapp/referat/page/{tid:r\d{2}}_{n:\d}.jpg", referat_page_handler)
        app.router.add_static("/webapp/", WEBAPP_DIR, show_index=False)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)
    app.router.add_get("/diag", diag_handler)
    app.router.add_post("/payments/click/prepare", click_prepare_handler)
    app.router.add_post("/payments/click/complete", click_complete_handler)
    app.router.add_post("/payments/payme", payme_handler)
    app.router.add_post("/payments/tezcheck/webhook", tezcheck_webhook_handler)
    from bot.admin_web import setup_admin
    setup_admin(app)
    return app


async def run_webhook_app(host: str, port: int, bot=None, dp=None):
    app = create_webhook_app(bot, dp)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info(f"Payment webhook server listening on {host}:{port}")
    from config import settings
    from bot.handlers.create_pres import webapp_url
    url = webapp_url()
    if url:
        logger.info(f"Mini App: {url}  (tekshirish: {url.split('/webapp')[0]}/diag)")
    else:
        logger.warning("Mini App O'CHIQ: WEBAPP_URL yo'q yoki noto'g'ri (%r). Railway: Settings -> Networking -> Generate Domain.",
                       settings.WEBAPP_URL)
    if bot is not None:
        import asyncio
        from services.payment.orders import reconcile_loop, payment_mode
        from bot.delivery import deliver_order
        if payment_mode() == "tezcheck":
            logger.info("To'lovlar: TezCheck (webhook: /payments/tezcheck/webhook)")
            _background.append(asyncio.ensure_future(reconcile_loop(lambda oid: deliver_order(bot, oid))))
        else:
            logger.warning("To'lovlar: %s rejimi — TEZCHECK_API_KEY va TEZCHECK_CASH_DESK_CODE kiritilmagan",
                           payment_mode().upper())
    if os.getenv("GALLERY_WARMUP", "1") != "0":
        import asyncio
        from services.gallery import warm_up
        _background.append(asyncio.create_task(warm_up()))
    if not os.path.exists(os.path.join(WEBAPP_DIR, "index.html")):
        logger.warning("webapp/index.html topilmadi: webapp papkasi serverga yuklanmagan!")
    return runner
