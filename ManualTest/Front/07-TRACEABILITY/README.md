# Manual Test Traceability

**Version**: 1.2.0  
**Last Updated**: 2026-03-06

---

## Overview

This directory maps **Use Cases**, **User Journeys**, and **Personas** to manual test scripts. For full automated test traceability, see [docs/TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md).

---

## Use Case → Script Mapping

### Auth Use Cases (UC-AUTH-001–004)

| Use Case | Title | Manual Script | E2E Spec |
|----------|-------|---------------|----------|
| UC-AUTH-001 | User Registers | [02-USE-CASES/UC-AUTH-001.md](../02-USE-CASES/UC-AUTH-001.md) | `journeys/auth/JOURNEY-AUTH-001.spec.ts` |
| UC-AUTH-002 | User Logs In | [02-USE-CASES/UC-AUTH-002.md](../02-USE-CASES/UC-AUTH-002.md) | `journeys/auth/JOURNEY-AUTH-002.spec.ts`, `login-app-shell.spec.ts` |
| UC-AUTH-003 | User Resets Password | [02-USE-CASES/UC-AUTH-003.md](../02-USE-CASES/UC-AUTH-003.md) | `journeys/auth/JOURNEY-AUTH-003.spec.ts` |
| UC-AUTH-004 | Unauthenticated User Accesses Public Resources | [02-USE-CASES/UC-AUTH-004.md](../02-USE-CASES/UC-AUTH-004.md) | `journeys/auth/JOURNEY-AUTH-004.spec.ts` |

### Visual Verification (Phase 29.66.18.3)

| Item | Checklist |
|------|-----------|
| UX components | [VISUAL_VERIFICATION_UX.md](VISUAL_VERIFICATION_UX.md) — asset upload, dataset edit, UUID copy, breadcrumbs, toast, ConfirmDialog |

### Other Use Cases

For use cases beyond auth, manual coverage is via **persona scripts** (04-PERSONAS/). Each persona script references the journeys that implement multiple use cases. See [docs/USE_CASES.md](../../docs/USE_CASES.md) and [docs/TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md) for full UC → test mapping.

---

## Journey → Script Mapping

### Auth Journeys

| Journey | Title | Manual Script | E2E Spec |
|---------|-------|---------------|----------|
| JOURNEY-AUTH-001 | First-Time Visitor Registers | [03-USER-JOURNEYS/auth/JOURNEY-AUTH-001.md](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-001.md) | `journeys/auth/JOURNEY-AUTH-001.spec.ts` |
| JOURNEY-AUTH-002 | User Logs In | [03-USER-JOURNEYS/auth/JOURNEY-AUTH-002.md](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-002.md) | `journeys/auth/JOURNEY-AUTH-002.spec.ts`, `login-app-shell.spec.ts` |
| JOURNEY-AUTH-003 | User Resets Password | [03-USER-JOURNEYS/auth/JOURNEY-AUTH-003.md](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-003.md) | `journeys/auth/JOURNEY-AUTH-003.spec.ts` |
| JOURNEY-AUTH-004 | Unauthenticated User Accesses Public Resources | [03-USER-JOURNEYS/auth/JOURNEY-AUTH-004.md](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-004.md) | `journeys/auth/JOURNEY-AUTH-004.spec.ts` |

### Role-Based Journeys

Role-based journeys are covered by **persona scripts**. Each persona script lists all journeys for that persona with links to docs and E2E specs. See [04-PERSONAS/README.md](../04-PERSONAS/README.md).

### Gap Coverage Journeys (useronboardfix Phases 8, 17)

| Journey | Title | Manual Script | E2E Spec |
|---------|-------|---------------|----------|
| JOURNEY-TA-SUBSCRIPTION | Manage Subscription and Invoices | [03-USER-JOURNEYS/ta/JOURNEY-TA-SUBSCRIPTION.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-SUBSCRIPTION.md) | `journeys/ta/JOURNEY-TA-SUBSCRIPTION.spec.ts` |
| JOURNEY-TA-TENANT-SETTINGS | View Usage and Configure Tenant | [03-USER-JOURNEYS/ta/JOURNEY-TA-TENANT-SETTINGS.md](../03-USER-JOURNEYS/ta/JOURNEY-TA-TENANT-SETTINGS.md) | `journeys/ta/JOURNEY-TA-TENANT-SETTINGS.spec.ts` |

See [docs/TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md#useronboardfix-gap-coverage-phases-7-17) for full traceability.

### Social / Communities Journeys (Phase 27)

| Journey | Title | Manual Script | E2E Spec |
|---------|-------|---------------|----------|
| JOURNEY-CM-001 | Manage Data Community | [03-USER-JOURNEYS/cm/JOURNEY-CM-001.md](../03-USER-JOURNEYS/cm/JOURNEY-CM-001.md) | `journeys/cm/JOURNEY-CM-001.spec.ts` |
| JOURNEY-DC-008 | Rate and Review Asset | [03-USER-JOURNEYS/dc/JOURNEY-DC-008.md](../03-USER-JOURNEYS/dc/JOURNEY-DC-008.md) | `journeys/dc/JOURNEY-DC-008.spec.ts` |
| JOURNEY-DC-009 | Join Data Community | [03-USER-JOURNEYS/dc/JOURNEY-DC-009.md](../03-USER-JOURNEYS/dc/JOURNEY-DC-009.md) | `journeys/dc/JOURNEY-DC-009.spec.ts` |
| JOURNEY-DPO-009 | Manage Asset Ratings and Reviews | [03-USER-JOURNEYS/dpo/JOURNEY-DPO-009.md](../03-USER-JOURNEYS/dpo/JOURNEY-DPO-009.md) | `journeys/dpo/JOURNEY-DPO-009.spec.ts` |

**Route reference**: `/communities` (Phase 27.2); `/social` redirects to `/communities`. Asset Community section on `/assets/:id` (Phase 27.1).

---

## Persona → Script Mapping

| Persona | Manual Script | E2E Persona Spec |
|---------|---------------|------------------|
| Visitor | [04-PERSONAS/visitor.md](../04-PERSONAS/visitor.md) | `personas/visitor.spec.ts` |
| Data Product Owner | [04-PERSONAS/data-product-owner.md](../04-PERSONAS/data-product-owner.md) | `personas/data-product-owner.spec.ts` |
| Data Consumer | [04-PERSONAS/data-consumer.md](../04-PERSONAS/data-consumer.md) | `personas/data-consumer.spec.ts` |
| Data Engineer | [04-PERSONAS/data-engineer.md](../04-PERSONAS/data-engineer.md) | `personas/data-engineer.spec.ts` |
| Compliance Officer | [04-PERSONAS/compliance-officer.md](../04-PERSONAS/compliance-officer.md) | `personas/compliance-officer.spec.ts` |
| Tenant Admin | [04-PERSONAS/tenant-admin.md](../04-PERSONAS/tenant-admin.md) | `personas/tenant-admin.spec.ts` |
| Platform Admin | [04-PERSONAS/platform-admin.md](../04-PERSONAS/platform-admin.md) | `personas/platform-admin.spec.ts` |
| External Developer | [04-PERSONAS/external-developer.md](../04-PERSONAS/external-developer.md) | `personas/external-developer.spec.ts` |
| Auditor | [04-PERSONAS/auditor.md](../04-PERSONAS/auditor.md) | `personas/auditor.spec.ts` |
| Data Scientist | [04-PERSONAS/data-scientist.md](../04-PERSONAS/data-scientist.md) | `personas/data-scientist.spec.ts` |
| Data Analyst | [04-PERSONAS/data-analyst.md](../04-PERSONAS/data-analyst.md) | `personas/data-analyst.spec.ts` |
| Community Manager | [04-PERSONAS/community-manager.md](../04-PERSONAS/community-manager.md) | `personas/community-manager.spec.ts` |
| Data Mesh Domain Owner | [04-PERSONAS/data-mesh-domain-owner.md](../04-PERSONAS/data-mesh-domain-owner.md) | `personas/data-mesh-domain-owner.spec.ts` |

---

## Deferred Journeys (Not Executable)

The following 6 journeys are **deferred** until the transformation pipeline exists:

- JOURNEY-DPO-008, JOURNEY-DE-007, JOURNEY-DC-007
- JOURNEY-AUD-005, JOURNEY-DA-001, JOURNEY-DEV-006

See [docs/USER_JOURNEYS.md](../../docs/USER_JOURNEYS.md#deferred-journeys-transformation-pipeline).
