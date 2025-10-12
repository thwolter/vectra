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
