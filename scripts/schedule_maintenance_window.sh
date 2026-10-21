#!/bin/bash
# Maintenance Window Scheduling Script
# Helps schedule and communicate maintenance windows

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

# Create maintenance window schedule
create_maintenance_schedule() {
    log_section "Maintenance Window Schedule"
    
    ENVIRONMENT="${1:-staging}"
    DATE="${2:-}"
    TIME="${3:-}"
    DURATION="${4:-3}"
    
    if [ -z "$DATE" ] || [ -z "$TIME" ]; then
        log_info "Please provide maintenance window details:"
        read -p "Date (YYYY-MM-DD): " DATE
        read -p "Time (HH:MM UTC): " TIME
        read -p "Duration (hours, default 3): " DURATION
        DURATION=${DURATION:-3}
    fi
    
    SCHEDULE_FILE="maintenance_schedules/${ENVIRONMENT}_${DATE}.md"
    mkdir -p maintenance_schedules
    
    {
        echo "# Maintenance Window Schedule"
        echo ""
        echo "**Environment**: $ENVIRONMENT"
        echo "**Date**: $DATE"
        echo "**Time**: $TIME UTC"
        echo "**Duration**: $DURATION hours"
        echo "**Type**: $(if [ "$ENVIRONMENT" = "production" ]; then echo "Zero-Downtime Deployment"; else echo "Scheduled Maintenance"; fi)"
        echo ""
        echo "## Timeline"
        echo ""
        echo "- **Start**: $DATE $TIME UTC"
        echo "- **End**: $DATE $(date -d "$TIME +$DURATION hours" +%H:%M 2>/dev/null || echo "TBD") UTC"
        echo ""
        echo "## Activities"
        echo ""
        echo "- [ ] Pre-deployment checks"
        echo "- [ ] Backup creation"
        echo "- [ ] Infrastructure deployment"
        echo "- [ ] Database migrations"
        echo "- [ ] Service deployment"
        echo "- [ ] Verification"
        echo "- [ ] Smoke tests"
        echo "- [ ] Monitoring setup"
        echo ""
        echo "## Stakeholder Notifications"
        echo ""
        echo "- [ ] Initial notification (2 weeks before)"
        echo "- [ ] Reminder (1 week before)"
        echo "- [ ] Final reminder (24 hours before)"
        echo "- [ ] Status updates during maintenance"
        echo "- [ ] Completion notification"
        echo ""
        echo "## Team"
        echo ""
        echo "- **Lead**: [To be assigned]"
        echo "- **On-Call**: [To be assigned]"
        echo "- **DBA**: [To be assigned]"
        echo ""
        echo "## Status"
        echo ""
        echo "**Status**: Scheduled"
        echo "**Created**: $(date)"
    } > "$SCHEDULE_FILE"
    
    log_info "Maintenance window schedule created: $SCHEDULE_FILE"
    cat "$SCHEDULE_FILE"
}

# Generate notification email
generate_notification() {
    log_section "Generate Notification Email"
    
    ENVIRONMENT="${1:-staging}"
    DATE="${2:-}"
    TIME="${3:-}"
    DURATION="${4:-3}"
    
    NOTIFICATION_FILE="maintenance_notifications/${ENVIRONMENT}_${DATE}_notification.txt"
    mkdir -p maintenance_notifications
    
    {
        echo "Subject: Scheduled Maintenance - Django 6 Upgrade - $ENVIRONMENT"
        echo ""
        echo "Dear Stakeholders,"
        echo ""
        echo "We will be performing a scheduled maintenance window to upgrade to Django 6."
        echo ""
        echo "**Environment**: $ENVIRONMENT"
        echo "**Date**: $DATE"
        echo "**Time**: $TIME UTC"
        echo "**Duration**: $DURATION hours"
        echo ""
        if [ "$ENVIRONMENT" = "production" ]; then
            echo "**Impact**: Minimal to no user impact (zero-downtime deployment)"
        else
            echo "**Impact**: Staging environment only (no user impact)"
        fi
        echo ""
        echo "During this maintenance window:"
        echo "- Django 6 upgrade will be deployed"
        echo "- Database migrations will be run"
        echo "- All services will be verified"
        echo "- Comprehensive tests will be executed"
        echo ""
        echo "We will provide status updates throughout the maintenance window."
        echo ""
        echo "If you have any questions or concerns, please contact the deployment team."
        echo ""
        echo "Thank you for your understanding."
        echo ""
        echo "Deployment Team"
        echo "$(date)"
    } > "$NOTIFICATION_FILE"
    
    log_info "Notification email created: $NOTIFICATION_FILE"
    cat "$NOTIFICATION_FILE"
}

# Main execution
main() {
    log_info "Maintenance Window Scheduling"
    echo ""
    
    ENVIRONMENT="${1:-staging}"
    
    create_maintenance_schedule "$ENVIRONMENT"
    echo ""
    generate_notification "$ENVIRONMENT"
    
    log_info "Maintenance window scheduling completed ✓"
    log_info "Next steps:"
    log_info "  1. Review the schedule file"
    log_info "  2. Send notification email to stakeholders"
    log_info "  3. Add to team calendar"
    log_info "  4. Update status page"
}

# Run main function
main "$@"

