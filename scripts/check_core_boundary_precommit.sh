#!/bin/bash
# Pre-commit fast gate — GATE-29 scoped to the staged files (Phase 313-H 1.6).
#
# pre-commit passes the staged filenames on argv; forward them to
# check_core_boundary.py's ``--paths`` so a paid-import leak in the commit
# fails at ``git commit`` time instead of CI time. Scoped scans run in
# milliseconds; the full-tree gate stays the CI backstop.
#
# The checker always ALSO scans hub/settings.py (MIDDLEWARE/ROUTERS string
# literals bypass the import scanner by design), so settings edits keep
# their coverage.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# REPO_ROOT override exists for the hook's own hermetic tests (temp repos);
# pre-commit always runs the hook from the repository root anyway.
REPO_ROOT="${CORE_BOUNDARY_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

# Python: prefer the canonical venv, fall back to any python3 (pre-commit's
# language:system runs in the caller's environment, not a hook venv).
PYTHON_BIN="${PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$REPO_ROOT/venv/bin/python" ]; then
    PYTHON_BIN="$REPO_ROOT/venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

# Allowlist: real repo's by default; CORE_BOUNDARY_ALLOWLIST overrides it for
# hermetic tests against temp repos (the script's own test suite).
ALLOWLIST="${CORE_BOUNDARY_ALLOWLIST:-$SCRIPT_DIR/core_boundary_allowlist.txt}"

exec "$PYTHON_BIN" "$SCRIPT_DIR/check_core_boundary.py" \
  --root "$REPO_ROOT" \
  --allowlist "$ALLOWLIST" \
  --check-guards \
  --guard-exceptions "$SCRIPT_DIR/core_guard_exceptions.txt" \
  --paths "$@"
