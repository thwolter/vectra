from typing import Protocol, runtime_checkable

from parsers.schemas import ParseResult


@runtime_checkable
class ParserProtocol(Protocol):
    async def parse(self, file: str) -> ParseResult: ...
    async def to_markdown(self) -> str: ...


@runtime_checkable
class ParserProvider(Protocol):
    def __call__(self, *, file_path: str, profile: str) -> ParserProtocol: ...
