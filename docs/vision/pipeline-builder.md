# Pipeline Builder — Product Vision

**Owner:** Product Team | **Date:** 2026-05-20

## Overview

The Pipeline Builder is a visual drag-and-drop editor for constructing multi-step data pipelines that chain ingestion, transformation, DQ checks, compliance scans, and exports into a single ordered execution graph.

## Wireframes (Textual)

```
┌─────────────────────────────────────────────────────┐
│ Pipeline Builder                          [Save] [Run] │
├─────────────────────────────────────────────────────┤
│  ┌──────────┐    ┌──────────────┐    ┌────────┐    │
│  │ Ingest   │───→│ Transform    │───→│ Export │    │
│  │ (S3)     │    │ (dbt model)  │    │ (S3)    │    │
│  └──────────┘    └──────────────┘    └────────┘    │
│       │                                    │        │
│       ├──→ DQ Check (GX)                  │        │
│       └──→ Compliance (GDPR)              │        │
├─────────────────────────────────────────────────────┤
│ Step Config:                                        │
│   Type: [dropdown: Ingest|Transform|DQ|Compliance|Export] │
│   Config: {JSON editor}                             │
│   Dependencies: [multi-select upstream steps]      │
└─────────────────────────────────────────────────────┘
```

## Data Flow

1. **Ingestion** fetches data from source (S3, warehouse, API)
2. **Transformation** runs dbt model against ingested dataset
3. **DQ Check** validates output against quality rules
4. **Compliance** scans for PII / regulatory violations
5. **Export** writes final dataset to destination

## User Stories

- As a Data Engineer, I want to chain ingestion → dbt → DQ → export so I can fully automate my data pipeline
- As a Compliance Officer, I want compliance gates before export so regulated data is blocked
- As a Platform Admin, I want to see pipeline dependency graphs so I understand data lineage

## Technical Constraints

- Pipelines are defined as ordered `PipelineDependency` rows (Phase 285.11)
- Execution respects dependency order via `DependencyAwareExecutor`
- Downstream auto-triggered on upstream completion via `PipelineTriggerEngine`
- Graph preview via `GET /api/v1/workflows/dependencies/preview/`
