"""One build per user at a time, a few per hour, and a limit on AI plan rewrites (services/guard.py)."""
import pytest

from services import guard, runtime


class Clock:
    def __init__(self):
        self.t = 5000.0

    def __call__(self):
        return self.t


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(runtime, "is_admin", lambda uid: uid == 1)
    guard._active.clear(); guard._starts.clear(); guard._edits.clear()
    yield
    guard._active.clear(); guard._starts.clear(); guard._edits.clear()


def test_second_build_waits_for_the_first(monkeypatch):
    monkeypatch.setattr(runtime, "get_int", lambda k, d=0, **kw: 6 if k == "max_builds_per_hour" else d)
    c = Clock()
    assert guard.start_build(50, "pres", clock=c) is None
    assert "hali tayyorlanmoqda" in guard.start_build(50, "referat", clock=c)
    assert guard.start_build(51, "pres", clock=c) is None      # other users are not affected
    guard.finish_build(50)
    assert guard.start_build(50, "referat", clock=c) is None


def test_hourly_build_limit(monkeypatch):
    monkeypatch.setattr(runtime, "get_int", lambda k, d=0, **kw: 3 if k == "max_builds_per_hour" else d)
    c = Clock()
    for _ in range(3):
        assert guard.start_build(60, clock=c) is None
        guard.finish_build(60)
        c.t += 60
    msg = guard.start_build(60, clock=c)
    assert msg and "Bir soatda 3" in msg
    c.t += 3600
    assert guard.start_build(60, clock=c) is None


def test_admins_are_never_limited(monkeypatch):
    monkeypatch.setattr(runtime, "get_int", lambda k, d=0, **kw: 1)
    c = Clock()
    for _ in range(10):
        assert guard.start_build(1, clock=c) is None
    assert all(guard.ai_edit_allowed(1, clock=c) for _ in range(50))


def test_ai_rewrites_per_hour(monkeypatch):
    monkeypatch.setattr(runtime, "get_int", lambda k, d=0, **kw: 4 if k == "max_ai_edits_per_hour" else d)
    c = Clock()
    assert [guard.ai_edit_allowed(70, clock=c) for _ in range(6)] == [True] * 4 + [False] * 2
    c.t += 3601
    assert guard.ai_edit_allowed(70, clock=c)
