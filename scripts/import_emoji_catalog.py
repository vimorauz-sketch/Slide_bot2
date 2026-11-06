"""Fills custom_emoji.json from a custom emoji catalog list, e.g. all_emojis.json of
https://github.com/abbosahmad/telegram-premium-emojis (catalog/all_emojis.json):

    python scripts/import_emoji_catalog.py path/to/all_emojis.json [--overwrite]

Items look like {"id": "5875465628285931233", "emoji": "✈️", "pack": "TgAndroidIcons"}. For every
emoji of the bot the first id of the most preferred pack is taken (PACK_ORDER: RestrictedEmoji is
Telegram's animated set for message text). Ids already in the file are kept unless --overwrite.
The bot checks every id with Telegram at startup and drops the ones that do not exist."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "custom_emoji.json")
VS16 = "️"
ID_RE = re.compile(r"^\d{5,25}$")
PACK_ORDER = ["RestrictedEmoji", "TgAndroidIcons", "tgmacicons", "NewsEmoji", "StatusEmoji", "RoboEmoji",
              "vector_icons_by_fStikBot"]


def main(argv) -> None:
    if not argv:
        sys.exit(__doc__)
    overwrite = "--overwrite" in argv
    with open([a for a in argv if not a.startswith("--")][0], encoding="utf-8") as f:
        items = json.load(f)
    rank = {p: i for i, p in enumerate(PACK_ORDER)}
    best = {}
    for pos, it in enumerate(items if isinstance(items, list) else []):
        if not isinstance(it, dict):
            continue
        cid, emoji = str(it.get("id") or it.get("custom_emoji_id") or ""), str(it.get("emoji") or "")
        if not ID_RE.match(cid) or not emoji:
            continue
        key = emoji.replace(VS16, "")
        score = (rank.get(it.get("pack"), len(PACK_ORDER)), pos)
        if key not in best or score < best[key][0]:
            best[key] = (score, cid)
    with open(OUT, encoding="utf-8") as f:
        data = json.load(f)
    filled = 0
    for emoji in list(data):
        if emoji.startswith("_") or (data[emoji] and not overwrite):
            continue
        if emoji in best:
            data[emoji] = best[emoji][1]
            filled += 1
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    empty = [k for k, v in data.items() if not k.startswith("_") and not v]
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{filled} ids added; {len(data) - 1 - len(empty)} of {len(data) - 1} emoji have an id")
    if empty:
        print("without an id (stay ordinary):", " ".join(empty))


if __name__ == "__main__":
    main(sys.argv[1:])
