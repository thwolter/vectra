#!/usr/bin/env bash
set -euo pipefail

# set-otel-to-zshrc.sh — Add/replace OTEL env vars in ~/.zshrc from a .env file
#
# This script reads the following variables from a .env file in the repo
# and ensures your ~/.zshrc contains matching export lines (replacing existing ones):
#   - OTEL_EXPORTER_OTLP_ENDPOINT
#   - OTEL_EXPORTER_OTLP_PROTOCOL
#   - OTEL_EXPORTER_OTLP_HEADERS
#
# Usage:
#   scripts/set-otel-to-zshrc.sh [--env PATH_TO_ENV] [--zshrc PATH_TO_ZSHRC]
#
# Defaults:
#   --env   ./.env (repo root)
#   --zshrc ~/.zshrc
#
# Notes:
# - Idempotent: running multiple times will keep ~/.zshrc up to date.
# - Makes a timestamped backup of ~/.zshrc before modifying it.
# - Only variables found in the .env will be written; missing ones are skipped.
# - Values are written with double quotes to preserve special characters.

ENV_FILE=".env"
ZSHRC_FILE="$HOME/.zshrc"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="$2"; shift 2 ;;
    --zshrc)
      ZSHRC_FILE="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,40p' "$0"
      exit 0 ;;
    *)
      echo "[set-otel] Unknown argument: $1" >&2
      exit 1 ;;
  esac
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[set-otel] .env file not found: $ENV_FILE" >&2
  exit 1
fi

# Read a VAR from .env, ignoring comments and blank lines, taking the first exact match
read_env_var() {
  local var_name="$1"
  # Use grep to find an exact start-of-line match; then cut after the first '='
  local line
  line=$(grep -E "^${var_name}=" "$ENV_FILE" | head -n 1 || true)
  if [[ -z "$line" ]]; then
    return 1
  fi
  # Strip VAR= prefix only for the first '=' occurrence
  echo "${line#${var_name}=}"
}

# Cross-platform in-place sed (BSD/macOS and GNU)
inplace_sed() {
  if sed --version >/dev/null 2>&1; then
    sed -i "$@"
  else
    # BSD sed (macOS)
    sed -i '' "$@"
  fi
}

# Ensure ~/.zshrc exists
if [[ ! -f "$ZSHRC_FILE" ]]; then
  touch "$ZSHRC_FILE"
fi

# Backup ~/.zshrc once per run
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="${ZSHRC_FILE}.bak.${TS}"
cp "$ZSHRC_FILE" "$BACKUP_FILE"
echo "[set-otel] Backup created: $BACKUP_FILE"

ensure_export() {
  local var_name="$1"
  local value="$2"
  local export_line="export ${var_name}=\"${value}\""

  # Replace if a line starting with export VAR= or VAR= already exists; otherwise append
  if grep -qE "^(export\s+)?${var_name}=" "$ZSHRC_FILE"; then
    inplace_sed "s|^(export[[:space:]]+)?${var_name}=.*$|${export_line}|" "$ZSHRC_FILE"
    echo "[set-otel] Updated ${var_name} in ${ZSHRC_FILE}"
  else
    {
      echo ""
      echo "# Added by set-otel-to-zshrc.sh (${TS})"
      echo "$export_line"
    } >> "$ZSHRC_FILE"
    echo "[set-otel] Added ${var_name} to ${ZSHRC_FILE}"
  fi
}

updated_any=false

if val=$(read_env_var OTEL_EXPORTER_OTLP_ENDPOINT); then
  ensure_export OTEL_EXPORTER_OTLP_ENDPOINT "$val"
  updated_any=true
else
  echo "[set-otel] Skipping: OTEL_EXPORTER_OTLP_ENDPOINT not found in $ENV_FILE"
fi

if val=$(read_env_var OTEL_EXPORTER_OTLP_PROTOCOL); then
  ensure_export OTEL_EXPORTER_OTLP_PROTOCOL "$val"
  updated_any=true
else
  echo "[set-otel] Skipping: OTEL_EXPORTER_OTLP_PROTOCOL not found in $ENV_FILE"
fi

if val=$(read_env_var OTEL_EXPORTER_OTLP_HEADERS); then
  ensure_export OTEL_EXPORTER_OTLP_HEADERS "$val"
  updated_any=true
else
  echo "[set-otel] Skipping: OTEL_EXPORTER_OTLP_HEADERS not found in $ENV_FILE"
fi

if [[ "$updated_any" == false ]]; then
  echo "[set-otel] No OTEL variables were updated. Nothing to do."
else
  echo "[set-otel] Done. Open a new terminal or 'source $ZSHRC_FILE' to apply."
fi
