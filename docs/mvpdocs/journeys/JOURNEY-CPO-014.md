# JOURNEY-CPO-014: Manage Processor Agreement Lifecycle

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-PA-001
**Phase:** 232 (GDPR Programme)
**Status:** Implemented
**E2E:** Existing PA spec in `frontend/e2e/`
**Routes:** `/compliance/processor-agreements`

## Overview

A Compliance & Privacy Officer manages the full lifecycle of Article 28 processor agreements: creating agreements linked to processing activities and external processors, tracking agreement status (DRAFT → ACTIVE → EXPIRED → TERMINATED), and ensuring every processor has a valid agreement before data processing begins.

## Journey Steps

1. **List processor agreements** — Navigate to the PA management page. Table shows agreement title, processor identity, status, effective dates, and linked processing activities count.
2. **Create agreement** — Fill form: processor name, contact, DPA location (EU/EEA/third-country with adequacy decision), agreement scope (data categories, processing purposes), effective dates. POSTs to `POST /api/v1/processor-agreements/`.
3. **Link to processing activities** — The CPO associates the agreement with specific assets or processing activities registered in the RoPA. This ensures Art. 28 coverage is auditable per processing activity.
4. **Review and activate** — DPO reviews the agreement, verifies adequacy decision for third-country transfers. Status transitions: DRAFT → ACTIVE.
5. **Renew or terminate** — On expiry, the CPO extends the effective period (ACTIVE with new end date) or terminates the agreement. Termination requires a replacement agreement to be linked to all affected processing activities.

## Error Handling

- **Missing processor details** — Inline validation on required fields (processor name, contact, effective dates).
- **Orphaned processing activities** — Terminating an agreement without a replacement shows a warning with the list of affected activities.
- **API failure** — `<ErrorDisplay>` with backend error code.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `PROCESSOR_AGREEMENT_CREATED` | New agreement record | 90 days |
| `PROCESSOR_AGREEMENT_ACTIVATED` | Status → ACTIVE | 90 days |
| `PROCESSOR_AGREEMENT_TERMINATED` | Status → TERMINATED | 90 days |

## Success Criteria

- Full CRUD lifecycle: create → activate → renew → terminate.
- Every processing activity with a third-party processor has a linked active agreement.
- Agreement expiry 30-day warning appears in the CPO dashboard.
- All state transitions emit audit events.

## Related

- Runbook: [phase232-compliance-programme.md](../../runbooks/phase232-compliance-programme.md)
- Components: `ProcessorAgreementListPage`, `ProcessorAgreementDetailPage`, `ProcessorAgreementCreatePage`
- Phase: 232.6 (Processor Agreements)
