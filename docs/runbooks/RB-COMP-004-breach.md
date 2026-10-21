# RB-COMP-004 — Breach Incident Investigation (283.3.4.5)

**Date:** 2026-05-15  
**Feature flag:** `compliance_breach_enabled` (GA)  
**GDPR basis:** Art. 33 (DPA notification), Art. 34 (subject notification)

## 1. Overview

The breach workflow manages the full incident lifecycle: create → investigate → notify DPA → notify subjects → resolve → close. Statutory deadlines are tracked per incident with SLA-level escalation.

## 2. Symptoms

### SLA deadline approaching

- **Symptom:** `BreachSLADeadlineApproaching` alert fires
- **Response:** Check `GET /api/v1/governance/breach-dashboard/` for overdue/approaching incidents. Prioritise CRITICAL first.

### Notification stuck

- **Symptom:** Incident stuck in `NOTIFIED_DPA` or `NOTIFIED_SUBJECTS` >24h
- **Response:** Check notification delivery status. Verify email provider (SES) is healthy. Retry failed notifications.

## 3. Investigation

```sql
-- Find overdue incidents
SELECT id, title, status, sla_level, notification_deadline
FROM breach_incident
WHERE status NOT IN ('RESOLVED', 'CLOSED')
  AND notification_deadline < NOW()
ORDER BY sla_level DESC;
```

## 4. Remediation

### SLA breach (deadline missed)

1. Escalate to DPO immediately
2. File late notification with supervisory authority
3. Document reason for delay in audit trail
4. Update incident status with resolution note

### Notification delivery failure

1. Check SES dashboard for bounce/complaint
2. Verify recipient email addresses
3. Resend via alternative channel
4. Document delivery attempts

## 5. Recovery Validation

- [ ] All overdue incidents addressed
- [ ] SLA metrics show zero overdue
- [ ] Notifications delivered and acknowledged
- [ ] Incident audit trail complete

## 6. Escalation

| Condition | Action |
|---|---|
| CRITICAL SLA overdue | Escalate to DPO + Platform Lead |
| Notification failure >3 attempts | Escalate to infra on-call |
| 5+ open incidents | Escalate to privacy-eng |

## 7. Related Runbooks

- `RB-COMP-001-compliance-fail-closed.md` — compliance gate investigation
- `vendor-failure-aws.md` — AWS/SES vendor outage
