"""Renders the Fotosintez sample deck in one or more themes and builds a contact sheet.

Usage: python scripts/render_sample.py [theme_id ...] [--out DIR] [--no-pptx]
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from services.deck import render_deck, shutdown_browser  # noqa: E402
from services.deck.themes import list_theme_ids  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def contact_sheet(pngs, path, cols=4, thumb_w=480):
    ims = [Image.open(p).convert("RGB") for p in pngs]
    th = int(thumb_w * 1080 / 1920)
    rows = (len(ims) + cols - 1) // cols
    gap = 12
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap, rows * th + (rows + 1) * gap), (40, 40, 46))
    for i, im in enumerate(ims):
        im = im.resize((thumb_w, th), Image.LANCZOS)
        sheet.paste(im, (gap + (i % cols) * (thumb_w + gap), gap + (i // cols) * (th + gap)))
    sheet.save(path, quality=88)
    return path


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("themes", nargs="*")
    ap.add_argument("--out", default=os.path.join(ROOT, "storage", "samples"))
    ap.add_argument("--no-pptx", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--content", default=os.path.join(ROOT, "tests", "fixtures", "fotosintez_content.json"))
    a = ap.parse_args()
    content = json.load(open(a.content, encoding="utf-8"))
    for tid in a.themes or list_theme_ids():
        t0 = time.time()
        out = os.path.join(a.out, tid)
        res = await render_deck(content, tid, out, want_pptx=not a.no_pptx, want_pdf=not a.no_pdf)
        sheet = contact_sheet(res.slide_pngs, os.path.join(a.out, f"{tid}_sheet.jpg"))
        fits = {f["i"] + 1: f["fit"] for f in res.fit if f["fit"] < 1}
        bad = [f["i"] + 1 for f in res.fit if f["overflow"]]
        print(f"{tid}: {len(res.slide_pngs)} slides in {time.time() - t0:.1f}s; shrunk={fits} overflow={bad} -> {sheet}")
    await shutdown_browser()


if __name__ == "__main__":
    asyncio.run(main())
