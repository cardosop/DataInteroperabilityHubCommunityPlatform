# Platform Admin Persona

**Persona**: Platform Admin / Marketplace Operator  
**Test User**: e2e_platform@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-6-platform-admin--marketplace-operator)

---

## Overview

Manages tenants, platform-wide settings, audit, and marketplace operations. Has cross-tenant visibility and admin capabilities.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. Multi-tenant backend and platform admin UI must be available

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-PA-001 | Onboard New Tenant | [pa/JOURNEY-PA-001.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-001.md) | `journeys/pa/JOURNEY-PA-001.spec.ts` | 20 min |
| JOURNEY-PA-002 | Manage Tenant Lifecycle | [pa/JOURNEY-PA-002.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-002.md) | `journeys/pa/JOURNEY-MPA-002.spec.ts` | 10 min |
| JOURNEY-PA-003 | Configure Platform Settings | [pa/JOURNEY-PA-003.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-003.md) | `journeys/pa/JOURNEY-MPA-003.spec.ts` | 10 min |
| JOURNEY-PA-004 | Review Platform Analytics | [pa/JOURNEY-PA-004.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-004.md) | `journeys/pa/JOURNEY-MPA-004.spec.ts` | 5 min |
| JOURNEY-PA-005 | Manage Marketplace Configuration | [pa/JOURNEY-PA-005.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-005.md) | `journeys/pa/JOURNEY-MPA-005.spec.ts` | 10 min |
| JOURNEY-PA-006 | Monitor Marketplace Health | [pa/JOURNEY-PA-006.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-006.md) | `journeys/pa/JOURNEY-MPA-006.spec.ts` | 5 min |
| JOURNEY-PA-007 | Manage ODPS Products (Platform) | [pa/JOURNEY-PA-007.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-007.md) | `journeys/pa/JOURNEY-MPA-007.spec.ts` | 10 min |
| JOURNEY-PA-008 | Configure External Marketplace Connections | [pa/JOURNEY-PA-008.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-008.md) | `journeys/pa/JOURNEY-MPA-008.spec.ts` | 10 min |
| JOURNEY-PA-009 | Manage Federated Assets | [pa/JOURNEY-PA-009.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-009.md) | `journeys/pa/JOURNEY-MPA-009.spec.ts` | 10 min |
| JOURNEY-PA-010 | Manage ODPS Products | [pa/JOURNEY-PA-010.md](../03-USER-JOURNEYS/pa/JOURNEY-PA-010.md) | `journeys/pa/JOURNEY-PA-010.spec.ts` | 10 min |

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

---

## Sign-Off

| Tester | Date | PA Persona Pass |
|--------|------|----------------|
| | | ☐ |
