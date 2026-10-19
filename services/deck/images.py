"""
Image resolution for slides.

Order (configurable with IMAGE_PROVIDERS): Pexels -> Pixabay -> Unsplash -> Openverse -> Wikimedia Commons ->
OpenAI image generation (only when AI_IMAGES_ENABLED). Providers without a key are skipped;
Openverse and Wikimedia need no key, so real photos work out of the box (Pexels gives the best ones).
Photo templates also get one photo per card / step / list item (resolve_item_photos). Anything
not found falls back to the theme's own generated art in the renderer, so a slide never ends
up empty. Downloads are cached on disk by query, and the chosen image is written back into
the content JSON so re-rendering (e.g. after payment) never hits the network again.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "storage" / "image_cache"
UA = "SlideLabBot/2.0 (Telegram presentation generator; contact via bot)"
TIMEOUT_S = 10

# Slot sizes the renderer uses (px at 1x): the downloaded image is cropped to cover them.
SLOT_PORTRAIT = (900, 1080)
SLOT_LANDSCAPE = (1920, 1080)
SLOT_ITEM = (960, 680)
PORTRAIT_LAYOUTS = {"text_image", "icon_list", "quote", "section", "stats", "summary", "agenda"}
ITEM_PHOTO_LAYOUTS = {"cards": "items", "process": "steps", "icon_list": "items"}
MAX_ITEM_PHOTOS = 24


def _settings():
    try:
        from config import settings
        return settings
    except Exception:  # pragma: no cover - config always importable inside the bot
        return None


def _cfg(name: str, default: Any = "") -> Any:
    s = _settings()
    return getattr(s, name, default) if s is not None else os.environ.get(name, default)


def enabled_providers() -> List[str]:
    order = [p.strip().lower() for p in str(_cfg("IMAGE_PROVIDERS", "pexels,pixabay,unsplash,openverse,wikimedia,openai")).split(",") if p.strip()]
    if "openverse" not in order and "wikimedia" in order:  # older .env values: add the keyless photo source
        order.insert(order.index("wikimedia"), "openverse")
    if "pixabay" not in order:
        order.insert(1 if order and order[0] == "pexels" else 0, "pixabay")
    out = []
    if _cfg("LOCAL_PHOTO_DIR") and os.path.isdir(str(_cfg("LOCAL_PHOTO_DIR"))):
        out.append("local")  # development / offline previews
    for p in order:
        if p == "openverse" and str(_cfg("OPENVERSE_ENABLED", True)).lower() not in ("0", "false", "no"):
            out.append(p)
            continue
        if p == "pexels" and _cfg("PEXELS_API_KEY"):
            out.append(p)
        elif p == "pixabay" and _cfg("PIXABAY_API_KEY"):
            out.append(p)
        elif p == "unsplash" and _cfg("UNSPLASH_ACCESS_KEY"):
            out.append(p)
        elif p == "wikimedia" and str(_cfg("WIKIMEDIA_ENABLED", True)).lower() not in ("0", "false", "no"):
            out.append(p)
        elif p == "openai" and str(_cfg("AI_IMAGES_ENABLED", False)).lower() in ("1", "true", "yes") and \
                str(_cfg("OPENAI_API_KEY", "")).startswith("sk-"):
            out.append(p)
    return out


# ------------------------------------------------------------------ helpers
def _key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]


def _crop_cover(data: bytes, size: Tuple[int, int]) -> Optional[bytes]:
    """Center-crops and downsizes to exactly cover `size`; returns JPEG bytes."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return None
    tw, th = size
    if im.width < tw * 0.5 or im.height < th * 0.5:
        return None  # too small to look good
    scale = max(tw / im.width, th / im.height)
    nw, nh = max(tw, int(im.width * scale + 0.5)), max(th, int(im.height * scale + 0.5))
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 3  # keep a little more of the top (faces, skies)
    im = im.crop((left, top, left + tw, top + th))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
    return buf.getvalue()


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


async def _get_json(session, url: str, headers: Dict[str, str], params: Dict[str, Any]) -> Optional[dict]:
    try:
        async with session.get(url, headers=headers, params=params, timeout=TIMEOUT_S) as r:
            if r.status != 200:
                logger.info("image search %s -> HTTP %s", url, r.status)
                return None
            return await r.json(content_type=None)
    except Exception as e:  # network errors are expected offline; fall through to art
        logger.info("image search failed (%s): %s", url, e)
        return None


async def _get_bytes(session, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[bytes]:
    try:
        async with session.get(url, headers=headers or {"User-Agent": UA}, timeout=TIMEOUT_S * 2) as r:
            if r.status != 200:
                return None
            return await r.read()
    except Exception as e:
        logger.info("image download failed (%s): %s", url, e)
        return None


# ------------------------------------------------------------------ providers
async def _pexels(session, query: str, orientation: str) -> List[Dict[str, Any]]:
    data = await _get_json(session, "https://api.pexels.com/v1/search",
                           {"Authorization": str(_cfg("PEXELS_API_KEY")), "User-Agent": UA},
                           {"query": query, "per_page": 8, "orientation": orientation})
    out = []
    for p in (data or {}).get("photos", []):
        src = p.get("src", {})
        url = src.get("portrait") if orientation == "portrait" else src.get("large2x") or src.get("large")
        if url:
            out.append({"id": f"pexels:{p.get('id')}", "url": url, "w": p.get("width", 0), "h": p.get("height", 0),
                        "credit": f"Foto: {p.get('photographer', '')} / Pexels", "alt": p.get("alt", "")})
    return out


async def _pixabay(session, query: str, orientation: str) -> List[Dict[str, Any]]:
    """Pixabay: free key (shown on pixabay.com/api/docs after signing in), high quality stock photos."""
    data = await _get_json(session, "https://pixabay.com/api/", {"User-Agent": UA}, {
        "key": str(_cfg("PIXABAY_API_KEY")), "q": query[:100], "image_type": "photo", "safesearch": "true",
        "orientation": "vertical" if orientation == "portrait" else "horizontal", "per_page": 12, "min_width": 1000,
    })
    out = []
    for p in (data or {}).get("hits", []):
        url = p.get("largeImageURL") or p.get("webformatURL")
        if url:
            out.append({"id": f"pixabay:{p.get('id')}", "url": url, "w": p.get("imageWidth", 0), "h": p.get("imageHeight", 0),
                        "credit": f"Foto: {p.get('user', '')} / Pixabay", "alt": p.get("tags", "")})
    return out


async def _unsplash(session, query: str, orientation: str) -> List[Dict[str, Any]]:
    data = await _get_json(session, "https://api.unsplash.com/search/photos",
                           {"Authorization": f"Client-ID {_cfg('UNSPLASH_ACCESS_KEY')}", "Accept-Version": "v1"},
                           {"query": query, "per_page": 8, "orientation": orientation, "content_filter": "high"})
    out = []
    for p in (data or {}).get("results", []):
        raw = (p.get("urls") or {}).get("raw")
        if not raw:
            continue
        w = 1000 if orientation == "portrait" else 1920
        out.append({"id": f"unsplash:{p.get('id')}", "url": f"{raw}&w={w}&q=80&fm=jpg&fit=max",
                    "w": p.get("width", 0), "h": p.get("height", 0),
                    "credit": f"Foto: {(p.get('user') or {}).get('name', '')} / Unsplash",
                    "alt": p.get("alt_description") or "",
                    "ping": (p.get("links") or {}).get("download_location")})
    return out


async def _wikimedia(session, query: str, orientation: str) -> List[Dict[str, Any]]:
    data = await _get_json(session, "https://commons.wikimedia.org/w/api.php", {"User-Agent": UA}, {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 10,
        "gsrsearch": f"filetype:bitmap {query}", "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime",
        "iiurlwidth": 1600,
    })
    out = []
    pages = ((data or {}).get("query") or {}).get("pages") or {}
    for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
            continue
        if info.get("width", 0) < 800:
            continue
        if not _looks_like_photo(p.get("title", "")):
            continue
        meta = info.get("extmetadata") or {}
        artist = _strip_html((meta.get("Artist") or {}).get("value", ""))[:60]
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        out.append({"id": f"wikimedia:{p.get('pageid')}", "url": info.get("thumburl") or info.get("url"),
                    "w": info.get("width", 0), "h": info.get("height", 0),
                    "credit": f"{artist} / Wikimedia Commons{', ' + lic if lic else ''}".strip(" /"),
                    "alt": p.get("title", "")})
    return out


_NOT_PHOTO = re.compile(r"\b(map|satellite|diagram|chart|logo|icon|svg|drawing|scheme|schema|graph|plan|flag|coat of arms|"
                        r"text|document|page|scan|stamp|poster|illustration|clipart|nasa|landsat|modis)\b", re.I)


_STRONG_NOT_PHOTO = re.compile(r"\b(map|satellite|diagram|landsat|nasa|modis|infographic)\b", re.I)


def _looks_like_photo(title: str) -> bool:
    return not _NOT_PHOTO.search(title or "")


async def _openverse(session, query: str, orientation: str) -> List[Dict[str, Any]]:
    """Openverse (WordPress.org): openly licensed photos from Flickr, Wikimedia and others, no key."""
    data = await _get_json(session, "https://api.openverse.org/v1/images/", {"User-Agent": UA}, {
        "q": query, "page_size": 12, "license_type": "commercial", "category": "photograph",
        "aspect_ratio": "tall" if orientation == "portrait" else "wide", "mature": "false",
    })
    if not (data or {}).get("results"):  # retry without the optional filters
        data = await _get_json(session, "https://api.openverse.org/v1/images/", {"User-Agent": UA},
                               {"q": query, "page_size": 12, "license_type": "commercial"})
    out = []
    for p in (data or {}).get("results", []):
        if (p.get("width") or 0) and p["width"] < 700:
            continue
        tags = " ".join(t.get("name", "") for t in (p.get("tags") or [])[:10] if isinstance(t, dict))
        if not _looks_like_photo(p.get("title", "")) or _STRONG_NOT_PHOTO.search(tags):
            continue
        lic = f"CC {str(p.get('license', '')).upper()} {p.get('license_version', '')}".strip()
        out.append({"id": f"openverse:{p.get('id')}", "url": p.get("url"), "w": p.get("width", 0), "h": p.get("height", 0),
                    "credit": f"Foto: {(p.get('creator') or '')[:40]} / {p.get('source', 'Openverse')}, {lic}".strip(),
                    "alt": p.get("title", "")})
    return out


def _local(query: str) -> List[Dict[str, Any]]:
    """Photos from LOCAL_PHOTO_DIR (development only), chosen deterministically from the query."""
    folder = Path(str(_cfg("LOCAL_PHOTO_DIR")))
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if not files:
        return []
    start = int(_key(query.lower()), 16) % len(files)
    return [{"id": f"local:{files[(start + k) % len(files)].name}", "path": str(files[(start + k) % len(files)]), "credit": ""}
            for k in range(len(files))]


async def _openai_image(prompt: str, orientation: str) -> Optional[bytes]:
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=str(_cfg("OPENAI_API_KEY")))
        size = "1024x1536" if orientation == "portrait" else "1536x1024"
        resp = await client.images.generate(model=str(_cfg("OPENAI_IMAGE_MODEL", "gpt-image-1")), prompt=prompt,
                                            size=size, quality=str(_cfg("OPENAI_IMAGE_QUALITY", "medium")), n=1)
        b64 = resp.data[0].b64_json
        return base64.b64decode(b64) if b64 else None
    except Exception as e:
        logger.warning("AI image generation failed: %s", e)
        return None


# ------------------------------------------------------------------ resolver
class ImageResolver:
    def __init__(self, theme: Dict[str, Any], cache_dir: Optional[Path] = None):
        self.theme = theme
        self.cache_dir = Path(cache_dir or CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.providers = enabled_providers()
        self.used: set = set()
        self.sem = asyncio.Semaphore(6)

    def _cache_paths(self, key: str) -> Tuple[Path, Path]:
        return self.cache_dir / f"{key}.jpg", self.cache_dir / f"{key}.json"

    async def resolve(self, session, query: str, prompt: str, kind: str, layout: str) -> Optional[Dict[str, Any]]:
        if not query or kind == "none" or not self.providers:
            return None
        if layout == "item":
            orientation, slot = "landscape", SLOT_ITEM
        else:
            orientation = "portrait" if layout in PORTRAIT_LAYOUTS or layout == "cover" else "landscape"
            slot = SLOT_PORTRAIT if orientation == "portrait" else SLOT_LANDSCAPE
        order = list(self.providers)
        if kind == "illustration":  # scientific / historical pictures: generated or encyclopedic first
            order = [p for p in ("openai", "wikimedia") if p in order] + [p for p in order if p not in ("openai", "wikimedia")]
        async with self.sem:
            for prov in order:
                key = _key(prov, query.lower(), orientation, kind, str(slot))
                jpg, meta = self._cache_paths(key)
                if jpg.exists() and meta.exists():
                    m = json.loads(meta.read_text(encoding="utf-8"))
                    if m.get("id") not in self.used:
                        self.used.add(m.get("id"))
                        return {"src": jpg.as_uri(), "credit": m.get("credit", ""), "is_art": False, "provider": prov}
                img = await self._from_provider(session, prov, query, prompt, orientation, slot)
                if img:
                    data, info = img
                    jpg.write_bytes(data)
                    meta.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
                    self.used.add(info.get("id"))
                    return {"src": jpg.as_uri(), "credit": info.get("credit", ""), "is_art": False, "provider": prov}
        return None

    async def _from_provider(self, session, prov, query, prompt, orientation, slot):
        if prov == "openai":
            style = self.theme.get("image_style", "")
            full = f"{prompt or query}. Style: {style}. No text, no letters, no watermark."
            raw = await _openai_image(full, orientation)
            data = _crop_cover(raw, slot) if raw else None
            return (data, {"id": f"openai:{_key(full)}", "credit": "AI tasvir"}) if data else None
        if prov == "local":
            candidates = _local(query)
        else:
            search = {"pexels": _pexels, "pixabay": _pixabay, "unsplash": _unsplash, "wikimedia": _wikimedia,
                      "openverse": _openverse}[prov]
            candidates = await search(session, query, orientation)
        if prov == "local" and all(c["id"] in self.used for c in candidates):
            self.used -= {c["id"] for c in candidates}  # development pool is small: allow repeats
        for c in candidates:
            if c["id"] in self.used:
                continue
            raw = Path(c["path"]).read_bytes() if c.get("path") else await _get_bytes(session, c["url"])
            data = _crop_cover(raw, slot) if raw else None
            if not data:
                continue
            if c.get("ping"):  # Unsplash API guidelines: report the download
                asyncio.ensure_future(_get_bytes(session, c["ping"] + f"&client_id={_cfg('UNSPLASH_ACCESS_KEY')}"))
            return data, {"id": c["id"], "credit": c.get("credit", ""), "alt": c.get("alt", "")}
        return None


def item_photo_query(item: Dict[str, Any], slide: Dict[str, Any], topic: str) -> str:
    """English query for one card/step photo (AI writes item.photo; otherwise a usable fallback)."""
    q = str(item.get("photo") or "").strip()
    if q:
        return q
    v = slide.get("visual") or {}
    base = (v.get("query") if isinstance(v, dict) else str(v)) or topic
    return f"{base} {item.get('title', '')}".strip()


async def resolve_item_photos(content: Dict[str, Any], theme: Dict[str, Any], resolver: "ImageResolver", session) -> int:
    """Photo templates: one photo per card / step / list item, stored as item['image']."""
    topic = str((content.get("title_slide") or {}).get("title", ""))
    jobs = []
    for slide in content.get("slides", []):
        from services.deck.catalog import resolve_layout_name
        key = ITEM_PHOTO_LAYOUTS.get(resolve_layout_name(slide.get("layout") or slide.get("layout_type")))
        if not key:
            continue
        for it in (slide.get(key) or [])[:5]:
            if not isinstance(it, dict):
                continue
            img = it.get("image") or {}
            if str(img.get("src", "")).startswith("file:") and os.path.exists(img["src"][7:]):
                continue
            if len(jobs) >= MAX_ITEM_PHOTOS:
                break
            jobs.append((it, resolver.resolve(session, item_photo_query(it, slide, topic), "", "photo", "item")))
    results = await asyncio.gather(*(j[1] for j in jobs), return_exceptions=True)
    n = 0
    for (it, _), res in zip(jobs, results):
        if isinstance(res, dict):
            it["image"] = res
            n += 1
    return n


def _needs_image(slide: Dict[str, Any], is_cover: bool, photo_theme: bool = False) -> bool:
    from services.deck.render import IMAGE_LAYOUTS, _ALWAYS_IMAGE
    from services.deck.catalog import resolve_layout_name
    layout = "cover" if is_cover else resolve_layout_name(slide.get("layout") or slide.get("layout_type"))
    v = slide.get("visual") or {}
    if isinstance(v, str):
        v = {"query": v}
    if layout in _ALWAYS_IMAGE or (photo_theme and layout in ("summary", "agenda")):
        return True
    return layout in IMAGE_LAYOUTS and (v.get("kind") or "photo") != "none"


async def resolve_images(content: Dict[str, Any], theme: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """Finds photos for every slide that shows one. Returns {slide_index: image} and also
    stores each image into the content dict (title_slide['image'] / slides[i]['image'])."""
    resolver = ImageResolver(theme)
    if not resolver.providers:
        return {}
    import aiohttp
    from services.deck.catalog import resolve_layout_name

    jobs = []
    ts = content.get("title_slide") or {}
    entries = [(0, ts, True)] + [(i + 1, s, False) for i, s in enumerate(content.get("slides", []))]
    async with aiohttp.ClientSession(headers={"User-Agent": UA}) as session:
        for idx, slide, is_cover in entries:
            if slide.get("image") and str(slide["image"].get("src", "")).startswith("file:") and \
                    os.path.exists(slide["image"]["src"][7:]):
                continue
            if not _needs_image(slide, is_cover, bool(theme.get("photo"))):
                continue
            v = slide.get("visual") or {}
            if isinstance(v, str):
                v = {"query": v}
            query = v.get("query") or slide.get("image_query") or slide.get("title", "")
            layout = "cover" if is_cover else resolve_layout_name(slide.get("layout") or slide.get("layout_type"))
            jobs.append((idx, slide, resolver.resolve(session, query, v.get("prompt", ""), v.get("kind", "photo"), layout)))
        results = await asyncio.gather(*(j[2] for j in jobs), return_exceptions=True)
        if theme.get("photo"):
            await resolve_item_photos(content, theme, resolver, session)
    found: Dict[int, Dict[str, Any]] = {}
    for (idx, slide, _), res in zip(jobs, results):
        if isinstance(res, dict):
            slide["image"] = res
            found[idx] = res
    return found
