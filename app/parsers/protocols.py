from typing import Protocol, runtime_checkable

from app.parsers.schemas import ParseResult


class ParserProtocol:
    async def parse(self) -> ParseResult: ...
    async def to_markdown(self) -> str: ...


@runtime_checkable
class ParserProvider(Protocol):
    def __call__(self, *, file_path: str, profile: str) -> ParserProtocol: ...
