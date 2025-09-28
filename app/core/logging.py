from __future__ import annotations

import sys

from loguru import logger

from app.core.config import get_settings

_configured = False


def configure_logging() -> None:
    """Configure Loguru to log to console (stderr) with env-driven settings.

    Uses settings from app.core.config.Settings. This configuration removes any
    file sinks and ensures logs are emitted to the container/console only.
    Idempotent: safe to call multiple times per process.
    """
    global _configured
    if _configured:
        return

    settings = get_settings()

    if settings.log_remove_default_sink:
        # Remove default stderr sink to avoid duplicate logs
        logger.remove()

    # Console-only logging (stderr), suitable for Docker/Kubernetes aggregation
    logger.add(
        sys.stderr,
        level=settings.log_level,
        enqueue=settings.log_enqueue,
        backtrace=settings.log_backtrace,
        diagnose=settings.log_diagnose,
        serialize=settings.log_serialize,
    )

    _configured = True
