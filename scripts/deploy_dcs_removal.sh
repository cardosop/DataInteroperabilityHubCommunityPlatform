#!/bin/bash
# Deploy DCS Removal (Phase 0.2)
#
# This script automates the deployment of Phase 0.2 (DCS removal) changes.
# It includes pre-deployment checks, migration execution, and post-deployment validation.
#
# Usage:
#   ./scripts/deploy_dcs_removal.sh [--dry-run] [--skip-migration] [--environment staging|production]
#
# Exit codes:
#   0 - Deployment successful
#   1 - Deployment failed
#   2 - Pre-deployment checks failed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
SKIP_MIGRATION=false
ENVIRONMENT="staging"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-migration)
            SKIP_MIGRATION=true
            shift
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--skip-migration] [--environment staging|production]"
            exit 1
            ;;
    esac
done

if [ "$ENVIRONMENT" != "staging" ] && [ "$ENVIRONMENT" != "production" ]; then
    echo -e "${RED}ERROR: Environment must be 'staging' or 'production'${NC}"
    exit 1
fi

echo "=========================================="
echo "DCS Removal Deployment"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}Mode: DRY RUN${NC}"
fi
echo ""

# Pre-deployment checks
echo "----------------------------------------"
echo "Pre-Deployment Checks"
echo "----------------------------------------"

# Check if Django is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ python3 not found${NC}"
    exit 2
fi
echo -e "${GREEN}✓ python3 found${NC}"

# Check if migration file exists
MIGRATION_FILE="hub/apps/contracts/migrations/0004_remove_datacontract_com_from_original_spec_type.py"
if [ ! -f "$MIGRATION_FILE" ]; then
    echo -e "${RED}✗ Migration file not found: $MIGRATION_FILE${NC}"
    exit 2
fi
echo -e "${GREEN}✓ Migration file exists${NC}"

# Check if migration report script exists
if [ ! -f "scripts/migration_report_dcs_removal.py" ]; then
    echo -e "${RED}✗ Migration report script not found${NC}"
    exit 2
fi
echo -e "${GREEN}✓ Migration report script exists${NC}"

# Generate migration report
echo ""
echo "----------------------------------------"
echo "Generating Migration Report"
echo "----------------------------------------"
if [ "$DRY_RUN" = false ]; then
    if python3 scripts/migration_report_dcs_removal.py; then
        echo -e "${GREEN}✓ Migration report generated${NC}"
    else
        echo -e "${YELLOW}⚠ Migration report generation had warnings (may be expected if no DCS contracts exist)${NC}"
    fi
else
    echo -e "${YELLOW}[DRY RUN] Would generate migration report${NC}"
fi

# Database migration
if [ "$SKIP_MIGRATION" = false ]; then
    echo ""
    echo "----------------------------------------"
    echo "Database Migration"
    echo "----------------------------------------"
    
    if [ "$DRY_RUN" = false ]; then
        echo "Running migration: python manage.py migrate contracts 0004"
        if python3 manage.py migrate contracts 0004 --verbosity=2; then
            echo -e "${GREEN}✓ Migration applied successfully${NC}"
        else
            echo -e "${RED}✗ Migration failed${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}[DRY RUN] Would run: python manage.py migrate contracts 0004${NC}"
    fi
else
    echo ""
    echo "----------------------------------------"
    echo "Database Migration"
    echo "----------------------------------------"
    echo -e "${YELLOW}⚠ Migration skipped (--skip-migration flag)${NC}"
fi

# Post-deployment validation
echo ""
echo "----------------------------------------"
echo "Post-Deployment Validation"
echo "----------------------------------------"

# Check that OriginalSpecType enum only has ODCS
echo "Validating OriginalSpecType enum..."
if [ "$DRY_RUN" = false ]; then
    if python3 scripts/test_migration_0004.py; then
        echo -e "${GREEN}✓ Enum validation passed${NC}"
    else
        echo -e "${RED}✗ Enum validation failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[DRY RUN] Would validate enum${NC}"
fi

# Check service health
echo ""
echo "Checking service health..."
if [ "$DRY_RUN" = false ]; then
    # Check if services are running (if docker-compose is available)
    if command -v docker-compose &> /dev/null; then
        if docker-compose ps | grep -q "Up"; then
            echo -e "${GREEN}✓ Services are running${NC}"
        else
            echo -e "${YELLOW}⚠ Some services may not be running${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ docker-compose not available, skipping service health check${NC}"
    fi
else
    echo -e "${YELLOW}[DRY RUN] Would check service health${NC}"
fi

# Summary
echo ""
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}DRY RUN completed - no changes were made${NC}"
    echo ""
    echo "To execute deployment, run:"
    echo "  $0 --environment $ENVIRONMENT"
else
    echo -e "${GREEN}✓ Deployment completed successfully${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Monitor services for errors"
    echo "  2. Run test suite: ./scripts/run_dcs_removal_test_suite.sh"
    echo "  3. Monitor API usage for DCS contract attempts"
    echo "  4. Provide support for users migrating from DCS"
fi
echo ""

exit 0

