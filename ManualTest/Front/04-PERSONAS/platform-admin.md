# Platform Admin Persona

**Persona**: Platform Admin / Marketplace Operator  
**Test User**: e2e_platform@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-6-platform-admin--marketplace-operator)

---

## Overview

Manages tenants, platform-wide settings, audit, and marketplace operations. Has cross-tenant visibility and admin capabilities.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-PA-001 | Onboard New Tenant | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-pa-001-onboard-new-tenant) | `journeys/pa/JOURNEY-PA-001.spec.ts` | 20 min |
| JOURNEY-PA-002 | Manage Tenant Lifecycle | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-002.spec.ts` | 10 min |
| JOURNEY-PA-003 | Configure Platform Settings | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-003.spec.ts` | 10 min |
| JOURNEY-PA-004 | Review Platform Analytics | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-004.spec.ts` | 5 min |
| JOURNEY-PA-005 | Manage Marketplace Configuration | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-005.spec.ts` | 10 min |
| JOURNEY-PA-006 | Monitor Marketplace Health | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-006.spec.ts` | 5 min |
| JOURNEY-PA-007 | Manage ODPS Products (Platform) | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-007.spec.ts` | 10 min |
| JOURNEY-PA-008 | Configure External Marketplace Connections | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-008.spec.ts` | 10 min |
| JOURNEY-PA-009 | Manage Federated Assets | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/pa/JOURNEY-MPA-009.spec.ts` | 10 min |
| JOURNEY-PA-010 | Manage ODPS Products | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-pa-010-manage-odps-products-new) | `journeys/pa/JOURNEY-PA-010.spec.ts` | 10 min |

**Total Estimated Duration**: ~60 min

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-PA-001** — Onboard new tenant
2. [ ] **JOURNEY-PA-002** — Manage tenant lifecycle
3. [ ] **JOURNEY-PA-003** — Configure platform settings
4. [ ] **JOURNEY-PA-004** — Review platform analytics
5. [ ] **JOURNEY-PA-005** — Manage marketplace configuration
6. [ ] **JOURNEY-PA-006** — Monitor marketplace health
7. [ ] **JOURNEY-PA-010** — Manage ODPS products
8. [ ] **JOURNEY-PA-007** — Manage ODPS products (platform-level)
9. [ ] **JOURNEY-PA-008** — Configure external marketplace connections
10. [ ] **JOURNEY-PA-009** — Manage federated assets

---

## Key Routes

- `/admin` (platform admin section)
- `/audit`, `/audit/:id`
- `/settings/sessions`, `/settings/api-keys`
- `/marketplace` (admin view)
- `/integrations/connections` (platform-level)
- `/governance` (platform-level)

---

## Prerequisites

- Platform Admin role (is_platform_admin=True)
- Backend configured for multi-tenant

---

## Sign-Off

| Tester | Date | PA Persona Pass |
|--------|------|----------------|
| | | ☐ |
