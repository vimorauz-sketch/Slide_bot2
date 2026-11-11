import pytest
from bot.handlers import create_pres
from bot.states.forms import PresentationForm
from tests.fixtures.telegram_fakes import FakeMessage, FakeCallbackQuery, FakeUser, FakeFSMContext


def _message(text, user_id=111):
    return FakeMessage(text=text, from_user=FakeUser(id=user_id))


# ---------------------------------------------------------------------------
# Template selection (typed number 1..200, inline buttons, Mini App, deep link)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("entered,expected_id", [
    ("01", "01_midnight_tech"),
    ("1", "01_midnight_tech"),
    ("09", "09_uzbek_heritage"),
    ("10", "10_3d_future"),
    ("20", "20_cosmos"),
    ("21", "021_paper_craft"),
    ("№ 200", "200_electric"),
])
async def test_valid_template_number_then_asks_the_topic(entered, expected_id):
    state = FakeFSMContext()
    await state.set_state(PresentationForm.template_selection)
    message = _message(entered)

    await create_pres.process_template_number_text(message, state)

    assert await state.get_state() == PresentationForm.topic  # the next missing answer
    assert (await state.get_data())["template_id"] == expected_id


@pytest.mark.asyncio
async def test_invalid_template_number_shows_error_and_does_not_advance():
    state = FakeFSMContext()
    await state.set_state(PresentationForm.template_selection)
    message = _message("999")

    await create_pres.process_template_number_text(message, state)

    assert await state.get_state() == PresentationForm.template_selection  # unchanged
    assert "1 dan 400 gacha" in message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_template_selection_callback_routes_to_custom_ai_design():
    state = FakeFSMContext()
    cb = FakeCallbackQuery(data="tpl_ai_custom")

    await create_pres.process_template_selection(cb, state)

    assert await state.get_state() == PresentationForm.custom_design_prompt


@pytest.mark.asyncio
async def test_template_selection_callback_routes_to_ocr_upload():
    state = FakeFSMContext()
    cb = FakeCallbackQuery(data="tpl_ocr_photo")

    await create_pres.process_template_selection(cb, state)

    assert await state.get_state() == PresentationForm.ocr_photo_upload


@pytest.mark.asyncio
async def test_template_selection_callback_with_a_real_template_asks_the_topic(patched_handlers_db):
    state = FakeFSMContext()
    cb = FakeCallbackQuery(data="tpl_05_nature_organic")

    await create_pres.process_template_selection(cb, state)

    assert await state.get_state() == PresentationForm.topic
    assert (await state.get_data())["template_id"] == "05_nature_organic"


@pytest.mark.asyncio
async def test_template_callback_with_a_colour_variant():
    state = FakeFSMContext()
    await state.set_state(PresentationForm.template_selection)
    cb = FakeCallbackQuery(data="tpl_150_apollo~emerald")
    await create_pres.process_template_selection(cb, state)
    assert (await state.get_data())["template_id"] == "150_apollo~emerald"
    assert "Apollo" in cb.bot.sent_messages[0]["text"]


@pytest.mark.asyncio
async def test_unknown_template_callback_alerts_and_keeps_state():
    state = FakeFSMContext()
    await state.set_state(PresentationForm.template_selection)
    cb = FakeCallbackQuery(data="tpl_999_nope")
    await create_pres.process_template_selection(cb, state)
    assert await state.get_state() == PresentationForm.template_selection
    assert cb.calls_for("answer")[0]["show_alert"]


@pytest.mark.asyncio
async def test_webapp_data_selects_theme_and_starts_wizard(patched_handlers_db):
    import json
    from types import SimpleNamespace
    state = FakeFSMContext()
    message = _message("")
    message.web_app_data = SimpleNamespace(data=json.dumps({"theme": "082_suzani~cherry"}))
    await create_pres.process_webapp_choice(message, state)
    assert await state.get_state() == PresentationForm.topic
    assert (await state.get_data())["template_id"] == "082_suzani~cherry"


@pytest.mark.asyncio
async def test_webapp_choice_mid_wizard_only_changes_design():
    import json
    from types import SimpleNamespace
    state = FakeFSMContext()
    await state.set_state(PresentationForm.topic)
    await state.update_data(subject="Fizika", template_id="05_nature_organic")
    message = _message("")
    message.web_app_data = SimpleNamespace(data=json.dumps({"theme": "15"}))
    await create_pres.process_webapp_choice(message, state)
    assert await state.get_state() == PresentationForm.topic
    data = await state.get_data()
    assert data["template_id"] == "15_blueprint" and data["subject"] == "Fizika"


@pytest.mark.asyncio
async def test_inline_gallery_navigation():
    state = FakeFSMContext()
    await state.set_state(PresentationForm.template_selection)
    cb = FakeCallbackQuery(data="gal_cats")
    await create_pres.gallery_categories(cb, state)
    kb = cb.message.calls_for("edit_reply_markup")[0]["reply_markup"].inline_keyboard
    datas = [b.callback_data for row in kb for b in row]
    assert "gal_l:education:0" in datas

    cb = FakeCallbackQuery(data="gal_l:all:1")
    await create_pres.gallery_list(cb, state)
    sent = (cb.message.calls_for("edit_media") or cb.message.calls_for("answer_photo") or cb.message.calls_for("edit_reply_markup"))[0]
    datas = [b.callback_data for row in sent["reply_markup"].inline_keyboard for b in row]
    assert "gal_t:09_uzbek_heritage" in datas and "gal_l:all:0" in datas and "gal_l:all:2" in datas
    assert len([d for d in datas if d.startswith("gal_t:")]) == create_pres.PAGE_SIZE

    cb = FakeCallbackQuery(data="gal_t:150_apollo")
    await create_pres.gallery_template(cb, state)
    sent = (cb.message.calls_for("answer_photo") or cb.message.calls_for("answer"))[0]
    datas = [b.callback_data for row in sent["reply_markup"].inline_keyboard for b in row]
    assert "tpl_150_apollo" in datas and "tpl_150_apollo~emerald" in datas
    assert len([d for d in datas if d.startswith("tpl_")]) == 10


@pytest.mark.asyncio
async def test_deep_link_payload_selects_template_and_colour(patched_handlers_db):
    state = FakeFSMContext()
    ok = await create_pres.apply_template_choice(_message("").bot, 1, state, "150_apollo--emerald")
    assert ok and (await state.get_data())["template_id"] == "150_apollo~emerald"
    assert await state.get_state() == PresentationForm.topic


# ---------------------------------------------------------------------------
# Slide count validation (min / max)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_slide_count_rejects_non_numeric_input(patched_handlers_db):
    state = FakeFSMContext()
    message = _message("ten")

    await create_pres.process_slide_count(message, state)

    assert "faqat raqam" in message.calls_for("answer")[0]["text"]
    assert await state.get_state() is None  # did not advance


@pytest.mark.asyncio
async def test_slide_count_rejects_below_minimum(patched_handlers_db):
    state = FakeFSMContext()
    message = _message("1")  # below default MIN_SLIDES_PER_ORDER=5

    await create_pres.process_slide_count(message, state)

    assert "Minimum" in message.calls_for("answer")[0]["text"]
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_slide_count_rejects_above_maximum(patched_handlers_db):
    state = FakeFSMContext()
    message = _message("500")  # far above default MAX_SLIDES_PER_ORDER=30

    await create_pres.process_slide_count(message, state)

    assert "Maksimum" in message.calls_for("answer")[0]["text"]
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_slide_count_accepts_value_within_bounds(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(topic="Fotosintez")
    message = _message("10")

    await create_pres.process_slide_count(message, state)

    assert await state.get_state() == PresentationForm.template_selection  # next: the template
    assert (await state.get_data())["slide_count"] == 10


# ---------------------------------------------------------------------------
# Data collection does not leak between independent users (FSM isolation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_users_fsm_states_are_independent():
    state_a = FakeFSMContext()
    state_b = FakeFSMContext()

    await create_pres.process_subject(_message("Biologiya", user_id=111), state_a)
    await create_pres.process_subject(_message("Fizika", user_id=222), state_b)

    assert (await state_a.get_data())["subject"] == "Biologiya"
    assert (await state_b.get_data())["subject"] == "Fizika"


# ---------------------------------------------------------------------------
# Optional field handling ("-" means skip)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_teacher_name_dash_means_skipped():
    state = FakeFSMContext()
    await create_pres.process_teacher_name(_message("-"), state)
    assert (await state.get_data())["teacher_name"] == ""


@pytest.mark.asyncio
async def test_teacher_name_is_stored_when_provided():
    state = FakeFSMContext()
    await create_pres.process_teacher_name(_message("Aliyev Vali"), state)
    assert (await state.get_data())["teacher_name"] == "Aliyev Vali"


# ---------------------------------------------------------------------------
# Order confirmation summary: HTML-escaping regression guard
# ---------------------------------------------------------------------------

def _texts(message):
    return [c.get("text") or c.get("caption") or "" for c in message.calls]


@pytest.mark.asyncio
async def test_confirmation_summary_escapes_dangerous_user_text(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(
        subject="Biologiya <script>", topic="5 < 3 & test", slide_count=5, template_id="05_nature_organic",
        author_name="A & B", institution="Maktab <1>", language="uz"
    )
    message = _message("-")

    await create_pres._show_summary(message, state, 111)

    summary_text = _texts(message)[-1]
    assert "<script>" not in summary_text
    assert "&lt;script&gt;" in summary_text and "A &amp; B" in summary_text
    assert await state.get_state() == PresentationForm.confirmation


@pytest.mark.asyncio
async def test_confirmation_summary_computes_total_price_and_offers_the_extras(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(topic="T", slide_count=10, template_id="05_nature_organic")
    message = _message("-")

    await create_pres._show_summary(message, state, 111)

    data = await state.get_data()
    assert data["total_price"] == 10 * 350  # default DEFAULT_PRICE_PER_SLIDE
    assert data["language"] == "uz"         # the default language is filled in
    markup = [c for c in message.calls if c.get("reply_markup") is not None][-1]["reply_markup"]
    buttons = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert {"confirm_pres_temp_order", "px_more", "px_tpl", "st_menu", "show_plan", "cancel_pres"} <= set(buttons)


# ---------------------------------------------------------------------------
# Cancel flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_clears_state_and_confirms_to_user():
    state = FakeFSMContext()
    await state.update_data(subject="should be wiped")
    cb = FakeCallbackQuery(data="cancel_pres")

    await create_pres.cancel_presentation_creation(cb, state)

    assert await state.get_data() == {}
    assert "bekor qilindi" in cb.message.calls_for("edit_text")[0]["text"]


# ---------------------------------------------------------------------------
# Remaining wizard steps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_pres_wizard_resets_state_and_asks_the_topic(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(leftover="from a previous attempt")

    message = _message("🎨 Presentation yaratish")
    await create_pres.start_pres_wizard(message, state)

    assert await state.get_state() == PresentationForm.topic      # the topic comes first now
    assert await state.get_data() == {}
    assert "mavzusini" in message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_custom_design_prompt_generates_spec_and_asks_the_topic(no_openai_key):
    state = FakeFSMContext()

    await create_pres.process_custom_design_prompt(_message("Ko'k va oq rangli dizayn"), state)

    data = await state.get_data()
    assert data["template_id"] == "custom_ai"
    assert "custom_design_spec" in data
    assert data["custom_design_spec"]["primary_color"].startswith("#")
    assert await state.get_state() == PresentationForm.topic


@pytest.mark.asyncio
async def test_process_topic_advances_to_slide_count_with_pricing_info(patched_handlers_db):
    state = FakeFSMContext()
    message = _message("Fotosintez jarayoni")

    await create_pres.process_topic(message, state)

    assert await state.get_state() == PresentationForm.slide_count
    assert (await state.get_data())["topic"] == "Fotosintez jarayoni"
    assert "Narxi" in message.calls_for("answer")[0]["text"]


async def _extras_state(**extra):
    state = FakeFSMContext()
    await state.update_data(topic="Fotosintez", slide_count=8, template_id="05_nature_organic", language="uz",
                            _return="more", **extra)
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize("handler,field,typed,stored", [
    ("process_author_name", "author_name", "Ali Valiyev", "Ali Valiyev"),
    ("process_institution", "institution", "TATU", "TATU"),
    ("process_institution", "institution", "⏭ O‘tkazib yuborish", ""),
    ("process_teacher_name", "teacher_name", "Karimova B.", "Karimova B."),
    ("process_teacher_name", "teacher_name", "-", ""),
    ("process_subject", "subject", "Biologiya", "Biologiya"),
    ("process_additional_notes", "additional_notes", "Rasmlar ko‘p bo‘lsin", "Rasmlar ko‘p bo‘lsin"),
    ("process_date", "date", "📅 Bugun: 20.10.2026", "20.10.2026"),
    ("process_date", "date", "📅 2026-yil", "2026-yil"),
    ("process_date", "date", "25.10.2026", "25.10.2026"),
    ("process_date", "date", "⏭ O‘tkazib yuborish", ""),
])
async def test_extras_are_saved_and_lead_back_to_the_extras_menu(handler, field, typed, stored):
    state = await _extras_state()
    message = _message(typed)
    await getattr(create_pres, handler)(message, state)
    assert (await state.get_data())[field] == stored
    assert await state.get_state() == PresentationForm.confirmation
    assert "Qo‘shimcha sozlamalar" in message.calls_for("answer")[-1]["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("level,first_button", [("Maktab", "1-sinf"), ("Universitet", "1-kurs"),
                                                ("Akademik litsey", "1-kurs")])
async def test_level_then_class_buttons_match_the_level(level, first_button):
    state = await _extras_state()
    message = _message(level)
    await create_pres.process_level(message, state)
    assert await state.get_state() == PresentationForm.course
    kb = message.calls_for("answer")[0]["reply_markup"]
    assert kb.keyboard[0][0].text == first_button
    await create_pres.process_course(_message(first_button), state)
    data = await state.get_data()
    assert (data["level"], data["course"]) == (level, first_button)
    assert await state.get_state() == PresentationForm.confirmation


@pytest.mark.asyncio
async def test_other_level_skips_the_class():
    state = await _extras_state()
    await create_pres.process_level(_message("Boshqa"), state)
    assert (await state.get_data())["course"] == ""
    assert await state.get_state() == PresentationForm.confirmation


@pytest.mark.asyncio
async def test_extras_buttons_open_the_right_question_and_language_is_a_button(patched_handlers_db):
    state = await _extras_state()
    await state.set_state(PresentationForm.confirmation)
    cb = FakeCallbackQuery(data="px_f:date")
    await create_pres.extras_field(cb, state)
    assert await state.get_state() == PresentationForm.date
    kb = cb.message.calls_for("answer")[-1]["reply_markup"]
    assert kb.keyboard[0][0].text.startswith("📅 Bugun:")

    await state.set_state(PresentationForm.confirmation)
    cb = FakeCallbackQuery(data="px_f:language")
    await create_pres.extras_field(cb, state)
    kb = cb.message.calls_for("edit_text")[-1]["reply_markup"]
    assert [b.callback_data for b in kb.inline_keyboard[0]] == ["px_l:uz", "px_l:ru", "px_l:en"]
    await create_pres.extras_language(FakeCallbackQuery(data="px_l:en"), state)
    assert (await state.get_data())["language"] == "en"


@pytest.mark.asyncio
async def test_extras_buttons_from_an_old_menu_are_refused():
    state = FakeFSMContext()                       # the order was finished or cancelled
    cb = FakeCallbackQuery(data="px_f:author_name")
    await create_pres.extras_field(cb, state)
    assert cb.calls_for("answer")[0]["show_alert"]
    assert await state.get_state() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("button_text,expected_code", [
    ("🇺🇿 O'zbekcha", "uz"),
    ("🇷🇺 Русский", "ru"),
    ("🇬🇧 English", "en"),
    ("something unexpected", "uz"),  # safe default
])
async def test_old_language_question_still_works_and_shows_the_summary(button_text, expected_code, patched_handlers_db):
    """A user who was in the middle of the old, longer wizard when the bot was updated."""
    state = FakeFSMContext()
    await state.update_data(topic="T", slide_count=5, template_id="05_nature_organic")
    await state.set_state(PresentationForm.language)

    await create_pres.process_language(_message(button_text), state)

    assert (await state.get_data())["language"] == expected_code
    assert await state.get_state() == PresentationForm.confirmation


@pytest.mark.asyncio
async def test_recommended_template_is_the_most_chosen_one(patched_handlers_db):
    from database import repository
    async with patched_handlers_db() as s:
        await repository.get_or_create_user(s, 5, "A", "a")
        for tid in ("150_apollo", "150_apollo", "09_uzbek_heritage"):
            await repository.create_presentation_order(s, 5, "T", "S", 8, tid, 2800)
    assert await create_pres.recommended_template() == "150_apollo"


@pytest.mark.asyncio
async def test_recommended_template_button_goes_to_the_summary(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(topic="Fotosintez", slide_count=8)
    await state.set_state(PresentationForm.template_selection)
    cb = FakeCallbackQuery(data="tpl_auto")
    await create_pres.process_template_selection(cb, state)
    assert (await state.get_data())["template_id"]
    assert await state.get_state() == PresentationForm.confirmation


@pytest.mark.asyncio
async def test_subject_and_slide_count_offer_buttons(patched_handlers_db):
    state = FakeFSMContext()
    m1 = _message("Biologiya")
    await create_pres.process_subject(m1, state)
    m2 = _message("Fotosintez")
    await create_pres.process_topic(m2, state)
    kb = m2.calls_for("answer")[0]["reply_markup"]
    assert [b.text for b in kb.keyboard[0]] == ["5", "7", "8", "10"]
    from bot.keyboards.reply import get_subject_keyboard
    assert get_subject_keyboard().keyboard[0][0].text == "Biologiya"


# ---------------------------------------------------------------------------
# Outline review (plan shown before slides are written)
# ---------------------------------------------------------------------------

async def _wizard_state(slide_count=8):
    state = FakeFSMContext()
    await state.update_data(template_id="05_nature_organic", subject="Biologiya", topic="Fotosintez",
                            slide_count=slide_count, author_name="A", institution="B", language="uz",
                            additional_notes="", total_price=slide_count * 350)
    await state.set_state(PresentationForm.confirmation)
    return state


async def test_confirmation_shows_the_outline_with_review_buttons(no_openai_key):
    state = await _wizard_state()
    cb = FakeCallbackQuery(data="confirm_pres_temp_order")
    await create_pres.confirm_and_show_outline(cb, state)
    assert await state.get_state() == PresentationForm.outline_review
    data = await state.get_data()
    assert len(data["outline"]["slides"]) == 7
    msg = cb.message.calls_for("answer")[-1]
    assert "TAQDIMOT REJASI" in msg["text"]
    buttons = [b.callback_data for row in msg["reply_markup"].inline_keyboard for b in row]
    assert {"outline_ok", "outline_edit", "outline_regen"} <= set(buttons)


async def test_outline_edit_asks_for_changes_then_regenerates(no_openai_key):
    state = await _wizard_state()
    await create_pres.confirm_and_show_outline(FakeCallbackQuery(data="confirm_pres_x"), state)
    cb = FakeCallbackQuery(data="outline_edit")
    await create_pres.ask_outline_changes(cb, state)
    assert await state.get_state() == PresentationForm.outline_edit
    msg = FakeMessage(text="Kalvin sikli haqida slayd qo‘sh")
    await create_pres.apply_outline_changes(msg, state)
    assert await state.get_state() == PresentationForm.outline_review
    assert "TAQDIMOT REJASI" in msg.calls_for("answer")[-1]["text"]


async def test_outline_regenerate_keeps_review_state(no_openai_key):
    state = await _wizard_state()
    await create_pres.confirm_and_show_outline(FakeCallbackQuery(data="confirm_pres_x"), state)
    cb = FakeCallbackQuery(data="outline_regen")
    await create_pres.regenerate_outline(cb, state)
    assert await state.get_state() == PresentationForm.outline_review
    assert "TAQDIMOT REJASI" in cb.message.calls_for("answer")[-1]["text"]


@pytest.mark.parametrize("url,expected", [
    ("", ""),
    ("https://domeningiz/webapp/", ""),
    ("http://bot.example.uz/webapp/", ""),
    ("https://127.0.0.1/webapp/", ""),
    ("https://bot.slidelab.uz/webapp", "https://bot.slidelab.uz/webapp/"),
])
def test_webapp_url_only_accepts_public_https(monkeypatch, url, expected):
    monkeypatch.setattr(create_pres.settings, "WEBAPP_URL", url)
    monkeypatch.setattr(create_pres, "_webapp_disabled", False)
    assert create_pres.webapp_url() == expected


@pytest.mark.asyncio
async def test_picker_falls_back_when_telegram_rejects_the_webapp_url(monkeypatch, patched_handlers_db):
    from aiogram.exceptions import TelegramBadRequest
    monkeypatch.setattr(create_pres.settings, "WEBAPP_URL", "https://bot.slidelab.uz/webapp/")
    monkeypatch.setattr(create_pres, "_webapp_disabled", False)
    message = _message("🖼 Shablonlar")
    sent = []

    async def answer_photo(photo, caption=None, reply_markup=None, parse_mode=None):
        has_webapp = any(getattr(b, "web_app", None) for row in reply_markup.inline_keyboard for b in row)
        if has_webapp:
            raise TelegramBadRequest(method=None, message="Bad Request: inline keyboard button Web App URL is invalid")
        sent.append(reply_markup)

    message.answer_photo = answer_photo
    await create_pres.start_with_templates(message, FakeFSMContext())
    assert len(sent) == 1 and create_pres.webapp_url() == ""
    monkeypatch.setattr(create_pres, "_webapp_disabled", False)
