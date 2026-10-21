#!/usr/bin/env bash
# publish_public.sh — mirror the core subset to the public repo (Phase 313.3.5).
#
# Pre-flight (aborts BEFORE anything is pushed):
#   1. copyleft audit (G7) of the shipped closures — python
#      (requirements + pyproject extras + CLI deps) and npm
#      (frontend + sdk/js), fail-closed
#   2. GATE-29 boundary scan + gitleaks + hostname grep on the BUILT
#      tree (the exact shipped bytes — the publish ships the INDEX
#      state, never the working tree)
# Then builds the core tree (git ls-files minus the manifest-generated
# exclusions) + the publish overlay, commits ONE sync commit onto the
# mirror branch of the public remote, and (when PUBLIC_REMOTE is
# configured) pushes + tags vYYYY.MM.N.
#
# The scrubbed HISTORY is produced once by the one-time filter-repo run
# (313.3.3) — this script only appends sync commits.
#
# Env: PUBLIC_REMOTE (default "public"), PUBLIC_REPO_DIR (default ../DataInteroperabilityHub-public),
#      SKIP_PUSH=1 for a dry run.

set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
# Resolve relative interpreters (venv/bin/python) against the PRIVATE repo
# root — the post-commit verification runs inside the public checkout where
# a relative path would not exist. Plain `python3` (PATH lookup) must keep
# working: the repo-root/$PYTHON form only wins when that file actually
# exists, otherwise fall back to PATH.
if [[ "$PYTHON" != /* ]]; then
  RESOLVED="$(cd "$(dirname "$0")/.." && pwd)/$PYTHON"
  if [ -x "$RESOLVED" ]; then
    PYTHON="$RESOLVED"
  elif command -v "$PYTHON" >/dev/null 2>&1; then
    PYTHON="$(command -v "$PYTHON")"
  fi
fi

PRIVATE_SHA="$(git rev-parse --short HEAD)"
REPLACE_TEXT_FILE="$(mktemp /tmp/publish_replace_text.XXXXXX.txt)"

trap 'rm -f "$REPLACE_TEXT_FILE"' EXIT

# Tree builder — sourced so scripts/tests/test_publish_tree.py can exercise
# the real build (313.DoD.5). Uses the same PYTHON resolution as above.
# shellcheck disable=SC1091
source scripts/publish_tree.sh
# Pre-flight gates — sourced so scripts/tests/test_publish_gates.py can
# exercise the real gitleaks gate (Phase P.8).
# shellcheck disable=SC1091
source scripts/publish_gates.sh
# Sync mechanics — sourced so scripts/tests/test_p25_public_replacement.py
# can exercise the real sync against fixture remotes (P2-5 root fixes:
# ROOT-lineage bootstrap, exact-tree commits, main fast-forward).
# shellcheck disable=SC1091
source scripts/publish_sync.sh

PUBLIC_REMOTE="${PUBLIC_REMOTE:-public}"
PUBLIC_REPO_DIR="${PUBLIC_REPO_DIR:-../DataInteroperabilityHub-public}"
TAG="$(date +v%Y.%m.%d)"

log() { echo "[publish] $*"; }

# ---------------------------------------------------------------------------
# Pre-flight gates — abort before any output exists
# ---------------------------------------------------------------------------
# Copyleft audit (G7, P0-13): the SHIPPED closures — python
# (requirements + pyproject extras + CLI deps) AND npm (frontend +
# sdk/js) — must be free of hard-copyleft and license-unresolvable
# dependencies. Fail-closed: a publish is the one non-recoverable
# distribution path, so a missing tool/node_modules refuses the run
# (the checker exits non-zero; CI's security-scan job runs the same
# checker as a second line of defense).
log "copyleft audit (G7)"
require_copyleft

# Replace-text mappings: same file the history scrub uses (313.3.3) — the
# published TREE must be sanitized exactly like the published history.
"$PYTHON" scripts/build_replace_text.py --out "$REPLACE_TEXT_FILE"

# ---------------------------------------------------------------------------
# Build the core tree (scripts/publish_tree.sh — sourced above)
# ---------------------------------------------------------------------------
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
STAGING="$WORK/tree"
build_publish_tree "$STAGING" "$REPLACE_TEXT_FILE"

# GATE-29 on the BUILT tree (P2-5 fix, the W0.4b class): the publish
# ships the INDEX state, never the working tree — a working-tree scan
# produces false failures on peer-lane WIP that never ships. The built
# tree carries its own checker + allowlist, so this scans the exact
# bytes that reach the public repo (the post-commit verification
# re-scans the same content inside the public checkout).
log "GATE-29 boundary scan (built publish tree)"
"$PYTHON" "$STAGING/scripts/check_core_boundary.py"

# gitleaks on the BUILT tree (W0.4b fix — the previous pre-flight ran
# against the raw working directory, catching untracked local artifacts
# and the pre-rewrite docs that the exclusions deliberately drop). The
# shared gate scans a non-repo dir directly (the built tree IS the exact
# shipped content); a missing CLI is a hard failure, never a skip
# (Phase P.8): a publish is the one non-recoverable leak path and local
# publishes run outside CI.
log "gitleaks (built publish tree)"
require_gitleaks "$STAGING"

# ---------------------------------------------------------------------------
# Sync to the public repo
# ---------------------------------------------------------------------------
if [ "${SKIP_PUSH:-0}" = "1" ]; then
  log "SKIP_PUSH=1 — dry run complete (tree at $STAGING would be removed by trap)"
  exit 0
fi

# G12 push-protection gate (P0-9): the public remote must have
# secret-scanning push protection ENABLED before ANY sync — "public
# BEFORE the first re-sync, never during the window". Runs on real
# publishes only (dry runs stay offline above); fail-closed.
log "push-protection gate (G12)"
require_push_protection "$PUBLIC_REMOTE"

if [ ! -d "$PUBLIC_REPO_DIR" ]; then
  log "ERROR: public repo checkout not found at $PUBLIC_REPO_DIR — clone it first"
  exit 1
fi

pushd "$PUBLIC_REPO_DIR" >/dev/null
# The sync (scripts/publish_sync.sh): bootstrap-or-append, exact-tree
# commit, post-commit verification, mirror + main + tag pushes.
sync_to_public "$STAGING" "$TAG" "$PRIVATE_SHA"
popd >/dev/null
log "published $TAG to $PUBLIC_REMOTE mirror/public-core + main"
