#!/bin/bash
# Monitor Test Execution Progress

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}Monitoring Test Execution...${RESET}"
echo ""

cd "$(dirname "$0")/.." || exit 1

# Check for running pytest processes
PYTEST_PROCESSES=$(ps aux | grep -E "pytest|python.*test" | grep -v grep | wc -l)

if [ "$PYTEST_PROCESSES" -gt 0 ]; then
    echo -e "${GREEN}✅ Test execution in progress (${PYTEST_PROCESSES} processes)${RESET}"
    echo ""
    echo "Running processes:"
    ps aux | grep -E "pytest|python.*test" | grep -v grep | head -5
    echo ""
else
    echo -e "${YELLOW}⚠️  No test processes found${RESET}"
fi

# Check for latest test reports
REPORT_DIR="test_reports_django6"
if [ -d "$REPORT_DIR" ]; then
    echo -e "${BLUE}Latest test reports:${RESET}"
    ls -lt "$REPORT_DIR"/*.txt 2>/dev/null | head -5 | awk '{print $9, $6, $7, $8}'
    echo ""
    
    # Show latest summary if available
    LATEST_SUMMARY=$(ls -t "$REPORT_DIR"/test_summary*.txt 2>/dev/null | head -1)
    if [ -n "$LATEST_SUMMARY" ]; then
        echo -e "${BLUE}Latest summary (last 20 lines):${RESET}"
        tail -20 "$LATEST_SUMMARY"
    fi
fi

# Check log file
if [ -f "test_execution_parallel.log" ]; then
    echo ""
    echo -e "${BLUE}Latest log output (last 30 lines):${RESET}"
    tail -30 test_execution_parallel.log
fi

