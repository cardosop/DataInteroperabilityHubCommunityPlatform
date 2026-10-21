#!/usr/bin/env bash
# 309.1 — ADR freshness check. Flags ADRs > 6 months without review.
# Run as monthly CI check. Exit 0 if all reviewed within 6 months.
set -euo pipefail

STALE_MONTHS=6
INDEX="docs/adr/index.md"
STALE_COUNT=0

if [ ! -f "$INDEX" ]; then
  echo "ADR index not found at $INDEX"
  exit 1
fi

# Extract dates from the index table
CUTOFF_DATE=$(date -d "$STALE_MONTHS months ago" +%Y-%m-%d 2>/dev/null || date -v-${STALE_MONTHS}m +%Y-%m-%d 2>/dev/null || echo "")

echo "ADR Freshness Check — cutoff: $CUTOFF_DATE ($STALE_MONTHS months ago)"
echo ""

# Parse markdown table: skip header + separator rows
while IFS='|' read -r _ id title _ _ _ _ date _; do
  # Normalize whitespace
  dt=$(echo "$date" | xargs)
  [ -z "$dt" ] && continue
  [ "$dt" == "Date" ] && continue
  [ "$dt" == "---" ] && continue
  
  # Compare dates
  if [[ "$dt" < "$CUTOFF_DATE" ]]; then
    echo "  STALE: $(echo "$id" | xargs) — $(echo "$title" | xargs) (last reviewed: $dt)"
    STALE_COUNT=$((STALE_COUNT + 1))
  fi
done < "$INDEX"

echo ""
if [ "$STALE_COUNT" -gt 0 ]; then
  echo "❌ $STALE_COUNT ADR(s) exceed ${STALE_MONTHS}-month review window."
  exit 1
fi

echo "✅ All ADRs reviewed within ${STALE_MONTHS}-month window."
exit 0
