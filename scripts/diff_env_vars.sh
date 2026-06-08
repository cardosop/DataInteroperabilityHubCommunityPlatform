#!/usr/bin/env bash
# 311.1 — Diff .env.staging vs .env.production.template for parity check.
set -euo pipefail

STAGING="${1:-.env.staging}"
PROD="${2:-.env.production.template}"

extract_keys() {
  grep -oP '^[A-Z_][A-Z0-9_]*\s*=' "$1" | sed 's/=$//' | sort -u
}

echo "=== Env Var Parity: staging ($(extract_keys "$STAGING" | wc -l) vars) vs production template ($(extract_keys "$PROD" | wc -l) vars) ==="

# Keys in production but not staging
comm -13 <(extract_keys "$STAGING") <(extract_keys "$PROD") > /tmp/missing_staging.txt
# Keys in staging but not production
comm -23 <(extract_keys "$STAGING") <(extract_keys "$PROD") > /tmp/extra_staging.txt

STAGING_COUNT=$(extract_keys "$STAGING" | wc -l)
PROD_COUNT=$(extract_keys "$PROD" | wc -l)
MISSING=$(wc -l < /tmp/missing_staging.txt)

PARITY_PCT=$(( STAGING_COUNT * 100 / PROD_COUNT ))

echo "Staging: $STAGING_COUNT vars"
echo "Production template: $PROD_COUNT vars"
echo "Parity: ${PARITY_PCT}%"
echo ""
echo "Missing from staging (${MISSING} vars):"
head -20 /tmp/missing_staging.txt
if [ "$MISSING" -gt 20 ]; then
  echo "  ... and $(( MISSING - 20 )) more"
fi

if [ "$PARITY_PCT" -lt 90 ]; then
  echo ""
  echo "❌ Parity ${PARITY_PCT}% < 90% target. Backfill needed."
  exit 1
fi
echo ""
echo "✅ Parity ${PARITY_PCT}% ≥ 90% target."
