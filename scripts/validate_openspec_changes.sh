#!/bin/bash
# Validate every ACTIVE openspec change dir with the repo-owned validator.
#
#   bash scripts/validate_openspec_changes.sh [repo_root]
#
# Per-change baselines: a change dir is STRICT once its baseline exists
# (`scripts/openspec_validation_baseline.txt` for preprod01,
# `scripts/openspec_validation_baseline_<name>.txt` otherwise). Dirs without
# a recorded baseline are report-only (exit 0) — their debt is printed but
# cannot block a publish until someone seeds the baseline. This keeps the
# active change protected without letting abandoned scratch dirs brick
# publishes.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

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

FAIL=0
COUNT=0
for change_dir in "$REPO_ROOT"/openspec/changes/*/; do
  [ -d "$change_dir" ] || continue
  name="$(basename "$change_dir")"
  [ "$name" = "archive" ] && continue
  COUNT=$((COUNT + 1))

  if [ "$name" = "preprod01" ]; then
    baseline="$REPO_ROOT/scripts/openspec_validation_baseline.txt"
  else
    baseline="$REPO_ROOT/scripts/openspec_validation_baseline_${name}.txt"
  fi

  if [ -f "$baseline" ]; then
    echo "OPENSPEC-STRUCT: $name (strict, baseline: $(basename "$baseline"))"
    "$PYTHON_BIN" "$SCRIPT_DIR/validate_openspec_change.py" \
      --change "$change_dir" --baseline "$baseline" || FAIL=1
  else
    violations="$("$PYTHON_BIN" "$SCRIPT_DIR/validate_openspec_change.py" \
      --change "$change_dir" --emit-baseline | wc -l)"
    echo "OPENSPEC-STRUCT: $name — no baseline; report-only ($violations violations, not blocking)"
  fi
done

if [ "$COUNT" -eq 0 ]; then
  echo "OPENSPEC-STRUCT: no active change dirs found under $REPO_ROOT/openspec/changes/"
  exit 1
fi

exit "$FAIL"
