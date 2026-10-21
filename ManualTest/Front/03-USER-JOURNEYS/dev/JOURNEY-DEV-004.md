# JOURNEY-DEV-004: Test Webhook Integration

**Journey ID**: JOURNEY-DEV-004  
**Title**: Test Webhook Integration  
**Persona**: External Developer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **External Developer** (e2e_developer@example.com / TestPass123)
- [ ] Webhook endpoint (e.g. webhook.site for testing)

---

## What You Will Do

Create webhook. Configure URL and events. Trigger event. Verify webhook received.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to webhooks | Go to **Settings** → **Webhooks** or **Developer** → **Webhooks**. | Webhooks page | ☐ |
| 2 | Create webhook | Click **Create Webhook**. Enter URL. | Webhook form | ☐ |
| 3 | Select events | Choose events (e.g. asset.created). | Events selected | ☐ |
| 4 | Save | Submit. | Webhook created | ☐ |
| 5 | Trigger event | Perform action that triggers event (e.g. create asset). | Event triggered | ☐ |
| 6 | Verify | Check webhook endpoint received payload. | Payload received | ☐ |

---

## Success Criteria

- Webhook created
- Event triggered
- Payload received

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dev/JOURNEY-DEV-004.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
