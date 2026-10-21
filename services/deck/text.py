"""Language-specific text clean-up applied to every string before it is drawn."""
from __future__ import annotations

import re
from typing import Any

# Uzbek Latin writes o‘/g‘ and the "tutuq belgisi" (ma’ruza). The official code points are
# U+02BB/U+02BC, but several bundled fonts (Nunito, IBM Plex Sans, Unbounded, Raleway...) give
# those glyphs a huge advance width, so "oʻsimlik" renders as "o ʻ simlik". The typographic
# quotes U+2018 ‘ and U+2019 ’ look right in every bundled font and are the common choice in
# Uzbek print, so every variant is normalized to them.
_APOS = "'’‘`ʹ′ʻʼ"
_OG = re.compile(rf"([oOgG])[{_APOS}]")
_TUTUQ = re.compile(rf"(?<=[A-Za-z\x00])[{_APOS}](?=[A-Za-z])")


def fix_uzbek(text: str) -> str:
    if not text:
        return text
    text = _OG.sub(lambda m: m.group(1) + "\x00", text)  # placeholder keeps o‘/g‘ out of the tutuq pass
    text = _TUTUQ.sub("’", text)
    return text.replace("\x00", "‘")


def tidy(text: str) -> str:
    """Typography shared by all languages: no double spaces, real dashes and ellipses."""
    if not text:
        return text
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" - ", " – ").replace("...", "…")
    return text


_DQ = re.compile(r'"([^"\n]{1,200})"')


def smart_quotes(text: str, language: str) -> str:
    if '"' not in text:
        return text
    left, right = ("«", "»") if language == "ru" else ("“", "”")
    return _DQ.sub(lambda m: f"{left}{m.group(1)}{right}", text)


def clean_value(value: Any, language: str) -> Any:
    """Recursively normalizes every string inside a slide/content structure."""
    if isinstance(value, str):
        v = smart_quotes(tidy(value), language)
        return fix_uzbek(v) if language == "uz" else v
    if isinstance(value, list):
        return [clean_value(v, language) for v in value]
    if isinstance(value, dict):
        return {k: (clean_value(v, language) if k not in _RAW_KEYS else v) for k, v in value.items()}
    return value


# Keys whose values are identifiers, URLs or search queries, never shown as prose.
_RAW_KEYS = {"layout", "variant", "icon", "query", "prompt", "kind", "type", "src", "path", "url", "credit_url"}
