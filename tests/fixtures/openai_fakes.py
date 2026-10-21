"""Fake OpenAI AsyncOpenAI client objects, for testing services/ai_service.py
without any real network access or API key."""


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, result):
        # `result` is either a JSON string (success) or an Exception instance (failure).
        self._result = result
        self.last_call_kwargs = None

    async def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        if isinstance(self._result, BaseException):
            raise self._result
        return _FakeResponse(self._result)


class FakeOpenAIClient:
    """Drop-in replacement for `openai.AsyncOpenAI` used by ai_service.py.

    Usage: FakeOpenAIClient('{"foo": "bar"}')     -> successful call
           FakeOpenAIClient(TimeoutError("..."))  -> raises on .create()
    """

    def __init__(self, result):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _FakeCompletions(result)

    @property
    def last_call_kwargs(self):
        return self.chat.completions.last_call_kwargs
