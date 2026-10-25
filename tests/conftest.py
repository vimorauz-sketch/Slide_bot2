import os
import sys

# Ensure project root is importable (no __init__.py anywhere in this project;
# everything relies on implicit namespace packages).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pytest_asyncio

from tests.fixtures.db import make_test_session_factory

# Make sure settings never accidentally pick up a real-looking OpenAI key from a
# developer's shell environment while the test suite runs.
os.environ.pop("OPENAI_API_KEY", None)


@pytest_asyncio.fixture
async def db():
    """Isolated SQLite engine/session factory, unique per test and disposed afterward.
    Never touches the real slidelab.db used by the running bot."""
    engine, session_factory = await make_test_session_factory()
    yield session_factory
    await engine.dispose()


@pytest.fixture
def storage_dir(tmp_path):
    """A pytest-managed temp directory (auto-cleaned by pytest) for generated files."""
    d = tmp_path / "storage"
    d.mkdir()
    return str(d)


@pytest_asyncio.fixture
async def patched_handlers_db(db, monkeypatch):
    """Redirects every bot handler module's AsyncSessionLocal to the isolated test DB.

    Each handler module does `from database.connection import AsyncSessionLocal`, which
    binds its own local name at import time, so patching database.connection alone is
    not enough -- every module that imported the name must be patched individually.
    """
    import database.connection as dbc
    from bot.handlers import create_pres, ocr_task, payment, admin, start
    from services.payment import click_webhook, payme_webhook, orders
    from services import broadcast, guard, credits
    from bot import delivery
    import bot.admin_web as admin_web
    from bot.admin_web import stats as admin_stats

    monkeypatch.setattr(dbc, "AsyncSessionLocal", db)
    for module in (create_pres, ocr_task, payment, admin, start, click_webhook, payme_webhook,
                   orders, broadcast, delivery, admin_web, admin_stats, guard, credits):
        monkeypatch.setattr(module, "AsyncSessionLocal", db)
    return db


@pytest.fixture
def no_openai_key(monkeypatch):
    """Forces the OpenAI-backed code paths into their mock/fallback branch."""
    monkeypatch.setattr("config.settings.OPENAI_API_KEY", "")
    return None


@pytest.fixture(autouse=True)
def no_network_images(monkeypatch):
    """Slide rendering must never reach Pexels/Unsplash/Wikimedia/OpenAI from the test suite;
    with no provider enabled the renderer uses the theme's generated art instead."""
    monkeypatch.setattr("config.settings.PEXELS_API_KEY", "")
    monkeypatch.setattr("config.settings.PIXABAY_API_KEY", "")
    monkeypatch.setattr("config.settings.UNSPLASH_ACCESS_KEY", "")
    monkeypatch.setattr("config.settings.WIKIMEDIA_ENABLED", False)
    monkeypatch.setattr("config.settings.OPENVERSE_ENABLED", False)
    monkeypatch.setattr("config.settings.LOCAL_PHOTO_DIR", "")
    monkeypatch.setattr("config.settings.AI_IMAGES_ENABLED", False)
    # never call the real OpenAI API from tests (tests that need it patch get_openai_client)
    monkeypatch.setattr("config.settings.OPENAI_API_KEY", "")
    return None


@pytest_asyncio.fixture(autouse=True)
async def close_render_browser():
    """Each test runs in its own event loop; the shared Chromium instance is bound to the
    loop that started it, so close it after every test that used it."""
    yield
    from services.deck import render as deck_render
    if deck_render._pw_state.get("browser") is not None:
        await deck_render.shutdown_browser()


@pytest.fixture(autouse=True)
async def finish_background_files():
    """PDF/PPTX are made by background tasks: let them finish inside the test that started them."""
    yield
    import asyncio
    from services import presentation
    from services import prefetch
    tasks = list(presentation._file_tasks.values()) + [j.task for j in prefetch._jobs.values()]
    presentation._file_tasks.clear()
    prefetch._jobs.clear()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture(autouse=True)
def fresh_runtime_settings():
    """Dashboard settings are cached in memory: every test starts from the defaults — except the
    free first presentation, which is off so the older tests see the paid flow (tests of the free
    presentation turn it on with runtime._values["free_trial"] = "1")."""
    from services import runtime
    runtime._values.clear()
    runtime.blocked_users.clear()
    runtime._values["free_trial"] = "0"
    yield
    runtime._values.clear()
    runtime.blocked_users.clear()


@pytest.fixture(autouse=True)
def demo_payments_in_tests(monkeypatch):
    """The suite exercises the DEMO payment flow; production has it off (ALLOW_DEMO_PAYMENTS=false)."""
    monkeypatch.setattr("config.settings.ALLOW_DEMO_PAYMENTS", True)
