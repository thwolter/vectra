from app.parsers.docling import DoclingParser
from app.parsers.protocols import ParserProtocol

_PARSER_REGISTRY: dict = {
    'docling': DoclingParser,
    'auto': DoclingParser,
    # "pdfminer": PdfMinerParser,
}


def parser_provider(*, file_path: str, profile: str) -> ParserProtocol:
    try:
        parser_cls = _PARSER_REGISTRY[profile]
    except KeyError as e:
        raise ValueError(f'Unknown parser profile: {profile!r}') from e
    return parser_cls(file=file_path)
