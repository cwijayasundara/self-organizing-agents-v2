from typing import Protocol


class ContextExecutor(Protocol):
    async def execute(self, code: str, handles: list[str], execution) -> dict: ...
