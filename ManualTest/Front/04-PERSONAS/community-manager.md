# Community Manager Persona

**Persona**: Community Manager / Data Steward  
**Test User**: e2e_test@example.com (DATA_PROVIDER) or e2e_admin@example.com (TENANT_ADMIN)  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-11-community-manager--data-steward)

---

## Overview

Manages data communities, moderates reviews and ratings, assigns data stewards, and manages activity feeds. Uses social and community features.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-CM-001 | Manage Data Community | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-cm-001-manage-data-community) | `journeys/cm/JOURNEY-CM-001.spec.ts` | 10 min |
| JOURNEY-CM-002 | Moderate Reviews and Ratings | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-cm-002-moderate-reviews-and-ratings) | `journeys/cm/JOURNEY-CM-002.spec.ts` | 5 min |
| JOURNEY-CM-003 | Assign Data Stewards | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-cm-003-assign-data-stewards) | `journeys/cm/JOURNEY-CM-003.spec.ts` | 5 min |
| JOURNEY-CM-004 | Manage Activity Feeds | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-cm-004-manage-activity-feeds) | `journeys/cm/JOURNEY-CM-004.spec.ts` | 10 min |

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

## Prerequisites

- Capability: social.ratings or social.communities
- Community/social features enabled

---

## Sign-Off

| Tester | Date | CM Persona Pass |
|--------|------|-----------------|
| | | ☐ |
