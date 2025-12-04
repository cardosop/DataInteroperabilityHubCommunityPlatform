#!/bin/bash
# Run E2E tests in batches
# Usage: ./scripts/run_e2e_tests_batch.sh [batch_number|all]

set -e

BATCH=${1:-all}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

export DJANGO_SETTINGS_MODULE=hub.settings

case "$BATCH" in
    1)
        echo "Running E2E Batch 1: Core API and Contracts"
        python3 -m pytest tests/e2e/ -m "e2e_batch1" -v --tb=short
        ;;
    2)
        echo "Running E2E Batch 2: Worker Service and Jobs"
        python3 -m pytest tests/e2e/ -m "e2e_batch2" -v --tb=short
        ;;
    3)
        echo "Running E2E Batch 3: Email Service and Notifications"
        python3 -m pytest tests/e2e/ -m "e2e_batch3" -v --tb=short
        ;;
    4)
        echo "Running E2E Batch 4: Rate Limiting and Tenant Config"
        python3 -m pytest tests/e2e/ -m "e2e_batch4" -v --tb=short
        ;;
    5)
        echo "Running E2E Batch 5: Persona Tests and Edge Cases"
        python3 -m pytest tests/e2e/ -m "e2e_batch5" -v --tb=short
        ;;
    all)
        echo "Running All E2E Tests"
        python3 -m pytest tests/e2e/ -m "e2e" -v --tb=short
        ;;
    *)
        echo "Usage: $0 [1|2|3|4|5|all]"
        echo "  Batch 1: Core API and Contracts"
        echo "  Batch 2: Worker Service and Jobs"
        echo "  Batch 3: Email Service and Notifications"
        echo "  Batch 4: Rate Limiting and Tenant Config"
        echo "  Batch 5: Persona Tests and Edge Cases"
        echo "  all: Run all E2E tests"
        exit 1
        ;;
esac

