#!/usr/bin/env bash
# Phase 121D — Test Quality Gate
#
# Detects anti-patterns in test files that produce
# trivially-passing or meaningless assertions.
#
# Exit codes:
#   0 — no anti-patterns found
#   1 — blocking anti-patterns found (121D.1, 121D.2)
#   (121D.3 time.sleep is warn-only, does not block)

set -euo pipefail

FAIL=0
WARN=0

echo "=== Test Quality Gate ==="

# ── 121D.1: Trivially-true assertions (BLOCKING) ────────

echo ""
echo "--- 121D.1: Trivially-true assertions ---"

PATTERNS=(
  'assertTrue(True)'
  'assertEqual(True, True)'
  'assert True$'
  'expect(document\.body)\.toBeTruthy()'
  'expect(container)\.toBeTruthy()'
)

for pat in "${PATTERNS[@]}"; do
  hits=$(grep -rn "$pat" \
    hub/apps/*/tests/ \
    frontend/src/ \
    sdk/ \
    cli/tests/ \
    2>/dev/null \
    | grep -v node_modules \
    | grep -v __pycache__ \
    | grep -v '\.md:' \
    || true)

  if [ -n "$hits" ]; then
    echo "FAIL: Found trivially-true pattern: $pat"
    echo "$hits" | head -5
    if [ "$(echo "$hits" | wc -l)" -gt 5 ]; then
      echo "  ... and $(( $(echo "$hits" | wc -l) - 5 )) more"
    fi
    FAIL=1
  fi
done

# assertIn(response.status_code, [...]) with 4+ codes
hits=$(grep -rn 'assertIn(response\.status_code.*\[' \
  hub/apps/*/tests/ 2>/dev/null \
  | grep -v __pycache__ \
  | grep -v '\.md:' \
  | grep -oP 'assertIn\(response\.status_code.*?\[.*?\]' \
  | awk -F',' 'NF>=5' || true)

if [ -n "$hits" ]; then
  echo "FAIL: assertIn(status_code, [...]) with 4+ codes:"
  echo "$hits" | head -5
  FAIL=1
fi

# ── 121D.2: Unused assertRaises context managers (BLOCKING) ─

echo ""
echo "--- 121D.2: Unused assertRaises context managers ---"

# Pattern: `with self.assertRaises(...) as cm:` where `cm`
# is never referenced after the with block
hits=$(grep -rn 'assertRaises.*as cm:' \
  hub/apps/*/tests/ \
  cli/tests/ \
  2>/dev/null | grep -v __pycache__ || true)

CM_FOUND=0
if [ -n "$hits" ]; then
  while IFS= read -r line; do
    file=$(echo "$line" | cut -d: -f1)
    lineno=$(echo "$line" | cut -d: -f2)
    tail_lines=$(sed -n "$((lineno+1)),$((lineno+10))p" "$file" 2>/dev/null || true)
    if ! echo "$tail_lines" | grep -q 'cm\.\|cm)'; then
      echo "FAIL: Unused assertRaises context manager at $file:$lineno"
      FAIL=1
      CM_FOUND=1
    fi
  done <<< "$hits"
fi

if [ "$CM_FOUND" -eq 0 ]; then
  echo "  OK: No unused assertRaises context managers found"
fi

# ── 121D.3: time.sleep() in tests (WARNING only) ────────

echo ""
echo "--- 121D.3: time.sleep() in test files (warning) ---"

hits=$(grep -rn 'time\.sleep(' \
  hub/apps/*/tests/ \
  frontend/src/ \
  cli/tests/ \
  sdk/ \
  2>/dev/null \
  | grep -v node_modules \
  | grep -v __pycache__ \
  | grep -v 'mock.*sleep\|patch.*sleep\|monkeypatch.*sleep' \
  || true)

if [ -n "$hits" ]; then
  count=$(echo "$hits" | wc -l)
  echo "WARN: Found $count time.sleep() calls in test files:"
  echo "$hits" | head -10
  if [ "$count" -gt 10 ]; then
    echo "  ... and $(( count - 10 )) more"
  fi
  WARN=1
else
  echo "  OK: No time.sleep() in test files"
fi

# ── Summary ──────────────────────────────────────────────

echo ""
echo "=== Summary ==="
if [ "$FAIL" -eq 1 ]; then
  echo "BLOCKED: Fix the FAIL items above before merging."
  exit 1
elif [ "$WARN" -eq 1 ]; then
  echo "PASSED with warnings. Consider fixing WARN items."
  exit 0
else
  echo "PASSED: No test quality issues found."
  exit 0
fi
