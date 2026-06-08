# ADR-DSF-006 — EICAR fixtures + CI antivirus segregation

**Status**: Accepted (Phase 260.0)

## Decision

`tests/fixtures/eicar.txt` stores the standard test string. GitHub-hosted runners MUST NOT run platform AV against the workspace; scanning remains inside isolated service containers.

See `docs/onboarding/datasets-files-feature.md`.

## Consequences

Eliminates flaky CI; relies on engineer discipline.

