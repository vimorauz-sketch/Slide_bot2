"""
Lightweight fake aiogram objects for handler unit tests.

These intentionally avoid any real Telegram Bot API / network access. They only
implement the small surface actually used by bot/handlers/*.py, and record every
call so tests can assert on what the handler tried to send.
"""
from typing import Any, Dict, List, Optional


class FakeUser:
    def __init__(self, id: int = 1, full_name: str = "Test User", username: Optional[str] = "testuser"):
        self.id = id
        self.full_name = full_name
        self.username = username


class FakeChat:
    def __init__(self, id: int = 1):
        self.id = id


class FakeFile:
    def __init__(self, file_path: str = "fake/path.jpg"):
        self.file_path = file_path


class FakeDownloadedFile:
    def __init__(self, data: bytes = b"fake-image-bytes"):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeBotInfo:
    def __init__(self, username: str = "SlideLabBot"):
        self.username = username


class FakeBot:
    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []

    async def get_file(self, file_id):
        return FakeFile()

    async def download_file(self, file_path):
        return FakeDownloadedFile()

    async def get_me(self):
        return FakeBotInfo()

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": text, **kwargs})

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.sent_messages.append({"chat_id": chat_id, "text": caption, "photo": photo, **kwargs})

    async def me(self):
        return FakeBotInfo()


class FakePhotoSize:
    def __init__(self, file_id: str = "photo123"):
        self.file_id = file_id


class _RecordingMixin:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def _record(self, method: str, **kwargs):
        self.calls.append({"method": method, **kwargs})

    def calls_for(self, method: str) -> List[Dict[str, Any]]:
        return [c for c in self.calls if c["method"] == method]


class FakeMessage(_RecordingMixin):
    def __init__(
        self,
        text: str = "",
        from_user: Optional[FakeUser] = None,
        chat_id: int = 1,
        photo=None,
        bot: Optional[FakeBot] = None,
    ):
        super().__init__()
        self.text = text
        self.from_user = from_user or FakeUser(id=chat_id)
        self.chat = FakeChat(id=chat_id)
        self.photo = photo
        self.bot = bot or FakeBot()
        self.deleted = False
        self.reply_markup = None
        self.web_app_data = None

    async def answer(self, text, reply_markup=None, parse_mode=None):
        sent = FakeMessage(text=text, from_user=self.from_user, chat_id=self.chat.id, bot=self.bot)
        self._record("answer", text=text, reply_markup=reply_markup, parse_mode=parse_mode, returned=sent)
        return sent

    async def answer_photo(self, photo, caption=None, reply_markup=None, parse_mode=None):
        self._record("answer_photo", photo=photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)

    async def answer_media_group(self, media):
        self._record("answer_media_group", media=media)

    async def answer_document(self, document, caption=None, parse_mode=None):
        self._record("answer_document", document=document, caption=caption, parse_mode=parse_mode)

    async def edit_text(self, text, reply_markup=None, parse_mode=None):
        self._record("edit_text", text=text, reply_markup=reply_markup, parse_mode=parse_mode)

    async def edit_media(self, media, reply_markup=None):
        self._record("edit_media", media=media, reply_markup=reply_markup)

    async def edit_reply_markup(self, reply_markup=None):
        self.reply_markup = reply_markup
        self._record("edit_reply_markup", reply_markup=reply_markup)

    async def delete(self):
        self.deleted = True
        self._record("delete")


class FakeCallbackQuery(_RecordingMixin):
    def __init__(self, data: str, from_user: Optional[FakeUser] = None, message: Optional[FakeMessage] = None):
        super().__init__()
        self.data = data
        self.from_user = from_user or FakeUser(id=1)
        self.message = message or FakeMessage(from_user=self.from_user)
        self.bot = self.message.bot

    async def answer(self, text: Optional[str] = None, show_alert: bool = False):
        self._record("answer", text=text, show_alert=show_alert)


class FakeFSMContext:
    """Minimal in-memory stand-in for aiogram's FSMContext."""

    def __init__(self):
        self._state = None
        self._data: Dict[str, Any] = {}

    async def clear(self):
        self._state = None
        self._data = {}

    async def set_state(self, state):
        self._state = state

    async def get_state(self):
        return self._state

    async def set_data(self, data):
        self._data = dict(data)

    async def update_data(self, **kwargs):
        self._data.update(kwargs)
        return dict(self._data)

    async def get_data(self) -> Dict[str, Any]:
        return dict(self._data)
