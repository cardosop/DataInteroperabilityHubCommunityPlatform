# Master Test Execution Script

**Version**: 1.0.0  
**Last Updated**: 2026-02-17  
**Estimated Total Duration**: 8–12 hours (full run)

---

## Execution Order

Execute in this order. Each section links to detailed scripts.

### Phase 0: Prerequisites

- [ ] Complete [00-PREREQUISITES.md](00-PREREQUISITES.md)
- [ ] Run [06-CHECKLISTS/smoke-test.md](06-CHECKLISTS/smoke-test.md) — ~15 min

---

### Phase 1: Authentication & Visitor (≈ 45 min)

| # | Script | Duration | Pass |
|---|--------|----------|------|
| 1 | [JOURNEY-AUTH-004](03-USER-JOURNEYS/auth/JOURNEY-AUTH-004.md) — Unauthenticated User Accesses Public Resources | 10 min | ☐ |
| 2 | [JOURNEY-AUTH-001](03-USER-JOURNEYS/auth/JOURNEY-AUTH-001.md) — First-Time Visitor Registers | 10 min | ☐ |
| 3 | [JOURNEY-AUTH-002](03-USER-JOURNEYS/auth/JOURNEY-AUTH-002.md) — User Logs In | 10 min | ☐ |
| 4 | [JOURNEY-AUTH-003](03-USER-JOURNEYS/auth/JOURNEY-AUTH-003.md) — User Resets Password | 15 min | ☐ |

---

### Phase 2: Core Personas (≈ 4–6 hours)

| # | Persona | Script | Duration | Pass |
|---|---------|--------|----------|------|
| 5 | Data Product Owner | [04-PERSONAS/data-product-owner.md](04-PERSONAS/data-product-owner.md) | 90 min | ☐ |
| 6 | Data Consumer | [04-PERSONAS/data-consumer.md](04-PERSONAS/data-consumer.md) | 60 min | ☐ |
| 7 | Data Engineer | [04-PERSONAS/data-engineer.md](04-PERSONAS/data-engineer.md) | 60 min | ☐ |
| 8 | Compliance Officer | [04-PERSONAS/compliance-officer.md](04-PERSONAS/compliance-officer.md) | 45 min | ☐ |
| 9 | Tenant Admin | [04-PERSONAS/tenant-admin.md](04-PERSONAS/tenant-admin.md) | 45 min | ☐ |
| 10 | Platform Admin | [04-PERSONAS/platform-admin.md](04-PERSONAS/platform-admin.md) | 60 min | ☐ |

---

### Phase 3: Extended Personas (≈ 2–3 hours)

| # | Persona | Script | Duration | Pass |
|---|---------|--------|----------|------|
| 11 | External Developer | [04-PERSONAS/external-developer.md](04-PERSONAS/external-developer.md) | 45 min | ☐ |
| 12 | Auditor | [04-PERSONAS/auditor.md](04-PERSONAS/auditor.md) | 30 min | ☐ |
| 13 | Data Scientist | [04-PERSONAS/data-scientist.md](04-PERSONAS/data-scientist.md) | 30 min | ☐ |
| 14 | Data Analyst | [04-PERSONAS/data-analyst.md](04-PERSONAS/data-analyst.md) | 30 min | ☐ |
| 15 | Community Manager | [04-PERSONAS/community-manager.md](04-PERSONAS/community-manager.md) | 30 min | ☐ |
| 16 | Data Mesh Domain Owner | [04-PERSONAS/data-mesh-domain-owner.md](04-PERSONAS/data-mesh-domain-owner.md) | 30 min | ☐ |

---

### Phase 4: Cross-Cutting (≈ 30 min)

| # | Area | Script | Duration | Pass |
|---|------|--------|----------|------|
| 17 | 404/403/Session | [06-CHECKLISTS/alternate-flows.md](06-CHECKLISTS/alternate-flows.md) | 30 min | ☐ |

---

### Release Sign-Off

Before release, complete [06-CHECKLISTS/release-sign-off.md](06-CHECKLISTS/release-sign-off.md).

---

## Sign-Off

| Tester | Date | Full Run Pass |
|--------|------|---------------|
| | | ☐ |

---

## Deferred Journeys (Not Executable)

The following 6 journeys are **deferred** until the transformation pipeline exists:

- JOURNEY-DPO-008, JOURNEY-DE-007, JOURNEY-DC-007
- JOURNEY-AUD-005, JOURNEY-DA-001, JOURNEY-DEV-006

See [docs/USER_JOURNEYS.md](../../docs/USER_JOURNEYS.md#deferred-journeys-transformation-pipeline).
