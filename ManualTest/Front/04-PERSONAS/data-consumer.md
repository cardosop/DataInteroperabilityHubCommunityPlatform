# Data Consumer Persona

**Persona**: Data Consumer  
**Test User**: e2e_consumer@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-4-data-consumer--buyer)

---

## Overview

Discovers, browses, and purchases data assets from the marketplace. May browse catalog, search, filter, and complete purchase flows.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-DC-001 | Discover and Purchase Marketplace Asset | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-001-discover-and-purchase-marketplace-asset) | `journeys/dc/JOURNEY-DC-001.spec.ts` | 15 min |
| JOURNEY-DC-002 | Browse Catalog | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dc/JOURNEY-DC-002.spec.ts` | 5 min |
| JOURNEY-DC-003 | Search and Filter Assets | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dc/JOURNEY-DC-003.spec.ts` | 5 min |
| JOURNEY-DC-004 | Access Entitlement | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dc/JOURNEY-DC-004.spec.ts` | 5 min |
| JOURNEY-DC-005 | Download Data | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dc/JOURNEY-DC-005.spec.ts` | 5 min |
| JOURNEY-DC-006 | Use Natural Language Search | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-006-use-natural-language-search-new) | `journeys/dc/JOURNEY-DC-006.spec.ts` | 5 min |
| JOURNEY-DC-007 | Create Transformation Pipeline | **Deferred** | — | — |
| JOURNEY-DC-008 | Rate and Review Asset | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-008-rate-and-review-asset-new) | `journeys/dc/JOURNEY-DC-008.spec.ts` | 5 min |
| JOURNEY-DC-009 | Join Data Community | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-009-join-data-community-new) | `journeys/dc/JOURNEY-DC-009.spec.ts` | 5 min |
| JOURNEY-DC-010 | Query Virtual Dataset | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-010-query-virtual-dataset-new) | `journeys/dc/JOURNEY-DC-010.spec.ts` | 10 min |
| JOURNEY-DC-011 | Purchase with Usage-Based Pricing | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-011-purchase-asset-with-usage-based-pricing-new) | `journeys/dc/JOURNEY-DC-011.spec.ts` | 10 min |
| JOURNEY-DC-012 | Preview Data Before Purchase | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-012-preview-data-before-purchase-new) | `journeys/dc/JOURNEY-DC-012.spec.ts` | 5 min |
| JOURNEY-DC-013 | Use Asset Recommendations | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-013-use-asset-recommendations-new) | `journeys/dc/JOURNEY-DC-013.spec.ts` | 5 min |
| JOURNEY-DC-014 | Discover ODPS Products (Semantic Search) | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-014-discover-odps-products-semantic-search-new) | `journeys/dc/JOURNEY-DC-014.spec.ts` | 10 min |
| JOURNEY-DC-015 | Purchase ODPS Product (Marketplace) | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dc-015-purchase-odps-product-marketplace-new) | `journeys/dc/JOURNEY-DC-015.spec.ts` | 15 min |

**Total Estimated Duration**: ~60 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DC-002** — Browse catalog
2. [ ] **JOURNEY-DC-003** — Search and filter assets
3. [ ] **JOURNEY-DC-001** — Discover and purchase marketplace asset
4. [ ] **JOURNEY-DC-004** — Access entitlement (after purchase)
5. [ ] **JOURNEY-DC-005** — Download data
6. [ ] **JOURNEY-DC-015** — Purchase ODPS product (marketplace)
7. [ ] **JOURNEY-DC-014** — Discover ODPS products (semantic search)
8. [ ] **JOURNEY-DC-010** — Query virtual dataset (if capability enabled)
9. [ ] **JOURNEY-DC-006** — Natural language search (if capability enabled)
10. [ ] **JOURNEY-DC-012** — Preview data before purchase (if capability enabled)
11. [ ] **JOURNEY-DC-011** — Purchase with usage-based pricing (if capability enabled)
12. [ ] **JOURNEY-DC-008** — Rate and review asset (if capability enabled)
13. [ ] **JOURNEY-DC-009** — Join data community (if capability enabled)
14. [ ] **JOURNEY-DC-013** — Use asset recommendations (if capability enabled)

---

## Key Routes

- `/marketplace`, `/marketplace/listings/:id`
- `/orders`, `/entitlements`
- `/search`, `/ai/search`
- `/virtualization`, `/virtualization/:id`
- `/semantic` (if capability enabled)

---

## Prerequisites

- At least one asset published to marketplace (run DPO flows first, or use seed data)

---

## Sign-Off

| Tester | Date | DC Persona Pass |
|--------|------|-----------------|
| | | ☐ |
