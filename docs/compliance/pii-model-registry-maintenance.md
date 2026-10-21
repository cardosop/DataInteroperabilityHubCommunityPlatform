# PII model registry maintenance (Phase 232.8.4)

This procedure keeps the **PII holding model catalogue** (`hub.apps.core.pii_registry`) aligned with runtime **erasure** behaviour.

## Owners

- Engineering: update code and migrations when a new tenant-scoped model stores personal data.
- Privacy / DPO: review classification when product scope changes.

## When to update

1. **New model** with `tenant_id` that can hold personal identifiers or subject-linked records.
2. **New field** on an existing registered model that introduces PII categories.
3. **Erasure path change** (soft-delete vs crypto-shred vs anonymise).

## Required code changes

1. Register the model in `hub.apps.core.pii_registry` (or equivalent module used by `registered_model_labels()`).
2. Add or extend a row in `hub.apps.core.pii_erasure_coverage.PII_ERASURE_COVERAGE` describing **mechanism** and **reference** (management command, service task, or documented manual step).
3. Ship an **RLS policy migration** paired with the model (see `CLAUDE.md` / `scripts/lint_rls_policies.py`).
4. Ensure **tenant_context** wraps any worker/signal code touching the model.

## Verification

- CI: `pytest hub/apps/core/tests/test_erasure_pii_catalogue_completeness.py`
- Data-protection review: confirm DSAR / erasure runbooks reference the same mechanism.
