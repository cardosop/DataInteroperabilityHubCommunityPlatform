# Data Analyst Persona

**Persona**: Data Analyst  
**Test User**: e2e_consumer@example.com / TestPass123  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-10-data-analyst)

---

## Overview

Wrangles data interactively, queries virtual datasets, and executes federated queries. Uses virtualization and data exploration tools.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-DA-001 | Create Transformation Pipeline | **Deferred** | — | — |
| JOURNEY-DA-002 | Wrangle Data Interactively | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-da-002-wrangle-data-interactively) | `journeys/da/JOURNEY-DA-002.spec.ts` | 10 min |
| JOURNEY-DA-003 | Query Virtual Dataset | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-da-003-query-virtual-dataset) | `journeys/da/JOURNEY-DA-003.spec.ts` | 10 min |
| JOURNEY-DA-004 | Execute Federated Query | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-da-004-execute-federated-query) | `journeys/da/JOURNEY-DA-004.spec.ts` | 10 min |

**Total Estimated Duration**: ~30 min (excluding deferred)

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DA-002** — Wrangle data interactively
2. [ ] **JOURNEY-DA-003** — Query virtual dataset
3. [ ] **JOURNEY-DA-004** — Execute federated query

---

## Key Routes

- `/virtualization`, `/virtualization/:id`
- `/search` (data exploration)

---

## Prerequisites

- Virtualization capability enabled
- At least one virtual dataset or federated source

---

## Sign-Off

| Tester | Date | DA Persona Pass |
|--------|------|-----------------|
| | | ☐ |
