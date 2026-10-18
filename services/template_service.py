"""
Template catalogue for the bot (names, codes, categories), backed by the theme folders in
themes/<id>/. Kept as a thin layer so existing callers keep a stable API; all visual data
lives in the themes and is drawn by services/deck.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.deck.catalog import CONTENT_LAYOUTS
from services.deck.themes import DEFAULT_THEME, get_theme, list_theme_ids, resolve_theme_id


def _as_template(theme: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": theme["id"],
        "code": theme.get("code", ""),
        "name": theme.get("name", ""),
        "category": theme.get("category", ""),
        "tagline": theme.get("tagline", ""),
        "theme_config": dict(theme.get("palette", {})),
        "layouts": list(CONTENT_LAYOUTS),
        "status": "ACTIVE",
    }


class TemplateManager:
    def get_all_templates(self) -> List[Dict[str, Any]]:
        return [_as_template(get_theme(tid)) for tid in list_theme_ids()]

    def get_template(self, key: Any) -> Optional[Dict[str, Any]]:
        return _as_template(get_theme(str(key).replace("tpl_", "").strip()))

    def get_template_design_system(self, key: Any) -> Dict[str, Any]:
        t = get_theme(str(key).replace("tpl_", "").strip())
        return {**_as_template(t), "theme": dict(t.get("palette", {})), "fonts": t.get("fonts", {}),
                "prompt_directive": t.get("writing_tone", "")}

    @staticmethod
    def resolve_id(key: Any) -> str:
        return resolve_theme_id(str(key).replace("tpl_", "").strip())


template_manager = TemplateManager()
DEFAULT_TEMPLATE_ID = DEFAULT_THEME
