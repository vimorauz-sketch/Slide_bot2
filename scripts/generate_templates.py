"""Generates themes/templates.json: 180 generated templates + colour sets for every template.

Templates 1-20 are the hand-made families in themes/<id>/ (their colours come from the family's
"recipe"); 21-200 are combinations from services/deck/design_space.py. Every template gets
10 contrast-checked colour sets; the first one is the template's own default.

Usage: python scripts/generate_templates.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services.deck import design_space as ds  # noqa: E402
from services.deck.palettes import check_palette  # noqa: E402


def main():
    themes_dir = os.path.join(ROOT, "themes")
    families = sorted(d for d in os.listdir(themes_dir) if os.path.exists(os.path.join(themes_dir, d, "theme.json")))
    fam_colors = {}
    for fam in families:
        t = json.load(open(os.path.join(themes_dir, fam, "theme.json"), encoding="utf-8"))
        r = t["recipe"]
        cols = ds.colors_for({"type": r["type"], "kwargs": r.get("kwargs", {})}, r.get("seeds", r["type"]), offset=0, n=ds.COLORS_PER_TEMPLATE - 1)
        fam_colors[fam] = [{"slug": "asl", "name": "Asl", "palette": None}] + cols
    gen = ds.generate(count=200 - len(families), start_code=len(families) + 1)
    problems = []
    for t in gen:
        for c in t["colors"]:
            if check_palette(c["palette"]):
                problems.append((t["id"], c["slug"], check_palette(c["palette"])))
    for fam, cols in fam_colors.items():
        for c in cols[1:]:
            if check_palette(c["palette"]):
                problems.append((fam, c["slug"], check_palette(c["palette"])))
    if problems:
        raise SystemExit(f"contrast problems: {problems[:5]}")
    ids = [t["id"] for t in gen]
    assert len(set(ids)) == len(ids), "duplicate ids"
    data = {"family_colors": fam_colors, "templates": gen}
    path = os.path.join(themes_dir, "templates.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    from collections import Counter
    for dim in ("art", "cover_variant", "tone"):
        print(dim, dict(Counter(t[dim] for t in gen)))
    print(f"{len(gen)} generated + {len(families)} families -> {path}")


if __name__ == "__main__":
    main()
