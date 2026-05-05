# API Error Codes Catalogue

**Status**: Authoritative — every error code returned by the Hub API MUST appear in this catalogue. CI lint enforces this contract: a PR that introduces a new code in source without a matching catalogue entry fails the merge gate.

**Phase**: 250.0.13 / D250.14
**CI gate**: [scripts/check_error_codes_catalogue.py](../../scripts/check_error_codes_catalogue.py) (invoked from `.github/workflows/ci.yml`)

## Conventions

- **Format**: `SCREAMING_SNAKE_CASE`. Numeric suffix discouraged — use a descriptive verb.
- **Stability**: error codes are part of the public API contract. Renames REQUIRE a 6-month deprecation window per Phase 240.3.B.3 / D250.10 precedent. Rename: add the new code in parallel; emit BOTH; mark old code `Deprecated:` in this catalogue with a `Sunset:` date; remove old code only after the date passes.
- **Localisation**: error codes are NOT localised. The accompanying `message` field MAY be localised; the `code` field MUST stay in English / SCREAMING_SNAKE_CASE.
- **Catalogue ordering**: by category (asset, compliance, dq, …) then alphabetical.

## Format used by the API

```json
{
  "code": "ASSET_FAIL_CLOSED_REJECTED",
  "message": "Compliance gate rejected this asset: <reason>",
  "details": { "compliance_run_id": "...", "rejection_reason": "..." },
  "remediation_url": "https://meshant-internal.example.com/runbooks/asset-fail-closed-rollback"
}
```

`details` and `remediation_url` are optional but recommended; `code` and `message` are mandatory.

---

## Asset (`ASSET_*`)

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ASSET_NOT_FOUND` | 404 | (existing) | Asset id is unknown OR not visible to the requesting tenant. | Verify the asset id; confirm tenant scope; for federated assets verify cross-tenant visibility per ADR-AST-002. |
| `ASSET_FAIL_CLOSED_REJECTED` | 422 | 250.1.A | Compliance OR DQ gate failed; asset NOT created. | Inspect the linked `compliance_run_id` / `dq_run_id` for failure reason. Run [docs/runbooks/asset-fail-closed-rollback.md](../runbooks/asset-fail-closed-rollback.md). |
| `ASSET_WORKFLOW_ROLLED_BACK` | 422 | 250.1.A | Post-persist workflow step failed; saga compensation rolled back the asset. | Inspect audit event with the workflow run id. |
| `ASSET_VERSION_MISMATCH` | 412 | 250.7.B | `If-Match` header version does not match current Asset version. | Refetch asset; reconcile via the 3-way merge UI. |
| `ASSET_IF_MATCH_REQUIRED` | 428 | 250.7.B | `If-Match` header missing on a PATCH that requires it (post-soak). | Send `If-Match: <current-version>`. |
| `ASSET_VISIBILITY_FIELD_REMOVED` | 400 | 250.3.C | Caller PATCH'd `visibility` field after Phase 2 deprecation. | Use `status` instead per ADR-AST-003. |
| `ASSET_CREATION_DISABLED` | 403 | 250.6.A | Tenant has `asset_creation_enabled=False`. | Tenant admin enables via `/settings/billing/enable-asset-creation` after onboarding completion. |
| `ASSET_SEMANTIC_DEGRADED` | 200 (soft) | 250.7.A | Asset is active but semantic indexing failed; banner shown. | User clicks Retry on the asset detail page. |
| `ASSET_LIVE_QUERY_DISABLED_FOR_TENANT` | 403 | 275.A | Tenant `warehouse_connectivity_enabled=False`; LIVE_QUERY assets are not allowed. | Tenant admin enables via warehouse-connectivity settings. |
| `ASSET_VISIBILITY_WRITE_DEPRECATED` | 200 (soft) | 250.3.B | Phase 1 deprecation: writes to `visibility` field route to `status` with warning. | Migrate to writing `status` directly. |

## Federated import (`FEDERATED_*`)

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `FEDERATED_IMPORT_DISABLED` | 403 | 250.5.A | Tenant `federated_import_enabled=False`. | DPO + Legal sign-off then admin flag flip per ADR-AST-002. |
| `FEDERATED_CROSS_TENANT_DENIED` | 404 | 250.5.A | Cross-tenant read on federated asset; deliberately returns 404 not 403 (existence-leak protection). | The asset is invisible to the requesting tenant; this is by design. |
| `FEDERATED_SOURCE_TENANT_DELETED` | 410 Gone | 250.5.A / D250.16 | Source tenant deleted; consumer-side copy is in 90-day grace. | Tenant exports the data within 90 days. |
| `EXTERNAL_RESOURCE_REFERENCE_SSRF_BLOCKED` | 400 | 250.5.B.1 | URL points to RFC1918 / loopback / link-local / IMDS. | Use a public URL. |

## Compliance (`COMPLIANCE_*`)

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `COMPLIANCE_DEGRADED_BLOCKED` | 503 | 250.1.A / D250.9 | Compliance circuit-breaker OPEN; tenant lacks `allow_intake_on_compliance_degraded=True` opt-in. | Wait for circuit recovery OR enable opt-in for permissive mode. Returned with `Retry-After` header. |
| `COMPLIANCE_FAIL_CLOSED_DISABLED` | 200 (soft warn) | 250.1.A / D250.12 | Existing tenant on the 30-day soak window — fail-closed not yet enforced. | Tenant flips `compliance_fail_closed_enabled=True` during the soak. |

## Idempotency (`IDEMPOTENCY_*`)

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `IDEMPOTENCY_KEY_BODY_MISMATCH` | 409 | 250.1.D / ADR-AST-005 | Same `Idempotency-Key`, different body. | Use a fresh key OR send the original body unchanged. |
| `IDEMPOTENCY_KEY_REQUIRED` | 428 | 250.1.D | `Idempotency-Key` header missing on `POST /assets/data-first/`. | Send the header per ADR-AST-005. |
| `IDEMPOTENCY_KEY_FORMAT_INVALID` | 400 | 250.1.D | Key does not match `<tenant_uuid>:<sha256(body)>` shape. | Use `client.idempotency_key_for(tenant_id, body)` SDK helper. |

## Workflow (`WORKFLOW_*`)

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `WORKFLOW_RUN_NOT_FOUND` | 404 | 250.1.A | The polled workflow run id is unknown OR cross-tenant. | Verify the id from the original async response. |
| `WORKFLOW_VERSION_MIGRATION_REQUIRED` | 410 Gone | 250.0.12 / D250.7 | In-flight run on a workflow version past its 14-day soak window. | Re-submit the request; the new workflow version will pick it up. |
| `WORKFLOW_DEFINITION_NOT_FOUND` | 404 | 250.0.12 | Requested explicit workflow `version=` does not exist. | Use the active version (omit `version=`). |

## Version compatibility (`VERSION_*`)

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `CROSS_SERVICE_VERSION_MISMATCH` | 503 (startup) | 250.0.14 / D250.15 | Hub started against a microservice version below the required minimum. | Upgrade dq-service / compliance-service to the required version per `HUB_REQUIRED_*_SERVICE_VERSION`. |

## Generic (`*`)

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `PERMISSION_DENIED` | 403 | (existing) | Caller's role/ACL does not permit the operation. | Check role; for connection-level ACL see ADR-AST-004 (warehouse) / role-based docs (asset). |
| `VALIDATION_ERROR` | 400 | (existing) | Generic validator-failed. `details` enumerates field-level errors. | Fix the request body. |
| `RATE_LIMIT_EXCEEDED` | 429 | (existing) | DRF throttle scope exceeded. | Honour `Retry-After`. |

---

## CI gate contract

The CI lint at [scripts/check_error_codes_catalogue.py](../../scripts/check_error_codes_catalogue.py) (Phase 250.0.13 deliverable) MUST:

1. Scan `hub/apps/**/*.py` for `"code": "<CODE_NAME>"` literals + `code=ErrorCode.<NAME>` references.
2. Cross-reference against this catalogue's `| CODE_NAME |` table cells.
3. Fail the PR if any code is missing from the catalogue (inferred → not documented = breakage of D250.14 contract).
4. Allow exemptions via a `# pragma: error-code-internal` line comment (for codes that are explicitly internal-only and never emitted on the API surface).

The lint runs in `.github/workflows/ci.yml` as a path-filtered job (`error-codes-catalogue-check`) on changes to `hub/apps/**/*.py` OR this file.

## Adding a new error code

1. Pick a code per the conventions above.
2. Add the row to the appropriate category table here (with HTTP status, phase, meaning, remediation).
3. Use it in code: `return Response({"code": "MY_NEW_CODE", "message": "..."}, status=400)`.
4. CI gate validates the code appears in this catalogue. Same-PR.

## Renaming or removing an error code

1. Add the new code per the steps above.
2. Have BOTH codes emit on the same condition for the deprecation window (default 6 months per D250.10 precedent).
3. Mark the old code's row with `Deprecated:` prefix + `Sunset: YYYY-MM-DD` in the meaning column.
4. After sunset, remove the old code from this catalogue AND from source. CI gate enforces removal.

## Audit record

Phase 250.0.13 lands the initial schema covering every code currently emitted by Phase 240/250 code paths plus the planned Phase 250 closeout codes. Future phases extend per the "Adding a new error code" procedure.
