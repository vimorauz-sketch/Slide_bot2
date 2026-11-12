import pytest

from bot.middlewares.throttling import ThrottlingMiddleware

class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_normal_use_is_never_limited():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, clock=c)
    for _ in range(60):          # one message every 1.5 s for a minute and a half
        assert m.allow(1) is None
        c.t += 1.5


def test_a_burst_is_cut_off_with_one_notice():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, clock=c)
    verdicts = [m.allow(1) for _ in range(20)]
    assert verdicts[:12] == [None] * 12
    assert verdicts[12] == "notice" and set(verdicts[13:]) == {"drop"}
    c.t += 5
    assert m.allow(1) is None    # tokens come back after a pause


def test_start_spam_costs_more_and_flooders_get_banned():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, ban_seconds=300, clock=c)
    passed = sum(m.allow(5, cost=3) is None for _ in range(10000))
    assert passed == 4                       # 10 000 × /start → only 4 reach the bot
    assert m.buckets[5].banned_until > c.t   # and the user is ignored for a while
    c.t += 100
    assert m.allow(5) == "drop"
    c.t += 300
    assert m.allow(5) is None


def test_users_are_independent_and_memory_is_pruned():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, clock=c)
    for _ in range(30):
        m.allow(1)
    assert m.allow(2) is None
    for uid in range(3, 2000):
        m.allow(uid)
    c.t += 10000
    m.allow(1)
    assert len(m.buckets) <= 2


@pytest.mark.asyncio
async def test_admins_are_not_limited():
    m = ThrottlingMiddleware(rate=1, burst=3, admins=[42])
    calls = []

    async def handler(event, data):
        calls.append(1)

    class Ev:
        class from_user:
            id = 42
    for _ in range(50):
        await m(handler, Ev(), {})
    assert len(calls) == 50


def test_flooding_at_twice_the_speed_is_banned():
    """Every other update got through before, so the drop streak never grew and the user was never banned."""
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, ban_seconds=300, clock=c)
    passed = 0
    for _ in range(400):           # two messages a second for over three minutes
        passed += m.allow(9) is None
        c.t += 0.5
    assert m.buckets[9].banned_until > c.t
    assert passed < 80


def test_a_calm_user_is_forgiven_and_an_admin_can_lift_a_ban():
    from bot.middlewares import throttling
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, ban_seconds=300, clock=c)
    throttling._instances.append(m)
    try:
        for _ in range(20):
            m.allow(3)
        c.t += 60                   # a calm minute
        assert m.allow(3) is None and m.buckets[3].dropped == 0
        for _ in range(500):
            m.allow(4)
        assert [r["user_id"] for r in throttling.banned_list()] == [4]
        assert throttling.unban(4) and m.allow(4) is None
        assert throttling.noisy_list()[0]["user_id"] == 4
    finally:
        throttling._instances.remove(m)


def test_a_double_tap_is_ignored_silently():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, clock=c)
    key = ("c", "confirm_pres_temp_order", 7)
    assert m.allow(1, key=key) is None
    c.t += 0.3
    assert m.allow(1, key=key) == "silent"        # the second tap does nothing and says nothing
    c.t += 0.3
    assert m.allow(1, key=("c", "px_more", 7)) is None   # another button works at once
    c.t += 3
    assert m.allow(1, key=key) is None            # the same button later is a new press


def test_hammering_one_button_counts_as_flooding():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, ban_seconds=300, clock=c)
    verdicts = []
    for _ in range(200):
        verdicts.append(m.allow(2, key=("m", "🎨 Presentation yaratish")))
        c.t += 0.2
    assert verdicts[0] is None and set(verdicts[1:3]) == {"silent"}
    assert "notice" in verdicts and "ban" in verdicts
    assert sum(v is None for v in verdicts) == 1


def test_menu_buttons_have_their_own_small_allowance():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, clock=c)
    passed = sum(m.allow(3, key=("m", f"menu{i % 7}"), menu=True) is None for i in range(20))
    assert passed == 5                             # 5 menu presses at once (12 for ordinary messages)
    c.t += 15
    assert m.allow(3, key=("m", "Fotosintez")) is None        # ordinary answers are not limited by it
    passed = 0
    for i in range(30):                            # then a menu button every 6 s for three minutes
        c.t += 6
        passed += m.allow(3, key=("m", f"menu{i % 7}"), menu=True) is None
    assert 14 <= passed <= 17                      # about one per 12 seconds
    assert m.buckets[3].banned_until <= c.t       # slow pressing is limited, never banned


def test_every_new_ban_is_longer():
    c = Clock()
    m = ThrottlingMiddleware(rate=1, burst=12, ban_seconds=300, clock=c)
    lengths = []
    for _ in range(3):
        while m.buckets.get(4) is None or m.buckets[4].banned_until <= c.t:
            m.allow(4)
        lengths.append(round(m.buckets[4].banned_until - c.t))
        c.t = m.buckets[4].banned_until + 1
    assert lengths == [300, 600, 1200]
