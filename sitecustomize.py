# Ensure the project 'app' directory is on sys.path so absolute imports like
# 'utils' and other modules resolve when running tests.
# This is a minimal, test-friendly adjustment and does not affect production
# packaging where proper module configuration should be used.

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(__file__)
APP_DIR = os.path.join(ROOT, 'app')

if os.path.isdir(APP_DIR) and APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Suppress noisy Pydantic warnings originating from third‑party libraries
try:
    import warnings

    try:  # pydantic v2 exposes specific warning classes
        from pydantic.warnings import UnsupportedFieldAttributeWarning  # type: ignore
    except Exception:  # pragma: no cover - fallback if pydantic internals change

        class UnsupportedFieldAttributeWarning(Warning):  # type: ignore
            pass

    # Some dependencies pass `validate_default` in Field() incorrectly; ignore that warning
    warnings.filterwarnings('ignore', category=UnsupportedFieldAttributeWarning)
except Exception:
    # Never fail app startup because of warning filter issues
    pass
