# Auditor Persona

**Persona**: Auditor  
**Test User**: e2e_auditor@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-8-auditor)

---

## Overview

Reviews audit logs, compliance, data mesh governance, and social feature activity. Has read-only audit access.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. **Dependency**: Audit logs populated. Run other flows first (login, asset create, etc.) to generate audit entries.

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-AUD-001 | Review Audit Logs | [aud/JOURNEY-AUD-001.md](../03-USER-JOURNEYS/aud/JOURNEY-AUD-001.md) | `journeys/aud/JOURNEY-AUD-001.spec.ts` | 10 min |
| JOURNEY-AUD-002 | Export Audit Report | [aud/JOURNEY-AUD-002.md](../03-USER-JOURNEYS/aud/JOURNEY-AUD-002.md) | `journeys/aud/JOURNEY-AUD-002.spec.ts` | 5 min |
| JOURNEY-AUD-003 | Review Compliance Audit | [aud/JOURNEY-AUD-003.md](../03-USER-JOURNEYS/aud/JOURNEY-AUD-003.md) | `journeys/aud/JOURNEY-AUD-003.spec.ts` | 5 min |
| JOURNEY-AUD-004 | Review Data Mesh Governance | [aud/JOURNEY-AUD-004.md](../03-USER-JOURNEYS/aud/JOURNEY-AUD-004.md) | `journeys/aud/JOURNEY-AUD-004.spec.ts` | 5 min |
| JOURNEY-AUD-005 | Audit Transformation Pipelines | **Deferred** | — | — |
| JOURNEY-AUD-006 | Review Social Feature Activity | [aud/JOURNEY-AUD-006.md](../03-USER-JOURNEYS/aud/JOURNEY-AUD-006.md) | `journeys/aud/JOURNEY-AUD-006.spec.ts` | 5 min |

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

---

## Sign-Off

| Tester | Date | AUD Persona Pass |
|--------|------|-------------------|
| | | ☐ |
