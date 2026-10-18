"""Builds the template gallery images and catalogue.

Writes
  webapp/thumbs/<template>/<n>.webp     6 preview slides in the default colours (Mini App)
  webapp/thumbs/<template>/c/<slug>.webp cover in each other colour set (Mini App colour grid)
  webapp/catalog.json                   templates, colours and categories for the Mini App
  themes/overview.jpg                   mosaic of covers (first picker message in the bot)
Other colours' full previews are rendered on demand by the bot server (services/gallery.py).

Usage: python scripts/build_gallery.py [template_id ...] [--skip-render] [--no-colors]
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from services import gallery  # noqa: E402
from services.deck import shutdown_browser  # noqa: E402
from services.deck.themes import CATEGORIES, catalog, list_theme_ids, theme_colors  # noqa: E402


async def render_all(ids, colors=True):
    try:
        for k, tid in enumerate(ids):
            t0 = time.time()
            await gallery.render_set(tid, os.path.join(gallery.THUMBS_DIR, tid))
            if colors:
                cdir = os.path.join(gallery.THUMBS_DIR, tid, "c")
                os.makedirs(cdir, exist_ok=True)
                for c in theme_colors(tid)[1:]:
                    tmp = os.path.join(cdir, "_tmp")
                    paths = await gallery.render_set(c["key"], tmp, cover_only=True, size=gallery.COVER_SIZE, quality=70)
                    shutil.move(paths[0], os.path.join(cdir, f"{c['slug']}.webp"))
                    shutil.rmtree(tmp, ignore_errors=True)
            print(f"[{k + 1}/{len(ids)}] {tid} {time.time() - t0:.1f}s", flush=True)
    finally:
        await shutdown_browser()


def build_catalog():
    cat = catalog()
    for t in cat:
        d = os.path.join(gallery.THUMBS_DIR, t["id"])
        t["previews"] = len([f for f in os.listdir(d) if f.endswith(".webp")]) if os.path.isdir(d) else 0
    cats = [{"key": k, "label": lbl, "emoji": e, "count": sum(k in t["categories"] for t in cat)} for k, lbl, e, _ in CATEGORIES]
    with open(os.path.join(gallery.WEBAPP_DIR, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump({"categories": cats, "themes": cat}, f, ensure_ascii=False, separators=(",", ":"))
    # overview mosaic: 40 covers spread over the catalogue
    ids = [t["id"] for t in cat]
    pick = ids[:20:2] + ids[20::6]
    pick = pick[:40]
    tw, th, cols = 300, 169, 8
    rows = (len(pick) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 6, rows * th + (rows + 1) * 6), (18, 18, 24))
    for i, tid in enumerate(pick):
        p = os.path.join(gallery.THUMBS_DIR, tid, "0.webp")
        if os.path.exists(p):
            sheet.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (6 + (i % cols) * (tw + 6), 6 + (i // cols) * (th + 6)))
    sheet.save(os.path.join(ROOT, "themes", "overview.jpg"), quality=86)
    shutil.rmtree(gallery.GALLERY_CACHE, ignore_errors=True)
    print(f"catalog: {len(cat)} templates, {sum(len(t['colors']) for t in cat)} colour sets")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("templates", nargs="*")
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--no-colors", action="store_true")
    a = ap.parse_args()
    if not a.skip_render:
        asyncio.run(render_all(a.templates or list_theme_ids(), colors=not a.no_colors))
    build_catalog()


if __name__ == "__main__":
    main()
