"""User-facing texts of the free presentation and the referral programme (Uzbek)."""
from __future__ import annotations

from typing import Optional

from bot.utils import escape_html

LINE = "━━━━━━━━━━━━━━━"


def som(amount) -> str:
    return f"{int(amount or 0):,}".replace(",", " ") + " so‘m"


def _name(name: Optional[str], fallback: str = "Do‘stingiz") -> str:
    name = " ".join((name or "").split())[:40]
    return f"<b>{escape_html(name)}</b>" if name else fallback


def _slides_note(max_slides: int) -> str:
    return f" ({max_slides} slaydgacha)" if max_slides > 0 else ""


def welcome_text(name: Optional[str], *, trial: bool, bonus: int, max_slides: int) -> str:
    hello = f"👋 <b>Assalomu alaykum, {escape_html(' '.join((name or '').split())[:40])}!</b>" if name \
        else "👋 <b>Assalomu alaykum!</b>"
    text = (f"{hello}\n\n"
            "<b>SlideLab</b> — sun’iy intellekt yordamida chiroyli taqdimotlarni <b>2–3 daqiqada</b> tayyorlaydi.\n\n"
            "✨ <b>Siz nima olasiz:</b>\n"
            "• 🎨 Zamonaviy dizayn shablonlari\n"
            "• 🖼 Har bir slaydga mos rasmlar\n"
            "• 📊 PowerPoint (.pptx) — matnini tahrirlash mumkin\n"
            "• 📄 PDF — chop etish va ko‘rsatish uchun\n\n")
    if trial:
        text += (f"🎁 <b>Sizga sovg‘a: birinchi taqdimot — BEPUL!</b>{_slides_note(max_slides)}\n\n"
                 "👇 Boshlash uchun <b>«🎨 Presentation yaratish»</b> tugmasini bosing.")
    elif bonus > 0:
        text += (f"🎁 Sizda <b>{bonus} ta bepul taqdimot</b> bor{_slides_note(max_slides)}.\n\n"
                 "👇 <b>«🎨 Presentation yaratish»</b> tugmasini bosing.")
    else:
        text += ("🎁 Do‘stlaringizni taklif qiling — har biri uchun <b>bepul taqdimot</b> oling! "
                 "Batafsil: <b>«🎁 Referal»</b>.\n\n"
                 "👇 Boshlash uchun <b>«🎨 Presentation yaratish»</b> tugmasini bosing.")
    return text


def free_slide_hint(max_slides: int, paid_possible: bool, *, trial: bool) -> str:
    what = "Birinchi taqdimotingiz" if trial else "Keyingi taqdimotingiz"
    text = f"🎁 <b>{what} bepul</b>{_slides_note(max_slides)}!"
    if max_slides > 0:
        text += ("\n<i>Ko‘proq slayd tanlasangiz — odatdagi narxda.</i>" if paid_possible
                 else f"\n<i>Iltimos, {max_slides} tagacha slayd tanlang.</i>")
    return text


def free_price_line(total_price: int, *, trial: bool) -> str:
    why = "birinchi taqdimot" if trial else "bonus taqdimot"
    return f"💰 <b>Narx:</b> <s>{som(total_price)}</s> → 🎁 <b>BEPUL</b> ({why})"


def free_too_big_text(max_slides: int) -> str:
    return (f"🎁 Bepul taqdimot <b>{max_slides} slaydgacha</b> bo‘ladi.\n"
            f"Iltimos, {max_slides} yoki kamroq slayd tanlang:")


def free_ready_text(topic: str, slide_count: int, kind: str) -> str:
    title = "🎁 <b>Bepul taqdimotingiz tayyor!</b>" if kind == "TRIAL" \
        else "🎁 <b>Bonus taqdimotingiz tayyor!</b> Do‘stlaringiz uchun rahmat 💛"
    return (f"{title}\n\n"
            f"📌 «{escape_html((topic or '')[:120])}» — {slide_count} ta slayd, belgilarsiz va to‘liq sifatda.\n"
            "📎 PowerPoint va PDF fayllar pastda 👇\n\n"
            "<i>PowerPoint faylidagi matnlarni bemalol tahrirlashingiz mumkin.</i>")


def after_free_text(price_per_slide: int, credits_left: int, bonus_per_friend: int, trigger: str) -> str:
    if credits_left > 0:
        return (f"✨ <b>Yoqdimi?</b>\n\nSizda yana <b>{credits_left} ta bepul taqdimot</b> bor — "
                "hoziroq yangisini yarating!")
    when = "birinchi taqdimotini yaratganda" if trigger == "first" else "birinchi to‘lovini qilganda"
    return ("✨ <b>Yoqdimi?</b>\n\n"
            f"💳 Keyingi taqdimotlar: 1 slayd — <b>{som(price_per_slide)}</b> "
            f"(10 slayd — {som(price_per_slide * 10)}).\n\n"
            f"🎁 <b>Yoki bepul oling!</b> Do‘stlaringizni taklif qiling: har bir do‘stingiz {when} "
            f"sizga <b>{bonus_per_friend} ta bepul taqdimot</b> beriladi.")


def referral_text(link: str, *, invited: int, rewarded: int, credits_left: int, bonus_per_friend: int,
                  trigger: str, trial_on: bool, max_slides: int) -> str:
    when = "birinchi taqdimotini yaratganda" if trigger == "first" else "birinchi marta to‘lov qilganda"
    text = ("🎁 <b>DO‘STLARNI TAKLIF QILING —\nBEPUL TAQDIMOT OLING!</b>\n\n"
            "<b>Qanday ishlaydi?</b>\n"
            "1️⃣ Havolangizni do‘stlaringizga yuborasiz\n"
            "2️⃣ Do‘stingiz havola orqali botga kiradi\n"
            f"3️⃣ U {when} — sizga <b>🎁 {bonus_per_friend} ta bepul taqdimot</b>{_slides_note(max_slides)}\n")
    if trial_on:
        text += "\n💛 Do‘stingiz ham yutadi: uning <b>birinchi taqdimoti bepul!</b>\n"
    text += (f"\n{LINE}\n"
             "📊 <b>Sizning natijangiz</b>\n"
             f"👥 Taklif qilinganlar: <b>{invited}</b> ta\n"
             f"✅ Bonus keltirganlar: <b>{rewarded}</b> ta\n"
             f"🎁 Bepul taqdimotlaringiz: <b>{credits_left}</b> ta\n"
             f"{LINE}\n\n"
             f"🔗 <b>Sizning havolangiz:</b>\n<code>{link}</code>\n\n"
             "👇 <b>«📤 Do‘stlarga yuborish»</b> tugmasini bosing — havola tayyor xabar bilan ketadi.")
    return text


def share_text(trial_on: bool) -> str:
    text = "🎓 SlideLab — sun’iy intellekt taqdimotni 2–3 daqiqada tayyorlab beradi: dizayn, rasmlar, PowerPoint va PDF!"
    if trial_on:
        text += "\n🎁 Birinchi taqdimot — BEPUL!"
    return text


def friend_joined_text(friend_name: Optional[str], bonus_per_friend: int, trigger: str) -> str:
    when = "birinchi taqdimotini yaratganda" if trigger == "first" else "birinchi to‘lovini qilganda"
    return ("👋 <b>Yangi do‘st qo‘shildi!</b>\n\n"
            f"{_name(friend_name)} sizning havolangiz orqali botga kirdi.\n"
            f"U {when} sizga <b>🎁 {bonus_per_friend} ta bepul taqdimot</b> beriladi.")


def referral_reward_text(friend_name: Optional[str], bonus: int, credits_left: int) -> str:
    return ("🎉 <b>Tabriklaymiz! Sizga bonus!</b>\n\n"
            f"Do‘stingiz {_name(friend_name, 'taklif qilgan do‘stingiz')} SlideLab’dan foydalandi — "
            f"sizga <b>🎁 {bonus} ta bepul taqdimot</b> qo‘shildi.\n\n"
            f"Hozir sizda: <b>{credits_left} ta</b> bepul taqdimot.\n"
            "👇 Hoziroq foydalaning!")


def profile_text(*, user_id: int, name: Optional[str], orders: int, trial: bool, bonus: int,
                 invited: int, link: str, balance: int = 0, trial_on: bool = True) -> str:
    free_total = int(trial) + bonus
    text = ("👤 <b>SIZNING PROFILINGIZ</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Ism: {escape_html(' '.join((name or '').split())[:60]) or 'Foydalanuvchi'}\n"
            f"📊 Taqdimotlar: <b>{orders}</b> ta\n")
    if balance:
        text += f"💰 Balans: <b>{som(balance)}</b>\n"
    text += (f"\n{LINE}\n"
             f"🎁 Bepul taqdimotlar: <b>{free_total}</b> ta\n"
             + (f"   • Birinchi bepul taqdimot: {'✅ mavjud' if trial else '☑️ ishlatilgan'}\n" if trial_on else "")
             + f"   • Bonuslar (do‘stlar uchun): <b>{bonus}</b> ta\n"
             f"👥 Taklif qilgan do‘stlar: <b>{invited}</b> ta\n"
             f"{LINE}\n\n"
             f"🔗 Taklif havolangiz:\n<code>{link}</code>")
    return text
