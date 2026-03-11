# Community Manager Persona

**Persona**: Community Manager / Data Steward  
**Test User**: e2e_test@example.com (DATA_PROVIDER) or e2e_admin@example.com (TENANT_ADMIN)  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-11-community-manager--data-steward)

---

## Overview

Manages data communities, moderates reviews and ratings, assigns data stewards, and manages activity feeds. Uses social and community features.

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. **Note**: Social/community capability must be enabled. Document "Capability not available" if skipped.

---

## Journeys Covered

| Journey | Title | Step-by-Step Script | E2E Spec | Est. |
|---------|-------|---------------------|----------|------|
| JOURNEY-CM-001 | Manage Data Community | [cm/JOURNEY-CM-001.md](../03-USER-JOURNEYS/cm/JOURNEY-CM-001.md) | `journeys/cm/JOURNEY-CM-001.spec.ts` | 10 min |
| JOURNEY-CM-002 | Moderate Reviews and Ratings | [cm/JOURNEY-CM-002.md](../03-USER-JOURNEYS/cm/JOURNEY-CM-002.md) | `journeys/cm/JOURNEY-CM-002.spec.ts` | 5 min |
| JOURNEY-CM-003 | Assign Data Stewards | [cm/JOURNEY-CM-003.md](../03-USER-JOURNEYS/cm/JOURNEY-CM-003.md) | `journeys/cm/JOURNEY-CM-003.spec.ts` | 5 min |
| JOURNEY-CM-004 | Manage Activity Feeds | [cm/JOURNEY-CM-004.md](../03-USER-JOURNEYS/cm/JOURNEY-CM-004.md) | `journeys/cm/JOURNEY-CM-004.spec.ts` | 10 min |

**Total Estimated Duration**: ~30 min

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-CM-001** — Manage data community
2. [ ] **JOURNEY-CM-002** — Moderate reviews and ratings
3. [ ] **JOURNEY-CM-003** — Assign data stewards
4. [ ] **JOURNEY-CM-004** — Manage activity feeds

---

## Key Routes

- `/social` (if capability enabled)

---

---

## Sign-Off

| Tester | Date | CM Persona Pass |
|--------|------|-----------------|
| | | ☐ |
