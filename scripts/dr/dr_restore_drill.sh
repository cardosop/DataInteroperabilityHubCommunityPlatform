#!/usr/bin/env bash
# =============================================================================
# scripts/dr/dr_restore_drill.sh — the REAL DR restore drill (pilot-readiness
# 4.4, "disaster_recovery suite as a REAL drill").
#
# Takes a real backup of a running compose-path Postgres, restores it into a
# SCRATCH database, verifies row-count parity between live and scratch, then
# writes a drill report (JSON + Markdown) under
# docs/operations/dr-drill-reports/YYYY-MM/ per the Disaster Recovery Policy
# ("Each report includes: drill date and operator, RTO achieved vs. target,
# snapshot ID used, any failures or anomalies, corrective actions").
#
# Unlike staging-compose-backup-restore.sh (staging-only), this drill is
# parameterized over the compose file + env file + service name, so the same
# drill procedure rehearses against whichever stack is up: the shared test
# stack today (docker-compose.test.yml), the staging stack when it exists
# (docker-compose.staging.yml), and any future environment. The procedure —
# not the file names — is what the drill certifies.
#
# Subcommands:
#   backup        — pg_dump (custom format) the live database + SHA-256
#                   manifest, then sweep dumps older than the retention window.
#   restore-drill — verify the latest dump's manifest, restore it into a
#                   scratch database (<db>_restore_drill), row-count parity
#                   between live and scratch, drop the scratch database,
#                   emit the drill report.
#
# Safety: the live database is only ever READ (pg_dump, count queries). The
# scratch database has a fixed `_restore_drill` suffix and is always dropped
# at the end (--keep-scratch for debugging). CREATE/DROP DATABASE run on the
# `postgres` maintenance database, never inside the live database.
#
# Usage:
#   bash scripts/dr/dr_restore_drill.sh backup
#   bash scripts/dr/dr_restore_drill.sh restore-drill --label "pilot 4.4"
#   bash scripts/dr/dr_restore_drill.sh --dry-run restore-drill
#   RETENTION_DAYS=7 PARITY_TABLES="tenants users files" \
#     bash scripts/dr/dr_restore_drill.sh restore-drill
#
# Exit codes: 0 success; 1 usage/precondition; 2 backup failure;
#             3 restore or parity failure.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

# ─── Configuration (flags override) ──────────────────────────────────────────
COMPOSE_FILE="docker-compose.test.yml"
ENV_FILE=".env.test"
SERVICE="postgres"
PROJECT_NAME=""
BACKUP_DIR="backups/dr-drill"
REPORT_DIR="docs/operations/dr-drill-reports"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
LABEL=""
DRY_RUN=false
KEEP_SCRATCH=false
# Parity probe: tables whose row counts MUST match between live and scratch.
# Unqualified names — this repo's schema uses short db_table names
# (users, roles, tenants, audit_events, files, assets), verified live
# 2026-10-06 against hub_test_test_shared.
PARITY_TABLES="${PARITY_TABLES:-tenants users audit_events files assets}"
# RTO target from the DR policy (4 hours) — overridable for rehearsals.
TARGET_RTO_SECONDS="${DR_TARGET_RTO_SECONDS:-14400}"
OPERATOR="${DR_OPERATOR:-$(id -un)}"

SUBCOMMAND=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)          DRY_RUN=true; shift ;;
    --compose-file)     COMPOSE_FILE="$2"; shift 2 ;;
    --env-file)         ENV_FILE="$2"; shift 2 ;;
    --service)          SERVICE="$2"; shift 2 ;;
    --project-name)     PROJECT_NAME="$2"; shift 2 ;;
    --backup-dir)       BACKUP_DIR="$2"; shift 2 ;;
    --report-dir)       REPORT_DIR="$2"; shift 2 ;;
    --retention-days)   RETENTION_DAYS="$2"; shift 2 ;;
    --parity-tables)    PARITY_TABLES="$2"; shift 2 ;;
    --label)            LABEL="$2"; shift 2 ;;
    --keep-scratch)     KEEP_SCRATCH=true; shift ;;
    backup|restore-drill) SUBCOMMAND="$1"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

[[ -n "${SUBCOMMAND}" ]] || { echo "usage: $0 [flags] backup|restore-drill" >&2; exit 1; }

# --project-name pins the compose project explicitly: the running stack's
# project was derived from the checkout path at bring-up time, and any
# invocation from a different cwd (e.g. inside the api container, where the
# repo lives at /app) would otherwise derive a different name and see
# "service not running" against a healthy stack.
DC=(docker compose)
[[ -n "${PROJECT_NAME}" ]] && DC+=(--project-name "${PROJECT_NAME}")
DC+=(-f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")

# Echo-form of the compose prefix for [DRY-RUN] lines (the array form is not
# printable).
DC_ECHO="docker compose"
[[ -n "${PROJECT_NAME}" ]] && DC_ECHO+=" --project-name ${PROJECT_NAME}"
DC_ECHO+=" -f ${COMPOSE_FILE} --env-file ${ENV_FILE}"

# ─── Env-file resolution (compose --env-file keeps the LAST occurrence) ──────
# The definitive source is the RESOLVED compose config (interpolation +
# defaults applied) — some stacks only carry the password via the compose
# file's ${VAR:-default} (e.g. the test stack's POSTGRES_TEST_PASSWORD), so
# grepping the env file alone silently finds nothing.
env_get() { grep -E "^${1}=" "${ENV_FILE}" | tail -1 | cut -d= -f2-; }
compose_get() {
  "${DC[@]}" config 2>/dev/null \
    | sed -n "s/^[[:space:]]*${1}: //p" | head -1 | tr -d '"'
}
POSTGRES_USER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(env_get POSTGRES_DB)}"
POSTGRES_USER="${POSTGRES_USER:-$(compose_get POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(compose_get POSTGRES_DB)}"
POSTGRES_USER="${POSTGRES_USER:-hub}"
POSTGRES_DB="${POSTGRES_DB:-hub}"
PGPASSWORD_VALUE="$(env_get POSTGRES_PASSWORD)"
PGPASSWORD_VALUE="${PGPASSWORD_VALUE:-$(compose_get POSTGRES_PASSWORD)}"
SCRATCH_DB="${POSTGRES_DB}_restore_drill"

log()      { echo "[dr-drill] $*"; }
log_ok()   { echo "[dr-drill] [OK]    $*"; }
log_warn() { echo "[dr-drill] [WARN]  $*" >&2; }
err()      { echo "[dr-drill] [ERROR] $*" >&2; }

# run CMD [ARGS...] — dry-run prints, live executes.
run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] $*"
    return 0
  fi
  "$@"
}

# pg_exec SQL — run psql inside the postgres container (maintenance DB safe).
pg_exec() {
  local db="$1" sql="$2"
  run "${DC[@]}" exec -T -e PGPASSWORD="${PGPASSWORD_VALUE}" "${SERVICE}" \
    psql -U "${POSTGRES_USER}" -d "${db}" -tAc "${sql}"
}

preflight() {
  command -v docker >/dev/null 2>&1 || { err "docker not found"; exit 1; }
  [[ -f "${ENV_FILE}" ]] || { err "${ENV_FILE} not found — run from the repo root"; exit 1; }
  if [[ "${DRY_RUN}" != "true" ]]; then
    "${DC[@]}" ps --status running "${SERVICE}" >/dev/null 2>&1 || {
      err "${SERVICE} service is not running (compose ${COMPOSE_FILE}) — bring the stack up first"
      exit 1
    }
    [[ -n "${PGPASSWORD_VALUE}" ]] || { err "POSTGRES_PASSWORD missing from ${ENV_FILE}"; exit 1; }
  fi
}

# write_report JSON_FILE — render the drill report (JSON) + Markdown twin.
write_report() {
  local json_file="$1" report_basename
  report_basename="${json_file%.json}"
  run python3 - "${json_file}" "${report_basename}" <<'PY'
import json, sys
json_file, base = sys.argv[1], sys.argv[2]
with open(json_file) as f:
    report = json.load(f)
md = f"""# DR Restore Drill — {report['timestamp'][:10]}

| Field | Value |
|---|---|
| Drill | `{report['drill']}` |
| Label | {report['label'] or '—'} |
| Operator | `{report['operator']}` |
| Environment | {report['environment']} ({report['compose_file']}) |
| Database | `{report['database']}` |
| Backup file | `{report['backup_file']}` |
| RTO achieved | {report['rto_seconds']}s |
| RTO target | {report['target_rto_seconds']}s |
| RTO within target | {'YES' if report['rto_within_target'] else 'NO'} |
| Status | **{report['status']}** |

## Parity

| Table | Live | Scratch | Match |
|---|---|---|---|
"""
for p in report["parity"]:
    md += f"| `{p['table']}` | {p['live_count']} | {p['scratch_count']} | {'✅' if p['match'] else '❌'} |\n"
if report["anomalies"]:
    md += "\n## Anomalies / Corrective Actions\n\n"
    for a in report["anomalies"]:
        md += f"- {a}\n"
else:
    md += "\n## Anomalies / Corrective Actions\n\nNone.\n"
with open(base + ".md", "w") as f:
    f.write(md)
PY
}

# ═══════════════════════════════════════════════════════════════════════════════
#  backup
# ═══════════════════════════════════════════════════════════════════════════════
do_backup() {
  preflight
  local stamp dump manifest
  stamp="$(date -u '+%Y-%m-%dT%H%M%SZ')"
  dump="${POSTGRES_DB}_${stamp}.dump"
  manifest="${dump}.sha256"

  log "backup → ${BACKUP_DIR}/${dump} (retention ${RETENTION_DAYS}d)"
  run mkdir -p "${BACKUP_DIR}"

  # 1. pg_dump (custom format) — streams out of the container onto the host.
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] ${DC_ECHO} exec -T -e PGPASSWORD=*** ${SERVICE} pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} --format=custom > ${BACKUP_DIR}/${dump}"
  else
    if ! "${DC[@]}" exec -T -e PGPASSWORD="${PGPASSWORD_VALUE}" "${SERVICE}" \
      pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --format=custom \
      > "${BACKUP_DIR}/${dump}"; then
      err "pg_dump failed"
      rm -f "${BACKUP_DIR}/${dump}" "${BACKUP_DIR}/${manifest}"
      exit 2
    fi
    log_ok "pg_dump complete: ${BACKUP_DIR}/${dump}"
  fi

  # 2. SHA-256 manifest — integrity gate for every future restore.
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] sha256sum ${dump} > ${manifest}"
  else
    (cd "${BACKUP_DIR}" && sha256sum "${dump}" > "${manifest}")
    log_ok "manifest written: ${BACKUP_DIR}/${manifest}"
  fi

  # 3. Retention sweep (dump + its manifest as a pair).
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] find ${BACKUP_DIR} -name '*.dump' -mtime +${RETENTION_DAYS} -print -delete (retention sweep, RETENTION_DAYS=${RETENTION_DAYS})"
  else
    while IFS= read -r old; do
      [[ -n "${old}" ]] || continue
      rm -f "${old}" "${old}.sha256"
      log "swept ${old} (older than ${RETENTION_DAYS}d)"
    done < <(find "${BACKUP_DIR}" -name '*.dump' -mtime +"${RETENTION_DAYS}" -print)
    log_ok "retention sweep complete"
  fi

  log "backup DONE (exit 0)"
}

# ═══════════════════════════════════════════════════════════════════════════════
#  restore-drill
# ═══════════════════════════════════════════════════════════════════════════════
do_restore_drill() {
  preflight
  local dump manifest drill_start anomalies=() parity_results=()
  drill_start="$(date +%s)"

  if [[ "${DRY_RUN}" == "true" ]]; then
    # Dry-run prints the plan without requiring an existing backup dir.
    dump="<latest .dump in ${BACKUP_DIR}>"
    manifest="<matching .sha256>"
  else
    dump="$(find "${BACKUP_DIR}" -name '*.dump' -type f | sort | tail -1 || true)"
    [[ -n "${dump}" ]] || {
      err "no dumps in ${BACKUP_DIR} — run the backup subcommand first"
      exit 1
    }
    manifest="${dump}.sha256"
  fi

  # 1. Integrity gate: the dump must match its manifest before we touch it.
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] (cd ${BACKUP_DIR} && sha256sum -c ${manifest##*/}) — manifest verified before restore"
  elif [[ -f "${manifest}" ]] && (cd "${BACKUP_DIR}" && sha256sum -c "${manifest##*/}" >/dev/null 2>&1); then
    log_ok "manifest verified: ${dump}"
  else
    err "manifest check FAILED for ${dump} — do not restore a corrupt dump"
    exit 3
  fi

  log "restore drill: ${dump} → scratch DB ${SCRATCH_DB} (live DB ${POSTGRES_DB} untouched except reads)"

  # 2. Scratch database — drop-if-exists, then create fresh.
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] ${DC_ECHO} exec -T ${SERVICE} psql -d postgres -c \"DROP DATABASE IF EXISTS ${SCRATCH_DB} WITH (FORCE);\""
    echo "  [DRY-RUN] ${DC_ECHO} exec -T ${SERVICE} psql -d postgres -c \"CREATE DATABASE ${SCRATCH_DB} OWNER ${POSTGRES_USER}\""
  else
    "${DC[@]}" exec -T -e PGPASSWORD="${PGPASSWORD_VALUE}" "${SERVICE}" \
      psql -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${SCRATCH_DB} WITH (FORCE);" \
      >/dev/null 2>&1 || true
    "${DC[@]}" exec -T -e PGPASSWORD="${PGPASSWORD_VALUE}" "${SERVICE}" \
      psql -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE ${SCRATCH_DB} OWNER ${POSTGRES_USER}" \
      >/dev/null 2>&1 || { err "scratch database create failed"; exit 3; }
    log_ok "scratch database ${SCRATCH_DB} created"
  fi

  # 3. pg_restore into the scratch database.
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] ${DC_ECHO} exec -T ${SERVICE} pg_restore -U ${POSTGRES_USER} -d ${SCRATCH_DB} --clean --if-exists --no-owner < ${dump}"
  else
    "${DC[@]}" exec -T -e PGPASSWORD="${PGPASSWORD_VALUE}" "${SERVICE}" \
      pg_restore -U "${POSTGRES_USER}" -d "${SCRATCH_DB}" --clean --if-exists --no-owner \
      < "${dump}" 2>/dev/null || { err "pg_restore failed"; exit 3; }
    log_ok "pg_restore into ${SCRATCH_DB} complete"
  fi

  # 4. Row-count parity: live vs scratch for every probe table.
  local table live_count scratch_count parity_failures=0 checked=0
  for table in ${PARITY_TABLES}; do
    if [[ "${DRY_RUN}" == "true" ]]; then
      echo "  [DRY-RUN] parity: SELECT count(*) FROM ${table} (live ${POSTGRES_DB} vs scratch ${SCRATCH_DB})"
      continue
    fi
    live_count="$(pg_exec "${POSTGRES_DB}" "SELECT count(*) FROM ${table}" 2>/dev/null || echo "MISSING")"
    scratch_count="$(pg_exec "${SCRATCH_DB}" "SELECT count(*) FROM ${table}" 2>/dev/null || echo "MISSING")"
    if [[ "${live_count}" == "MISSING" && "${scratch_count}" == "MISSING" ]]; then
      log_warn "parity skip: ${table} absent from both databases"
      parity_results+=("{\"table\": \"${table}\", \"live_count\": null, \"scratch_count\": null, \"match\": null, \"note\": \"absent in both\"}")
      continue
    fi
    checked=$((checked + 1))
    if [[ "${live_count}" == "${scratch_count}" ]]; then
      log_ok "parity ${table}: ${live_count} = ${scratch_count}"
      parity_results+=("{\"table\": \"${table}\", \"live_count\": ${live_count}, \"scratch_count\": ${scratch_count}, \"match\": true}")
    else
      err "parity FAILED ${table}: live=${live_count} scratch=${scratch_count}"
      anomalies+=("parity mismatch on ${table}: live=${live_count} scratch=${scratch_count}")
      parity_results+=("{\"table\": \"${table}\", \"live_count\": ${live_count}, \"scratch_count\": ${scratch_count}, \"match\": false}")
      parity_failures=$((parity_failures + 1))
    fi
  done

  # 5. Drop the scratch database (always, unless --keep-scratch).
  if [[ "${KEEP_SCRATCH}" == "true" ]]; then
    log_warn "scratch database ${SCRATCH_DB} kept (--keep-scratch)"
  elif [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] ${DC_ECHO} exec -T ${SERVICE} psql -d postgres -c \"DROP DATABASE IF EXISTS ${SCRATCH_DB} WITH (FORCE);\""
  else
    "${DC[@]}" exec -T -e PGPASSWORD="${PGPASSWORD_VALUE}" "${SERVICE}" \
      psql -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${SCRATCH_DB} WITH (FORCE);" \
      >/dev/null 2>&1 || { err "scratch database drop failed"; exit 3; }
    log_ok "scratch database ${SCRATCH_DB} dropped"
  fi

  # 6. Drill report — JSON + Markdown under docs/operations/dr-drill-reports/.
  local rto_seconds report_month report_file status label_json env_name anomalies_json
  rto_seconds=$(( $(date +%s) - drill_start ))
  report_month="$(date -u '+%Y-%m')"
  report_file="${REPORT_DIR}/${report_month}/dr-drill-$(date -u '+%Y-%m-%dT%H%M%SZ').json"
  if [[ "${parity_failures}" -eq 0 ]]; then
    status="PASSED"
  else
    status="FAILED"
  fi
  if [[ -n "${LABEL}" ]]; then
    label_json="\"${LABEL}\""
  else
    label_json="null"
  fi
  env_name="$(env_get ENVIRONMENT 2>/dev/null || true)"
  # NOTE: "${anomalies[@]:-}" on an EMPTY array expands to one empty element
  # (classic bash trap) — guard on the array length instead.
  if [[ ${#anomalies[@]} -gt 0 ]]; then
    anomalies_json="$(for a in "${anomalies[@]}"; do printf '"%s",' "${a//\"/\\\"}"; done | sed 's/,$//')"
  else
    anomalies_json=""
  fi

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] drill-report: ${report_file} (label='${LABEL}', operator=${OPERATOR}, rto_seconds=${rto_seconds}, status=${status}, backup_file=${dump##*/})"
    echo "  [DRY-RUN] report rendered as ${report_file%.json}.md"
  else
    run mkdir -p "$(dirname "${report_file}")"
    cat > "${report_file}" <<JSON
{
  "drill": "dr-restore-drill",
  "label": ${label_json},
  "operator": "${OPERATOR}",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "environment": "${env_name:-unknown}",
  "compose_file": "${COMPOSE_FILE}",
  "database": "${POSTGRES_DB}",
  "backup_file": "${dump##*/}",
  "rto_seconds": ${rto_seconds},
  "target_rto_seconds": ${TARGET_RTO_SECONDS},
  "rto_within_target": $([ "${rto_seconds}" -le "${TARGET_RTO_SECONDS}" ] && echo true || echo false),
  "status": "${status}",
  "parity": [$(IFS=,; echo "${parity_results[*]}")],
  "anomalies": [${anomalies_json}]
}
JSON
    write_report "${report_file}"
    log_ok "drill report: ${report_file} (+ ${report_file%.json}.md)"
  fi

  if [[ "${DRY_RUN}" != "true" ]]; then
    log "restore drill: ${checked} parity table(s) checked, ${parity_failures} mismatch(es), RTO ${rto_seconds}s"
  fi
  [[ "${parity_failures}" -eq 0 ]] || { err "restore drill FAILED — parity mismatches"; exit 3; }
  log "restore-drill DONE (exit 0)"
}

case "${SUBCOMMAND}" in
  backup)        do_backup ;;
  restore-drill) do_restore_drill ;;
esac
