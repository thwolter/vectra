from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.core.config import get_settings

_configured = False


def configure_logging() -> None:
    """Configure Loguru to log to a file with rotation and env-driven settings.

    Reads settings from app.core.config.Settings which are populated via .env.
    Creates the parent directory for the log file if it does not exist.
    Idempotent: safe to call multiple times per process.
    """
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.log_remove_default_sink:
        # Remove default stderr sink to avoid duplicate logs
        logger.remove()

    logger.add(
        str(log_path),
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression=settings.log_compression,
        enqueue=settings.log_enqueue,
        backtrace=settings.log_backtrace,
        diagnose=settings.log_diagnose,
        serialize=settings.log_serialize,
    )

    _configured = True
