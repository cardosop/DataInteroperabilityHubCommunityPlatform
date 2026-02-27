# Tenant Admin Persona

**Persona**: Tenant Admin  
**Test User**: e2e_admin@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-5-tenant-admin)

---

## Overview

Manages tenant users, roles, settings, data mesh domains, governance, and integration ecosystem. Has tenant-scoped admin access.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-TA-001 | Onboard New User | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ta-001-onboard-new-user) | `journeys/ta/JOURNEY-TA-001.spec.ts` | 15 min |
| JOURNEY-TA-002 | Manage User Roles | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/ta/JOURNEY-TA-002.spec.ts` | 10 min |
| JOURNEY-TA-003 | Configure Tenant Settings | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/ta/JOURNEY-TA-003.spec.ts` | 10 min |
| JOURNEY-TA-004 | Review Tenant Analytics | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/ta/JOURNEY-TA-004.spec.ts` | 5 min |
| JOURNEY-TA-005 | Configure Data Mesh Domains | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ta-005-configure-data-mesh-domains-new) | `journeys/ta/JOURNEY-TA-005.spec.ts` | 10 min |
| JOURNEY-TA-006 | Set Up Advanced Governance | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ta-006-set-up-advanced-governance-new) | `journeys/ta/JOURNEY-TA-006.spec.ts` | 10 min |
| JOURNEY-TA-007 | Monitor Cost Tracking | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ta-007-monitor-cost-tracking-new) | `journeys/ta/JOURNEY-TA-007.spec.ts` | 5 min |
| JOURNEY-TA-008 | Configure Integration Ecosystem | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ta-008-configure-integration-ecosystem-new) | `journeys/ta/JOURNEY-TA-008.spec.ts` | 15 min |

**Total Estimated Duration**: ~45 min

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
