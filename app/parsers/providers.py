from __future__ import annotations

from collections.abc import Callable
from typing import Dict

from .docling import DoclingParser, DoclingParserConfig
from .protocols import ParserProtocol
from .schemas import ParserConfig

ParserFactory = Callable[..., ParserProtocol]
PARSER_PROVIDERS: Dict[str, ParserFactory] = {}


def register_parser_provider(name: str, factory: ParserFactory) -> None:
    """Register or replace a parser factory for the given name."""

    PARSER_PROVIDERS[name] = factory


def get_parser_factory(name: str) -> ParserFactory:
    try:
        return PARSER_PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(f'Unknown parser provider: {name!r}') from exc


def parser_provider(*, name: str, config: ParserConfig) -> ParserProtocol:
    factory = get_parser_factory(name)
    return factory(config=config)


def _docling_parser_factory(*, config: ParserConfig) -> ParserProtocol:
    if not isinstance(config, DoclingParserConfig):
        # Allow plain ParserConfig instances by coercing into DoclingParserConfig
        config = DoclingParserConfig(**config.model_dump())
    return DoclingParser(config=config)


register_parser_provider('docling', _docling_parser_factory)
