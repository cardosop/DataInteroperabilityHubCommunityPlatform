# Tenant Admin Persona

**Persona**: Tenant Admin  
**Test User**: e2e_admin@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-5-tenant-admin)

---

## Overview

Manages tenant users, roles, settings, data mesh domains, governance, and integration ecosystem. Has tenant-scoped admin access.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. For JOURNEY-TA-002: At least one other user in tenant (invite via TA-001 or use existing)

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-TA-001 | Onboard New User | [ta/JOURNEY-TA-001.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-001.md) | `journeys/ta/JOURNEY-TA-001.spec.ts` | 15 min |
| JOURNEY-TA-002 | Manage User Roles | [ta/JOURNEY-TA-002.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-002.md) | `journeys/ta/JOURNEY-TA-002.spec.ts` | 10 min |
| JOURNEY-TA-003 | Configure Tenant Settings | [ta/JOURNEY-TA-003.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-003.md) | `journeys/ta/JOURNEY-TA-003.spec.ts` | 10 min |
| JOURNEY-TA-004 | Review Tenant Analytics | [ta/JOURNEY-TA-004.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-004.md) | `journeys/ta/JOURNEY-TA-004.spec.ts` | 5 min |
| JOURNEY-TA-005 | Configure Data Mesh Domains | [ta/JOURNEY-TA-005.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-005.md) | `journeys/ta/JOURNEY-TA-005.spec.ts` | 10 min |
| JOURNEY-TA-006 | Set Up Advanced Governance | [ta/JOURNEY-TA-006.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-006.md) | `journeys/ta/JOURNEY-TA-006.spec.ts` | 10 min |
| JOURNEY-TA-007 | Monitor Cost Tracking | [ta/JOURNEY-TA-007.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-007.md) | `journeys/ta/JOURNEY-TA-007.spec.ts` | 5 min |
| JOURNEY-TA-008 | Configure Integration Ecosystem | [ta/JOURNEY-TA-008.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-008.md) | `journeys/ta/JOURNEY-TA-008.spec.ts` | 15 min |
| JOURNEY-TA-SUBSCRIPTION | Manage Subscription and Invoices | [ta/JOURNEY-TA-SUBSCRIPTION.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-SUBSCRIPTION.md) | `journeys/ta/JOURNEY-TA-SUBSCRIPTION.spec.ts` | 10 min |
| JOURNEY-TA-TENANT-SETTINGS | View Usage and Configure Tenant | [ta/JOURNEY-TA-TENANT-SETTINGS.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-TENANT-SETTINGS.md) | `journeys/ta/JOURNEY-TA-TENANT-SETTINGS.spec.ts` | 10 min |

**Total Estimated Duration**: ~65 min

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-TA-001** — Onboard new user (invite flow)
2. [ ] **JOURNEY-TA-002** — Manage user roles
3. [ ] **JOURNEY-TA-003** — Configure tenant settings
4. [ ] **JOURNEY-TA-004** — Review tenant analytics
5. [ ] **JOURNEY-TA-005** — Configure data mesh domains
6. [ ] **JOURNEY-TA-006** — Set up advanced governance
7. [ ] **JOURNEY-TA-008** — Configure integration ecosystem (connections, sync jobs)
8. [ ] **JOURNEY-TA-007** — Monitor cost tracking (if capability enabled)
9. [ ] **JOURNEY-TA-SUBSCRIPTION** — Manage subscription and invoices (change plan, invoice history)
10. [ ] **JOURNEY-TA-TENANT-SETTINGS** — View usage and configure tenant (usage tab, config tab)

---

## Key Routes

- `/accept-invitation`, `/auth/accept-invitation`
- `/admin` (tenant admin section)
- `/settings/*` (tenant settings)
- `/mesh`, `/mesh/topology`, `/mesh/create`, `/mesh/:id`
- `/governance`, `/governance/access-requests/*`
- `/integrations/connections`, `/sync-jobs`, `/mappings`
- `/observability` (if capability enabled)

---

## Sign-Off

| Tester | Date | TA Persona Pass |
|--------|------|-----------------|
| | | ☐ |
