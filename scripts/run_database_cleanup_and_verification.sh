#!/bin/bash
#
# Master script to clean up test databases and verify batch fixes
#
# This script:
# 1. Cleans up old test databases (399 databases causing WAL lock contention)
# 2. Re-runs batches to verify signal fixes
# 3. Investigates actual execution errors (if any remain)
# 4. Continues with other FAILED batches (starting with smallest)
# 5. Re-runs full batch suite to verify overall improvements
#
# Usage:
#     ./scripts/run_database_cleanup_and_verification.sh [--dry-run] [--skip-cleanup] [--skip-verification]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Parse arguments
DRY_RUN=false
SKIP_CLEANUP=false
SKIP_VERIFICATION=false
SKIP_FAILED_BATCHES=false
SKIP_FULL_SUITE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --skip-verification)
            SKIP_VERIFICATION=true
            shift
            ;;
        --skip-failed-batches)
            SKIP_FAILED_BATCHES=true
            shift
            ;;
        --skip-full-suite)
            SKIP_FULL_SUITE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--skip-cleanup] [--skip-verification] [--skip-failed-batches] [--skip-full-suite]"
            exit 1
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Database Cleanup and Batch Verification${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo ""

# Step 1: Clean up old test databases
if [ "$SKIP_CLEANUP" = false ]; then
    echo -e "${BOLD}Step 1: Cleaning up old test databases${RESET}"
    echo "----------------------------------------"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}🔍 DRY RUN MODE - No databases will be dropped${RESET}"
        python3 "$SCRIPT_DIR/cleanup_test_databases.py" --dry-run
    else
        echo "Cleaning up test databases matching 'hub_test%' pattern..."
        python3 "$SCRIPT_DIR/cleanup_test_databases.py"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Database cleanup completed successfully${RESET}"
        else
            echo -e "${RED}❌ Database cleanup failed${RESET}"
            exit 1
        fi
    fi
    echo ""
else
    echo -e "${YELLOW}⏭️  Skipping database cleanup${RESET}"
    echo ""
fi

# Step 2: Verify signal fixes
if [ "$SKIP_VERIFICATION" = false ]; then
    echo -e "${BOLD}Step 2: Verifying signal fixes${RESET}"
    echo "----------------------------------------"
    echo "Re-running batches with signal fixes applied..."

    python3 "$SCRIPT_DIR/verify_batch_fixes.py" --signal-fixes

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Signal fix verification completed${RESET}"
    else
        echo -e "${YELLOW}⚠️  Some batches failed - check report for details${RESET}"
    fi
    echo ""
else
    echo -e "${YELLOW}⏭️  Skipping signal fix verification${RESET}"
    echo ""
fi

# Step 3: Run other FAILED batches
if [ "$SKIP_FAILED_BATCHES" = false ]; then
    echo -e "${BOLD}Step 3: Running other FAILED batches${RESET}"
    echo "----------------------------------------"
    echo "Running batches that previously failed (starting with smallest)..."

    python3 "$SCRIPT_DIR/verify_batch_fixes.py" --all-failed

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ All failed batches completed${RESET}"
    else
        echo -e "${YELLOW}⚠️  Some batches failed - check report for details${RESET}"
    fi
    echo ""
else
    echo -e "${YELLOW}⏭️  Skipping failed batches${RESET}"
    echo ""
fi

# Step 4: Re-run full batch suite (optional - can be time-consuming)
if [ "$SKIP_FULL_SUITE" = false ]; then
    echo -e "${BOLD}Step 4: Re-running full batch suite${RESET}"
    echo "----------------------------------------"
    echo -e "${YELLOW}⚠️  This step can be time-consuming.${RESET}"
    echo "Press Ctrl+C within 5 seconds to skip, or wait to continue..."

    # Wait 5 seconds for user to cancel
    sleep 5 || exit 0

    # Check if comprehensive test execution script exists
    if [ -f "$SCRIPT_DIR/run_comprehensive_test_execution.py" ]; then
        echo "Running comprehensive test suite..."
        python3 "$SCRIPT_DIR/run_comprehensive_test_execution.py"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Full batch suite completed${RESET}"
        else
            echo -e "${YELLOW}⚠️  Some tests failed - check report for details${RESET}"
        fi
    else
        echo -e "${YELLOW}⚠️  Comprehensive test execution script not found, skipping${RESET}"
    fi
    echo ""
else
    echo -e "${YELLOW}⏭️  Skipping full batch suite${RESET}"
    echo ""
fi

# Final summary
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Summary${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo ""
echo "✅ All steps completed!"
echo ""
echo "Reports are available in: test_reports_comprehensive/"
echo ""
echo "Next steps:"
echo "  1. Review test reports in test_reports_comprehensive/"
echo "  2. Investigate any remaining failures"
echo "  3. Fix root causes for any errors"
echo "  4. Re-run verification as needed"
echo ""
