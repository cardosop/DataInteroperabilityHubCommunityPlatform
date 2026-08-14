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
# a relative path would not exist.
if [[ "$PYTHON" != /* ]]; then
  PYTHON="$(cd "$(dirname "$0")/.." && pwd)/$PYTHON"
fi

REPLACE_TEXT_FILE="$(mktemp /tmp/publish_replace_text.XXXXXX.txt)"

trap 'rm -f "$REPLACE_TEXT_FILE"' EXIT

PUBLIC_REMOTE="${PUBLIC_REMOTE:-public}"
PUBLIC_REPO_DIR="${PUBLIC_REPO_DIR:-../DataInteroperabilityHub-public}"
TAG="$(date +v%Y.%m.%d)"

log() { echo "[publish] $*"; }

# ---------------------------------------------------------------------------
# Pre-flight gates — abort before any output exists
# ---------------------------------------------------------------------------
log "GATE-29 boundary scan"
"$PYTHON" scripts/check_core_boundary.py

log "gitleaks (tracked tree)"
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --config .gitleaks.toml --redact --no-banner --log-level=warn
else
  log "gitleaks CLI absent — SKIPPING (CI runs gitleaks-action)"
fi

log "copyleft audit (requirements.txt closure)"
"$PYTHON" scripts/check_copyleft.py

# Replace-text mappings: same file the history scrub uses (313.3.3) — the
# published TREE must be sanitized exactly like the published history.
"$PYTHON" scripts/build_replace_text.py --out "$REPLACE_TEXT_FILE"

# ---------------------------------------------------------------------------
# Build the core tree
# ---------------------------------------------------------------------------
log "building core tree"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
STAGING="$WORK/tree"
mkdir -p "$STAGING"

# Exclusion entries are file paths or trailing-slash dir prefixes
# (manifest-generated) — the python filter handles both forms.
"$PYTHON" - "$WORK/files.txt" <<'PYEOF'
import sys
out_path = sys.argv[1]
excl = [l.strip() for l in open("scripts/publish_paths_exclude.txt") if l.strip() and not l.startswith("#")]
import subprocess
files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.splitlines()
keep = []
for f in files:
    if any(f == e or f.startswith(e) for e in excl if e.endswith("/")):
        continue
    keep.append(f)
open(out_path, "w").write("\n".join(keep) + "\n")
PYEOF

# Extract the INDEX state (not the working tree): the publishable source of
# truth is the committed/staged content — uncommitted moves/edits must be
# staged (or committed) before they ship, and untracked files never leak.
git checkout-index -f --prefix="$STAGING/" --stdin < "$WORK/files.txt"

# overlay (patched worker Dockerfile, license/community files)
if [ -d scripts/publish_public_overlay ]; then
  cp -r scripts/publish_public_overlay/. "$STAGING/"
fi

# Sanitize the staged tree with the same replace mappings as the history
# scrub — leaked values + internal hostnames must never enter sync commits.
"$PYTHON" - "$STAGING" "$REPLACE_TEXT_FILE" <<'PYEOF'
import sys
from pathlib import Path

staging, replace_file = Path(sys.argv[1]), Path(sys.argv[2])
pairs = []
for line in replace_file.read_text().splitlines():
    if "==>" in line:
        old, _, new = line.partition("==>")
        pairs.append((old, new))
text_suffixes = (".md", ".py", ".yml", ".yaml", ".toml", ".txt", ".json", ".sh", ".ini", ".cfg", ".html", ".js", ".ts", ".tsx", ".cjs", ".mjs", ".css")
for path in staging.rglob("*"):
    if not path.is_file() or not path.suffix.lower() in text_suffixes:
        continue
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for old, new in pairs:
        content = content.replace(old, new)
    path.write_text(content, encoding="utf-8")
PYEOF

log "tree built: $(find "$STAGING" -type f | wc -l) files (sanitized)"

# Authoritative post-build gate: the SANITIZED tree must be clean.
HOSTNAME_HITS="$(grep -rIlE 'staging\.hub\.meshant\.com|wiki\.internal|grafana\.internal' "$STAGING" 2>/dev/null || true)"
if [ -n "$HOSTNAME_HITS" ]; then
  log "ERROR: internal hostnames remain after sanitization:"
  echo "$HOSTNAME_HITS"
  exit 1
fi

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
git commit -q -m "sync: core subset @ $(git -C "$(dirname "$0")/.." rev-parse --short HEAD)" || log "nothing to commit"
git tag -f "$TAG"

# Post-commit verification IN the public checkout (before any push):
# GATE-29 + gitleaks + compose config must all pass here.
log "post-commit verification (public checkout)"
"$PYTHON" scripts/check_core_boundary.py
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --config .gitleaks.toml --redact --no-banner --log-level=warn
fi
docker compose -f docker-compose.test.yml -f docker-compose.test.core.yml config -q

git push -q "$PUBLIC_REMOTE" mirror/public-core --tags
popd >/dev/null
log "published $TAG to $PUBLIC_REMOTE mirror/public-core"
