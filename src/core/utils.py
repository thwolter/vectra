import pathlib
import tomllib
from functools import lru_cache
from typing import Any, ClassVar

from nexor import utils as nexor_utils


class ValidatedSettings(nexor_utils.ValidatedSettings):
    """Wrapper over Nexor settings that preserves explicit validation."""

    required_keys: ClassVar[list[str]] = []

    def model_post_init(self, context: Any, /) -> None:
        # Avoid automatic validation; we rely on explicit checks.
        return None

    def check_missing_keys(self) -> list[str]:
        return nexor_utils._check_missing_keys(self)


class ValidatedModel(nexor_utils.ValidatedModel):
    """Wrapper over Nexor models that preserves explicit validation."""

    required_keys: ClassVar[list[str]] = []

    def model_post_init(self, context: Any, /) -> None:
        # Avoid automatic validation; we rely on explicit checks.
        return None

    def check_missing_keys(self) -> list[str]:
        return nexor_utils._check_missing_keys(self)


FingerprintMixin = nexor_utils.FingerprintMixin
parse_cors_origins = nexor_utils.parse_cors_origins
