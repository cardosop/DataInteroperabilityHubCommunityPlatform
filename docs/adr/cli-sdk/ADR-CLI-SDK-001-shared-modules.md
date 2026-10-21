# ADR: Shared Python Modules Between CLI and SDK

**Date:** 2026-05-14
**Phase:** 278.AA.15
**Status:** Accepted
**Author:** Platform Engineering

## Context

Two Python codebases — `cli/datahub_cli/` and `sdk/python/datahub_interoperability/` —
independently duplicated `_mvp_detection.py` (~120 lines of pure functions for detecting
MVP-gated API paths). The files were functionally identical but maintained in two places.
Any change to the gated-prefix logic required coordinated edits in both repos,
creating a drift risk (and drift was observed: the CLI version had an additional
`NON_MVP_PATHS` entry that the SDK lacked).

## Decision

Place shared Python modules at the repository root under `shared/`. Each consumer
(`cli/` and `sdk/python/`) adds the shared directory to its `package_data` in `setup.py`.

### Module naming convention

- `shared/mvp_detection.py` — side-effect-free utility functions (no imports beyond stdlib)
- `shared/python/` — Python packages that may import from each other or from third-party libs

### Consumer integration

Both `cli/setup.py` and `sdk/python/setup.py` declare:

```python
setup(
    packages=find_packages(),
    package_data={"": ["../shared/mvp_detection.py", "../shared/python/*.py"]},
)
```

Imports use the canonical path from the consumer's perspective:
- CLI: `from datahub_cli._mvp_detection import ...` (re-exports shared module)
- SDK: `from datahub_interoperability._mvp_detection import ...` (re-exports shared module)

### Why not a pip package?

A separate `shared/` pip package would add a third wheel to build, version, publish, and
install. For ~200 lines of pure functions, the operational overhead of a package outweighs
the deduplication benefit. If the shared surface grows beyond ~500 lines or gains
third-party dependencies, this decision should be revisited.

## Consequences

- Single source of truth for MVP-gated path detection and error code constants.
- Both `setup.py` files must be updated when a new shared module is added.
- CI must verify that the two consumer copies are byte-identical to the canonical source
  (enforced by `scripts/lint_shared_modules.py`).
- If a consumer needs to diverge (e.g., CLI needs a Click-specific helper), that code
  belongs in the consumer's own module, not in `shared/`.

## Related

- ADR-CLI-SDK-002 — Shared Python packages (`shared/python/`)
- Phase 278.AA.15 — Deduplication of `_mvp_detection.py`
