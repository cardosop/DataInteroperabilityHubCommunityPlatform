# Data Engineer Persona

**Persona**: Data Engineer / Contract Author  
**Test User**: e2e_test@example.com (DATA_PROVIDER) or e2e_admin@example.com (TENANT_ADMIN)  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-2-data-engineer--contract-author)

---

## Overview

Works programmatically with contracts, APIs, scheduled ingestion, data quality, compliance scanning, and integrations. Uses UI and API.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. **Support material**: `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json`, `05-SUPPORT-MATERIAL/data/sample-upload.csv`

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-DE-001 | Programmatic Contract-First Onboarding | [de/JOURNEY-DE-001.md](../03-USER-JOURNEYS/de/JOURNEY-DE-001.md) | `journeys/de/JOURNEY-DE-001.spec.ts` | 15 min |
| JOURNEY-DE-002 | Set Up Scheduled Ingestion | [de/JOURNEY-DE-002.md](../03-USER-JOURNEYS/de/JOURNEY-DE-002.md) | `journeys/de/JOURNEY-DE-002.spec.ts` | 15 min |
| JOURNEY-DE-003 | Configure Data Quality Checks | [de/JOURNEY-DE-003.md](../03-USER-JOURNEYS/de/JOURNEY-DE-003.md) | `journeys/de/JOURNEY-DE-003.spec.ts` | 10 min |
| JOURNEY-DE-004 | Set Up Compliance Scanning | [de/JOURNEY-DE-004.md](../03-USER-JOURNEYS/de/JOURNEY-DE-004.md) | `journeys/de/JOURNEY-DE-004.spec.ts` | 10 min |
| JOURNEY-DE-005 | Integrate External Data Source | [de/JOURNEY-DE-005.md](../03-USER-JOURNEYS/de/JOURNEY-DE-005.md) | `journeys/de/JOURNEY-DE-005.spec.ts` | 15 min |
| JOURNEY-DE-006 | Monitor Data Pipeline Health | [de/JOURNEY-DE-006.md](../03-USER-JOURNEYS/de/JOURNEY-DE-006.md) | `journeys/de/JOURNEY-DE-006.spec.ts` | 10 min |
| JOURNEY-DE-007 | Create Transformation Pipeline | **Deferred** | — | — |
| JOURNEY-DE-008 | Integrate AI Schema Matching | [de/JOURNEY-DE-008.md](../03-USER-JOURNEYS/de/JOURNEY-DE-008.md) | `journeys/de/JOURNEY-DE-008.spec.ts` | 10 min |
| JOURNEY-DE-009 | Set Up Data Virtualization | [de/JOURNEY-DE-009.md](../03-USER-JOURNEYS/de/JOURNEY-DE-009.md) | `journeys/de/JOURNEY-DE-009.spec.ts` | 15 min |
| JOURNEY-DE-010 | Configure Connector for Data Source | [de/JOURNEY-DE-010.md](../03-USER-JOURNEYS/de/JOURNEY-DE-010.md) | `journeys/de/JOURNEY-DE-010.spec.ts` | 15 min |
| JOURNEY-DE-011 | Set Up Reverse ETL | [de/JOURNEY-DE-011.md](../03-USER-JOURNEYS/de/JOURNEY-DE-011.md) | `journeys/de/JOURNEY-DE-011.spec.ts` | 10 min |
| JOURNEY-DE-012 | Create Custom Plugin | [de/JOURNEY-DE-012.md](../03-USER-JOURNEYS/de/JOURNEY-DE-012.md) | `journeys/de/JOURNEY-DE-012.spec.ts` | 10 min |
| JOURNEY-DE-013 | Configure Data Mesh Domain | [de/JOURNEY-DE-013.md](../03-USER-JOURNEYS/de/JOURNEY-DE-013.md) | `journeys/de/JOURNEY-DE-013.spec.ts` | 10 min |
| JOURNEY-DE-014 | Create ODPS via API | [de/JOURNEY-DE-014.md](../03-USER-JOURNEYS/de/JOURNEY-DE-014.md) | `journeys/de/JOURNEY-DE-014.spec.ts` | 15 min |

**Total Estimated Duration**: ~60 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DE-001** — Contract-first onboarding (create contract, link asset)  
   **Support**: `contracts/odps-with-embedded-odcs.json`, `data/sample-upload.csv`
2. [ ] **JOURNEY-DE-003** — Configure data quality checks
3. [ ] **JOURNEY-DE-004** — Set up compliance scanning
4. [ ] **JOURNEY-DE-005** — Integrate external data source
5. [ ] **JOURNEY-DE-002** — Set up scheduled ingestion
6. [ ] **JOURNEY-DE-006** — Monitor data pipeline health (jobs)
7. [ ] **JOURNEY-DE-014** — Create ODPS via API  
   **Support**: `contracts/odps-with-embedded-odcs.json`
8. [ ] **JOURNEY-DE-009** — Set up data virtualization
9. [ ] **JOURNEY-DE-010** — Configure connector (integrations)
10. [ ] **JOURNEY-DE-008** — AI schema matching (if capability enabled)
11. [ ] **JOURNEY-DE-011** — Set up reverse ETL (if capability enabled)
12. [ ] **JOURNEY-DE-012** — Create custom plugin (if capability enabled)
13. [ ] **JOURNEY-DE-013** — Configure data mesh domain (if capability enabled)

---

## Key Routes

- `/contracts`, `/contracts/:id`, `/contracts/:id/edit`, `/contracts/:id/link-odps`
- `/dq`, `/dq/runs/:id`
- `/compliance`, `/compliance/runs/:id`
- `/integrations/connections`, `/sync-jobs`, `/mappings`
- `/jobs`, `/jobs/:id`
- `/virtualization`, `/virtualization/create`, `/virtualization/:id`
- `/odps`, `/odps/upload`, `/odps/:id`
- `/scheduled-ingestions/*`

---

## Sign-Off

| Tester | Date | DE Persona Pass |
|--------|------|-----------------|
| | | ☐ |
