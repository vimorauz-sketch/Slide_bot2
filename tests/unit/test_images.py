import io
from PIL import Image
from services.deck import images


def _jpeg(w=1600, h=1200):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 120, 60)).save(buf, "JPEG")
    return buf.getvalue()


def test_no_provider_is_enabled_without_keys(monkeypatch):
    # conftest disables every provider for the test suite
    assert images.enabled_providers() == []


def test_providers_follow_configured_keys(monkeypatch):
    monkeypatch.setattr("config.settings.PEXELS_API_KEY", "k")
    monkeypatch.setattr("config.settings.WIKIMEDIA_ENABLED", True)
    monkeypatch.setattr("config.settings.IMAGE_PROVIDERS", "wikimedia,pexels,openai")
    assert images.enabled_providers() == ["wikimedia", "pexels"]  # openverse disabled in tests
    monkeypatch.setattr("config.settings.OPENVERSE_ENABLED", True)
    assert images.enabled_providers() == ["openverse", "wikimedia", "pexels"]  # keyless photos added for old .env values


def test_crop_cover_produces_exact_slot_size():
    out = images._crop_cover(_jpeg(), (900, 1080))
    assert Image.open(io.BytesIO(out)).size == (900, 1080)
    assert images._crop_cover(_jpeg(200, 150), (900, 1080)) is None  # too small


async def test_resolver_downloads_once_then_uses_the_cache(monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.PEXELS_API_KEY", "k")
    calls = {"search": 0, "download": 0}

    async def fake_pexels(session, query, orientation):
        calls["search"] += 1
        return [{"id": "pexels:1", "url": "https://x/1.jpg", "credit": "Foto: A / Pexels"}]

    async def fake_bytes(session, url, headers=None):
        calls["download"] += 1
        return _jpeg()

    monkeypatch.setattr(images, "_pexels", fake_pexels)
    monkeypatch.setattr(images, "_get_bytes", fake_bytes)
    r1 = images.ImageResolver({"image_style": ""}, cache_dir=tmp_path)
    img = await r1.resolve(None, "green leaf", "", "photo", "text_image")
    assert img and img["src"].startswith("file:") and "Pexels" in img["credit"]
    r2 = images.ImageResolver({"image_style": ""}, cache_dir=tmp_path)
    img2 = await r2.resolve(None, "green leaf", "", "photo", "text_image")
    assert img2["src"] == img["src"]
    assert calls == {"search": 1, "download": 1}


async def test_resolve_images_writes_the_image_back_into_content(monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.PEXELS_API_KEY", "k")
    monkeypatch.setattr(images, "CACHE_DIR", tmp_path)

    async def fake_pexels(session, query, orientation):
        return [{"id": f"pexels:{query}", "url": "u", "credit": "c"}]

    async def fake_bytes(session, url, headers=None):
        return _jpeg()

    monkeypatch.setattr(images, "_pexels", fake_pexels)
    monkeypatch.setattr(images, "_get_bytes", fake_bytes)
    content = {"title_slide": {"title": "T", "visual": {"query": "cover"}},
               "slides": [{"layout": "text_image", "title": "A", "visual": {"query": "leaf"}},
                          {"layout": "cards", "title": "B", "items": []}]}
    found = await images.resolve_images(content, {"image_style": ""})
    assert set(found) == {0, 1}
    assert content["slides"][0]["image"]["src"].startswith("file:")
    assert "image" not in content["slides"][1]



async def test_openverse_results_are_parsed(monkeypatch):
    async def fake_json(session, url, headers, params):
        assert "openverse" in url and params["q"] == "coral reef"
        return {"results": [{"id": "abc", "url": "https://x/y.jpg", "width": 1600, "height": 900, "creator": "Ann",
                             "source": "flickr", "license": "by", "license_version": "2.0", "title": "Reef"},
                            {"id": "small", "url": "https://x/s.jpg", "width": 300, "height": 200}]}
    monkeypatch.setattr(images, "_get_json", fake_json)
    out = await images._openverse(None, "coral reef", "landscape")
    assert [o["id"] for o in out] == ["openverse:abc"]
    assert "Ann" in out[0]["credit"] and "CC BY 2.0" in out[0]["credit"]


async def test_item_photos_are_resolved_for_cards(monkeypatch, tmp_path):
    from PIL import Image as _I
    folder = tmp_path / "photos"
    folder.mkdir()
    for k in range(3):
        _I.new("RGB", (1600, 1100), (k * 60, 120, 200)).save(folder / f"p{k}.jpg")
    monkeypatch.setattr("config.settings.LOCAL_PHOTO_DIR", str(folder))
    content = {"title_slide": {"title": "Ekotizim"}, "slides": [
        {"layout": "cards", "title": "T", "items": [{"title": "Suv", "photo": "lake water"}, {"title": "Tuproq"}, {"title": "Havo"}]}]}
    found = await images.resolve_images(content, {"photo": True})
    items = content["slides"][0]["items"]
    assert all(it.get("image", {}).get("src", "").startswith("file:") for it in items)
    assert images.item_photo_query(items[1], content["slides"][0], "Ekotizim").endswith("Tuproq")
