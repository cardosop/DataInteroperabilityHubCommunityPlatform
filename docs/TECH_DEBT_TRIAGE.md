# Technical Debt Triage Report

**Last Updated**: 2025-02-03
**Phase**: 24.8.1

## Overview

This document tracks TODO/FIXME/XXX/HACK references in `hub/apps` and their status.

## Summary

- **19 TODOs**: Legitimate future work items
- **0 FIXMEs**: None found
- **1 HACK**: Test data (not a real hack)
- **0 XXXs**: None found

## TODO References

### High Priority (Missing Features)

1. **auth/views.py:622** - Track last_login_at in User model or separate LoginHistory model
   - **Status**: Future enhancement
   - **Priority**: Medium
   - **Owner**: TBD

2. **scheduled_ingestion/views.py:967** - Add last_tested_at and last_test_result fields to ScheduledIngestion model
   - **Status**: Future enhancement
   - **Priority**: Medium
   - **Owner**: TBD

### Medium Priority (Integration Work)

3. **orchestration/workflows/version_creation.py:797** - Implement actual lineage reference updates when lineage system is ready
   - **Status**: Blocked on lineage system
   - **Priority**: Medium
   - **Owner**: TBD

4. **orchestration/workflows/version_creation.py:899** - Implement actual notification sending when notification system is ready
   - **Status**: Blocked on notification system
   - **Priority**: Medium
   - **Owner**: TBD

5. **orchestration/workflows/marketplace_publication.py:715** - Implement actual notification sending when notification system is ready
   - **Status**: Blocked on notification system
   - **Priority**: Medium
   - **Owner**: TBD

6. **tenants/views.py:294,307** - Implement email notification when notification service is ready
   - **Status**: Blocked on notification service
   - **Priority**: Medium
   - **Owner**: TBD

7. **dq/alerting.py:167,182,197,212** - Integrate with email service, Slack API, HTTP POST, PagerDuty API
   - **Status**: Future integration work
   - **Priority**: Medium
   - **Owner**: TBD

### Low Priority (Enhancements)

8. **mesh/views.py:628-629** - Calculate health score and health status from topology business rules
   - **Status**: Future enhancement
   - **Priority**: Low
   - **Owner**: TBD

9. **files/views.py:392** - Make this strict in production
   - **Status**: Production hardening
   - **Priority**: Low
   - **Owner**: TBD

10. **files/views.py:537** - Add for_browser parameter to generate_presigned_part_url
    - **Status**: Future enhancement
    - **Priority**: Low
    - **Owner**: TBD

11. **audit/management/commands/archive_old_audit_events.py:68** - Implement actual archiving (move to cold storage, mark as archived, etc.)
    - **Status**: Future enhancement
    - **Priority**: Low
    - **Owner**: TBD

### Test-Related (Documentation)

12. **users/tests/test_views.py:147** - Update this test when resource checking is implemented
    - **Status**: Test update needed when feature is implemented
    - **Priority**: Low
    - **Owner**: TBD

13. **users/tests/test_user_deletion.py:73** - When resources are implemented (assets, datasets, etc.)
    - **Status**: Test update needed when feature is implemented
    - **Priority**: Low
    - **Owner**: TBD

## HACK References

1. **ml/tests/test_e2e.py:434** - "odh_model_id": "model-hack"
   - **Status**: Test data only, not a real hack
   - **Action**: No action needed

## Resolved

1. **auth/views.py:426** - ~~TODO: Implement audit logging~~ ✅ RESOLVED
   - **Status**: Audit logging is already implemented via middleware and signal handlers
   - **Resolution**: Updated comment to reflect current implementation

## Recommendations

1. **Create tickets** for high-priority TODOs (items 1-2)
2. **Track dependencies** for medium-priority TODOs (items 3-7) - these are blocked on other systems
3. **Document in backlog** for low-priority TODOs (items 8-11)
4. **Update tests** when related features are implemented (items 12-13)

## Notes

- All TODOs are legitimate future work items, not ambiguous tech-debt markers
- No TODOs are left without clear context or purpose
- The single HACK reference is test data and not a code quality issue
