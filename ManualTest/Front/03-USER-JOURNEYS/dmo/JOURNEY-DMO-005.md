# JOURNEY-DMO-005: Monitor Domain Health

**Journey ID**: JOURNEY-DMO-005  
**Title**: Monitor Domain Health  
**Persona**: Data Mesh Domain Owner  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dmo-005-monitor-domain-health)

---

## Prerequisites

- [ ] Logged in as **Data Mesh Domain Owner** (e2e_dmo@example.com / TestPass123)
- [ ] At least one domain

---

## What You Will Do

View domain health dashboard. Quality, freshness, compliance. Identify issues.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to domain | Go to **Mesh** → select domain. | Domain detail | ☐ |
| 2 | Open health | Find **Health** or **Monitoring** section. | Health dashboard | ☐ |
| 3 | View metrics | Check quality, freshness, compliance. | Metrics displayed | ☐ |
| 4 | Identify issues | Review any alerts or issues. | Issues visible | ☐ |

---

## Success Criteria

- Health dashboard visible
- Metrics displayed
- Issues identifiable

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dmo/JOURNEY-DMO-005.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
