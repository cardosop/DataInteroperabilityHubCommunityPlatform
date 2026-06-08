# UC-COMP-004: Generate RoPA

**ID:** UC-COMP-004
**Title:** Generate Record of Processing Activities (RoPA)
**Persona:** Compliance & Privacy Officer (CPO)
**Priority:** High
**Phase:** 283.3 (GA)
**Feature Flag:** `compliance_ropa_enabled` (ON by default for new tenants)

## Summary

The Compliance Officer generates a Record of Processing Activities (RoPA)
from the Hub's asset and contract registry, reviews it for completeness,
and exports it for regulatory submission (GDPR Art. 30).

## Preconditions

- Tenant has `compliance_ropa_enabled = True`
- Assets and contracts exist in the tenant's catalogue
- User has CPO role

## Main Flow

1. CPO navigates to RoPA List
2. Hub auto-generates a RoPA document from registered assets, contracts, and
   processing activities
3. CPO reviews the generated RoPA: verifies processing purposes, data categories,
   recipients, retention periods
4. CPO can manually add entries not captured by automated discovery
5. CPO exports RoPA as PDF or CSV for regulatory submission
6. Hub timestamps the export for audit

## Acceptance Criteria

- RoPA auto-generated from asset/contract registry
- Manual entry supported for non-Hub processing activities
- Export to PDF and CSV formats
- Audit event recorded on each generation and export
