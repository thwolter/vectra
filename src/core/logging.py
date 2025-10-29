from __future__ import annotations

import sys

from loguru import logger

from core.config import get_settings

_configured = False


def _map_loguru_level(level_name: str) -> int:
    import logging

    mapping = {
        'TRACE': logging.DEBUG,
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'SUCCESS': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }
    return mapping.get(level_name.upper(), logging.INFO)


def configure_logging() -> None:
    """Configure logging for console and OpenTelemetry Logs.

    - Console: human-friendly plain text to stderr (Loguru).
    - OpenTelemetry Logs: configure SDK LoggerProvider with OTLP exporter and
      bridge Loguru records into Python stdlib logging so they are exported.

    Idempotent and controlled by Settings and OTEL_* env.
    """
    import logging
    from typing import Dict

    from opentelemetry.sdk.resources import Resource

    try:
        # OTEL Logs SDK (available in opentelemetry-sdk >= 1.21)
        from opentelemetry._logs import set_logger_provider

        # HTTP/protobuf exporter (honors OTEL_EXPORTER_OTLP_* env vars)
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    except Exception:
        LoggerProvider = None  # type: ignore
        LoggingHandler = None  # type: ignore
        set_logger_provider = None  # type: ignore
        BatchLogRecordProcessor = None  # type: ignore
        OTLPLogExporter = None  # type: ignore

    global _configured
    if _configured:
        return

    settings = get_settings()

    # Remove default sink to avoid duplicates (uvicorn also configures logging)
    if settings.log_remove_default_sink:
        logger.remove()

    # 1) Console sink — plain text
    logger.add(
        sys.stderr,
        level=settings.log_level,
        enqueue=settings.log_enqueue,
        backtrace=settings.log_backtrace,
        diagnose=settings.log_diagnose,
        serialize=False,  # keep console human readable
        format='<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
        '<level>{level: <8}</level> | '
        '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - '
        '<level>{message}</level>',
    )

    # 2) OpenTelemetry Logs pipeline (optional)
    if (
        settings.monitoring_enabled
        and settings.otel_enabled
        and settings.otel_logs_exporter != 'none'
        and LoggerProvider is not None
    ):
        # Build Resource for logs as well
        resource = Resource.create(
            {
                'service.name': settings.service_name_app,
                'service.namespace': settings.service_namespace,
                'deployment.environment': settings.deployment_env,
            }
        )

        provider = LoggerProvider(resource=resource)  # type: ignore[call-arg]
        exporter = OTLPLogExporter()  # type: ignore[call-arg]
        processor = BatchLogRecordProcessor(exporter)  # type: ignore[call-arg]
        provider.add_log_record_processor(processor)
        set_logger_provider(provider)  # type: ignore[misc]

        # Attach OTEL LoggingHandler to stdlib root logger
        std_logging_handler = LoggingHandler(level=logging.NOTSET)  # type: ignore[call-arg]
        root_logger = logging.getLogger()
        # Prevent duplicate handlers if function called twice in tests
        if not any(isinstance(h, type(std_logging_handler)) for h in root_logger.handlers):
            root_logger.addHandler(std_logging_handler)
        root_logger.setLevel(_map_loguru_level(settings.log_level))

        # Bridge Loguru to stdlib logging so OTEL pipeline sees Loguru records
        level_map: Dict[str, int] = {
            'TRACE': logging.DEBUG,
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'SUCCESS': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
        }

        def _forward_to_stdlog(message):
            rec = message.record
            lvl = level_map.get(rec['level'].name, logging.INFO)
            extra = rec.get('extra', {})
            logging.getLogger(rec['name']).log(lvl, rec['message'], extra=extra)

        logger.add(
            _forward_to_stdlog,
            level=settings.log_level,
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )

    _configured = True
