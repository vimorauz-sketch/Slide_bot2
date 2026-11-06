"""Writes custom_emoji.json: every emoji the bot uses in its messages, with an empty id to fill in
(python scripts/collect_emoji.py). Ids already in the file are kept."""
import collections
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "custom_emoji.json")
HELP = ("Har bir emoji uchun Telegram Premium custom_emoji_id (faqat raqamlar), masalan tg-emoji-hub'dan "
        "nusxalang. Bo'sh qolgani oddiy emoji bo'lib qoladi. Yangi emoji qo'shilsa: python scripts/collect_emoji.py")
# flags (two regional letters), keycaps, then pictographs with ZWJ sequences; not the progress-bar
# shapes (▰ ▱ ◐ ◑ ◒ ◓ ▪ ▫), arrows or dashes used as plain text
EMOJI = re.compile(
    "[🇦-🇿]{2}|[0-9#*]️?⃣|"
    "(?:[🌀-🫿☀-➿⬅-⬇⬛⬜⭐⭕⏩-⏺⌚⌛"
    "⌨‼⁉ℹⓂ〰〽㊗㊙🀄🃏🅰-🉑]"
    "️?(?:‍[🌀-🫿☀-➿]️?)*)")


def main() -> None:
    files = (glob.glob(os.path.join(ROOT, "bot", "**", "*.py"), recursive=True)
             + glob.glob(os.path.join(ROOT, "services", "**", "*.py"), recursive=True)
             + glob.glob(os.path.join(ROOT, "locales", "*.json")) + [os.path.join(ROOT, "main.py")])
    skip = (os.sep + "admin_web" + os.sep, os.sep + "deck" + os.sep, "custom_emoji.py")
    count = collections.Counter()
    for path in files:
        if any(s in path for s in skip):
            continue
        with open(path, encoding="utf-8") as f:
            for m in EMOJI.findall(f.read()):
                count[m.replace("️", "")] += 1
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    data = {"_help": HELP}
    for emoji, _ in count.most_common():
        data[emoji] = old.get(emoji, "")
    for emoji, cid in old.items():  # ids added by hand for emoji not found in the code
        if not emoji.startswith("_") and emoji not in data:
            data[emoji] = cid
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{OUT}: {len(data) - 1} emoji, {sum(1 for k, v in data.items() if v and not k.startswith('_'))} with an id")


if __name__ == "__main__":
    main()
