# External Developer Persona

**Persona**: External Developer / Integrator  
**Test User**: e2e_developer@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-7-external-developer--integrator)

---

## Overview

Builds integrations with the hub via API, SDK, developer portal, and plugins. Uses API keys, documentation, and developer tools.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. API docs: http://localhost:3010/api-docs/ (via frontend proxy) or http://localhost:8001/api/v1/openapi.json

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-DEV-001 | Build Custom Integration | [dev/JOURNEY-DEV-001.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-001.md) | `journeys/dev/JOURNEY-DEV-001.spec.ts` | 15 min |
| JOURNEY-DEV-002 | Obtain API Credentials | [dev/JOURNEY-DEV-002.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-002.md) | `journeys/dev/JOURNEY-DEV-002.spec.ts` | 5 min |
| JOURNEY-DEV-003 | Use SDK for Asset Operations | [dev/JOURNEY-DEV-003.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-003.md) | `journeys/dev/JOURNEY-DEV-003.spec.ts` | 10 min |
| JOURNEY-DEV-004 | Test Webhook Integration | [dev/JOURNEY-DEV-004.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-004.md) | `journeys/dev/JOURNEY-DEV-004.spec.ts` | 10 min |
| JOURNEY-DEV-005 | Use Natural Language Search API | [dev/JOURNEY-DEV-005.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-005.md) | `journeys/dev/JOURNEY-DEV-005.spec.ts` | 5 min |
| JOURNEY-DEV-006 | Integrate Transformation Pipeline API | **Deferred** | — | — |
| JOURNEY-DEV-007 | Build Custom Connector | [dev/JOURNEY-DEV-007.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-007.md) | `journeys/dev/JOURNEY-DEV-007.spec.ts` | 10 min |
| JOURNEY-DEV-008 | Use Plugin System | [dev/JOURNEY-DEV-008.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-008.md) | `journeys/dev/JOURNEY-DEV-008.spec.ts` | 5 min |
| JOURNEY-DEV-009 | Integrate with Developer Portal | [dev/JOURNEY-DEV-009.md](../03-USER-JOURNEYS/dev/JOURNEY-DEV-009.md) | `journeys/dev/JOURNEY-DEV-009.spec.ts` | 10 min |

**Total Estimated Duration**: ~45 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DEV-002** — Obtain API credentials (settings/api-keys)
2. [ ] **JOURNEY-DEV-001** — Build custom integration (review docs, test auth)
3. [ ] **JOURNEY-DEV-003** — Use SDK for asset operations
4. [ ] **JOURNEY-DEV-004** — Test webhook integration
5. [ ] **JOURNEY-DEV-009** — Integrate with developer portal
6. [ ] **JOURNEY-DEV-005** — Natural language search API (if capability enabled)
7. [ ] **JOURNEY-DEV-007** — Build custom connector (if capability enabled)
8. [ ] **JOURNEY-DEV-008** — Use plugin system (if capability enabled)

---

## Key Routes

- `/developer` (developer portal)
- `/settings/api-keys`
- `/webhooks` (list, create, :id)
- `/baas` (BaaS API keys, if capability enabled)

---

## Sign-Off

| Tester | Date | DEV Persona Pass |
|--------|------|------------------|
| | | ☐ |
