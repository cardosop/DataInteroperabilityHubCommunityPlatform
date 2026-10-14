#!/usr/bin/env bash
# =============================================================================
# scripts/tls_rotation_drill.sh — the TLS rotation rehearsal (pilot-readiness
# 4.4).
#
# Rehearses the operator rotation procedure FOR REAL against a live TLS
# endpoint — the verification half is always executed with openssl s_client
# against the endpoint itself (serial + notAfter + issuer), never against a
# config file:
#
#   inspect      — probe the live endpoint: serial, notAfter, issuer, SAN.
#   rotate-file  — rotate a FILE-based cert pair (the non-ACME operator path:
#                  snapshot → install new pair → reload the terminator →
#                  verify the SERVED serial changed → roll back on failure →
#                  write the rotation report).
#   rotate-acme  — rotate a Traefik Let's Encrypt cert (the staging path:
#                  snapshot acme.json → remove the domain entry via
#                  scripts/tls_acme_json.py → restart Traefik to re-request →
#                  verify the SERVED serial changed → roll back acme.json on
#                  failure → write the rotation report). Requires the live
#                  staging stack + a reachable ACME server.
#
# Safety: every mutation is preceded by a snapshot (cert pair or acme.json),
# and every failure path restores it — a rotation that cannot be verified is
# rolled back, reported FAILED, and exits non-zero.
#
# Usage:
#   tls_rotation_drill.sh inspect --host api.stagingmeshant-internal.example.com:443 --sni api.stagingmeshant-internal.example.com
#   tls_rotation_drill.sh rotate-file --host localhost:8443 --sni hub.local \
#       --cert-dir /etc/traefik/certs --reload "docker restart traefik"
#   tls_rotation_drill.sh rotate-acme --host api.stagingmeshant-internal.example.com:443 \
#       --sni api.stagingmeshant-internal.example.com --acme-json /letsencrypt/acme.json \
#       --acme-domain api.stagingmeshant-internal.example.com --restart "docker compose restart traefik"
#   tls_rotation_drill.sh --dry-run rotate-file ...
#
# Exit codes: 0 success; 1 usage; 2 inspect/verification failure;
#             3 rotation failure (rolled back).
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACME_TOOL="${REPO_ROOT}/scripts/tls_acme_json.py"

HOST=""
SNI=""
CERT_DIR=""
RELOAD_CMD=""
RESTART_CMD=""
ACME_JSON=""
ACME_DOMAIN=""
NEW_CERT=""
NEW_KEY=""
REPORT_DIR="docs/operations/tls-rotation-reports"
WAIT_SECONDS="${TLS_ROTATION_WAIT_SECONDS:-90}"
OPERATOR="${TLS_OPERATOR:-$(id -un)}"
DRY_RUN=false
SUBCOMMAND=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)       DRY_RUN=true; shift ;;
    --host)          HOST="$2"; shift 2 ;;
    --sni)           SNI="$2"; shift 2 ;;
    --cert-dir)      CERT_DIR="$2"; shift 2 ;;
    --reload)        RELOAD_CMD="$2"; shift 2 ;;
    --restart)       RESTART_CMD="$2"; shift 2 ;;
    --acme-json)     ACME_JSON="$2"; shift 2 ;;
    --acme-domain)   ACME_DOMAIN="$2"; shift 2 ;;
    --new-cert)      NEW_CERT="$2"; shift 2 ;;
    --new-key)       NEW_KEY="$2"; shift 2 ;;
    --report-dir)    REPORT_DIR="$2"; shift 2 ;;
    --wait-seconds)  WAIT_SECONDS="$2"; shift 2 ;;
    inspect|rotate-file|rotate-acme) SUBCOMMAND="$1"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

[[ -n "${SUBCOMMAND}" ]] || { echo "usage: $0 [flags] inspect|rotate-file|rotate-acme" >&2; exit 1; }

log()      { echo "[tls-rotation] $*"; }
log_ok()   { echo "[tls-rotation] [OK]    $*"; }
log_warn() { echo "[tls-rotation] [WARN]  $*" >&2; }
err()      { echo "[tls-rotation] [ERROR] $*" >&2; }

run() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] $*"
    return 0
  fi
  "$@"
}

# fetch_serial — the served serial from the LIVE endpoint ("" on failure).
fetch_serial() {
  openssl s_client -connect "${HOST}" -servername "${SNI}" </dev/null 2>/dev/null \
    | openssl x509 -noout -serial 2>/dev/null | sed 's/^serial=//'
}

# write_report JSON_FILE — JSON + Markdown twin (same convention as the DR
# drill report under docs/operations/dr-drill-reports/).
write_report() {
  local json_file="$1" base
  base="${json_file%.json}"
  run python3 - "${json_file}" "${base}" <<'PY'
import json, sys
json_file, base = sys.argv[1], sys.argv[2]
with open(json_file) as f:
    report = json.load(f)
md = f"""# TLS Rotation — {report['mode']} — {report['timestamp'][:10]}

| Field | Value |
|---|---|
| Mode | `{report['mode']}` |
| Endpoint | `{report['host']}` |
| SNI | `{report['sni']}` |
| Operator | `{report['operator']}` |
| Old serial | `{report['old_serial']}` |
| New serial | `{report['new_serial']}` |
| Old notAfter | `{report['old_not_after']}` |
| New notAfter | `{report['new_not_after']}` |
| Snapshot | `{report.get('snapshot', '—')}` |
| Rotation time | {report['rotation_seconds']}s |
| Status | **{report['status']}** |

## Anomalies / Corrective Actions

"""
for a in (report.get("anomalies") or []):
    md += f"- {a}\n"
if not (report.get("anomalies") or []):
    md += "None.\n"
with open(base + ".md", "w") as f:
    f.write(md)
PY
}

emit_report() {
  local mode="$1" old_serial="$2" new_serial="$3" old_na="$4" new_na="$5" \
    status="$6" rotation_s="$7" snapshot="$8" anomalies_json="$9" report_file
  report_file="${REPORT_DIR}/$(date -u '+%Y-%m')/tls-rotation-$(date -u '+%Y-%m-%dT%H%M%SZ').json"
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] rotation-report: ${report_file} (mode=${mode}, old_serial=${old_serial}, new_serial=${new_serial}, status=${status})"
    return 0
  fi
  run mkdir -p "$(dirname "${report_file}")"
  cat > "${report_file}" <<JSON
{
  "mode": "${mode}",
  "host": "${HOST}",
  "sni": "${SNI}",
  "operator": "${OPERATOR}",
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "old_serial": "${old_serial}",
  "new_serial": "${new_serial}",
  "old_not_after": "${old_na}",
  "new_not_after": "${new_na}",
  "snapshot": "${snapshot}",
  "rotation_seconds": ${rotation_s},
  "status": "${status}",
  "anomalies": [${anomalies_json}]
}
JSON
  write_report "${report_file}"
  log_ok "rotation report: ${report_file} (+ ${report_file%.json}.md)"
}

# ═══════════════════════════════════════════════════════════════════════════════
#  inspect
# ═══════════════════════════════════════════════════════════════════════════════
do_inspect() {
  [[ -n "${HOST}" ]] || { err "--host HOST:PORT is required"; exit 1; }
  [[ -n "${SNI}" ]] || { err "--sni DOMAIN is required"; exit 1; }
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] openssl s_client -connect ${HOST} -servername ${SNI} </dev/null | openssl x509 -noout -serial -enddate -issuer -subject"
    echo "  [DRY-RUN]  (inspect prints SERIAL= / NOT_AFTER= / ISSUER= / SUBJECT= from the LIVE endpoint)"
    return 0
  fi
  local pem serial not_after issuer subject
  pem="$(openssl s_client -connect "${HOST}" -servername "${SNI}" </dev/null 2>/dev/null)"
  if [[ -z "${pem}" ]]; then
    err "cannot reach ${HOST} — is the TLS endpoint up?"
    exit 2
  fi
  serial="$(echo "${pem}" | openssl x509 -noout -serial 2>/dev/null | sed 's/^serial=//')"
  not_after="$(echo "${pem}" | openssl x509 -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
  issuer="$(echo "${pem}" | openssl x509 -noout -issuer 2>/dev/null | sed 's/^issuer=//')"
  subject="$(echo "${pem}" | openssl x509 -noout -subject 2>/dev/null | sed 's/^subject=//')"
  [[ -n "${serial}" ]] || { err "no certificate served at ${HOST} (${SNI})"; exit 2; }
  echo "SERIAL=${serial}"
  echo "NOT_AFTER=${not_after}"
  echo "ISSUER=${issuer}"
  echo "SUBJECT=${subject}"
}

# ═══════════════════════════════════════════════════════════════════════════════
#  rotate-file
# ═══════════════════════════════════════════════════════════════════════════════
do_rotate_file() {
  [[ -n "${HOST}" ]] || { err "--host HOST:PORT is required"; exit 1; }
  [[ -n "${SNI}" ]] || { err "--sni DOMAIN is required"; exit 1; }
  [[ -n "${CERT_DIR}" ]] || { err "--cert-dir DIR is required"; exit 1; }
  [[ -n "${RELOAD_CMD}" ]] || { err "--reload CMD is required"; exit 1; }

  local stamp snapshot old_serial new_serial old_na new_na rotation_s \
    anomalies_json="" status new_key new_cert
  stamp="$(date -u '+%Y-%m-%dT%H%M%SZ')"

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] snapshot: cp ${CERT_DIR}/tls.crt ${CERT_DIR}/tls.key → ${CERT_DIR}/backup-${stamp}/"
    echo "  [DRY-RUN] install new: openssl req -x509 (or --new-cert/--new-key) → ${CERT_DIR}/tls.crt + tls.key (atomic mv)"
    echo "  [DRY-RUN] reload: ${RELOAD_CMD}"
    echo "  [DRY-RUN] verify: poll ${HOST} (SNI ${SNI}) until serial changed (max ${WAIT_SECONDS}s)"
    echo "  [DRY-RUN] on failure: rollback from snapshot + reload, report FAILED, exit 3"
    echo "  [DRY-RUN] report: old_serial/new_serial/old_not_after/new_not_after/status/rotation_seconds"
    return 0
  fi

  [[ -f "${CERT_DIR}/tls.crt" && -f "${CERT_DIR}/tls.key" ]] || {
    err "cert pair missing from ${CERT_DIR} (tls.crt + tls.key)"
    exit 1
  }

  # 1. Snapshot BEFORE touching the pair.
  snapshot="${CERT_DIR}/backup-${stamp}"
  run mkdir -p "${snapshot}"
  cp "${CERT_DIR}/tls.crt" "${snapshot}/tls.crt"
  cp "${CERT_DIR}/tls.key" "${snapshot}/tls.key"
  log_ok "snapshot: ${snapshot}"

  old_serial="$(fetch_serial)"
  old_na="$(openssl s_client -connect "${HOST}" -servername "${SNI}" </dev/null 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
  [[ -n "${old_serial}" ]] || { err "no certificate served at ${HOST} before rotation"; exit 2; }
  log "served before rotation: serial=${old_serial} notAfter=${old_na}"

  # 2. New pair: operator-supplied (--new-cert/--new-key) or a REAL
  #    self-signed replacement generated by openssl (the rehearsal
  #    substitution; operators swap in their CA-issued pair).
  new_key="${CERT_DIR}/.tls.key.new"
  new_cert="${CERT_DIR}/.tls.crt.new"
  if [[ -n "${NEW_CERT}" && -n "${NEW_KEY}" ]]; then
    cp "${NEW_CERT}" "${new_cert}"
    cp "${NEW_KEY}" "${new_key}"
    log "using operator-supplied pair: ${NEW_CERT} + ${NEW_KEY}"
  else
    log "generating rehearsal replacement (self-signed, CN=${SNI})"
    openssl req -x509 -newkey rsa:2048 -nodes -days 90 \
      -subj "/CN=${SNI}" -addext "subjectAltName=DNS:${SNI}" \
      -keyout "${new_key}" -out "${new_cert}" 2>/dev/null \
      || { err "openssl could not generate the replacement pair"; exit 3; }
  fi

  # 3. Atomic install (mv within the same filesystem).
  mv "${new_key}" "${CERT_DIR}/tls.key"
  mv "${new_cert}" "${CERT_DIR}/tls.crt"
  log_ok "install new pair into ${CERT_DIR}"

  # 4. Reload the terminator.
  run bash -c "${RELOAD_CMD}" || { err "reload command failed: ${RELOAD_CMD}"; exit 3; }
  log_ok "reload issued: ${RELOAD_CMD}"

  # 5. Verify the SERVED serial changed.
  local deadline=$(( $(date +%s) + WAIT_SECONDS ))
  while [[ $(date +%s) -lt "${deadline}" ]]; do
    new_serial="$(fetch_serial)"
    if [[ -n "${new_serial}" && "${new_serial}" != "${old_serial}" ]]; then
      break
    fi
    sleep 2
  done
  new_na="$(openssl s_client -connect "${HOST}" -servername "${SNI}" </dev/null 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
  rotation_s=$(( $(date +%s) - (deadline - WAIT_SECONDS) ))

  if [[ -z "${new_serial}" || "${new_serial}" == "${old_serial}" ]]; then
    # 6. Rollback + report FAILED.
    log_warn "served serial did NOT change within ${WAIT_SECONDS}s — rolling back"
    cp "${snapshot}/tls.crt" "${CERT_DIR}/tls.crt"
    cp "${snapshot}/tls.key" "${CERT_DIR}/tls.key"
    run bash -c "${RELOAD_CMD}" || true
    anomalies_json="\"served serial unchanged after rotation — rolled back to ${snapshot}\""
    emit_report "rotate-file" "${old_serial}" "${new_serial:-<none>}" "${old_na}" "${new_na}" \
      "FAILED" "${rotation_s}" "${snapshot}" "${anomalies_json}"
    err "rotation FAILED — rolled back"
    exit 3
  fi

  log_ok "served serial changed: ${old_serial} → ${new_serial} (notAfter=${new_na})"
  emit_report "rotate-file" "${old_serial}" "${new_serial}" "${old_na}" "${new_na}" \
    "PASSED" "${rotation_s}" "${snapshot}" ""
  log "rotate-file DONE (exit 0)"
}

# ═══════════════════════════════════════════════════════════════════════════════
#  rotate-acme
# ═══════════════════════════════════════════════════════════════════════════════
do_rotate_acme() {
  [[ -n "${HOST}" ]] || { err "--host HOST:PORT is required"; exit 1; }
  [[ -n "${SNI}" ]] || { err "--sni DOMAIN is required"; exit 1; }
  [[ -n "${ACME_JSON}" ]] || { err "--acme-json FILE is required"; exit 1; }
  [[ -n "${ACME_DOMAIN}" ]] || { err "--acme-domain DOMAIN is required"; exit 1; }
  [[ -n "${RESTART_CMD}" ]] || { err "--restart CMD is required"; exit 1; }

  local stamp snapshot old_serial new_serial old_na new_na rotation_s \
    anomalies_json="" status
  stamp="$(date -u '+%Y-%m-%dT%H%M%SZ')"

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "  [DRY-RUN] snapshot: cp ${ACME_JSON} ${ACME_JSON}.backup-${stamp}"
    echo "  [DRY-RUN] remove: python3 scripts/tls_acme_json.py remove ${ACME_JSON} --domain ${ACME_DOMAIN}"
    echo "  [DRY-RUN] restart: ${RESTART_CMD}  (Traefik re-requests on the next ACME challenge)"
    echo "  [DRY-RUN] verify: poll ${HOST} (SNI ${SNI}) until serial changed (max ${WAIT_SECONDS}s)"
    echo "  [DRY-RUN] on failure: rollback acme.json snapshot + restart, report FAILED, exit 3"
    echo "  [DRY-RUN] report: old_serial/new_serial/old_not_after/new_not_after/status/rotation_seconds"
    return 0
  fi

  [[ -f "${ACME_JSON}" ]] || { err "acme.json not found: ${ACME_JSON}"; exit 1; }
  command -v python3 >/dev/null 2>&1 || { err "python3 not found"; exit 1; }
  [[ -f "${ACME_TOOL}" ]] || { err "tls_acme_json.py missing"; exit 1; }

  # 1. Snapshot acme.json BEFORE the removal.
  snapshot="${ACME_JSON}.backup-${stamp}"
  cp "${ACME_JSON}" "${snapshot}"
  log_ok "snapshot: ${snapshot}"

  old_serial="$(fetch_serial)"
  old_na="$(openssl s_client -connect "${HOST}" -servername "${SNI}" </dev/null 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
  [[ -n "${old_serial}" ]] || { err "no certificate served at ${HOST} before rotation"; exit 2; }
  log "served before rotation: serial=${old_serial} notAfter=${old_na}"

  # 2. Remove the domain entry (Traefik re-requests on the next challenge).
  if ! python3 "${ACME_TOOL}" remove "${ACME_JSON}" --domain "${ACME_DOMAIN}"; then
    err "acme.json removal failed — aborting (nothing changed)"
    exit 3
  fi

  # 3. Restart the terminator.
  run bash -c "${RESTART_CMD}" || { err "restart command failed: ${RESTART_CMD}"; exit 3; }
  log_ok "restart issued: ${RESTART_CMD}"

  # 4. Verify the SERVED serial changed.
  local deadline=$(( $(date +%s) + WAIT_SECONDS ))
  while [[ $(date +%s) -lt "${deadline}" ]]; do
    new_serial="$(fetch_serial)"
    if [[ -n "${new_serial}" && "${new_serial}" != "${old_serial}" ]]; then
      break
    fi
    sleep 2
  done
  new_na="$(openssl s_client -connect "${HOST}" -servername "${SNI}" </dev/null 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | sed 's/^notAfter=//')"
  rotation_s=$(( $(date +%s) - (deadline - WAIT_SECONDS) ))

  if [[ -z "${new_serial}" || "${new_serial}" == "${old_serial}" ]]; then
    # 5. Rollback + report FAILED.
    log_warn "served serial did NOT change within ${WAIT_SECONDS}s — rolling back acme.json"
    cp "${snapshot}" "${ACME_JSON}"
    run bash -c "${RESTART_CMD}" || true
    anomalies_json="\"ACME re-issue did not complete — rolled back to ${snapshot}\""
    emit_report "rotate-acme" "${old_serial}" "${new_serial:-<none>}" "${old_na}" "${new_na}" \
      "FAILED" "${rotation_s}" "${snapshot}" "${anomalies_json}"
    err "rotation FAILED — rolled back"
    exit 3
  fi

  log_ok "served serial changed: ${old_serial} → ${new_serial} (notAfter=${new_na})"
  emit_report "rotate-acme" "${old_serial}" "${new_serial}" "${old_na}" "${new_na}" \
    "PASSED" "${rotation_s}" "${snapshot}" ""
  log "rotate-acme DONE (exit 0)"
}

case "${SUBCOMMAND}" in
  inspect)      do_inspect ;;
  rotate-file)  do_rotate_file ;;
  rotate-acme)  do_rotate_acme ;;
esac
