"""The «Menu» commands: every listed command has a handler that runs before any wizard step."""
import pytest
from aiogram.filters import Command

from bot import commands
from bot.handlers import start


def _handled_commands():
    names = set()
    for h in start.router.message.handlers:
        for f in h.filters or []:
            cb = getattr(f, "callback", None)
            if isinstance(cb, Command):
                names |= {c if isinstance(c, str) else c.pattern for c in cb.commands}
    return names


def test_every_menu_command_has_a_handler_in_the_first_router():
    handled = _handled_commands() | {"start"}
    for name, desc in commands.COMMANDS:
        assert name in handled, name
        assert all(0 < len(d) <= 256 for d in desc.values())
        assert set(desc) == {"uz", "ru", "en"}
    assert [c.command for c in commands.commands_for("uz", admin=True)][-1] == "admin"
    assert commands.commands_for("ru")[1].description.startswith("🎨 Создать")


@pytest.mark.asyncio
async def test_commands_are_written_for_every_language_and_admins():
    calls = []

    class Bot:
        async def set_my_commands(self, cmds, scope=None, language_code=None):
            calls.append((len(cmds), type(scope).__name__, language_code))

        async def set_chat_menu_button(self, menu_button=None):
            calls.append(("menu", type(menu_button).__name__))

    await commands.setup_commands(Bot(), [42])
    assert (len(commands.COMMANDS), "BotCommandScopeAllPrivateChats", None) in calls
    assert (len(commands.COMMANDS), "BotCommandScopeAllPrivateChats", "ru") in calls
    assert (len(commands.COMMANDS) + 1, "BotCommandScopeChat", None) in calls
    assert ("menu", "MenuButtonCommands") in calls


@pytest.mark.asyncio
async def test_failure_does_not_stop_the_bot():
    class Bot:
        async def set_my_commands(self, *a, **k):
            raise RuntimeError("network")
    await commands.setup_commands(Bot())   # no exception
