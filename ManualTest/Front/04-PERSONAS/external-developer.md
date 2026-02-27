# External Developer Persona

**Persona**: External Developer / Integrator  
**Test User**: e2e_developer@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-7-external-developer--integrator)

---

## Overview

Builds integrations with the hub via API, SDK, developer portal, and plugins. Uses API keys, documentation, and developer tools.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-DEV-001 | Build Custom Integration | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dev-001-build-custom-integration) | `journeys/dev/JOURNEY-DEV-001.spec.ts` | 15 min |
| JOURNEY-DEV-002 | Obtain API Credentials | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dev/JOURNEY-DEV-002.spec.ts` | 5 min |
| JOURNEY-DEV-003 | Use SDK for Asset Operations | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dev/JOURNEY-DEV-003.spec.ts` | 10 min |
| JOURNEY-DEV-004 | Test Webhook Integration | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/dev/JOURNEY-DEV-004.spec.ts` | 10 min |
| JOURNEY-DEV-005 | Use Natural Language Search API | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dev-005-use-natural-language-search-api-new) | `journeys/dev/JOURNEY-DEV-005.spec.ts` | 5 min |
| JOURNEY-DEV-006 | Integrate Transformation Pipeline API | **Deferred** | — | — |
| JOURNEY-DEV-007 | Build Custom Connector | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dev-007-build-custom-connector-new) | `journeys/dev/JOURNEY-DEV-007.spec.ts` | 10 min |
| JOURNEY-DEV-008 | Use Plugin System | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dev-008-use-plugin-system-new) | `journeys/dev/JOURNEY-DEV-008.spec.ts` | 5 min |
| JOURNEY-DEV-009 | Integrate with Developer Portal | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-dev-009-integrate-with-developer-portal-new) | `journeys/dev/JOURNEY-DEV-009.spec.ts` | 10 min |

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
