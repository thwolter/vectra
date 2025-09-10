from typing import Annotated

from pydantic import StringConstraints


# 32-byte SHA-256 as *standard* Base64 (uses + /), padded: 43 chars + trailing '='
SHA256B64 = Annotated[
    str,
    StringConstraints(min_length=44, max_length=44, pattern=r'^[A-Za-z0-9+/]{43}=$'),
]
