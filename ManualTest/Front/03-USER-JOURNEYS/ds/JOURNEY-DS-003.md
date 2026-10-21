# JOURNEY-DS-003: Configure ML-Based Anomaly Detection

**Journey ID**: JOURNEY-DS-003  
**Title**: Configure ML-Based Anomaly Detection  
**Persona**: Data Scientist  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-ds-003-configure-ml-based-anomaly-detection)

---

## Prerequisites

- [ ] Logged in as **Data Scientist** (e2e_test@example.com or e2e_consumer@example.com / TestPass123)
- [ ] ML anomaly detection capability enabled

---

## What You Will Do

Configure ML anomaly detection for asset/dataset. Set thresholds. Run detection. Review results.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to ML/DQ | Go to **ML** or **DQ** → **Anomaly Detection**. | Anomaly config page | ☐ |
| 2 | Select target | Choose asset or dataset. | Target selected | ☐ |
| 3 | Configure | Set sensitivity, thresholds. | Config saved | ☐ |
| 4 | Run | Trigger anomaly detection. | Run executes | ☐ |
| 5 | Review | View anomalies. | Anomalies displayed | ☐ |

---

## Success Criteria

- Detection configured
- Run executes
- Anomalies visible

---

## Note

If ML anomaly detection is not implemented, document "Capability not available" and skip.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/ds/JOURNEY-DS-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
