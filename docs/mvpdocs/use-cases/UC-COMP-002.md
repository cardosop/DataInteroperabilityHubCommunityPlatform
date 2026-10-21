# UC-COMP-002: Report and Manage Data Breach

**ID:** UC-COMP-002
**Title:** Report and Manage Data Breach
**Persona:** Compliance & Privacy Officer (CPO)
**Priority:** High
**Phase:** 283.3 (GA)
**Feature Flag:** `compliance_breach_enabled` (ON by default for new tenants)

## Summary

The Compliance Officer identifies a personal data breach, creates a breach record
in the Hub, runs the statutory notification workflow, and tracks the breach
through resolution with SLA clock monitoring.

## Preconditions

- Tenant has `compliance_breach_enabled = True`
- User has CPO or TENANT_ADMIN role
- Breach notification templates configured for relevant jurisdictions

## Main Flow

1. CPO navigates to Breach Dashboard
2. CPO creates a new breach record: description, affected data categories,
   estimated subjects, data controller contact
3. Hub auto-starts the statutory clock based on jurisdiction (GDPR: 72h)
4. CPO triggers notification to supervisory authority via configured template
5. CPO notifies affected data subjects
6. Hub tracks SLA deadlines and escalates if approaching
7. CPO marks breach as resolved; Hub records resolution with audit trail

## Acceptance Criteria

- Breach record created with all mandatory fields
- Statutory clock auto-started with correct deadline
- Notifications sent via email/webhook
- SLA status visible on BreachDashboard
- Full audit trail for regulatory inspection
