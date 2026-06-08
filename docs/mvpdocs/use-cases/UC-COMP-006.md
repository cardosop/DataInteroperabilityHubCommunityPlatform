# UC-COMP-006: Handle DSAR Request

**ID:** UC-COMP-006
**Title:** Handle Data Subject Access Request (DSAR)
**Persona:** Compliance & Privacy Officer (CPO)
**Priority:** High
**Phase:** 283.3 (GA)
**Feature Flag:** `compliance_dsar_enabled` (ON by default for new tenants)

## Summary

A data subject submits a Data Subject Access Request (DSAR) through the
public portal. The CPO verifies the request, processes it within the
statutory SLA, and provides the subject with their data.

## Preconditions

- Tenant has `compliance_dsar_enabled = True`
- Public DSAR portal is reachable
- User has CPO role for the handler queue

## Main Flow

1. Data subject visits the public DSAR portal and submits a request with
   identity verification (OTP to registered email)
2. Hub enqueues the request in the tenant's DSAR handler queue
3. CPO reviews the request in the DsarQueue
4. CPO verifies the subject's identity and the scope of the request
5. Hub collects the subject's data across all assets/contracts/datasets
6. CPO reviews the collected data, redacts third-party data if needed
7. CPO exports the data package and sends it to the subject
8. Hub records the DSAR completion with audit trail and SLA timestamp

## Acceptance Criteria

- Public DSAR portal accepts requests with OTP verification
- Handler queue shows pending DSARs with SLA deadlines
- Data collection spans all tenant resources
- Export package includes all relevant data
- Full audit trail for regulatory inspection
