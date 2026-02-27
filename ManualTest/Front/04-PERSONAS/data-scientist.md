# Data Scientist Persona

**Persona**: Data Scientist / ML Engineer  
**Test User**: e2e_test@example.com (DATA_PROVIDER) or e2e_consumer@example.com (DATA_CONSUMER)  
**Source**: [docs/USER_PERSONAS.md](../../docs/USER_PERSONAS.md#persona-9-data-scientist--ml-engineer)

---

## Overview

Uses natural language search, AI schema matching, ML anomaly detection, recommendation engine tuning, and auto-classification. Works with AI/ML capabilities.

---

## Journeys Covered

| Journey | Title | Docs | E2E Spec | Est. |
|---------|-------|------|----------|------|
| JOURNEY-DS-001 | Use Natural Language Search | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ds-001-use-natural-language-search) | `journeys/ds/JOURNEY-DS-001.spec.ts` | 5 min |
| JOURNEY-DS-002 | Use AI Schema Matching | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ds-002-use-ai-schema-matching) | `journeys/ds/JOURNEY-DS-002.spec.ts` | 5 min |
| JOURNEY-DS-003 | Configure ML-Based Anomaly Detection | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ds-003-configure-ml-based-anomaly-detection) | `journeys/ds/JOURNEY-DS-003.spec.ts` | 10 min |
| JOURNEY-DS-004 | Tune Recommendation Engine | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ds-004-tune-recommendation-engine) | `journeys/ds/JOURNEY-DS-004.spec.ts` | 5 min |
| JOURNEY-DS-005 | Review Auto-Classification Results | [USER_JOURNEYS](../../docs/USER_JOURNEYS.md#journey-ds-005-review-auto-classification-results) | `journeys/ds/JOURNEY-DS-005.spec.ts` | 5 min |

**Total Estimated Duration**: ~30 min

---

## Execution Order (Recommended)

1. [ ] **JOURNEY-DS-001** — Use natural language search
2. [ ] **JOURNEY-DS-002** — Use AI schema matching
3. [ ] **JOURNEY-DS-003** — Configure ML-based anomaly detection
4. [ ] **JOURNEY-DS-004** — Tune recommendation engine
5. [ ] **JOURNEY-DS-005** — Review auto-classification results

---

## Key Routes

- `/search`, `/ai/search`
- `/ai/schema-matching`
- `/ml` (ML models, if capability enabled)
- `/dq` (anomaly detection, quality runs)

---

## Prerequisites

- Capabilities: ai.natural-language-search, ai.schema-matching, ml.models (as applicable)

---

## Sign-Off

| Tester | Date | DS Persona Pass |
|--------|------|-----------------|
| | | ☐ |
