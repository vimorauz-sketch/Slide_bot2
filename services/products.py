"""
What SlideLab makes — the «Nima tayyorlaymiz?» Mini App home (webapp/home/) and its prices.

Active products open their wizard in the chat; the others are shown as «Tez orada» until their
generator is ready (they reuse the referat engine or get their own: test, crossword).
"""
from __future__ import annotations

from typing import Any, Dict, List

# key, emoji, name, short description, active
CATALOG = [
    ("pres", "📊", "Taqdimot", "PowerPoint + PDF, 400 shablon", True),
    ("referat", "📄", "Referat", "Word + PDF, 200 shablon", True),
    ("mustaqil", "📝", "Mustaqil ish", "Topshiriq talablari bo‘yicha", False),
    ("kurs", "📚", "Kurs ishi", "Kirish, boblar, xulosa, adabiyotlar", False),
    ("diplom", "🎓", "Diplom ishi", "Bitiruv malakaviy ishi", False),
    ("dars", "👩‍🏫", "Dars ishlanmasi", "O‘qituvchilar uchun reja", False),
    ("hisobot", "📈", "Hisobot", "Amaliyot va laboratoriya hisoboti", False),
    ("esse", "✍️", "Esse", "1–3 bet, erkin fikr", False),
    ("maqola", "📰", "Maqola", "Ilmiy-ommabop maqola", False),
    ("tezis", "📑", "Tezis", "Konferensiya uchun qisqa tezis", False),
    ("test", "❓", "Test", "Savollar va javoblar kaliti", False),
    ("krossvord", "🔤", "Krossvord", "Mavzu bo‘yicha krossvord", False),
]
ACTIVE = {key for key, *_, active in CATALOG if active}


def _som(n: int) -> str:
    return f"{int(n):,}".replace(",", " ") + " so‘m"


async def prices() -> Dict[str, str]:
    """«… so‘mdan» for the active products (the smallest order at the current settings)."""
    from bot.handlers.create_pres import _limits
    from services import runtime
    from services.referat import writer
    min_slides, _, per_slide = await _limits()
    per_page = runtime.get_int("referat_price_per_page", 500, lo=50, hi=1_000_000)
    smallest = min(s["pages"] for s in writer.SIZES.values())
    return {"pres": _som(per_slide * min_slides) + "dan", "referat": _som(per_page * smallest) + "dan"}


async def catalog() -> List[Dict[str, Any]]:
    p = await prices()
    return [{"key": key, "emoji": emoji, "name": name, "desc": desc, "active": active,
             "price": p.get(key, "") if active else "Tez orada"}
            for key, emoji, name, desc, active in CATALOG]
