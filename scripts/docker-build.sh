#!/usr/bin/env bash
set -euo pipefail

# docker-build.sh — Build the vecapi Docker image
# Usage:
#   scripts/docker-build.sh [--buildx-push|--push] [TAG]
# Examples:
#   scripts/docker-build.sh                         # builds vecapi:latest locally
#   scripts/docker-build.sh myrepo/vecapi:dev       # local build with custom tag
#   scripts/docker-build.sh --push myrepo/vecapi:ci # buildx build with provenance+push
#
# Notes:
# - Uses DOCKER_BUILDKIT for faster, cached builds when available.
# - Respects Dockerfile in repo root.

MODE="docker"  # docker | buildx-push
TAG="vecapi:latest"

if [[ ${1-} == "--buildx-push" || ${1-} == "--push" ]]; then
  MODE="buildx-push"
  shift || true
fi

TAG="${1:-$TAG}"

export DOCKER_BUILDKIT=1

if [[ "$MODE" == "buildx-push" ]]; then
  echo "[docker-build] buildx build+push with provenance: ${TAG}"
  docker buildx build --provenance=mode=max --push -t "${TAG}" .
else
  echo "[docker-build] Building image locally with tag: ${TAG}"
  docker build -t "${TAG}" .
fi

echo "[docker-build] Done: ${TAG}"
