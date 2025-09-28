#!/usr/bin/env bash
set -euo pipefail

# docker-build.sh — Build the vecapi Docker image
# Usage:
#   scripts/docker-build.sh [TAG]
# Examples:
#   scripts/docker-build.sh               # builds vecapi:latest
#   scripts/docker-build.sh myrepo/vecapi:dev
#
# Notes:
# - Uses DOCKER_BUILDKIT for faster, cached builds when available.
# - Respects Dockerfile in repo root.

TAG="${1:-vecapi:latest}"

export DOCKER_BUILDKIT=1

echo "[docker-build] Building image with tag: ${TAG}"
docker build -t "${TAG}" .

echo "[docker-build] Done: ${TAG}"