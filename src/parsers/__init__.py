from .llama import LlamaParser, LlamaParserConfig

__all__ = [
    'LlamaParser',
    'LlamaParserConfig',
]

try:
    from .docling import DoclingParser, DoclingParserConfig
except ImportError:
    DoclingParser = None  # type: ignore[assignment]
    DoclingParserConfig = None  # type: ignore[assignment]
else:
    __all__ += [
        'DoclingParser',
        'DoclingParserConfig',
    ]
