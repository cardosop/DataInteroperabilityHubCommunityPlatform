#!/bin/bash
# Monitor DCS Removal Post-Deployment
#
# This script monitors the system after DCS removal deployment to:
# - Check for errors related to DCS removal
# - Monitor API usage patterns
# - Detect DCS contract ingestion attempts
# - Track migration support requests
#
# Usage:
#   ./scripts/monitor_dcs_removal.sh [--duration 3600] [--interval 60]
#
# Exit codes:
#   0 - Monitoring completed successfully
#   1 - Errors detected during monitoring

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

# Default values
DURATION=3600  # 1 hour
INTERVAL=60    # 1 minute

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--duration SECONDS] [--interval SECONDS]"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "DCS Removal Post-Deployment Monitoring"
echo "=========================================="
echo "Duration: ${DURATION}s (${INTERVAL}s intervals)"
echo ""

# Check if Django is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 not found${NC}"
    exit 1
fi

# Set up environment
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="${PYTHONPATH:-}:$PROJECT_ROOT"

# Create monitoring script
MONITOR_SCRIPT=$(cat << 'PYTHON_SCRIPT'
import os
import sys
import django
import json
from datetime import datetime, timedelta
from pathlib import Path

# Setup Django
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()

from django.db.models import Q, Count
from django.utils import timezone
from hub.apps.contracts.models import Contract, OriginalSpecType
# Try to import AuditLog if available, otherwise skip audit log checks
try:
    from hub.apps.audit.models import AuditLog
    HAS_AUDIT_LOG = True
except ImportError:
    HAS_AUDIT_LOG = False
import logging

logger = logging.getLogger(__name__)

def check_dcs_contract_attempts():
    """Check for DCS contract ingestion attempts (via error logs)"""
    # Check recent normalization failures that might be DCS-related
    recent_time = timezone.now() - timedelta(minutes=5)
    
    # Check audit logs for DCS-related errors (if available)
    if HAS_AUDIT_LOG:
        dcs_errors = AuditLog.objects.filter(
            created_at__gte=recent_time,
            action__icontains='normalization',
            details__icontains='DCS'
        ).count()
    else:
        # Fallback: check normalization failures in contracts
        dcs_errors = Contract.objects.filter(
            created_at__gte=recent_time,
            normalization_status='NORMALIZATION_FAILED',
            normalization_warnings__icontains='DCS'
        ).count()
    
    return dcs_errors

def check_api_errors():
    """Check for API errors related to DCS"""
    recent_time = timezone.now() - timedelta(minutes=5)
    
    # Check for normalization failures
    failed_contracts = Contract.objects.filter(
        created_at__gte=recent_time,
        normalization_status='NORMALIZATION_FAILED'
    ).count()
    
    return failed_contracts

def check_odcs_contracts():
    """Check that new contracts are ODCS"""
    recent_time = timezone.now() - timedelta(minutes=5)
    
    new_contracts = Contract.objects.filter(created_at__gte=recent_time)
    odcs_count = new_contracts.filter(original_spec_type=OriginalSpecType.ODCS).count()
    total_count = new_contracts.count()
    
    return odcs_count, total_count

def check_service_health():
    """Check service health (basic check)"""
    # This would check service endpoints in a real implementation
    # For now, just check database connectivity
    try:
        Contract.objects.count()
        return True
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        return False

def main():
    """Run monitoring checks"""
    timestamp = datetime.now().isoformat()
    
    results = {
        'timestamp': timestamp,
        'dcs_contract_attempts': check_dcs_contract_attempts(),
        'api_errors': check_api_errors(),
        'service_health': check_service_health(),
    }
    
    odcs_count, total_count = check_odcs_contracts()
    results['odcs_contracts'] = odcs_count
    results['total_new_contracts'] = total_count
    
    # Print results
    print(json.dumps(results, indent=2))
    
    # Return exit code based on results
    if results['dcs_contract_attempts'] > 0:
        print(f"WARNING: {results['dcs_contract_attempts']} DCS contract attempts detected", file=sys.stderr)
        return 1
    
    if not results['service_health']:
        print("ERROR: Service health check failed", file=sys.stderr)
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
PYTHON_SCRIPT
)

# Write monitoring script to temp file
TEMP_SCRIPT="/tmp/monitor_dcs_removal_$$.py"
echo "$MONITOR_SCRIPT" > "$TEMP_SCRIPT"
chmod +x "$TEMP_SCRIPT"

# Monitoring loop
START_TIME=$(date +%s)
ITERATION=0
ERRORS_DETECTED=0

cleanup() {
    rm -f "$TEMP_SCRIPT"
    echo ""
    echo "Monitoring stopped"
    exit $ERRORS_DETECTED
}

trap cleanup EXIT INT TERM

echo "Starting monitoring..."
echo ""

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    if [ $ELAPSED -ge $DURATION ]; then
        break
    fi
    
    ITERATION=$((ITERATION + 1))
    REMAINING=$((DURATION - ELAPSED))
    
    echo "----------------------------------------"
    echo "Iteration $ITERATION (${REMAINING}s remaining)"
    echo "----------------------------------------"
    
    if python3 "$TEMP_SCRIPT"; then
        echo -e "${GREEN}✓ All checks passed${NC}"
    else
        echo -e "${RED}✗ Issues detected${NC}"
        ERRORS_DETECTED=1
    fi
    
    if [ $ELAPSED -lt $DURATION ]; then
        echo ""
        echo "Waiting ${INTERVAL}s until next check..."
        sleep $INTERVAL
    fi
done

echo ""
echo "=========================================="
echo "Monitoring Summary"
echo "=========================================="
echo "Total iterations: $ITERATION"
if [ $ERRORS_DETECTED -eq 0 ]; then
    echo -e "${GREEN}✓ No errors detected during monitoring period${NC}"
else
    echo -e "${RED}✗ Errors were detected - review logs above${NC}"
fi
echo ""

exit $ERRORS_DETECTED

