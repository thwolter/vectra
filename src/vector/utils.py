from typing import Optional

from langchain_core.documents import Document


def estimate_text_tokens(text: Optional[str]) -> int:
    """Estimate token count for a text.

    This is a simple heuristic (≈ 4 chars per token for English). It avoids zero by
    returning at least 1 for any non-empty string.
    """
    if text is None:
        return 1
    s = str(text).strip()
    if not s:
        return 1
    return max(1, len(s) // 4)


def estimate_docs_tokens(docs: list[Document]) -> int:
    """Estimate total tokens for a collection of documents."""
    return sum([estimate_text_tokens(doc.page_content) for doc in docs])


def get_doc_content(doc: Document) -> str:
    """Safely extract content from a Document supporting different attributes.

    Prefers `page_content`, falls back to `content`, otherwise returns empty string.
    """
    return getattr(doc, 'page_content', None) or getattr(doc, 'content', '') or ''


def validate_docs(docs: list[Document]) -> tuple[list[Document], list[str]]:
    """Validate documents for ingestion.

    Rules:
    - Filter out docs missing non-empty page_content (or fallback content).
    - Return a tuple of (valid_docs, errors) with human-readable error strings.
    """
    if not docs:
        return [], []

    valid: list[Document] = []
    errors: list[str] = []
    for i, doc in enumerate(docs):
        reasons: list[str] = []

        # Ensure metadata is a dict (not used for validation now but normalized)
        _ = doc.metadata if isinstance(doc.metadata, dict) else {}

        content = get_doc_content(doc).strip()
        if not content:
            reasons.append('missing page_content')

        if reasons:
            errors.append(f'doc[{i}] invalid: {", ".join(reasons)}')
        else:
            valid.append(doc)

    return valid, errors
