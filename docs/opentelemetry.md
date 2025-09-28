# Deployment Guide (vecapi + OpenTelemetry)

This guide documents a reproducible deployment for `vecapi` with **uv**, **Docker**, **OpenTelemetry auto-instrumentation**, and **Grafana Cloud OTLP**. It covers local smoke tests, container build, environment configuration, and production rollout (e.g., Coolify).

---

## 1) Prerequisites

- Python 3.11+ locally (for quick checks)  
- Docker / container runtime  
- A Postgres instance (network-reachable from the app)  
- Grafana Cloud (or Grafana Agent/Tempo/OTLP endpoint) + an **OTLP access token**

---

## 2) Project dependencies (uv)

Install core deps and set up auto-instrumentation in a way that plays nicely with `uv`:

```bash
# In the project root
uv add opentelemetry-distro opentelemetry-exporter-otlp

# Discover and install per-integration instrumentations via uv (NOT pip)
uv run opentelemetry-bootstrap -a requirements | uv pip install --requirement -