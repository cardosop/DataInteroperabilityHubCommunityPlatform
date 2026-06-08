# JOURNEY-CPO-012: Complete DPIA Assessment Wizard

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-DPIA-001
**Phase:** 284 (GA Promotion — Pre-Existing Bug Fixes)
**Status:** Implemented (284.F.5)
**E2E:** `dpia-wizard-flow.spec.ts`
**Routes:** `/governance/dpia/new`, `/governance/dpia/{id}`, `/governance/dpia/{id}/review`, `/governance/dpia/review-queue`

## Overview

A Compliance & Privacy Officer conducts a Data Protection Impact Assessment (DPIA) for a new or changed processing activity. The wizard guides the CPO through four steps — Basics, Processing Narrative, Risks & Measures, and Review — then submits the DPIA for DPO review. The DPO reviews the assessment, approves/rejects/requests consultation, and completes the Art. 36 consultation path when required.

## Journey Steps

1. **Create new DPIA** — Navigate to `/governance/dpia/new`. If the `compliance_dpia_enabled` capability is off, the page renders a warning Banner.
2. **Step 0 — Basics** — Fill title (`#dpia-title`), select regime (`#dpia-regime`: GDPR/LGPD/CCPA), optionally link an asset UUID (`#dpia-asset`). Click Next.
3. **Step 1 — Processing Narrative** — Fill the processing narrative textarea (`#dpia-proc`) describing the nature, scope, context, and purposes of processing.
4. **Step 2 — Risks & Measures** — Fill inherent/residual risks (`#dpia-risk`) and mitigations (`#dpia-mit`). Click Next.
5. **Step 3 — Review** — Review all fields in summary view. Click "Submit for review" → `POST /api/v1/dpia/records/{id}/submit/` → transitions status to IN_REVIEW → redirects to `/governance/dpia/review-queue`.
6. **DPO Review** — DPO navigates to `/governance/dpia/review-queue`, clicks a record to open `/governance/dpia/{id}/review`. Selects decision from `#dpia-outcome` dropdown (Approved/Rejected/Requires consultation), sets residual risk (`#dpia-resid`), writes DPO summary (`#dpia-dpo`), clicks "Submit decision" → `POST /api/v1/dpia/records/{id}/review/`.
7. **Consultation complete** (Art. 36 path) — When status is REQUIRES_CONSULTATION, the DPO clicks "Approve after consultation" or "Return to review" → `POST /api/v1/dpia/records/{id}/consultation/complete/`.

## Error Handling

- **Wizard state preservation** — On API failure during Next/Submit, the wizard stays on the current step; field values are preserved.
- **Capability disabled** — Renders Banner: "DPIA is disabled for this tenant."
- **Validation** — Empty title on submit shows inline error; regime is required.
- **Network failure** — `<ErrorDisplay>` with retry; wizard state is not lost.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `DPIA_CREATED` | New DPIA record | 90 days |
| `DPIA_SUBMITTED` | DPIA submitted for review | 90 days |
| `DPIA_REVIEWED` | DPO review submitted | 90 days |
| `DPIA_CONSULTATION_COMPLETED` | Art. 36 consultation resolved | 90 days |

## Success Criteria

- CPO completes all 4 wizard steps and submits without page crash.
- Wizard preserves field values across step navigation (Back/Next).
- DPO review page loads with version diff when multiple versions exist.
- All 3 review outcomes (APPROVED/REJECTED/REQUIRES_CONSULTATION) work end-to-end.
- Every state transition emits the corresponding audit event.

## Related

- E2E: `frontend/e2e/journeys/dpia-wizard-flow.spec.ts` (284.F.5)
- Runbook: [RB-COMP-005-dpia.md](../../runbooks/RB-COMP-005-dpia.md)
- Components: `DpiaWizardPage`, `DpiaReviewPage`, `DpiaReviewQueuePage`
- Phase: 232.5 (DPIA wizard), 284.F.5 (E2E gap closure)
