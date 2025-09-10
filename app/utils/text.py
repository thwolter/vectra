from typing import List


def contains_phrase(texts: List[str], phrase: str) -> bool:
    """Check if phrase is present in any of the texts."""
    p = (phrase or '').strip().lower()
    return bool(p) and any(p in (t or '').lower() for t in texts)
