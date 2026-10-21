#!/usr/bin/env bash
# Generate test summary report from test_reports_comprehensive/{date}/.
# Per gapfix1 Phase 7.4 and testreview1 Phase 14.
# Usage: ./scripts/generate_test_summary_report.sh [YYYY-MM-DD]
# If no date given, uses latest date directory under test_reports_comprehensive/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

DATE="${1:-}"
if [[ -z "$DATE" ]]; then
  if [[ -d "test_reports_comprehensive" ]]; then
    DATE=$(find test_reports_comprehensive -maxdepth 1 -type d -name '20*' | sort -r | head -1 | xargs basename)
  fi
fi
if [[ -z "$DATE" ]]; then
  echo "Usage: $0 YYYY-MM-DD" 1>&2
  echo "Or run after evidence is collected so the latest date under test_reports_comprehensive/ is used." 1>&2
  exit 1
fi

if [[ ! -d "test_reports_comprehensive/${DATE}" ]]; then
  echo "Error: test_reports_comprehensive/${DATE} does not exist. Run Phase 12A or collect evidence first." 1>&2
  exit 1
fi

python3 "${SCRIPT_DIR}/generate_test_summary_report.py" --date "$DATE"
echo "Report generated for date: $DATE"
