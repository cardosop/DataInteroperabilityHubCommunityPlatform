# Data Mesh Domain Owner Persona

**Persona**: Data Mesh Domain Owner  
**Test User**: e2e_dmo@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-12-data-mesh-domain-owner)

---

## Overview

Creates and manages data mesh domains, configures federated governance, manages domain topology, transfers asset ownership, and monitors domain health.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-DMO-001 | Create Data Mesh Domain | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dmo-001-create-data-mesh-domain) | `journeys/dmo/JOURNEY-DMO-001.spec.ts` | 10 min |
| JOURNEY-DMO-002 | Configure Federated Governance | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dmo-002-configure-federated-governance) | `journeys/dmo/JOURNEY-DMO-002.spec.ts` | 10 min |
| JOURNEY-DMO-003 | Manage Domain Topology | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dmo-003-manage-domain-topology) | `journeys/dmo/JOURNEY-DMO-003.spec.ts` | 5 min |
| JOURNEY-DMO-004 | Transfer Asset Ownership | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dmo-004-transfer-asset-ownership) | `journeys/dmo/JOURNEY-DMO-004.spec.ts` | 5 min |
| JOURNEY-DMO-005 | Monitor Domain Health | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dmo-005-monitor-domain-health) | `journeys/dmo/JOURNEY-DMO-005.spec.ts` | 5 min |

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

## Prerequisites

- TENANT_ADMIN or DATA_MESH_DOMAIN_OWNER role
- Data mesh capability enabled

---

## Sign-Off

| Tester | Date | DMO Persona Pass |
|--------|------|------------------|
| | | ☐ |
