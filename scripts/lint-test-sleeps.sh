#!/usr/bin/env bash
# Phase 84.6 — CI lint: block new time.sleep() in test files without INTENTIONAL comment.
#
# Usage:
#   scripts/lint-test-sleeps.sh           # Check all test files
#   scripts/lint-test-sleeps.sh --diff    # Check only files changed vs main
#
# Exit codes:
#   0 — No violations found
#   1 — Violations found (new time.sleep without INTENTIONAL comment)
#
# To mark a sleep as intentional, add an inline comment:
#   time.sleep(2)  # INTENTIONAL: wait for rate-limit window to reset

set -euo pipefail

THRESHOLD=50  # Maximum allowed non-INTENTIONAL sleeps
DIFF_MODE=false

if [[ "${1:-}" == "--diff" ]]; then
    DIFF_MODE=true
fi

if $DIFF_MODE; then
    # Only check files changed relative to main/origin
    BASE_BRANCH="${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-${GITHUB_BASE_REF:-main}}"
    FILES=$(git diff --name-only --diff-filter=ACMR "$BASE_BRANCH"...HEAD -- '*test*.py' '*spec*.py' 2>/dev/null || true)
    if [[ -z "$FILES" ]]; then
        echo "✅ No test files changed — nothing to check."
        exit 0
    fi
else
    FILES=$(find hub/ tests/ services/ -name '*test*.py' -o -name '*spec*.py' 2>/dev/null | \
            grep -v venv/ | grep -v backups/ | grep -v node_modules/ | grep -v venv-python312-test/)
fi

# Count non-INTENTIONAL time.sleep() calls
VIOLATIONS=0
VIOLATION_FILES=""

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ ! -f "$file" ]] && continue

    # Find lines with actual time.sleep() calls (not string literals,
    # comments, or function definitions).
    # Exclude: INTENTIONAL-marked, function defs, string literals
    # (single/double quoted), and comment-only lines (# prefix after
    # the grep line-number prefix).
    MATCHES=$(grep -n "time\.sleep(" "$file" 2>/dev/null \
        | grep -v "INTENTIONAL" \
        | grep -v "def.*time\.sleep" \
        | grep -v "'.*time\.sleep.*'" \
        | grep -v '".*time\.sleep.*"' \
        | grep -v ":[[:space:]]*#" \
        || true)
    if [[ -n "$MATCHES" ]]; then
        COUNT=$(echo "$MATCHES" | wc -l)
        VIOLATIONS=$((VIOLATIONS + COUNT))
        VIOLATION_FILES="${VIOLATION_FILES}\n  ${file} (${COUNT} unmarked sleeps)"
        if $DIFF_MODE; then
            echo "❌ $file:"
            echo "$MATCHES" | sed 's/^/    /'
        fi
    fi
done <<< "$FILES"

echo ""
echo "=== Test Sleep Lint Report ==="
echo "Total non-INTENTIONAL time.sleep() calls: $VIOLATIONS"
echo "Threshold: $THRESHOLD"

if [[ $VIOLATIONS -gt $THRESHOLD ]]; then
    echo ""
    echo "❌ FAIL: $VIOLATIONS non-INTENTIONAL sleeps exceed threshold of $THRESHOLD."
    echo ""
    echo "Files with unmarked sleeps:$VIOLATION_FILES"
    echo ""
    echo "Fix: Replace with wait_for_event_persistence() from tests.utils.wait_helpers,"
    echo "     or add '# INTENTIONAL: <reason>' comment to justify the delay."
    exit 1
else
    echo "✅ PASS: $VIOLATIONS ≤ $THRESHOLD"
    exit 0
fi
