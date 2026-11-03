"""Admin AI studio and template manager: drafts are generated (offline mode without an OpenAI key), published
templates appear in the bot and the Mini App catalog, hide/disable/delete work, test jobs finish with
downloadable files, promo texts reach the broadcast page, and every page / link of the panel opens."""
import asyncio
import re
from html import unescape

import pytest

from services import admin_studio, custom_templates as ct, runtime
from services.deck import themes
from services.referat import designs
from tests.integration import test_admin_dashboard as dash
from tests.integration.test_admin_dashboard import _csrf, _login

env = dash.env          # the dashboard's fixture: seeded DB + signed-in test client


@pytest.fixture(autouse=True)
def _clean(no_openai_key):
    yield
    themes.set_custom([])
    designs.set_custom([])
    admin_studio.JOBS.clear()


async def _post(client, path, data, csrf):
    return await client.post(path, data={"csrf": csrf, **data}, allow_redirects=False)


async def test_slide_draft_publish_and_catalog(env):
    client, *_ = env
    await _login(client)
    csrf = await _csrf(client, "/admin/studio")
    r = await _post(client, "/admin/studio/generate/slide", {"prompt": "kosmos bolalar uchun", "count": "2"}, csrf)
    assert r.status in (302, 303)
    html = await (await client.get("/admin/studio?tab=slide")).text()
    drafts = re.findall(r'name="draft" value="([^"]+)"', html)
    assert len(drafts) == 2
    pic = re.search(r'src="(/admin/studio/preview/[^"]+)"', html)
    assert pic and (await client.get(unescape(pic.group(1)))).status == 200

    r = await _post(client, "/admin/studio/publish/slide", {"draft": drafts[0], "name": "Kosmik sinf"}, csrf)
    assert r.status in (302, 303) and "/admin/templates" in r.headers["Location"]
    rows = await ct.list_all("slide")
    assert len(rows) == 1 and rows[0].code == ct.SLIDE_START and rows[0].name == "Kosmik sinf"
    tid = rows[0].id
    assert tid in themes.list_theme_ids()

    cat = await (await client.get("/webapp/catalog.json")).json()
    items = cat["themes"]
    assert any(t["id"] == tid and t.get("ai") for t in items)

    page = await (await client.get("/admin/templates?k=slide&f=ai")).text()
    assert "Kosmik sinf" in page

    # hide -> gone from the catalog; show -> back
    assert (await _post(client, f"/admin/templates/slide/{tid}/hide", {}, csrf)).status in (302, 303)
    assert tid in runtime.hidden_templates("slide")
    cat = await (await client.get("/webapp/catalog.json")).json()
    items = cat["themes"]
    assert not any(t["id"] == tid for t in items)
    await _post(client, f"/admin/templates/slide/{tid}/show", {}, csrf)
    assert tid not in runtime.hidden_templates("slide")

    # disable -> out of the bot; delete -> gone
    await _post(client, f"/admin/templates/slide/{tid}/disable", {}, csrf)
    assert tid not in themes.list_theme_ids()
    await _post(client, f"/admin/templates/slide/{tid}/delete", {}, csrf)
    assert await ct.list_all("slide") == []


async def test_referat_draft_publish(env):
    client, *_ = env
    await _login(client)
    csrf = await _csrf(client, "/admin/studio?tab=referat")
    await _post(client, "/admin/studio/generate/referat", {"prompt": "milliy naqsh, bordo va oltin", "count": "1"}, csrf)
    html = await (await client.get("/admin/studio?tab=referat")).text()
    draft = re.search(r'name="draft" value="([^"]+)"', html).group(1)
    pic = re.search(r'src="(/admin/studio/rpreview/[^"]+)"', html)
    assert pic and (await client.get(unescape(pic.group(1)))).status == 200
    await _post(client, "/admin/studio/publish/referat", {"draft": draft}, csrf)
    rows = await ct.list_all("referat")
    assert len(rows) == 1 and rows[0].code == ct.REFERAT_START
    assert designs.has_number(ct.REFERAT_START) and rows[0].id in designs.BY_ID


async def test_empty_prompt_and_unknown_draft_are_refused(env):
    client, *_ = env
    await _login(client)
    csrf = await _csrf(client, "/admin/studio")
    r = await _post(client, "/admin/studio/generate/slide", {"prompt": "  "}, csrf)
    assert r.status in (302, 303)
    r = await _post(client, "/admin/studio/publish/slide", {"draft": "draft_nope"}, csrf)
    assert r.status in (302, 303) and "/admin/studio" in r.headers["Location"]
    assert await ct.list_all() == []
    r = await _post(client, "/admin/templates/slide/05_nature_organic/delete", {}, csrf)
    assert r.status in (302, 303)        # a built-in template can't be deleted
    assert "05_nature_organic" in themes.list_theme_ids()


async def test_test_job_runs_and_serves_files(env, monkeypatch, tmp_path):
    client, *_ = env
    await _login(client)
    csrf = await _csrf(client, "/admin/studio?tab=test")
    monkeypatch.setattr(admin_studio, "STUDIO_DIR", str(tmp_path))

    async def fake_deck(job, progress):
        await progress("render", 1, 2)
        pdf, png = tmp_path / "t.pdf", tmp_path / "s1.png"
        pdf.write_bytes(b"%PDF-1.4 test")
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        job.files, job.pictures = {"pdf": str(pdf)}, [str(png)]
    monkeypatch.setattr(admin_studio, "_deck", fake_deck)

    r = await _post(client, "/admin/studio/test", {"kind": "deck", "topic": "Quyosh tizimi",
                                                    "template": "05_nature_organic", "slides": "6"}, csrf)
    assert r.status in (302, 303)
    jid = re.search(r"job=([0-9a-f]+)", r.headers["Location"]).group(1)
    await asyncio.wait_for(admin_studio.get(jid).task, 10)
    assert admin_studio.get(jid).status == "done"
    html = await (await client.get(f"/admin/studio?tab=test&job={jid}")).text()
    assert "Quyosh tizimi" in html and f"/admin/studio/job/{jid}/pdf" in html
    assert (await client.get(f"/admin/studio/job/{jid}/pdf")).status == 200
    assert (await client.get(f"/admin/studio/job/{jid}/0")).status == 200
    assert (await client.get(f"/admin/studio/job/{jid}/pptx")).status == 404


async def test_promo_texts_go_to_broadcast(env):
    client, *_ = env
    await _login(client)
    csrf = await _csrf(client, "/admin/studio?tab=text")
    r = await _post(client, "/admin/studio/text", {"brief": "50 ta yangi shablon qo'shildi", "tone": "friendly"}, csrf)
    assert r.status in (200, 302, 303)
    html = await (await client.get("/admin/studio?tab=text")).text() if r.status != 200 else await r.text()
    link = re.search(r'href="(/admin/broadcast\?text=[^"]+)"', html)
    assert link
    page = await (await client.get(unescape(link.group(1)))).text()
    assert "50 ta yangi shablon" in unescape(page)


async def test_every_admin_link_opens(env):
    """Crawls the panel from the home page: every internal GET link answers below 400."""
    client, *_ = env
    await _login(client)
    seen, todo, bad = set(), ["/admin"], []
    skip = re.compile(r"/admin/(logout|login)|\.csv|/admin/studio/job/|/admin/orders/\d+/(file|pdf)")
    while todo and len(seen) < 120:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        r = await client.get(path, allow_redirects=False)
        if r.status >= 400:
            bad.append((path, r.status))
            continue
        if "text/html" not in r.headers.get("Content-Type", ""):
            continue
        for href in re.findall(r'href="([^"#]+)"', await r.text()):
            href = unescape(href)
            if href.startswith("?"):
                href = path.split("?")[0] + href
            if href.startswith("/admin") and not skip.search(href) and href not in seen:
                todo.append(href)
    assert not bad, bad
    for must in ("/admin/studio", "/admin/templates", "/admin/security", "/admin/settings", "/admin/system"):
        assert any(p.split("?")[0] == must for p in seen), must
