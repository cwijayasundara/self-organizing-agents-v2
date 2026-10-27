from collections import deque
from .protocol import ModelResponse


class ScriptedModel:
    """Explicit offline fixture. Usage and pricing are synthetic, never billing."""
    def __init__(self, responses):
        self.responses = deque(responses)

    async def complete(self, request):
        if not self.responses:
            raise RuntimeError('script exhausted')
        response = self.responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response
