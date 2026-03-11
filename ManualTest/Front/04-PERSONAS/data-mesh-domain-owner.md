# Data Mesh Domain Owner Persona

**Persona**: Data Mesh Domain Owner  
**Test User**: e2e_dmo@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-12-data-mesh-domain-owner)

---

## Overview

Creates and manages data mesh domains, configures federated governance, manages domain topology, transfers asset ownership, and monitors domain health.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. **Note**: Data mesh capability must be enabled. e2e_dmo may need subscription (ensure_e2e_subscription does not include e2e_dmo by default—check if 403 occurs).

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-DMO-001 | Create Data Mesh Domain | [dmo/JOURNEY-DMO-001.md](../03-USER-JOURNEYS/dmo/JOURNEY-DMO-001.md) | `journeys/dmo/JOURNEY-DMO-001.spec.ts` | 10 min |
| JOURNEY-DMO-002 | Configure Federated Governance | [dmo/JOURNEY-DMO-002.md](../03-USER-JOURNEYS/dmo/JOURNEY-DMO-002.md) | `journeys/dmo/JOURNEY-DMO-002.spec.ts` | 10 min |
| JOURNEY-DMO-003 | Manage Domain Topology | [dmo/JOURNEY-DMO-003.md](../03-USER-JOURNEYS/dmo/JOURNEY-DMO-003.md) | `journeys/dmo/JOURNEY-DMO-003.spec.ts` | 5 min |
| JOURNEY-DMO-004 | Transfer Asset Ownership | [dmo/JOURNEY-DMO-004.md](../03-USER-JOURNEYS/dmo/JOURNEY-DMO-004.md) | `journeys/dmo/JOURNEY-DMO-004.spec.ts` | 5 min |
| JOURNEY-DMO-005 | Monitor Domain Health | [dmo/JOURNEY-DMO-005.md](../03-USER-JOURNEYS/dmo/JOURNEY-DMO-005.md) | `journeys/dmo/JOURNEY-DMO-005.spec.ts` | 5 min |

**Total Estimated Duration**: ~30 min

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DMO-001** — Create data mesh domain
2. [ ] **JOURNEY-DMO-002** — Configure federated governance
3. [ ] **JOURNEY-DMO-003** — Manage domain topology
4. [ ] **JOURNEY-DMO-004** — Transfer asset ownership
5. [ ] **JOURNEY-DMO-005** — Monitor domain health

---

## Key Routes

- `/mesh`, `/mesh/topology`, `/mesh/create`, `/mesh/:id`

---

---

## Sign-Off

| Tester | Date | DMO Persona Pass |
|--------|------|------------------|
| | | ☐ |
