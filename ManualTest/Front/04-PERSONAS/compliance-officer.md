# Compliance Officer Persona

**Persona**: Compliance & Privacy Officer (CPO)  
**Test User**: e2e_cpo@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-3-compliance--privacy-officer)

---

## Overview

Reviews compliance for assets, configures retention policies, and manages governance. Uses compliance scanning, retention rules, and access request workflows.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. **Dependency**: At least one asset with compliance runs. Run [Data Product Owner](data-product-owner.md) JOURNEY-DPO-001 or compliance scan first.

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-CPO-001 | Review Compliance for Asset | [cpo/JOURNEY-CPO-001.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-001.md) | `journeys/cpo/JOURNEY-CPO-001.spec.ts` | 10 min |
| JOURNEY-CPO-002 | Configure Retention Policy | [cpo/JOURNEY-CPO-002.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-002.md) | `journeys/cpo/JOURNEY-CPO-002.spec.ts` | 10 min |
| JOURNEY-CPO-003 | Review Access Request | [cpo/JOURNEY-CPO-003.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-003.md) | `journeys/governance-retention/governance-retention-crud.spec.ts` | 10 min |
| JOURNEY-CPO-004 | Run Compliance Scan | [cpo/JOURNEY-CPO-004.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-004.md) | `journeys/cpo/JOURNEY-CPO-004.spec.ts` | 10 min |
| JOURNEY-CPO-005 | Generate Compliance Report | [cpo/JOURNEY-CPO-005.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-005.md) | `journeys/cpo/JOURNEY-CPO-005.spec.ts` | 5 min |
| JOURNEY-CPO-006 | Configure Automated Compliance | [cpo/JOURNEY-CPO-006.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-006.md) | `journeys/cpo/JOURNEY-CPO-006.spec.ts` | 5 min |
| JOURNEY-CPO-007 | Set Up GDPR Right to be Forgotten | [cpo/JOURNEY-CPO-007.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-007.md) | `journeys/cpo/JOURNEY-CPO-007.spec.ts` | 5 min |
| JOURNEY-CPO-008 | Manage Consent Tracking | [cpo/JOURNEY-CPO-008.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-008.md) | `journeys/cpo/JOURNEY-CPO-008.spec.ts` | 5 min |
| JOURNEY-CPO-009 | Configure Automated Retention Policies | [cpo/JOURNEY-CPO-009.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-009.md) | `journeys/cpo/JOURNEY-CPO-009.spec.ts` | 10 min |
| JOURNEY-CPO-010 | Review AI Auto-Classification Results | [cpo/JOURNEY-CPO-010.md](../03-USER-JOURNEYS/cpo/JOURNEY-CPO-010.md) | `journeys/cpo/JOURNEY-CPO-010.spec.ts` | 5 min |

**Total Estimated Duration**: ~45 min

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-CPO-001** — Review compliance for asset
2. [ ] **JOURNEY-CPO-004** — Run compliance scan
3. [ ] **JOURNEY-CPO-005** — Generate compliance report
4. [ ] **JOURNEY-CPO-002** — Configure retention policy
5. [ ] **JOURNEY-CPO-003** — Review access request (governance)
6. [ ] **JOURNEY-CPO-009** — Configure automated retention policies
7. [ ] **JOURNEY-CPO-006** — Configure automated compliance (if capability enabled)
8. [ ] **JOURNEY-CPO-007** — GDPR Right to be Forgotten (if capability enabled)
9. [ ] **JOURNEY-CPO-008** — Manage consent tracking (if capability enabled)
10. [ ] **JOURNEY-CPO-010** — Review AI auto-classification (if capability enabled)

---

## Key Routes

- `/compliance`, `/compliance/runs/:id`
- `/governance`, `/governance/access-requests/*`
- `/governance/retention`, `/governance/retention/new`, `/governance/retention/:id`
- `/dq` (DQ runs for quality/compliance)

---

---

## Sign-Off

| Tester | Date | CPO Persona Pass |
|--------|------|------------------|
| | | ☐ |
