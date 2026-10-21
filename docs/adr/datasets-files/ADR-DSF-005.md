# ADR-DSF-005 — FILES/DATASETS error-code layering

**Status**: Accepted (Phase 260.0)

## Decision

New failure codes land in `docs/api/error-codes.md` before serializers emit them; linted by `scripts/check_error_codes_catalogue.py`.

## Consequences

Adds doc burden; prevents silent client regressions.

