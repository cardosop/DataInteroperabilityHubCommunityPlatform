# UC-COMP-003: Conduct DPIA Assessment

**ID:** UC-COMP-003
**Title:** Conduct DPIA Assessment
**Persona:** Compliance & Privacy Officer (CPO)
**Priority:** High
**Phase:** 283.3 (GA)
**Feature Flag:** `compliance_dpia_enabled` (OFF by default, requires DPO signoff)

## Summary

The Compliance Officer conducts a Data Protection Impact Assessment (DPIA)
for a high-risk processing activity, submits it for DPO review, and tracks
it through the assessment lifecycle including periodic re-review.

## Preconditions

- Tenant has `compliance_dpia_enabled = True`
- User has CPO or DPO role
- A high-risk asset or processing activity identified

## Main Flow

1. CPO navigates to DPIA Wizard
2. CPO creates a new DPIA: processing purpose, data categories, risk assessment
3. Wizard guides through the assessment steps: necessity, proportionality, risk mitigation
4. CPO submits DPIA for DPO review
5. DPO reviews, may request consultation
6. After approval, DPIA is published and linked to the asset
7. Hub schedules periodic re-review (annual by default)

## Acceptance Criteria

- DPIA created with all mandatory sections
- DPO review workflow functional
- Consultation step available for complex assessments
- Periodic re-review sweep detects due DPIAs
- Audit trail for each lifecycle state transition
