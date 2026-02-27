# Data Product Owner Persona

**Persona**: Data Product Owner  
**Test User**: e2e_test@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-1-data-product-owner)

---

## Overview

Owns datasets and publishes them as data products. Works primarily through the web UI. Responsible for asset lifecycle, contracts, quality, and marketplace publishing.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-DPO-001 | Onboard New Asset via Data-First Flow | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-001-onboard-new-asset-via-data-first-flow) | `journeys/dpo/asset-creation-flow.spec.ts` | 20 min |
| JOURNEY-DPO-002 | Publish Asset to Marketplace | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-002-publish-asset-to-marketplace) | `journeys/dpo/JOURNEY-DPO-002.spec.ts` | 15 min |
| JOURNEY-DPO-003 | Manage Asset Lifecycle | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-003-manage-asset-lifecycle) | `journeys/dpo/JOURNEY-DPO-003.spec.ts` | 10 min |
| JOURNEY-DPO-004 | Monitor Asset Quality | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dpo/JOURNEY-DPO-004.spec.ts` | 10 min |
| JOURNEY-DPO-005 | Configure Data Contracts | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dpo/contract-creation-flow.spec.ts` | 15 min |
| JOURNEY-DPO-006 | Manage Marketplace Listings | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dpo/JOURNEY-DPO-006.spec.ts` | 10 min |
| JOURNEY-DPO-007 | Use AI Schema Matching | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-007-use-ai-schema-matching-for-asset-creation-new) | `journeys/dpo/JOURNEY-DPO-007.spec.ts` | 10 min |
| JOURNEY-DPO-008 | Create Transformation Pipeline | **Deferred** | — | — |
| JOURNEY-DPO-009 | Manage Asset Ratings and Reviews | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-009-manage-asset-ratings-and-reviews-new) | `journeys/dpo/JOURNEY-DPO-009.spec.ts` | 5 min |
| JOURNEY-DPO-010 | Publish with Usage-Based Pricing | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-010-publish-asset-with-usage-based-pricing-new) | `journeys/dpo/JOURNEY-DPO-010.spec.ts` | 10 min |
| JOURNEY-DPO-011 | Assign Data Stewards | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-011-assign-data-stewards-new) | `journeys/dpo/JOURNEY-DPO-011.spec.ts` | 5 min |
| JOURNEY-DPO-012 | Join Data Community | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-012-join-data-community-new) | `journeys/dpo/JOURNEY-DPO-012.spec.ts` | 5 min |
| JOURNEY-DPO-013 | Configure Data Mesh Domain | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-013-configure-data-mesh-domain-new) | `journeys/dpo/JOURNEY-DPO-013.spec.ts` | 10 min |
| JOURNEY-DPO-014 | Monitor Asset Reliability Score | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-014-monitor-asset-reliability-score-new) | `journeys/dpo/JOURNEY-DPO-014.spec.ts` | 5 min |
| JOURNEY-DPO-015 | Create ODPS Product (Product-First Flow) | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-015-create-odps-product-product-first-flow-new) | `journeys/dpo/JOURNEY-DPO-015.spec.ts` | 15 min |
| JOURNEY-DPO-016 | Link ODPS to ODCS Contract | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-016-link-odps-to-odcs-contract-technical-first-flow-new) | `journeys/dpo/JOURNEY-DPO-016.spec.ts` | 15 min |
| JOURNEY-DPO-017 | Export ODPS Product | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dpo-017-export-odps-product-new) | `journeys/dpo/JOURNEY-DPO-017.spec.ts` | 10 min |

**Total Estimated Duration**: ~90 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DPO-001** — Create asset → upload file → dataset → compliance → DQ → contract → activate
2. [ ] **JOURNEY-DPO-005** — Create contract (or contract-creation flow)
3. [ ] **JOURNEY-DPO-002** — Publish asset to marketplace
4. [ ] **JOURNEY-DPO-003** — Manage asset lifecycle (status changes)
5. [ ] **JOURNEY-DPO-004** — Monitor asset quality (DQ runs)
6. [ ] **JOURNEY-DPO-015** — Create ODPS product (product-first)
7. [ ] **JOURNEY-DPO-016** — Link ODPS to ODCS contract
8. [ ] **JOURNEY-DPO-017** — Export ODPS product
9. [ ] **JOURNEY-DPO-007** — AI schema matching (if capability enabled)
10. [ ] **JOURNEY-DPO-006** — Manage marketplace listings
11. [ ] **JOURNEY-DPO-009** — Ratings and reviews (if capability enabled)
12. [ ] **JOURNEY-DPO-010** — Usage-based pricing (if capability enabled)
13. [ ] **JOURNEY-DPO-011** — Assign data stewards (if capability enabled)
14. [ ] **JOURNEY-DPO-012** — Join data community (if capability enabled)
15. [ ] **JOURNEY-DPO-013** — Configure data mesh domain (if capability enabled)
16. [ ] **JOURNEY-DPO-014** — Monitor reliability score (if capability enabled)

---

## Key Routes

- `/assets`, `/assets/create`, `/assets/:id`
- `/datasets`, `/datasets/create`, `/datasets/:id`
- `/contracts`, `/contracts/:id`, `/contracts/:id/link-odps`
- `/marketplace`, `/marketplace/publish`, `/marketplace/listings/:id`
- `/odps`, `/odps/upload`, `/odps/:id`
- `/dq`, `/dq/runs/:id`
- `/compliance`, `/compliance/runs/:id`

---

## Sign-Off

| Tester | Date | DPO Persona Pass |
|--------|------|------------------|
| | | ☐ |
