import pytest

from bot.middlewares.throttling import ThrottlingMiddleware, FLOOD_BAN


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
