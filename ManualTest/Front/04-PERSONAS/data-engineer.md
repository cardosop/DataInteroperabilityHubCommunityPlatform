# Data Engineer Persona

**Persona**: Data Engineer / Contract Author  
**Test User**: e2e_test@example.com (DATA_PROVIDER) or e2e_admin@example.com (TENANT_ADMIN)  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-2-data-engineer--contract-author)

---

## Overview

Works programmatically with contracts, APIs, scheduled ingestion, data quality, compliance scanning, and integrations. Uses UI and API.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-DE-001 | Programmatic Contract-First Onboarding | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-001-programmatic-contract-first-onboarding) | `journeys/de/JOURNEY-DE-001.spec.ts` | 15 min |
| JOURNEY-DE-002 | Set Up Scheduled Ingestion | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/de/JOURNEY-DE-002.spec.ts` | 15 min |
| JOURNEY-DE-003 | Configure Data Quality Checks | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/de/JOURNEY-DE-003.spec.ts` | 10 min |
| JOURNEY-DE-004 | Set Up Compliance Scanning | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/de/JOURNEY-DE-004.spec.ts` | 10 min |
| JOURNEY-DE-005 | Integrate External Data Source | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/de/JOURNEY-DE-005.spec.ts` | 15 min |
| JOURNEY-DE-006 | Monitor Data Pipeline Health | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/de/JOURNEY-DE-006.spec.ts` | 10 min |
| JOURNEY-DE-007 | Create Transformation Pipeline | **Deferred** | — | — |
| JOURNEY-DE-008 | Integrate AI Schema Matching | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-008-integrate-ai-schema-matching-into-workflow-new) | `journeys/de/JOURNEY-DE-008.spec.ts` | 10 min |
| JOURNEY-DE-009 | Set Up Data Virtualization | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-009-set-up-data-virtualization-new) | `journeys/de/JOURNEY-DE-009.spec.ts` | 15 min |
| JOURNEY-DE-010 | Configure Connector for Data Source | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-010-configure-connector-for-data-source-new) | `journeys/de/JOURNEY-DE-010.spec.ts` | 15 min |
| JOURNEY-DE-011 | Set Up Reverse ETL | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-011-set-up-reverse-etl-new) | `journeys/de/JOURNEY-DE-011.spec.ts` | 10 min |
| JOURNEY-DE-012 | Create Custom Plugin | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-012-create-custom-plugin-new) | `journeys/de/JOURNEY-DE-012.spec.ts` | 10 min |
| JOURNEY-DE-013 | Configure Data Mesh Domain | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-013-configure-data-mesh-domain-new) | `journeys/de/JOURNEY-DE-013.spec.ts` | 10 min |
| JOURNEY-DE-014 | Create ODPS via API | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-de-014-create-odps-via-api-new) | `journeys/de/JOURNEY-DE-014.spec.ts` | 15 min |

**Total Estimated Duration**: ~60 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DE-001** — Contract-first onboarding (create contract, link asset)
2. [ ] **JOURNEY-DE-003** — Configure data quality checks
3. [ ] **JOURNEY-DE-004** — Set up compliance scanning
4. [ ] **JOURNEY-DE-005** — Integrate external data source
5. [ ] **JOURNEY-DE-002** — Set up scheduled ingestion
6. [ ] **JOURNEY-DE-006** — Monitor data pipeline health (jobs)
7. [ ] **JOURNEY-DE-014** — Create ODPS via API
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
