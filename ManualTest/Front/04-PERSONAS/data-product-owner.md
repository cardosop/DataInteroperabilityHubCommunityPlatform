# Data Product Owner Persona

**Persona**: Data Product Owner  
**Test User**: e2e_test@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-1-data-product-owner)

---

## Overview

Owns datasets and publishes them as data products. Works primarily through the web UI. Responsible for asset lifecycle, contracts, quality, and marketplace publishing.

---

## Before You Start

1. **Start test stack**: `docker compose -f docker-compose.test.yml up -d`
2. **Ensure E2E users**: `docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles`
3. **Ensure subscriptions**: `docker exec hub-test-api python hub/manage.py ensure_e2e_subscription`
4. **Open frontend**: http://localhost:3010
5. **Log in** as e2e_test@example.com / TestPass123
6. **Prepare support material** (see [05-SUPPORT-MATERIAL](../05-SUPPORT-MATERIAL/README.md)):
   - `05-SUPPORT-MATERIAL/data/sample-upload.csv` — for asset/dataset creation
   - `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json` — for contract creation
   - `05-SUPPORT-MATERIAL/contracts/odps-invalid-missing-schema.json` — for error testing

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|--------------------|----------|------|
| JOURNEY-DPO-001 | Onboard New Asset via Data-First Flow | [dpo/JOURNEY-DPO-001.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-001.md) | `journeys/dpo/asset-creation-flow.spec.ts` | 20 min |
| JOURNEY-DPO-002 | Publish Asset to Marketplace | [dpo/JOURNEY-DPO-002.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-002.md) | `journeys/dpo/JOURNEY-DPO-002.spec.ts` | 15 min |
| JOURNEY-DPO-003 | Manage Asset Lifecycle | [dpo/JOURNEY-DPO-003.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-003.md) | `journeys/dpo/JOURNEY-DPO-003.spec.ts` | 10 min |
| JOURNEY-DPO-004 | Monitor Asset Quality | [dpo/JOURNEY-DPO-004.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-004.md) | `journeys/dpo/JOURNEY-DPO-004.spec.ts` | 10 min |
| JOURNEY-DPO-005 | Configure Data Contracts | [dpo/JOURNEY-DPO-005.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-005.md) | `journeys/dpo/contract-creation-flow.spec.ts` | 15 min |
| JOURNEY-DPO-006 | Manage Marketplace Listings | [dpo/JOURNEY-DPO-006.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-006.md) | `journeys/dpo/JOURNEY-DPO-006.spec.ts` | 10 min |
| JOURNEY-DPO-007 | Use AI Schema Matching | [dpo/JOURNEY-DPO-007.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-007.md) | `journeys/dpo/JOURNEY-DPO-007.spec.ts` | 10 min |
| JOURNEY-DPO-008 | Create Transformation Pipeline | **Deferred** | — | — |
| JOURNEY-DPO-009 | Manage Asset Ratings and Reviews | [dpo/JOURNEY-DPO-009.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-009.md) | `journeys/dpo/JOURNEY-DPO-009.spec.ts` | 5 min |
| JOURNEY-DPO-010 | Publish with Usage-Based Pricing | [dpo/JOURNEY-DPO-010.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-010.md) | `journeys/dpo/JOURNEY-DPO-010.spec.ts` | 10 min |
| JOURNEY-DPO-011 | Assign Data Stewards | [dpo/JOURNEY-DPO-011.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-011.md) | `journeys/dpo/JOURNEY-DPO-011.spec.ts` | 5 min |
| JOURNEY-DPO-012 | Join Data Community | [dpo/JOURNEY-DPO-012.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-012.md) | `journeys/dpo/JOURNEY-DPO-012.spec.ts` | 5 min |
| JOURNEY-DPO-013 | Configure Data Mesh Domain | [dpo/JOURNEY-DPO-013.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-013.md) | `journeys/dpo/JOURNEY-DPO-013.spec.ts` | 10 min |
| JOURNEY-DPO-014 | Monitor Asset Reliability Score | [dpo/JOURNEY-DPO-014.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-014.md) | `journeys/dpo/JOURNEY-DPO-014.spec.ts` | 5 min |
| JOURNEY-DPO-015 | Create ODPS Product (Product-First Flow) | [dpo/JOURNEY-DPO-015.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-015.md) | `journeys/dpo/JOURNEY-DPO-015.spec.ts` | 15 min |
| JOURNEY-DPO-016 | Link ODPS to ODCS Contract | [dpo/JOURNEY-DPO-016.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-016.md) | `journeys/dpo/JOURNEY-DPO-016.spec.ts` | 15 min |
| JOURNEY-DPO-017 | Export ODPS Product | [dpo/JOURNEY-DPO-017.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-017.md) | `journeys/dpo/JOURNEY-DPO-017.spec.ts` | 10 min |

**Total Estimated Duration**: ~90 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DPO-001** — Create asset → upload file → dataset → compliance → DQ → contract → activate  
   **Support**: `data/sample-upload.csv`, `contracts/odps-with-embedded-odcs.json`
2. [ ] **JOURNEY-DPO-005** — Create contract via ODPS upload (valid + invalid)  
   **Support**: `contracts/odps-with-embedded-odcs.json`, `odps-invalid-missing-schema.json`
3. [ ] **JOURNEY-DPO-002** — Publish asset to marketplace (requires ACTIVE asset from DPO-001)
4. [ ] **JOURNEY-DPO-003** — Manage asset lifecycle (status changes)
5. [ ] **JOURNEY-DPO-004** — Monitor asset quality (DQ runs)
6. [ ] **JOURNEY-DPO-015** — Create ODPS product (product-first)  
   **Support**: `contracts/odps-with-embedded-odcs.json`
7. [ ] **JOURNEY-DPO-016** — Link ODPS to ODCS contract (requires ODCS + ODPS from DPO-015)
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

| Route | Purpose |
|-------|---------|
| `/assets`, `/assets/create`, `/assets/:id` | Asset list, create, detail |
| `/datasets`, `/datasets/create`, `/datasets/:id` | Dataset list, create (from file upload), detail |
| `/contracts`, `/contracts/:id`, `/contracts/:id/link-odps` | Contract list, detail, link ODPS |
| `/marketplace`, `/marketplace/publish`, `/marketplace/listings/:id` | Marketplace, publish, listing detail |
| `/odps`, `/odps/upload`, `/odps/:id` | ODPS list, upload (Create Contract → here), detail |
| `/dq`, `/dq/runs/:id` | Data quality runs |
| `/compliance`, `/compliance/runs/:id` | Compliance runs |

**Note**: "Create Contract" (Contracts page) navigates to `/odps/upload` — contract creation is via ODPS upload.

---

## Sign-Off

| Tester | Date | DPO Persona Pass |
|--------|------|------------------|
| | | ☐ |
