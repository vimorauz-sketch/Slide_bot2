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
async def test_valid_template_number_advances_to_subject_state(entered, expected_id):
    state = FakeFSMContext()
    await state.set_state(PresentationForm.template_selection)
    message = _message(entered)

    await create_pres.process_template_number_text(message, state)

    assert await state.get_state() == PresentationForm.style  # fonts/colour menu first
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
async def test_template_selection_callback_with_a_real_template_sets_subject_state():
    state = FakeFSMContext()
    cb = FakeCallbackQuery(data="tpl_05_nature_organic")

    await create_pres.process_template_selection(cb, state)

    assert await state.get_state() == PresentationForm.style  # fonts/colour menu first
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
async def test_webapp_data_selects_theme_and_starts_wizard():
    import json
    from types import SimpleNamespace
    state = FakeFSMContext()
    message = _message("")
    message.web_app_data = SimpleNamespace(data=json.dumps({"theme": "082_suzani~cherry"}))
    await create_pres.process_webapp_choice(message, state)
    assert await state.get_state() == PresentationForm.style  # fonts/colour menu first
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
async def test_deep_link_payload_selects_template_and_colour():
    state = FakeFSMContext()
    ok = await create_pres.apply_template_choice(_message("").bot, 1, state, "150_apollo--emerald")
    assert ok and (await state.get_data())["template_id"] == "150_apollo~emerald"
    assert await state.get_state() == PresentationForm.style  # fonts/colour menu first


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
    message = _message("10")

    await create_pres.process_slide_count(message, state)

    assert await state.get_state() == PresentationForm.author_name
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

@pytest.mark.asyncio
async def test_confirmation_summary_escapes_dangerous_user_text(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(
        subject="Biologiya <script>", topic="5 < 3 & test", slide_count=5,
        author_name="A & B", institution="Maktab <1>", language="uz"
    )
    message = _message("-")

    await create_pres.process_additional_notes(message, state)

    summary_text = message.calls_for("answer")[-1]["text"]
    assert "<script>" not in summary_text
    assert "&lt;script&gt;" in summary_text
    assert await state.get_state() == PresentationForm.confirmation


@pytest.mark.asyncio
async def test_confirmation_summary_computes_total_price(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(
        subject="S", topic="T", slide_count=10,
        author_name="A", institution="I", language="uz"
    )
    message = _message("-")

    await create_pres.process_additional_notes(message, state)

    data = await state.get_data()
    assert data["total_price"] == 10 * 350  # default DEFAULT_PRICE_PER_SLIDE


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
async def test_start_pres_wizard_resets_state_and_shows_template_selection():
    state = FakeFSMContext()
    await state.update_data(leftover="from a previous attempt")

    await create_pres.start_pres_wizard(_message("🎨 Presentation yaratish"), state)

    assert await state.get_state() == PresentationForm.template_selection
    assert await state.get_data() == {}


@pytest.mark.asyncio
async def test_custom_design_prompt_generates_spec_and_advances_to_subject(no_openai_key):
    state = FakeFSMContext()

    await create_pres.process_custom_design_prompt(_message("Ko'k va oq rangli dizayn"), state)

    data = await state.get_data()
    assert data["template_id"] == "custom_ai"
    assert "custom_design_spec" in data
    assert data["custom_design_spec"]["primary_color"].startswith("#")
    assert await state.get_state() == PresentationForm.style  # fonts/colour menu first


@pytest.mark.asyncio
async def test_process_topic_advances_to_slide_count_with_pricing_info(patched_handlers_db):
    state = FakeFSMContext()
    message = _message("Fotosintez jarayoni")

    await create_pres.process_topic(message, state)

    assert await state.get_state() == PresentationForm.slide_count
    assert (await state.get_data())["topic"] == "Fotosintez jarayoni"
    assert "Narxi" in message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
async def test_author_name_is_followed_by_the_level_buttons():
    state = FakeFSMContext()
    await create_pres.process_author_name(_message("Ali Valiyev"), state)
    assert await state.get_state() == PresentationForm.level


@pytest.mark.asyncio
async def test_level_is_followed_by_the_optional_institution():
    state = FakeFSMContext()
    message = _message("Maktab")
    await create_pres.process_level(message, state)
    assert await state.get_state() == PresentationForm.institution
    assert "ixtiyoriy" in message.calls_for("answer")[0]["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("level,first_button", [("Maktab", "1-sinf"), ("Universitet", "1-kurs"),
                                                ("Akademik litsey", "1-kurs")])
async def test_institution_then_class_buttons_match_the_level(level, first_button):
    state = FakeFSMContext()
    await state.update_data(level=level)
    message = _message("TATU")
    await create_pres.process_institution(message, state)
    assert await state.get_state() == PresentationForm.course
    assert (await state.get_data())["institution"] == "TATU"
    kb = message.calls_for("answer")[0]["reply_markup"]
    assert kb.keyboard[0][0].text == first_button


@pytest.mark.asyncio
async def test_institution_can_be_skipped_and_other_level_skips_the_class():
    state = FakeFSMContext()
    await state.update_data(level="Boshqa")
    await create_pres.process_institution(_message("⏭ O‘tkazib yuborish"), state)
    data = await state.get_data()
    assert data["institution"] == "" and data["course"] == ""
    assert await state.get_state() == PresentationForm.teacher_name


@pytest.mark.asyncio
async def test_process_course_advances_to_teacher_name():
    state = FakeFSMContext()

    await create_pres.process_course(_message("3-kurs"), state)

    assert await state.get_state() == PresentationForm.teacher_name
    assert (await state.get_data())["course"] == "3-kurs"


@pytest.mark.asyncio
async def test_teacher_is_followed_by_the_date_with_a_today_button():
    state = FakeFSMContext()
    message = _message("Karimova B.")
    await create_pres.process_teacher_name(message, state)
    assert await state.get_state() == PresentationForm.date
    kb = message.calls_for("answer")[0]["reply_markup"]
    assert kb.keyboard[0][0].text.startswith("📅 Bugun:")


@pytest.mark.asyncio
@pytest.mark.parametrize("typed,stored", [("📅 Bugun: 20.10.2026", "20.10.2026"), ("📅 2026-yil", "2026-yil"),
                                          ("25.10.2026", "25.10.2026"), ("⏭ O‘tkazib yuborish", "")])
async def test_date_buttons_and_typed_dates(typed, stored):
    state = FakeFSMContext()
    await create_pres.process_date(_message(typed), state)
    assert (await state.get_data())["date"] == stored
    assert await state.get_state() == PresentationForm.language


@pytest.mark.asyncio
@pytest.mark.parametrize("button_text,expected_code", [
    ("🇺🇿 O'zbekcha", "uz"),
    ("🇷🇺 Русский", "ru"),
    ("🇬🇧 English", "en"),
    ("something unexpected", "uz"),  # safe default
])
async def test_process_language_maps_button_text_to_language_code(button_text, expected_code):
    state = FakeFSMContext()

    await create_pres.process_language(_message(button_text), state)

    assert (await state.get_data())["language"] == expected_code
    assert await state.get_state() == PresentationForm.notes_choice


@pytest.mark.asyncio
async def test_notes_no_goes_straight_to_the_summary(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(subject="S", topic="T", slide_count=5, author_name="A", language="uz")
    await create_pres.process_notes_choice(_message("🚫 Yo‘q"), state)
    assert (await state.get_data())["additional_notes"] == ""
    assert await state.get_state() == PresentationForm.confirmation


@pytest.mark.asyncio
async def test_notes_yes_asks_for_the_wishes(patched_handlers_db):
    state = FakeFSMContext()
    await state.update_data(subject="S", topic="T", slide_count=5, author_name="A", language="uz")
    await create_pres.process_notes_choice(_message("✅ Ha, bor"), state)
    assert await state.get_state() == PresentationForm.additional_notes
    await create_pres.process_additional_notes(_message("Rasmlar ko‘p bo‘lsin"), state)
    assert (await state.get_data())["additional_notes"] == "Rasmlar ko‘p bo‘lsin"
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
async def test_picker_falls_back_when_telegram_rejects_the_webapp_url(monkeypatch):
    from aiogram.exceptions import TelegramBadRequest
    monkeypatch.setattr(create_pres.settings, "WEBAPP_URL", "https://bot.slidelab.uz/webapp/")
    monkeypatch.setattr(create_pres, "_webapp_disabled", False)
    message = _message("🎨 Presentation yaratish")
    sent = []

    async def answer_photo(photo, caption=None, reply_markup=None, parse_mode=None):
        has_webapp = any(getattr(b, "web_app", None) for row in reply_markup.inline_keyboard for b in row)
        if has_webapp:
            raise TelegramBadRequest(method=None, message="Bad Request: inline keyboard button Web App URL is invalid")
        sent.append(reply_markup)

    message.answer_photo = answer_photo
    await create_pres.start_pres_wizard(message, FakeFSMContext())
    assert len(sent) == 1 and create_pres.webapp_url() == ""
    monkeypatch.setattr(create_pres, "_webapp_disabled", False)
