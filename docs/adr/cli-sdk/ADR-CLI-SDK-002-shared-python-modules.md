# ADR: Shared Python Error Code Constants (`shared/python/`)

**Date:** 2026-05-14
**Phase:** 279.J.2
**Status:** Accepted
**Author:** Platform Engineering

## Context

Both the CLI and SDK handle structured API error codes (e.g., `COMPLIANCE_THRESHOLD_EXCEEDED`,
`ABAC_POLICY_DENIED`, `SEMANTIC_FEATURE_DISABLED`). Before this ADR, error codes were
hardcoded as bare strings in each consumer:

```python
# CLI — cli/datahub_cli/commands/compliance.py
if error.get("code") == "COMPLIANCE_THRESHOLD_EXCEEDED":
    ...

# SDK — sdk/python/datahub_interoperability/assets.py
if error_code == "COMPLIANCE_THRESHOLD_EXCEEDED":
    ...
```

This caused:
- **Typos**: `"COMPLIANCE_TRESHOLD_EXCEEDED"` (missing 'h') silently failed to match.
- **Drift**: New error codes added to the backend (`docs/api/error-codes.md`) were not
  consistently reflected in either consumer.
- **Discoverability**: IDE autocomplete couldn't help developers find the right error code.

## Decision

Create `shared/python/datahub_error_codes.py` as a single source of truth for all
structured API error codes. Both CLI and SDK import from it. The module is placed
under `shared/python/` (not bare `shared/`) to avoid conflation with the frontend
TypeScript `shared/` directory.

### Structure

```python
# Compliance & Governance
COMPLIANCE_THRESHOLD_EXCEEDED = "COMPLIANCE_THRESHOLD_EXCEEDED"
COMPLIANCE_RUN_REQUIRED = "COMPLIANCE_RUN_REQUIRED"
ABAC_POLICY_DENIED = "ABAC_POLICY_DENIED"

# Semantic
SEMANTIC_FEATURE_DISABLED = "SEMANTIC_FEATURE_DISABLED"

# ... grouped by domain
```

Constants are `UPPER_SNAKE_CASE` matching the backend's error code strings exactly.
Grouped by API domain with section headers for readability.

### Consumer integration

```python
# CLI
from datahub_error_codes import COMPLIANCE_THRESHOLD_EXCEEDED

# SDK
from datahub_error_codes import COMPLIANCE_THRESHOLD_EXCEEDED
```

### Why not an Enum?

String constants (not `enum.Enum`) are intentionally used because:
1. The backend may add error codes without a coordinated CLI/SDK release;
   a bare string constant degrades gracefully (no `ValueError` on unknown member).
2. CLI `--format json` output embeds the raw API error code string; an Enum would
   require `.value` access everywhere or a custom JSON encoder.
3. String constants are importable at module level without runtime cost.

## Consequences

- Single source of truth for all structured API error codes.
- New backend error codes must be added to `shared/python/datahub_error_codes.py`
  for IDE autocomplete to pick them up (enforced by `scripts/lint_error_codes.py`).
- Existing hardcoded strings in CLI and SDK are migrated incrementally — new modules
  use the constants from day one; existing modules are converted as they're touched.
- `shared/python/` uses its own subdirectory to avoid namespace collision with
  the frontend TypeScript `shared/` directory.

## Related

- ADR-CLI-SDK-001 — Shared modules convention (`shared/` vs `shared/python/`)
- `docs/api/error-codes.md` — Canonical error code reference
- Phase 279.J.2 — Error code constants implementation
