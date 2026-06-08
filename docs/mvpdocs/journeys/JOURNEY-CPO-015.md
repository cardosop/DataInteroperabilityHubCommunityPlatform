# JOURNEY-CPO-015: Submit and Track DSAR Request

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-DSAR-001
**Phase:** 232 (GDPR Programme)
**Status:** Implemented
**E2E:** `dsar-otp-flow.spec.ts`
**Routes:** `/legal/dsar` (public), `/compliance/dsar/queue` (admin)

## Overview

A Data Subject submits a Data Subject Access Request (DSAR) through the public form. They verify their identity via a one-time password (OTP) sent to their email. A Compliance & Privacy Officer reviews the DSAR queue, validates the request, compiles the response (data export), and completes the request within the statutory 30-day GDPR deadline.

## Journey Steps

1. **Data Subject submits DSAR** — Navigate to `/legal/dsar` (public, unauthenticated). Fill email (`#dsar-email`), select request type (`#dsar-type`: access/erasure/rectification/portability), complete hCaptcha verification. Submit → `POST /api/v1/public/dsar/`.
2. **OTP verification** — Data Subject receives OTP email, navigates to `/legal/dsar/status/{token}`, enters OTP code. On success, the request status transitions from PENDING_VERIFICATION to PENDING.
3. **CPO reviews DSAR queue** — CPO navigates to `/compliance/dsar/queue` (requires TENANT_ADMIN or CPO role). Queue shows: requester email (masked), request type, submission date, SLA deadline (30-day countdown), status badge.
4. **CPO processes DSAR** — Clicks into a DSAR detail page. Reviews the request, exports the data subject's data via `POST /api/v1/dsar/{id}/export/`, uploads the response package. Marks COMPLETED → emits `DSAR_COMPLETED`.
5. **Erasure path** — For erasure requests (GDPR Art. 17), the CPO triggers the erasure workflow which cascades through all data stores, retention policies, and backup systems. Legal holds override erasure.

## Error Handling

- **Invalid OTP** — Shows "Invalid or expired code. Request a new one." with resend link.
- **Expired OTP** — OTP expires after 15 minutes; user must re-submit the DSAR.
- **hCaptcha failure** — Inline error; form state preserved.
- **SLA breach warning** — Requests approaching 30-day deadline show amber (25+ days) or red (30+ days) SLA badge.
- **Legal hold conflict** — Erasure blocked by active legal hold shows specific hold reference.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `DSAR_CREATED` | Public DSAR submission | 90 days |
| `DSAR_OTP_VERIFIED` | OTP verification success | 90 days |
| `DSAR_COMPLETED` | CPO marks request complete | 90 days |
| `DSAR_ERASURE_EXECUTED` | Erasure workflow completes | 90 days |

## Success Criteria

- Data Subject can submit DSAR and verify via OTP without authentication.
- CPO queue shows SLA countdown with correct color coding.
- Data export includes all data categories linked to the requesting email.
- Erasure cascades through all systems; legal holds prevent erroneous deletion.
- All state transitions emit audit events.

## Related

- E2E: `frontend/e2e/journeys/dsar-otp-flow.spec.ts` (283.3.2.3)
- Runbook: [phase232-dsar.md](../../runbooks/phase232-dsar.md)
- Components: `PublicDsarSubmitPage`, `PublicDsarStatusPage`, `DsarQueuePage`, `DsarDetailPage`
- Phase: 232.2 (DSAR public ingress + OTP)
