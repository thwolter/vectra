#!/usr/bin/env bash
set -euo pipefail

# run-jaeger.sh — Start a local Jaeger all-in-one container
#
# Default equivalent to:
#   docker run --rm --name jaeger \
#     -p 16686:16686 \
#     -p 4317:4317 \
#     -p 4318:4318 \
#     -p 5778:5778 \
#     -p 9411:9411 \
#     cr.jaegertracing.io/jaegertracing/jaeger:2.10.0
#
# Usage:
#   scripts/run-jaeger.sh [--version 2.10.0] [--name jaeger] [--no-detach]
#
# Notes:
# - By default runs with --detach so it doesn't block your terminal.
# - Use --no-detach to run in the foreground (Ctrl+C to stop). Container is
#   created with --rm so it will be removed on stop.
# - UI available at http://localhost:16686
# - OTLP gRPC endpoint at 4317, OTLP HTTP at 4318.

IMAGE="cr.jaegertracing.io/jaegertracing/jaeger"
VERSION="2.10.0"
NAME="jaeger"
DETACH=true

print_help() {
  cat <<EOF
Start a local Jaeger all-in-one container.

Options:
  --version <ver>   Jaeger image version (default: ${VERSION})
  --name <name>     Container name (default: ${NAME})
  --no-detach       Run in foreground (default: detached)
  -h, --help        Show this help

Exposed ports:
  16686  Jaeger UI (http://localhost:16686)
  4317   OTLP gRPC
  4318   OTLP HTTP
  5778   Config (agent thrift)
  9411   Zipkin compatible
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --name)
      NAME="${2:-}"
      shift 2
      ;;
    --no-detach)
      DETACH=false
      shift 1
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      print_help
      exit 1
      ;;
  esac
done

# If a container with the same name exists (even exited), remove it to avoid conflicts.
if docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
  echo "[run-jaeger] Removing existing container '${NAME}'"
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
fi

RUN_ARGS=(
  run --rm --name "${NAME}"
  -p 16686:16686
  -p 4317:4317
  -p 4318:4318
  -p 5778:5778
  -p 9411:9411
)

if [[ "${DETACH}" == "true" ]]; then
  RUN_ARGS+=( -d )
fi

echo "[run-jaeger] Starting ${IMAGE}:${VERSION} as '${NAME}'"
docker "${RUN_ARGS[@]}" "${IMAGE}:${VERSION}"

if [[ "${DETACH}" == "true" ]]; then
  echo "[run-jaeger] Jaeger is running in the background. UI: http://localhost:16686"
  echo "[run-jaeger] Stop with: docker stop ${NAME} (container will be removed due to --rm)"
fi
