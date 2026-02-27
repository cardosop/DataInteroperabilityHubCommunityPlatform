# Auditor Persona

**Persona**: Auditor  
**Test User**: e2e_auditor@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-8-auditor)

---

## Overview

Reviews audit logs, compliance, data mesh governance, and social feature activity. Has read-only audit access.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-AUD-001 | Review Audit Logs | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-aud-001-review-audit-logs) | `journeys/aud/JOURNEY-AUD-001.spec.ts` | 10 min |
| JOURNEY-AUD-002 | Export Audit Report | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/aud/JOURNEY-AUD-002.spec.ts` | 5 min |
| JOURNEY-AUD-003 | Review Compliance Audit | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md) | `journeys/aud/JOURNEY-AUD-003.spec.ts` | 5 min |
| JOURNEY-AUD-004 | Review Data Mesh Governance | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-aud-004-review-data-mesh-governance-new) | `journeys/aud/JOURNEY-AUD-004.spec.ts` | 5 min |
| JOURNEY-AUD-005 | Audit Transformation Pipelines | **Deferred** | — | — |
| JOURNEY-AUD-006 | Review Social Feature Activity | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-aud-006-review-social-feature-activity-new) | `journeys/aud/JOURNEY-AUD-006.spec.ts` | 5 min |

**Total Estimated Duration**: ~30 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-AUD-001** — Review audit logs
2. [ ] **JOURNEY-AUD-002** — Export audit report
3. [ ] **JOURNEY-AUD-003** — Review compliance audit
4. [ ] **JOURNEY-AUD-004** — Review data mesh governance
5. [ ] **JOURNEY-AUD-006** — Review social feature activity (if capability enabled)

---

## Key Routes

- `/audit`, `/audit/:id`
- `/admin` (audit section, if role permits)

---

## Prerequisites

- AUDITOR role
- Audit logs populated (run other flows first)

---

## Sign-Off

| Tester | Date | AUD Persona Pass |
|--------|------|-------------------|
| | | ☐ |
