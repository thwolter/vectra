from __future__ import annotations

import sys

from loguru import logger

from app.core.config import get_settings

_configured = False


def configure_logging() -> None:
    """Configure logging sinks for console and OpenTelemetry.

    - Console: plain text to stderr for human-friendly local/dev logs.
    - OpenTelemetry: forward a JSON payload via std logging so OTEL logging
      auto-instrumentation (enabled by `opentelemetry-instrument`) can export
      it to the configured OTLP endpoint.

    Idempotent and controlled by Settings and OTEL_* env.
    """
    import json
    import logging
    import os
    from datetime import datetime, timezone

    global _configured
    if _configured:
        return

    settings = get_settings()

    if settings.log_remove_default_sink:
        # Remove default stderr sink to avoid duplicate logs
        logger.remove()

    # 1) Console sink — plain text
    logger.add(
        sys.stderr,
        level=settings.log_level,
        enqueue=settings.log_enqueue,
        backtrace=settings.log_backtrace,
        diagnose=settings.log_diagnose,
        serialize=False if settings.log_console_plain else False,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
    )

    # 2) OpenTelemetry bridge — emit JSON to std logging so OTEL picks it up
    otel_logs_exporter = os.getenv("OTEL_LOGS_EXPORTER", "otlp").lower()
    otel_enabled = os.getenv("OTEL_ENABLED", "true").lower() == "true"
    if settings.monitoring_enabled and otel_enabled and otel_logs_exporter != "none" and settings.log_otel_json:
        level_map = {
            "TRACE": logging.DEBUG,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "SUCCESS": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        def _otel_sink(message: "logger.Message") -> None:  # type: ignore[name-defined]
            record = message.record
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record["level"].name,
                "message": record["message"],
                "name": record["name"],
                "function": record["function"],
                "line": record["line"],
                "module": record["module"],
                "file": record["file"].name if record.get("file") else None,
                "process": record.get("process").id if record.get("process") else None,
                "thread": record.get("thread").id if record.get("thread") else None,
                "extra": record.get("extra", {}),
            }
            lvl = level_map.get(record["level"].name, logging.INFO)
            logging.getLogger("app.otel").log(lvl, json.dumps(payload, separators=(",", ":")))

        logger.add(
            _otel_sink,
            level=settings.log_level,
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )

    _configured = True
