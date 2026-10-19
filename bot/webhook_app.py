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
DP_KEY = web.AppKey("dp", object) if hasattr(web, "AppKey") else "dp"
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")


async def webapp_index_handler(request: web.Request) -> web.StreamResponse:
    if not request.path.endswith("/"):
        raise web.HTTPFound(request.path + "/")
    return web.FileResponse(os.path.join(WEBAPP_DIR, "index.html"), headers={"Cache-Control": "no-cache"})


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
    ok = await apply_template_choice(bot, user_id, state, str(body.get("theme", "")))
    return web.json_response({"ok": ok}, status=200 if ok else 404)


async def webapp_preview_handler(request: web.Request) -> web.StreamResponse:
    """Preview slide n of any template/colour key (rendered once, then cached)."""
    from services.gallery import preview_path

    try:
        n = int(request.match_info["n"])
    except ValueError:
        raise web.HTTPNotFound()
    path = await preview_path(request.match_info["key"], n)
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "public, max-age=604800"})


async def diag_handler(request: web.Request) -> web.Response:
    """Mini App diagnostics: open https://<domain>/diag in a browser."""
    from config import settings
    from bot.handlers.create_pres import webapp_url

    thumbs = os.path.join(WEBAPP_DIR, "thumbs")
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
    }
    return web.json_response(info, dumps=lambda o: json.dumps(o, ensure_ascii=False, indent=1))


def create_webhook_app(bot=None, dp=None) -> web.Application:
    app = web.Application()
    app[BOT_KEY], app[DP_KEY] = bot, dp
    if os.path.isdir(WEBAPP_DIR):
        app.router.add_get("/webapp", webapp_index_handler)
        app.router.add_get("/webapp/", webapp_index_handler)
        app.router.add_post("/webapp/api/select", webapp_select_handler)
        app.router.add_get(r"/webapp/preview/{key}/{n:\d+}.webp", webapp_preview_handler)
        app.router.add_static("/webapp/", WEBAPP_DIR, show_index=False)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", health_handler)
    app.router.add_get("/diag", diag_handler)
    app.router.add_post("/payments/click/prepare", click_prepare_handler)
    app.router.add_post("/payments/click/complete", click_complete_handler)
    app.router.add_post("/payments/payme", payme_handler)
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
    if not os.path.exists(os.path.join(WEBAPP_DIR, "index.html")):
        logger.warning("webapp/index.html topilmadi: webapp papkasi serverga yuklanmagan!")
    return runner
