"""Referats: writing (offline text), PDF + Word, the wizard, payment / free delivery, Mini App."""
import json
import os
import zipfile

import pytest
from sqlalchemy import select

from bot.handlers import referat as rf
from bot.states.forms import ReferatForm
from database.models import PresentationOrder
from services import runtime
from services.payment import orders
from services.referat import builder, designs, render, writer
from tests.fixtures.telegram_fakes import FakeCallbackQuery, FakeFSMContext, FakeMessage, FakeUser

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "referat_sample.json")


def _sample():
    with open(SAMPLE, encoding="utf-8") as f:
        return json.load(f)


def test_hundred_distinct_templates_with_known_parts():
    assert len(designs.TEMPLATES) == 100
    looks = set()
    for t in designs.TEMPLATES:
        assert t["cover"] in designs.COVERS and t["heading"] in designs.HEADINGS and t["page"] in designs.PAGES
        assert t["topic"] in designs.TOPICS and t["cover"] in designs.GROUP_OF
        assert t["palette"]["accent"].startswith("#")
        looks.add((t["cover"], t["variant"], t["palette_id"], t["heading"]))
    assert len(looks) == 100  # no two templates look the same
    assert len({t["cover"] for t in designs.TEMPLATES}) == len(designs.LAYOUTS)
    assert designs.by_number(7)["id"] == "r07" and designs.get("nope")["id"] == designs.DEFAULT


def test_cover_decoration_and_mirrored_geometry():
    from services.referat import decor
    for t in designs.TEMPLATES:
        svg = decor.cover_svg(t["cover"], t["palette"], t["variant"], bool(t["layout"].get("mirrored")))
        assert svg.startswith("<svg") and svg.endswith("</svg>")
    lay = designs.LAYOUTS["band"]
    m = designs.geometry("band", 1)
    assert m["mirrored"] and m["left"] == lay["right"] and m["right"] == lay["left"]


def test_every_sample_topic_has_its_own_referat():
    from services.referat import gallery
    topics = set()
    for name in designs.TOPICS:
        doc = gallery.sample_doc({"topic": name})
        topics.add(doc["meta"]["topic"])
        assert len([s for s in doc["sections"] if s["kind"] == "chapter"]) == 2
        vm = render.view_model(doc, designs.get("r01"), {"s1.0": "data:x", "s2.1": "data:y"})
        assert vm["sections"][1]["subsections"][0]["image"]  # the inner sample page shows a picture
    assert len(topics) == len(designs.TOPICS)


def test_title_page_data_follows_the_level():
    school = writer.build_meta({"level": "Maktab", "language": "uz", "topic": "T", "group": "9-sinf"})
    uni = writer.build_meta({"level": "Universitet", "language": "ru", "topic": "T"})
    assert "MAKTAB TA’LIMI" in school["ministry"] and school["group_label"] == "Sinf"
    assert "ВЫСШЕГО ОБРАЗОВАНИЯ" in uni["ministry"] and uni["kind"] == "РЕФЕРАТ"


def test_offline_text_has_the_planned_structure():
    doc = writer.mock_document({"topic": "Suv aylanishi", "size": "long", "with_images": True})
    kinds = [s["kind"] for s in doc["sections"]]
    assert kinds == ["intro", "chapter", "chapter", "chapter", "conclusion"]
    assert all(len(s["subsections"]) == 3 for s in doc["sections"] if s["kind"] == "chapter")
    assert any(sub.get("image") for s in doc["sections"] for sub in s.get("subsections", []))


def test_numbering_of_chapters_figures_and_tables():
    vm = render.view_model(_sample(), designs.get("r01"), {"s1.0": "data:x", "s2.1": "data:y"})
    ch = [s for s in vm["sections"] if s["number"]]
    assert [s["number"] for s in ch] == ["1.", "2."]
    assert ch[0]["subsections"][1]["number"] == "1.2."
    assert ch[0]["subsections"][0]["image"]["n"] == 1 and ch[1]["subsections"][1]["image"]["n"] == 2
    assert ch[1]["subsections"][0]["table"]["n"] == 1


@pytest.mark.asyncio
async def test_pdf_and_word_files(tmp_path):
    res = await builder.build_referat({"referat_template": "r09", "language": "uz"}, str(tmp_path), doc=_sample())
    assert res.pages >= 6 and os.path.exists(res.pdf_path) and len(res.previews) == 2
    with zipfile.ZipFile(res.docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        footers = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/footer"))
    assert "Fotosintez jarayoni va uning tabiatdagi ahamiyati" in xml
    assert "Doniyorbek Normurodov" in xml and 'behindDoc="1"' in xml and "PAGE" in footers
    # files are rebuilt from referat.json when the server lost them
    os.remove(res.pdf_path)
    os.remove(res.docx_path)
    again = await builder.ensure_files(str(tmp_path))
    assert os.path.exists(again.pdf_path) and os.path.exists(again.docx_path)


@pytest.mark.asyncio
async def test_template_page_pictures_exist_for_every_template():
    from services.referat import gallery
    for t in designs.TEMPLATES:
        assert gallery.path(t["id"], 1) and gallery.path(t["id"], 4)
    assert await gallery.sheet(0)


async def _walk_wizard(user_id, state, answers):
    for state_name, text in answers:
        cur = await state.get_state()
        assert cur == getattr(ReferatForm, state_name), (cur, state_name)
        handler = {"subject": rf.ask_topic, "topic": rf.ask_size, "size": rf.ask_author, "author": rf.ask_level,
                   "level": rf.ask_institution, "institution": rf.ask_group, "group": rf.ask_teacher,
                   "teacher": rf.ask_city, "city": rf.ask_language, "language": rf.ask_images,
                   "images": rf.ask_notes, "notes_choice": rf.notes_choice}[state_name]
        await handler(FakeMessage(text=text, from_user=FakeUser(id=user_id)), state)


ANSWERS = [("subject", "Tarix"), ("topic", "Amir Temur davlati"), ("size", "5–7 bet · 3 000 so‘m"),
           ("author", "Ali Valiyev"), ("level", "Universitet"), ("institution", "⏭ O‘tkazib yuborish"),
           ("group", "211-21"), ("teacher", "S. Rahimov"), ("city", "Samarqand"), ("language", "🇺🇿 O'zbekcha"),
           ("images", rf.IMG_NO), ("notes_choice", "🚫 Yo‘q")]


@pytest.mark.asyncio
async def test_wizard_then_paid_order_is_delivered_as_word_and_pdf(patched_handlers_db, monkeypatch, tmp_path):
    monkeypatch.setattr(rf.os.path, "abspath", lambda p, _a=os.path.abspath: _a(p))
    monkeypatch.setattr(builder, "SAVE_NAME", "referat.json")
    state = FakeFSMContext()
    ok = await rf.apply_template_choice(FakeMessage().bot, 81, state, "r04")
    assert ok and await state.get_state() == ReferatForm.subject
    await _walk_wizard(81, state, ANSWERS)
    assert await state.get_state() == ReferatForm.confirmation
    data = await state.get_data()
    assert data["size"] == "short" and data["city"] == "Samarqand" and data["with_images"] is False

    cb = FakeCallbackQuery(data="rf_go", from_user=FakeUser(id=81))
    await rf.confirm(cb, state)
    async with patched_handlers_db() as s:
        order = (await s.execute(select(PresentationOrder).where(PresentationOrder.user_id == 81))).scalars().one()
    assert order.kind == "referat" and order.status == "PREVIEW_READY"
    assert order.total_price == 500 * writer.SIZES["short"]["pages"]
    assert cb.message.calls_for("answer_media_group")
    assert "Word (.docx)" in cb.message.calls_for("answer")[-1]["text"]

    from bot.delivery import deliver_order
    await orders.mark_paid(order.id, by="TEZCHECK", amount=order.total_price)
    bot = cb.message.bot
    assert await deliver_order(bot, order.id)
    names = [m["document"].filename for m in bot.sent_messages if m.get("document")]
    assert any(n.endswith(".docx") for n in names) and any(n.endswith(".pdf") for n in names)
    assert any("referatingiz tayyor" in (m["text"] or "") for m in bot.sent_messages)


@pytest.mark.asyncio
async def test_first_referat_is_free_while_payments_are_off(patched_handlers_db, monkeypatch):
    runtime._values["free_trial"] = "1"
    monkeypatch.setattr("config.settings.ALLOW_DEMO_PAYMENTS", False)
    monkeypatch.setattr("config.settings.PAYMENT_ENV", "DEMO")
    monkeypatch.setattr("config.settings.TEZCHECK_API_KEY", "")
    state = FakeFSMContext()
    await rf.apply_template_choice(FakeMessage().bot, 82, state, "r01")
    await _walk_wizard(82, state, ANSWERS)
    cb = FakeCallbackQuery(data="rf_go", from_user=FakeUser(id=82))
    await rf.confirm(cb, state)
    async with patched_handlers_db() as s:
        order = (await s.execute(select(PresentationOrder).where(PresentationOrder.user_id == 82))).scalars().one()
    assert order.paid_by == "TRIAL" and order.delivered_at is not None
    assert any("Bepul referatingiz tayyor" in (m["text"] or "") for m in cb.message.bot.sent_messages)


@pytest.mark.asyncio
async def test_referat_closed_when_payments_off_and_nothing_free(patched_handlers_db, monkeypatch):
    monkeypatch.setattr("config.settings.ALLOW_DEMO_PAYMENTS", False)
    monkeypatch.setattr("config.settings.PAYMENT_ENV", "DEMO")
    monkeypatch.setattr("config.settings.TEZCHECK_API_KEY", "")
    msg = FakeMessage(text="📄 Referat yaratish", from_user=FakeUser(id=83))
    state = FakeFSMContext()
    await rf.start_referat(msg, state)
    assert await state.get_state() is None
    assert "to‘xtatilgan" in msg.calls_for("answer")[-1]["text"]


@pytest.mark.asyncio
async def test_mini_app_page_and_selection(monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer
    from bot.webhook_app import create_webhook_app
    async with TestClient(TestServer(create_webhook_app(None, None))) as client:
        r = await client.get("/webapp/referat/")
        html = await r.text()
        assert r.status == 200 and '"id": "r100"' in html and "__CATALOG__" not in html
        r = await client.get("/webapp/referat/page/r05_1.jpg")
        assert r.status == 200 and r.headers["Content-Type"].startswith("image/")
        assert (await client.get("/webapp/referat/page/r999_1.jpg")).status == 404


@pytest.mark.asyncio
async def test_mini_app_send_data_starts_the_referat_wizard():
    from types import SimpleNamespace
    from bot.handlers import create_pres
    state = FakeFSMContext()
    msg = FakeMessage(text="")
    msg.web_app_data = SimpleNamespace(data=json.dumps({"referat": "r12"}))
    await create_pres.process_webapp_choice(msg, state)
    assert await state.get_state() == ReferatForm.subject
    assert (await state.get_data())["referat_template"] == "r12"
