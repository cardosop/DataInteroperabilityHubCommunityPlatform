# ADR-DSF-001 — Dataset versioning correctness & audit scope

**Status**: Accepted (Phase 260.0)

## Decision

Canonical dataset versioning stays centralized in `VersionHistoryManager`; scheduled ingestion invokes `create_version(..., is_current=True)` after persisting dataset metadata (`hub/apps/scheduled_ingestion/worker_services.py`).

## Consequences

Single demotion path prevents worker vs API drift; new writers must reuse the manager.

