# B-RLS-0.7 Signal `on_commit` Context Audit

Date: 2026-05-05

## Scope

Audit and hardening of deferred signal callbacks so tenant-scoped work scheduled
with `transaction.on_commit(...)` executes inside explicit `tenant_context(...)`.

## Implemented Fixes

- `hub/apps/tenants/signals.py`
  - Added `_with_context(tenant_id, callback, *args, **kwargs)`.
  - Refactored `create_default_roles` deferred callback to run via `_with_context`.
  - Refactored onboarding deferred callbacks (`tenant_admin_assigned`,
    `kyc_submitted`, `subscription_activated`) to run via `_with_context`.

- `hub/apps/contracts/signals.py`
  - Added `_with_context(tenant_id, callback)`.
  - Wrapped deferred lineage-update dispatch callback and contract-tombstone
    callback with `_with_context`.

- `hub/apps/semantic/signals.py`
  - Added `_with_context(tenant_id, callback)`.
  - Wrapped deferred contract/asset semantic callbacks (mapping, snapshot,
    LDN outbound scheduling) with `_with_context`.

- `hub/apps/datasets/signals.py`
  - Added `_with_context(tenant_id, callback)`.
  - Wrapped deferred dataset-tombstone callback with `_with_context`.

- `hub/apps/assets/signals.py`
  - Added `_with_context(tenant_id, callback)`.
  - Wrapped deferred asset-tombstone callback with `_with_context`.

- `hub/apps/transformation/signals.py`
  - Added `_with_context(tenant_id, callback)`.
  - Wrapped deferred pipeline-event publish callback with `_with_context`.

## Audited Files (no change required)

- `hub/apps/marketplace/signals.py` — no `transaction.on_commit(...)` callbacks.
- `hub/apps/notifications/signals.py` — has `on_commit`, but callback only queues
  email tasks (no tenant-table access).
- `hub/apps/integrations/signals.py` — no `transaction.on_commit(...)` callbacks.
- `hub/apps/governance/signals.py` — no `transaction.on_commit(...)` callbacks.
- `hub/apps/mesh/signals.py` — no `transaction.on_commit(...)` callbacks.

## TDD / Validation

- Added tests in `hub/apps/tenants/tests/test_signals.py`:
  - `test_with_context_sets_and_restores_tenant_guc`
  - `test_with_context_inside_on_commit_preserves_callback_writes`

- Regression test run:
  - `hub/apps/tenants/tests/test_signals.py`
  - `hub/apps/assets/tests/test_signals.py`
  - `hub/apps/contracts/tests/test_signals.py`
  - `hub/apps/semantic/tests/test_signals.py`
  - `hub/apps/transformation/tests/test_signals.py`
  - Result: `31 passed`
