from typing import Any

from nexor.logging import LogExporterSettings


def build_log_export_settings(settings: Any, *, service_name: str | None) -> LogExporterSettings:
    """Produce a default OTLP exporter config for vectra deployments."""
    enabled = bool(
        getattr(settings, 'monitoring_enabled', False)
        and getattr(settings, 'otel_enabled', False)
        and getattr(settings, 'otel_logs_exporter', 'otlp') != 'none'
    )

    return LogExporterSettings(
        enabled=enabled,
        service_name=service_name,
        service_namespace=getattr(settings, 'service_namespace', None),
        deployment_environment=getattr(settings, 'deployment_env', None),
    )
