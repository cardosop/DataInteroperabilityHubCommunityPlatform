# JOURNEY-AUD-001: Review Audit Logs

**Journey ID**: JOURNEY-AUD-001  
**Title**: Review Audit Logs  
**Persona**: Auditor  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-aud-001-review-audit-logs)

---

## Prerequisites

- [ ] Logged in as **Auditor** (e2e_auditor@example.com / TestPass123)
- [ ] Audit logs populated (run other flows first: login, asset create, etc.)

---

## What You Will Do

View audit logs, filter by action/actor/time, and review log details.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to audit | Go to **Audit** or **Admin** → **Audit Logs**. | Audit page loads | ☐ |
| 2 | View log list | Browse recent audit entries. | Entries displayed (action, actor, timestamp) | ☐ |
| 3 | Filter (if available) | Filter by action type, user, date range. | Filtered results | ☐ |
| 4 | View detail | Click an entry. | Detail (payload, changes) visible | ☐ |
| 5 | Export (if available) | Export report. | File downloaded | ☐ |

---

## Success Criteria

- Audit logs accessible
- Entries visible
- Filtering works (if available)
- Detail view works

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/aud/JOURNEY-AUD-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
