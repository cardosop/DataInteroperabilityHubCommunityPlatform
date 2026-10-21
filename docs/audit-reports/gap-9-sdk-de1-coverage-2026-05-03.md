# Gap 9 verification — SDK DE-1 (Data Engineer 1) journey coverage

**Audit task**: 250.0.8
**Audit date**: 2026-05-03
**Auditor**: Phase 250.0 Asset-Creation-Hardening pre-flight
**Status**: ⚠️ **PARTIAL — capability spec covers personas + journeys; explicit DE-1 polling sequence requires Phase 250.4 follow-up**

## Original gap statement

Phase 250 source plan flagged Gap 9: "the SDK programmatic asset-creation flow may not match the documented DE-1 (Data Engineer 1) sequence — specifically the polling pattern for async workflow status (`POST /workflows/asset-creation/runs/` → `GET /workflows/runs/{run_id}/` until terminal state)."

DE-1 is one of the 13 D145 personas (`data_engineer`) referenced in [openspec/changes/preprod01/specs/cli-sdk-mvp-coverage-parity/spec.md](../../openspec/changes/preprod01/specs/cli-sdk-mvp-coverage-parity/spec.md).

## Verification scope

Repository-on-disk inspection — there is NO standalone `cli-sdk` repo at `/home/ph/Desktop/cli-sdk/` or similar. The SDK + CLI live as capability specs under preprod01 (`cli-sdk-mvp-awareness`, `cli-sdk-mvp-coverage-parity`, `cli-sdk-hardening`). DE-1 polling coverage is therefore assessed against the spec content, not against running code.

## Findings

1. **Persona registry**: `data_engineer` is one of 13 personas declared in [openspec/changes/preprod01/specs/cli-sdk-mvp-coverage-parity/spec.md:5](../../openspec/changes/preprod01/specs/cli-sdk-mvp-coverage-parity/spec.md#L5). ✓ present.
2. **Journey tests** for the persona: spec lists 9 P0 use-case journeys at line 23 — `auth_lifecycle`, `signup_onboarding`, `invitation_accept`, `sso_login`, `tenant_switching`, `cross_tenant_isolation`, `gdpr_lifecycle`, `billing_lifecycle`, `marketplace_order`. **Asset-creation journey is NOT in the P0 list.** → gap.
3. **Dimension tests** at line 65 include `dim_idempotency.py`, `dim_pagination.py`, `dim_webhook_roundtrip.py` — useful for the polling pattern but not a dedicated DE-1 asset-creation dimension.
4. **Polling pattern**: no explicit "poll workflow status until terminal" test in the spec. Phase 250's workflow re-sequence (`250.1.A`) introduces async-by-default semantics; the SDK MUST adapt.

## Conclusion

The SDK has the personas + journey infrastructure but lacks an **asset-creation programmatic-flow journey** that exercises the DE-1 polling sequence. This is **NOT a regression** (no prior coverage existed) but **IS a gap relative to Phase 250's async-by-default workflow**.

## Recommended remediation

Phase 250.4 (already scheduled in tasks.md as "SDK programmatic flow (P1, depends on 250.0.8 verification)") owns the remediation. The audit promotes the remediation from "verify and assess" to "implement" with the following deliverable:

- **NEW journey file** `sdk/python/tests/use_cases/asset_creation_data_engineer.py` (mirror `cli/tests/use_cases/asset_creation_data_engineer.py`) parametrized over `data_engineer` persona, exercising the canonical sequence:
  1. `client.files.upload(...)` → returns `file_id`
  2. `client.assets.create_data_first(file_id, contract_metadata, idempotency_key=...)` → returns `workflow_run_id` (NOT a fully-formed asset)
  3. Poll `client.workflows.get_run(workflow_run_id)` until `state ∈ {COMPLETED, FAILED}`; max wait 60s; backoff 1s → 5s → 10s.
  4. On `COMPLETED`, fetch the resulting `asset_id` from the run's `output.asset_id` field.
  5. On `FAILED`, surface the structured error to the caller (must include `error_code`, `error_message`, `details_json`).
- **NEW SDK method** `client.workflows.poll_until_terminal(workflow_run_id, timeout_s, backoff_initial_s, backoff_max_s)` with retry-after-aware backoff (reads `Retry-After` header).
- **Dimension test** `dim_workflow_polling.py` covering: terminal-state convergence; timeout; transient-error retry; idempotency-key replay produces the same workflow run.

## Closeout

Phase 250 tasks.md marks Phase 250.4's deliverables as: "1 NEW journey file + 1 NEW SDK polling helper + 1 NEW dimension test, scoped to the DE-1 sequence; tracked in this audit report."
