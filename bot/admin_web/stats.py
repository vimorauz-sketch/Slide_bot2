"""Numbers for the dashboard. Grouping by day is done in Python (works the same on SQLite and
PostgreSQL); days are Tashkent days (UTC+5)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import func, select

from database.connection import AsyncSessionLocal
from database.models import PresentationOrder, User

TZ = timedelta(hours=5)
PERIODS = {"1": ("Bugun", 1), "7": ("7 kun", 7), "30": ("30 kun", 30)}


def local_now() -> datetime:
    return datetime.utcnow() + TZ


def period_start(days: int) -> datetime:
    """UTC start of a period: today = since local midnight; 7/30 = rolling days."""
    if days == 1:
        midnight = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight - TZ
    return datetime.utcnow() - timedelta(days=days)


def money(n) -> str:
    return f"{int(n or 0):,}".replace(",", " ")


def _paid_value(o) -> int:
    return int(o.paid_amount if o.paid_amount is not None else o.total_price or 0)


async def overview(period: str = "7") -> Dict[str, Any]:
    label, days = PERIODS.get(period, PERIODS["7"])
    now = datetime.utcnow()
    start = period_start(days)
    prev_start = start - (now - start)
    async with AsyncSessionLocal() as s:
        paid_rows = (await s.execute(select(PresentationOrder.paid_at, PresentationOrder.paid_amount,
                                            PresentationOrder.total_price)
                                     .where(PresentationOrder.status.in_(("PAID", "REFUNDED")),
                                            PresentationOrder.paid_at >= now - timedelta(days=60))
                                     )).all()
        created = (await s.execute(select(PresentationOrder.created_at, PresentationOrder.status,
                                          PresentationOrder.template_id, PresentationOrder.subject,
                                          PresentationOrder.user_id)
                                   .where(PresentationOrder.created_at >= min(prev_start, now - timedelta(days=30))))).all()
        users_new = (await s.execute(select(User.created_at).where(User.created_at >= prev_start))).scalars().all()
        active_ids = set((await s.execute(select(User.telegram_id).where(
            (User.last_seen_at >= start) | (User.created_at >= start)))).scalars().all())
        total_users = (await s.execute(select(func.count()).select_from(User))).scalar() or 0
        open_orders = (await s.execute(select(func.count()).select_from(PresentationOrder)
                                       .where(PresentationOrder.status == "WAITING_PAYMENT"))).scalar() or 0

    def in_range(t, a, b):
        return t is not None and a <= t < b

    rev = sum(int(a if a is not None else p) for t, a, p in paid_rows if in_range(t, start, now + timedelta(1)))
    rev_prev = sum(int(a if a is not None else p) for t, a, p in paid_rows if in_range(t, prev_start, start))
    pays = sum(1 for t, *_ in paid_rows if in_range(t, start, now + timedelta(1)))
    pays_prev = sum(1 for t, *_ in paid_rows if in_range(t, prev_start, start))
    prev_n = sum(1 for r in created if in_range(r[0], start, now + timedelta(1)))
    prev_n_prev = sum(1 for r in created if in_range(r[0], prev_start, start))
    nu = sum(1 for t in users_new if in_range(t, start, now + timedelta(1)))
    nu_prev = sum(1 for t in users_new if in_range(t, prev_start, start))
    conv = round(100 * pays / prev_n) if prev_n else 0
    conv_prev = round(100 * pays_prev / prev_n_prev) if prev_n_prev else 0

    def delta(a, b, pct=True):
        if b == 0:
            return ("—", "flat") if a == 0 else ("yangi", "up")
        d = (a - b) / b * 100 if pct else a - b
        sign = "↑" if d > 0 else "↓" if d < 0 else ""
        return (f"{sign} {abs(round(d))}%" if pct else f"{sign} {abs(int(d))}").strip() or "0", \
            "up" if d > 0 else "down" if d < 0 else "flat"

    # 14 daily points (this and the previous 14 days) for the chart
    today = local_now().date()
    by_day = defaultdict(int)
    for t, a, p in paid_rows:
        if t:
            by_day[(t + TZ).date()] += int(a if a is not None else p)
    days14 = [today - timedelta(days=13 - i) for i in range(14)]
    series = [by_day.get(d, 0) for d in days14]
    series_prev = [by_day.get(d - timedelta(days=14), 0) for d in days14]
    # daily small series for the cards (7 days)
    d7 = [today - timedelta(days=6 - i) for i in range(7)]
    cnt_paid = Counter((t + TZ).date() for t, *_ in paid_rows if t)
    cnt_prev = Counter((r[0] + TZ).date() for r in created if r[0])
    cnt_users = Counter((t + TZ).date() for t in users_new if t)

    in_period = [r for r in created if in_range(r[0], start, now + timedelta(1))]
    status_counts = Counter(r[1] for r in in_period)
    month = [r for r in created if r[0] and r[0] >= now - timedelta(days=30)]
    top_templates = Counter(r[2] for r in month if r[2]).most_common(5)
    top_subjects = Counter((r[3] or "—").strip().title() for r in month).most_common(6)
    users_with_order = len({r[4] for r in in_period})
    return {
        "period": period, "period_label": label,
        "revenue": rev, "revenue_delta": delta(rev, rev_prev),
        "payments": pays, "payments_delta": delta(pays, pays_prev, pct=False),
        "previews": prev_n, "previews_delta": delta(prev_n, prev_n_prev),
        "new_users": nu, "new_users_delta": delta(nu, nu_prev),
        "conversion": conv, "conversion_delta": conv - conv_prev,
        "avg_check": round(rev / pays) if pays else 0,
        "total_users": total_users, "waiting": open_orders,
        "days": [d.strftime("%d.%m") for d in days14], "series": series, "series_prev": series_prev,
        "spark_paid": [cnt_paid.get(d, 0) for d in d7], "spark_previews": [cnt_prev.get(d, 0) for d in d7],
        "spark_users": [cnt_users.get(d, 0) for d in d7],
        "status": {
            "PAID": status_counts.get("PAID", 0),
            "PREVIEW_READY": status_counts.get("PREVIEW_READY", 0) + status_counts.get("CREATED", 0),
            "WAITING_PAYMENT": status_counts.get("WAITING_PAYMENT", 0),
            "CANCELLED": status_counts.get("CANCELLED", 0) + status_counts.get("REFUNDED", 0),
        },
        "top_templates": top_templates, "top_subjects": top_subjects,
        # each step is a subset of the previous one: everyone who made a preview was active, and so on
        "funnel": [("Botdan foydalanganlar", len(active_ids | {r[4] for r in in_period})),
                   ("Namuna yaratganlar", users_with_order),
                   ("To‘lov qilganlar", len({r[4] for r in in_period if r[1] == "PAID"}))],
    }


# ---------------------------------------------------------------------- chart helpers
def smooth_path(values: List[float], w: float = 650, h: float = 200, x0: float = 40, y0: float = 220,
                top: float = 0) -> str:
    top = top or max(values + [1])
    pts = [(x0 + i * (w / max(1, len(values) - 1)), y0 - v / top * h) for i, v in enumerate(values)]
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        cx = (ax + bx) / 2
        d += f" C{cx:.1f} {ay:.1f} {cx:.1f} {by:.1f} {bx:.1f} {by:.1f}"
    return d


def spark_path(values: List[float]) -> str:
    mx, mn = max(values + [0]), min(values + [0])
    rng = (mx - mn) or 1
    n = max(1, len(values) - 1)
    return " ".join(f"{'M' if i == 0 else 'L'}{4 + i * 82 / n:.1f} {34 - (v - mn) / rng * 30:.1f}"
                    for i, v in enumerate(values))


def nice_top(v: float) -> int:
    if v <= 0:
        return 1000
    import math
    mag = 10 ** int(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * mag >= v:
            return int(m * mag)
    return int(10 * mag)
