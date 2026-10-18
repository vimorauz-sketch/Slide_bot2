"""Telegram previews: watermarked slide images and a low-resolution overview of the whole deck."""
from __future__ import annotations

import os
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

WATERMARK = "SLIDELAB • PREVIEW • @SlideLabBot"
_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")


def _font(size: int) -> ImageFont.ImageFont:
    for cand in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


def add_watermark_to_image(input_image_path: str, output_image_path: str, watermark_text: str = WATERMARK,
                           opacity: int = 70) -> str:
    """Tiles a diagonal semi-transparent watermark over the whole image."""
    base = Image.open(input_image_path).convert("RGBA")
    w, h = base.size
    layer = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(max(18, w // 45))
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    step_x, step_y = tw + w // 10, th * 5
    for row, y in enumerate(range(0, h * 2, step_y)):
        offset = (row % 2) * step_x // 2
        for x in range(-step_x, w * 2, step_x):
            draw.text((x + offset, y), watermark_text, font=font, fill=(255, 255, 255, opacity), stroke_width=2,
                      stroke_fill=(0, 0, 0, opacity // 2))
    layer = layer.rotate(24, resample=Image.BICUBIC)
    layer = layer.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
    out = Image.alpha_composite(base, layer).convert("RGB")
    out.save(output_image_path, "JPEG", quality=88)
    return output_image_path


def pick_preview_indices(n_slides: int, count: int = 2) -> List[int]:
    """Cover first, then the most visual early content slide (slide 3 when it exists)."""
    if n_slides <= 0:
        return []
    picks = [0]
    for cand in (2, 1, 3):
        if len(picks) >= count:
            break
        if cand < n_slides and cand not in picks:
            picks.append(cand)
    return picks[:count]


def make_watermarked_previews(slide_pngs: List[str], out_dir: str, count: int = 2) -> List[str]:
    out = []
    for k, i in enumerate(pick_preview_indices(len(slide_pngs), count)):
        dst = os.path.join(out_dir, f"preview_slide_{k + 1}_wm.jpg")
        add_watermark_to_image(slide_pngs[i], dst)
        out.append(dst)
    return out


def make_overview_grid(slide_pngs: List[str], path: str, watermark: bool = False, cols: Optional[int] = None,
                       thumb_w: int = 360) -> Optional[str]:
    """All slides as small thumbnails in one picture (shown before payment, watermarked)."""
    if not slide_pngs:
        return None
    n = len(slide_pngs)
    cols = cols or (3 if n <= 9 else 4)
    th = int(thumb_w * 9 / 16)
    gap = 10
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap, rows * th + (rows + 1) * gap), (24, 24, 30))
    for i, p in enumerate(slide_pngs):
        im = Image.open(p).convert("RGB").resize((thumb_w, th), Image.LANCZOS)
        sheet.paste(im, (gap + (i % cols) * (thumb_w + gap), gap + (i // cols) * (th + gap)))
    sheet.save(path, "JPEG", quality=85)
    if watermark:
        add_watermark_to_image(path, path, opacity=60)
    return path
