#!/usr/bin/env bash
# publish_public.sh — mirror the core subset to the public repo (Phase 313.3.5).
#
# Pre-flight (aborts BEFORE any tree is built or pushed):
#   1. GATE-29 boundary scan (core must not import paid)
#   2. gitleaks on the tracked tree (when the CLI is available)
#   3. internal-hostname grep over the core subset
#   4. copyleft audit of the requirements.txt closure
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

PUBLIC_REMOTE="${PUBLIC_REMOTE:-public}"
PUBLIC_REPO_DIR="${PUBLIC_REPO_DIR:-../DataInteroperabilityHub-public}"
TAG="$(date +v%Y.%m.%d)"

log() { echo "[publish] $*"; }

# ---------------------------------------------------------------------------
# Pre-flight gates — abort before any output exists
# ---------------------------------------------------------------------------
log "GATE-29 boundary scan"
"$PYTHON" scripts/check_core_boundary.py

log "copyleft audit (requirements.txt closure)"
"$PYTHON" scripts/check_copyleft.py

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

# gitleaks on the BUILT tree (W0.4b fix — the previous pre-flight ran
# against the raw working directory, catching untracked local artifacts
# and the pre-rewrite docs that the exclusions deliberately drop). A
# missing CLI is a hard failure, never a skip (Phase P.8): a publish is
# the one non-recoverable leak path and local publishes run outside CI.
if ! command -v gitleaks >/dev/null 2>&1; then
  log "ERROR: gitleaks CLI not found — refusing to publish an unscanned tree."
  exit 1
fi
log "gitleaks (built publish tree)"
# Scan from INSIDE the tree with a relative --source: the config's
# path allowlists match repo-relative paths, and an absolute --source
# records absolute paths that never match (W0.4b finding).
CONFIG_ABS="$(cd "$(dirname "$0")/.." && pwd)/.gitleaks.toml"
(cd "$STAGING" && gitleaks detect --no-git --source . \
    --config "$CONFIG_ABS" \
    --redact --no-banner --log-level=warn)

# ---------------------------------------------------------------------------
# Sync to the public repo
# ---------------------------------------------------------------------------
if [ "${SKIP_PUSH:-0}" = "1" ]; then
  log "SKIP_PUSH=1 — dry run complete (tree at $STAGING would be removed by trap)"
  exit 0
fi

if [ ! -d "$PUBLIC_REPO_DIR" ]; then
  log "ERROR: public repo checkout not found at $PUBLIC_REPO_DIR — clone it first"
  exit 1
fi

pushd "$PUBLIC_REPO_DIR" >/dev/null
git checkout -q mirror/public-core 2>/dev/null || git checkout -q -b mirror/public-core
# replace tracked content with the new tree (sync commit = full snapshot)
git ls-files | while IFS= read -r f; do rm -f "$f"; done
(cd "$STAGING" && find . -type f | sed 's|^\./||') | while IFS= read -r f; do
  mkdir -p "$(dirname "$f")"
  cp "$STAGING/$f" "$f"
done
git add -A
# frontend/.gitignore excludes the generated shared/ copy (the private CI
# builds it fresh) — but the PUBLIC repo must be self-contained, so the
# published tree force-adds it.
git add -f -A frontend/shared 2>/dev/null || true
git commit -q -m "sync: core subset @ ${PRIVATE_SHA}" || log "nothing to commit"
git tag -f "$TAG"

# Post-commit verification IN the public checkout (before any push):
# GATE-29 + gitleaks + compose config must all pass here.
log "post-commit verification (public checkout)"
"$PYTHON" scripts/check_core_boundary.py
# Same hard gate as the pre-flight: the public tree was assembled from the
# tracked tree in THIS run — rescanning it here catches sanitizer or
# overlay mistakes before they reach the mirror.
require_gitleaks .
docker compose -f docker-compose.test.yml -f docker-compose.test.core.yml config -q

git push -q "$PUBLIC_REMOTE" mirror/public-core
# Tags are movable (vYYYY.MM.DD) — force ONLY the tag ref, never the branch.
git push -q --force "$PUBLIC_REMOTE" "$TAG"
popd >/dev/null
log "published $TAG to $PUBLIC_REMOTE mirror/public-core"
