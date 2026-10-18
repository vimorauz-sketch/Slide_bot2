import json
import pytest
from services import ai_service
from tests.fixtures.openai_fakes import FakeOpenAIClient


# ---------------------------------------------------------------------------
# deck structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [5, 6, 7, 8, 10, 12, 15, 20, 30])
def test_mock_outline_has_exactly_the_requested_slide_count(n):
    outline = ai_service.generate_mock_outline({"topic": "T", "subject": "S", "slide_count": n})
    assert 1 + len(outline["slides"]) == n


@pytest.mark.parametrize("n", [5, 8, 10, 15, 30])
def test_outline_never_repeats_a_layout_on_neighbouring_slides(n):
    outline = ai_service.generate_mock_outline({"topic": "T", "slide_count": n})
    layouts = [s["layout"] for s in outline["slides"]]
    assert all(a != b for a, b in zip(layouts, layouts[1:])), layouts


def test_structure_adds_agenda_summary_references_and_closing_by_size():
    small, big = ai_service.plan_structure(5), ai_service.plan_structure(15)
    assert not small["agenda"] and not small["closing"] and small["summary"]
    assert big["agenda"] and big["closing"] and big["references"]
    assert ai_service.plan_structure(8, notes="adabiyotlar ro‘yxati bo‘lsin")["references"]


def test_enforce_outline_fixes_length_rare_layouts_and_neighbours():
    proposed = [{"layout": "quote"}, {"layout": "quote"}, {"layout": "chart"}, {"layout": "chart"},
                {"layout": "chart"}, {"layout": "cards"}, {"layout": "cards"}, {"layout": "summary", "title": "Yakun"}]
    slides = ai_service.enforce_outline(proposed, 10)
    layouts = [s["layout"] for s in slides]
    assert len(slides) == 9
    assert layouts[0] == "agenda" and layouts[-2:] == ["summary", "closing"]
    assert layouts.count("quote") <= 1 and layouts.count("chart") <= 2
    assert all(a != b for a, b in zip(layouts, layouts[1:]))
    assert slides[-2]["title"] == "Yakun"  # the model's title for a fixed slide is kept


def test_outline_text_numbers_slides_from_two():
    outline = ai_service.generate_mock_outline({"topic": "Fotosintez", "slide_count": 6})
    text = ai_service.outline_to_text(outline, "uz")
    assert text.splitlines()[0].startswith("1. Fotosintez")
    assert text.splitlines()[-1].startswith("6. ")


# ---------------------------------------------------------------------------
# mock presentation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [5, 6, 10, 15, 30])
def test_mock_presentation_total_slide_count_matches_request(n):
    content = ai_service.generate_mock_presentation({"topic": "T", "subject": "S", "slide_count": n})
    assert 1 + len(content["slides"]) == n
    assert any(s["layout"] == "summary" for s in content["slides"])


def test_mock_presentation_enforces_a_five_slide_floor_and_defaults():
    assert 1 + len(ai_service.generate_mock_presentation({"slide_count": 1})["slides"]) == 5
    content = ai_service.generate_mock_presentation({})
    assert content["title_slide"]["author"] and content["title_slide"]["institution"]
    assert 1 + len(content["slides"]) == 10


def test_mock_presentation_uses_provided_author_and_institution():
    content = ai_service.generate_mock_presentation({
        "topic": "Fotosintez", "subject": "Biologiya", "slide_count": 5,
        "author_name": "Jasur Aliyev", "institution": "TATU", "teacher_name": "B. Karimova"})
    ts = content["title_slide"]
    assert (ts["author"], ts["institution"], ts["teacher"], ts["title"]) == ("Jasur Aliyev", "TATU", "B. Karimova", "Fotosintez")


def test_mock_presentation_follows_a_given_outline():
    outline = ai_service.generate_mock_outline({"topic": "T", "slide_count": 8})
    content = ai_service.generate_mock_presentation({"topic": "T", "slide_count": 8}, outline)
    assert [s["layout"] for s in content["slides"]] == [s["layout"] for s in outline["slides"]]


# ---------------------------------------------------------------------------
# AI paths (fake client)
# ---------------------------------------------------------------------------

async def test_outline_uses_mock_without_api_key(no_openai_key):
    outline = await ai_service.generate_outline({"topic": "T", "slide_count": 7})
    assert outline["source"] == "mock" and len(outline["slides"]) == 6


async def test_outline_from_model_is_enforced(monkeypatch):
    payload = json.dumps({"title": "Fotosintez", "subtitle": "s", "slides": [
        {"title": f"S{i}", "key_point": "k", "layout": "cards"} for i in range(12)]})
    fake = FakeOpenAIClient(payload)
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: fake)
    outline = await ai_service.generate_outline({"topic": "T", "slide_count": 10, "language": "uz"})
    layouts = [s["layout"] for s in outline["slides"]]
    assert len(layouts) == 9 and layouts[0] == "agenda"
    assert all(a != b for a, b in zip(layouts, layouts[1:]))
    system = fake.last_call_kwargs["messages"][0]["content"]
    assert "o‘ and g‘" in system and "cycle" in system


async def test_outline_feedback_is_sent_to_the_model(monkeypatch):
    fake = FakeOpenAIClient(json.dumps({"title": "T", "slides": []}))
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: fake)
    prev = ai_service.generate_mock_outline({"topic": "T", "slide_count": 6})
    await ai_service.generate_outline({"topic": "T", "slide_count": 6}, feedback="Kalvin siklini qo‘sh", previous=prev)
    assert "Kalvin siklini qo‘sh" in fake.last_call_kwargs["messages"][1]["content"]


async def test_outline_falls_back_to_mock_on_api_error(monkeypatch):
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: FakeOpenAIClient(ConnectionError("down")))
    outline = await ai_service.generate_outline({"topic": "T", "slide_count": 6})
    assert outline["source"] == "mock"


async def test_content_uses_mock_when_no_api_key(no_openai_key):
    content = await ai_service.generate_presentation_content({"topic": "T", "subject": "S", "slide_count": 5})
    assert content["meta"]["source"] == "mock" and 1 + len(content["slides"]) == 5


async def test_content_survives_api_errors_slide_by_slide(monkeypatch):
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: FakeOpenAIClient(ConnectionError("down")))
    outline = ai_service.generate_mock_outline({"topic": "T", "slide_count": 6})
    content = await ai_service.generate_presentation_content({"topic": "T", "slide_count": 6}, outline)
    assert len(content["slides"]) == 5
    assert all(s["layout"] for s in content["slides"])


async def test_content_keeps_caller_author_and_layout_from_outline(monkeypatch):
    payload = json.dumps({"title": "Slayd", "items": [{"icon": "leaf", "title": "A", "text": "B"}] * 3,
                          "visual": {"kind": "photo", "query": "leaf"}, "notes": "n", "author": "AI-guess"})
    fake = FakeOpenAIClient(payload)
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: fake)
    outline = ai_service.generate_mock_outline({"topic": "T", "slide_count": 6})
    content = await ai_service.generate_presentation_content(
        {"topic": "T", "slide_count": 6, "author_name": "Real Author", "institution": "Real School"}, outline)
    assert content["title_slide"]["author"] == "Real Author"
    assert content["title_slide"]["institution"] == "Real School"
    assert [s["layout"] for s in content["slides"]] == [s["layout"] for s in outline["slides"]]


async def test_slide_prompt_contains_layout_shape_and_icon_list(monkeypatch):
    fake = FakeOpenAIClient(json.dumps({"title": "x", "steps": [{"title": "a", "text": "b"}] * 3}))
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: fake)
    outline = {"title": "T", "slides": [{"layout": "process", "title": "Bosqichlar", "key_point": "k"}]}
    await ai_service.generate_presentation_content({"topic": "T", "slide_count": 2}, outline)
    system = fake.last_call_kwargs["messages"][0]["content"]
    assert "'process'" in system or "Layout" in system


# ---------------------------------------------------------------------------
# parse_task_image / custom design (unchanged behaviour)
# ---------------------------------------------------------------------------

async def test_parse_task_image_returns_fallback_when_no_api_key(no_openai_key):
    result = await ai_service.parse_task_image(b"fake-bytes")
    assert result["subject"] == "Biologiya" and "missing_fields" in result


async def test_parse_task_image_returns_parsed_json_on_success(monkeypatch):
    payload = json.dumps({"subject": "Fizika", "topic": "Kvant", "slide_count": 12, "language": "uz",
                          "requirements": "", "missing_fields": []})
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: FakeOpenAIClient(payload))
    result = await ai_service.parse_task_image(b"fake-bytes")
    assert result["subject"] == "Fizika" and result["slide_count"] == 12


async def test_parse_task_image_falls_back_on_errors(monkeypatch):
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: FakeOpenAIClient("not json {{"))
    result = await ai_service.parse_task_image(b"x")
    assert "subject" in result and "topic" in result


async def test_custom_design_spec_mock_and_success(monkeypatch, no_openai_key):
    spec = await ai_service.generate_custom_design_spec("blue minimal")
    assert spec["primary_color"].startswith("#")
    payload = json.dumps({"primary_color": "#123456", "accent_color": "#654321", "background_color": "#FFFFFF"})
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: FakeOpenAIClient(payload))
    assert (await ai_service.generate_custom_design_spec("x"))["primary_color"] == "#123456"
    monkeypatch.setattr(ai_service, "get_openai_client", lambda: FakeOpenAIClient(RuntimeError("boom")))
    assert (await ai_service.generate_custom_design_spec("x"))["primary_color"].startswith("#")
