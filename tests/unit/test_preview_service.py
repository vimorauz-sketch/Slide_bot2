import os
from PIL import Image
from services.preview_service import add_watermark_to_image, make_overview_grid, make_watermarked_previews, pick_preview_indices


def _pngs(tmp_path, n):
    out = []
    for i in range(n):
        p = os.path.join(tmp_path, f"s{i}.png")
        Image.new("RGB", (1920, 1080), (20 * i, 100, 150)).save(p)
        out.append(p)
    return out


def test_preview_picks_cover_and_a_content_slide():
    assert pick_preview_indices(10, 2) == [0, 2]
    assert pick_preview_indices(2, 2) == [0, 1]
    assert pick_preview_indices(0, 2) == []


def test_watermark_changes_the_image(tmp_path):
    src = _pngs(str(tmp_path), 1)[0]
    dst = os.path.join(tmp_path, "wm.jpg")
    add_watermark_to_image(src, dst)
    a = Image.open(src).convert("RGB").resize((96, 54))
    b = Image.open(dst).convert("RGB").resize((96, 54))
    assert list(a.getdata()) != list(b.getdata())


def test_previews_and_overview_are_written(tmp_path):
    pngs = _pngs(str(tmp_path), 7)
    previews = make_watermarked_previews(pngs, str(tmp_path), count=2)
    assert len(previews) == 2 and all(os.path.exists(p) for p in previews)
    grid = make_overview_grid(pngs, os.path.join(tmp_path, "grid.jpg"), watermark=True)
    w, h = Image.open(grid).size
    assert w > h  # 3 columns x 3 rows of 16:9 thumbnails
