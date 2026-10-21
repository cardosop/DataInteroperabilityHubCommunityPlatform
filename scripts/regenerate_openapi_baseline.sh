#!/usr/bin/env bash
# Phase 232.8.17 — Regenerate the checked-in OpenAPI JSON baseline (drift gate input).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/docs/api/openapi-baseline.json"

if docker compose -f "${ROOT}/docker-compose.yml" ps -q api-service &>/dev/null; then
  echo "Using docker compose exec api-service …"
  docker compose -f "${ROOT}/docker-compose.yml" exec -T api-service \
    python hub/manage.py spectacular --color --file /tmp/openapi-baseline.json
  docker compose -f "${ROOT}/docker-compose.yml" cp "api-service:/tmp/openapi-baseline.json" "${OUT}"
else
  export PYTHONPATH="${PYTHONPATH:-${ROOT}}"
  export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-hub.settings}"
  cd "${ROOT}"
  python hub/manage.py spectacular --color --file "${OUT}"
fi

echo "Wrote ${OUT}"
