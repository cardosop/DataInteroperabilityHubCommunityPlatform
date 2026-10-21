#!/usr/bin/env bash
# =============================================================================
# scripts/stage_config_artifacts.sh — W0.7 (oss-release-remediation)
#
# Copies the ro config artifacts the staging compose mounts (init SQL,
# pgbouncer/fuseki/traefik configs, monitoring configs, the prefect
# integration tree) into the gitignored
# `infrastructure/staging/config-artifacts/` dir and writes a SHA256SUMS
# manifest. The staging containers mount ONLY these staged copies — the
# repo sources are never bind-mounted into a staging container again
# (the `.:/app` RW mount exposure).
#
# Idempotent: every run re-syncs the sources into the dest (staging-up
# semantics — the artifacts are the sanctioned copies) and rewrites the
# manifest. A missing source FAILS loudly.
#
# Usage:
#   bash scripts/stage_config_artifacts.sh                  # repo defaults
#   bash scripts/stage_config_artifacts.sh --source-root SRC --dest DEST
#   bash scripts/stage_config_artifacts.sh --pg-role ROLE   # override the
#       app-DB role substituted into scripts/init-db.sql
#       (default: POSTGRES_USER from .env.staging; FAILS loudly when
#       neither is available — W11.11: the verbatim copy shipped the
#       TEST-stack `FOR ROLE hub_test` lines to staging, whose
#       default-privileges grants then failed on initdb and left the
#       admin-alias login lookup without SELECT on `users`)
#
# Never prints file contents — paths and counts only.
# =============================================================================
set -euo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${SOURCE_ROOT}/infrastructure/staging/config-artifacts"
PG_ROLE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-root) SOURCE_ROOT="$(cd "$2" && pwd)"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    --pg-role) PG_ROLE="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${PG_ROLE}" ]]; then
  ENV_STAGING="${SOURCE_ROOT}/.env.staging"
  if [[ -f "${ENV_STAGING}" ]]; then
    PG_ROLE="$(grep -E '^POSTGRES_USER=' "${ENV_STAGING}" | tail -1 | cut -d= -f2- || true)"
  fi
  if [[ -z "${PG_ROLE}" ]]; then
    echo "ERROR: cannot determine the staging app-DB role — pass --pg-role" >&2
    exit 1
  fi
fi

# Every repo-source mount the staging compose carries, as relative paths.
# Files and directories alike; the directory entries copy their trees.
ARTIFACTS=(
  "scripts/init-db.sql"
  "infrastructure/postgres/03-pgbouncer-user.sh"
  "infrastructure/pgbouncer/pgbouncer.staging.ini"
  "infrastructure/fuseki/config.ttl"
  "scripts/fuseki_password_sync.sh"
  "scripts/wait_for_prefect_db.py"
  "services/prefect-integration"
  "monitoring/prometheus/prometheus.yml"
  "monitoring/prometheus/alerts.yml"
  "monitoring/prometheus/alerts"
  "monitoring/grafana/dashboards"
  "monitoring/grafana/datasources"
  "monitoring/alertmanager/alertmanager-staging.yml"
  "infrastructure/traefik/traefik-staging.yml"
  "infrastructure/traefik/dynamic"
)

missing=0
for rel in "${ARTIFACTS[@]}"; do
  if [[ ! -e "${SOURCE_ROOT}/${rel}" ]]; then
    echo "ERROR: staging artifact source missing: ${rel}" >&2
    missing=1
  fi
done
[[ "$missing" -eq 0 ]] || exit 1

mkdir -p "${DEST}"
copied=0
for rel in "${ARTIFACTS[@]}"; do
  target="${DEST}/${rel}"
  mkdir -p "$(dirname "${target}")"
  if [[ -d "${SOURCE_ROOT}/${rel}" ]]; then
    # W0.8: content-sync IN PLACE — never `rm -rf` + recreate a directory
    # that a running container bind-mounts: docker keeps the mount
    # attached to the deleted inode and the container sees "no such file
    # or directory" forever (the live grafana dashboards mount broke
    # after a re-stage while the stack was up). Replace the CONTENTS
    # (stale files refresh out), preserve the directory identity.
    find "${target}" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
    cp -r "${SOURCE_ROOT}/${rel}/." "${target}/"
  else
    cp "${SOURCE_ROOT}/${rel}" "${target}"
    if [[ "${rel}" == "scripts/init-db.sql" ]]; then
      # W11.11: the repo source names the TEST-stack app role in its
      # `FOR ROLE` default-privileges lines; the staged copy must name
      # the STAGING app role or those grants fail on staging initdb.
      sed -i "s/FOR ROLE hub_test IN SCHEMA/FOR ROLE ${PG_ROLE} IN SCHEMA/g" "${target}"
    fi
  fi
  copied=$((copied + 1))
done

# SHA256SUMS manifest — one row per FILE under the dest tree (the
# container mounts read it only for the record; GATE-side pins parse it).
(
  cd "${DEST}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum
) > "${DEST}/SHA256SUMS"

echo "staged ${copied} artifacts -> ${DEST} (SHA256SUMS written)"
