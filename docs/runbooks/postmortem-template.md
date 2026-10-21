# Postmortem: [INCIDENT-XXX] — Incident Title

**Status:** Draft | Reviewed | Published
**Author:** [Name]
**Date:** YYYY-MM-DD
**Incident Commander:** [Name]
**Severity:** P0 | P1 | P2
**Related incident doc:** [link]

---

## 1. Timeline (all times UTC)

| Time (UTC) | Event |
|---|---|
| `2026-01-01 12:00` | Incident detected (alert fired / customer report) |
| `12:05` | On-call acknowledged, investigation started |
| `12:15` | Root cause identified |
| `12:20` | Mitigation applied |
| `12:45` | Resolution confirmed via health checks |
| `12:50` | Incident resolved / declared closed |

**Total duration:** [X] hours [Y] minutes

---

## 2. Impact

- **Users affected:** [how many, which tenants, which features]
- **Data affected:** [data loss? data corruption? PII exposure?]
- **Revenue impact:** [estimated revenue loss, if applicable]
- **Regulatory impact:** [GDPR Art. 33 breach notification required?]

---

## 3. Root cause (5-whys)

1. **Why** did the incident occur?
   - [First-level cause]

2. **Why** did that condition exist?
   - [Second-level cause]

3. **Why** was the safeguard absent or insufficient?
   - [Third-level cause]

4. **Why** did the process allow this?
   - [Fourth-level cause]

5. **Why** was the system designed this way?
   - [Root cause — the systemic issue]

---

## 4. Detection

- **How was it detected?** [alert / customer report / manual observation / external]
- **Alert that fired** (if applicable): [alert name]
- **Time-to-detect:** [X] minutes (from incident start to acknowledgement)
- **Could detection have been faster?** [yes/no — if yes, what would help]

---

## 5. Resolution

- **Steps taken:**
  1. [Step 1]
  2. [Step 2]
  3. [Step 3]
- **Revert / rollback needed?** [yes/no — describe]
- **Data recovery needed?** [yes/no — describe]
- **Time-to-resolve:** [X] minutes (from acknowledgement to resolution confirmation)
- **External dependencies:** [vendor status pages checked? vendor support contacted?]

---

## 6. Prevention items

| # | Action item | Owner | Due date | Status |
|---|---|---|---|---|
| 1 | [Prevention item 1] | [@owner] | YYYY-MM-DD | [ ] |
| 2 | [Prevention item 2] | [@owner] | YYYY-MM-DD | [ ] |
| 3 | [Prevention item 3] | [@owner] | YYYY-MM-DD | [ ] |

Every prevention item must have a **single owner** and a **concrete due date**.
Items without both will be rejected at postmortem review.

---

## 7. Lessons learned

### What went well

- [Positive observation 1]
- [Positive observation 2]

### What went poorly

- [Negative observation 1]
- [Negative observation 2]

### What should change in the response process

- [Process improvement 1]
- [Process improvement 2]

---

## 8. Attachments

- [Link to incident Slack channel]
- [Link to dashboard screenshot]
- [Link to relevant logs / audit events]
- [Link to vendor support ticket, if applicable]

---

*Template version: 2026-05-13. Fill this out within 48 hours of incident resolution per [postmortem process](../process/postmortems.md).*
