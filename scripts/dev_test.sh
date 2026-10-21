#!/bin/bash
#
# Development Test Script
#
# This script runs tests with appropriate configuration for development.
#
# Usage:
#   ./scripts/dev_test.sh [--coverage] [--parallel] [--verbose] [--file FILE]
#

set -euo pipefail

COVERAGE=false
PARALLEL=false
VERBOSE=false
FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --file)
            FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest"

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=hub --cov=services --cov-report=html --cov-report=term"
fi

if [ "$PARALLEL" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -n auto"
fi

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ -n "$FILE" ]; then
    PYTEST_CMD="$PYTEST_CMD $FILE"
else
    PYTEST_CMD="$PYTEST_CMD tests"
fi

# Run tests
echo "Running: $PYTEST_CMD"
exec $PYTEST_CMD

