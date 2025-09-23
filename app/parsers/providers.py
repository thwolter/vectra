from .docling import DoclingParser, DoclingParserConfig
from .protocols import ParserProtocol


def parser_provider(*, name: str, config: DoclingParserConfig) -> ParserProtocol:
    if name == 'docling':
        return DoclingParser(config=config)
    else:
        raise ValueError(f'Unknown parser profile: {name!r}')
