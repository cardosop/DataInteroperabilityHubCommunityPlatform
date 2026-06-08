# RB-COMP-005 — DPIA Review Investigation (283.3.5.5)

**Date:** 2026-05-16  
**Feature flag:** `compliance_dpia_enabled` (GA, opt-in)  
**GDPR basis:** Art. 35 (DPIA requirement), Art. 36 (prior consultation)

## 1. Overview

The DPIA workflow manages Data Protection Impact Assessments: create → submit → DPO review → approve/reject → periodic review. High-risk processing activities require a DPIA before processing begins.

## 2. Symptoms

### Review queue backlog

- **Symptom:** `DpiaReviewQueueBacklog` alert fires (>10 DPIAs pending review)
- **Response:** Check `GET /api/v1/dpia/records/review-queue/`. Assign DPO reviewers.

### Periodic review overdue

- **Symptom:** DPIA past `next_review_date` without being reviewed
- **Response:** Trigger review via `POST /api/v1/dpia/records/{id}/trigger-review/`

## 3. Investigation

```sql
-- Find overdue periodic reviews
SELECT id, title, status, last_reviewed_at, next_review_date
FROM dpia_dpia
WHERE status = 'APPROVED'
  AND next_review_date < NOW()
ORDER BY next_review_date;
```

## 4. Remediation

### Review backlog

1. Assign DPO reviewers to all pending DPIAs
2. Prioritise HIGH risk assessments
3. If backlog >20, escalate to DPO for triage

### Overdue periodic review

1. Trigger review with notes
2. Update assessment with new findings
3. Set `next_review_date` for next cycle

## 5. Recovery Validation

- [ ] Review queue <10 pending
- [ ] Zero overdue periodic reviews
- [ ] All HIGH risk DPIAs reviewed within 30 days
- [ ] Audit trail complete

## 6. Escalation

| Condition | Action |
|---|---|
| HIGH risk DPIA >30 days unreviewed | Escalate to DPO |
| Review queue >20 | Escalate to privacy-eng + DPO |
| Periodic review overdue >90 days | File with supervisory authority |

## 7. Related Runbooks

- `RB-COMP-001-compliance-fail-closed.md` — compliance gate
- `RB-COMP-004-breach.md` — breach notification
