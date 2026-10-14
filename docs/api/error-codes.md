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
| `ASSET_VERSION_MISMATCH` | 412 | 250.7.B | Asset version precondition failed. | Refresh the asset and retry. |
| `DATABRICKS_HOST_NOT_ALLOWED` | 400 | add-databricks-control-plane P0 | Host is not a Databricks workspace host (family allowlist). | Use the workspace's `*.cloud.databricks.com` (or regional/gov variant) hostname. |
| `SSRF_PROTECTION_TRIGGERED` | 400 | add-databricks-control-plane P0 | Host failed the canonical SSRFGuard checks (private/reserved IP or scheme). | Use a public, family-valid workspace hostname. |
| `SSRF_DNS_REBINDING` | 502 | add-databricks-control-plane P0 | Dispatch-time re-resolution found the host pointing at blocked space. | Re-register the workspace after the DNS record is corrected. |
| `DATA_RESIDENCY_MISMATCH` | 400 | add-databricks-control-plane P0 | Workspace region is outside the tenant's data-residency allowlist. | Choose a workspace region within the tenant's residency regime. |
| `DATABRICKS_AUTH_FAILED` | 502 | add-databricks-control-plane P0 | Workspace rejected the stored credentials (masked response). | Rotate the workspace credential and re-run the connection test. |
| `DATABRICKS_API_ERROR` | 502 | add-databricks-control-plane P0 | The Databricks client's DEFAULT classified rejection — no more specific `DATABRICKS_*` classification applies. | Read the surfaced message; the workspace's own status code rides through. |
| `DATABRICKS_WORKSPACE_HAS_DEPENDENTS` | 409 | add-databricks-control-plane P0 | Workspace has dependent objects (credentials). | Delete the dependents first, or soft-disable the workspace. |
| `DATABRICKS_CONTROL_PLANE_DISABLED` | 403 | add-databricks-control-plane P0 | The tenant's `databricks_control_plane_enabled` flag is off. | Ask a tenant admin to enable the Databricks control plane. |
| `DATABRICKS_WORKSPACES_DISABLED` | 403 | add-databricks-control-plane P0 | Emergency kill switch flipped for the tenant. | Contact the platform administrator to re-enable the control plane. |
| `WAREHOUSE_TYPE_DISABLED_FOR_TENANT` | 403 | add-databricks-control-plane P0 | The Databricks warehouse type is not enabled for the tenant (`warehouse_databricks_enabled`). | Ask a tenant admin to enable the Databricks warehouse connector. |
| `DATABRICKS_WORKSPACE_NAME_CONFLICT` | 400 | add-databricks-control-plane P0 | A workspace with this name already exists for the tenant. | Use a different name, or rename/delete the existing workspace first. |
| `DATABRICKS_CIRCUIT_OPEN` | 503 | add-databricks-control-plane P0 | Circuit breaker OPEN — the workspace call failed fast without a network attempt. | Wait for the cooldown, then retry. |
| `DATABRICKS_CONNECTION_ERROR` | 502 | add-databricks-control-plane P0 | Transport-level failure (DNS, refused, timeout) after retries. | Verify workspace connectivity and DNS resolution. |
| `DATABRICKS_RATE_LIMITED` | 429 | add-databricks-control-plane P0 | Databricks rate limit exceeded after the retry budget. | Back off and retry later. |
| `DATABRICKS_SERVER_ERROR` | 502 | add-databricks-control-plane P0 | Databricks 5xx after the retry budget. | Check the Databricks workspace status; retry later. |
| `DATABRICKS_STATEMENT_CANCELED` | 409 | add-databricks-control-plane P0 | SQL statement terminal state CANCELED. | Re-submit the statement if execution is still wanted. |
| `DATABRICKS_STATEMENT_FAILED` | 422 | add-databricks-control-plane P0 | SQL statement reached the terminal FAILED state in the workspace. | Read the statement's error message; fix and re-submit. |
| `DATABRICKS_STATEMENT_TIMEOUT` | 504 | add-databricks-control-plane P0 | Statement never reached a terminal state within the poll budget. | Increase the poll budget or tune the statement. |
| `DATABRICKS_OBO_REFRESH_FAILED` | 502 | add-databricks-control-plane P0b | OBO bearer failed: no bound token for the workspace (fail-closed), the refresh exchange failed, or the refreshed token was rejected again. | Sign in with Databricks again; if it persists, re-register the Hub app connection. |
| `DATABRICKS_DDL_EXECUTION_FAILED` | 400 | add-databricks-uc-write P2 | The UCChangeExecutor failed locally: an unsupported (type, action) combination, a missing required SQL-fallback option, or a failed SQL statement. | Correct the DDL payload (or its required options) and re-request. |
| `DATABRICKS_DDL_DENYLISTED` | 403 | add-databricks-uc-write P2 | A destructive DDL request (the DROP family) was refused because the tenant's `databricks_uc_destructive_ddl_enabled` flag is off — the D3 denylist is the outermost guard. | Enable the destructive-DDL tenant flag (DRAFT) after the approver chain review; the request still requires approval. |
| `DATABRICKS_DDL_INVALID_IDENTIFIER` | 400 | add-databricks-uc-write P2 | A UC identifier failed the per-level regex validation (or the payload carried the wrong number of identifier parts) — request-time and execute-time guards. | Correct the identifier to the UC naming rules (leading letter/underscore, letters/digits/underscores, ≤255 chars; model aliases also allow hyphens). |
| `DATABRICKS_DDL_APPROVAL_REQUIRED` | 403 | add-databricks-uc-write P2 | Execution of a UC change request was refused because the request is not in APPROVED state — the `databricks.uc.change.execute` chain's stage check failed. | Submit the request for approval and wait for the final approver before executing. |
| `DATABRICKS_GRANT_UNSUPPORTED` | 400 | add-databricks-uc-write P2 | The grants bridge refused a plan: an OWN/OWNERSHIP privilege (the DPO owns — the bridge never issues OWN) or a grant the UC surface cannot represent. | Remove the ownership privilege from the policy and re-plan; the request never reaches Databricks. |
| `DATABRICKS_HYBRID_IDENTITY_VIOLATION` | 403 | add-databricks-control-plane P0b | D12 enforcement: a background purpose ran without the workspace M2M credential / approver-chain linkage, or an unclassified purpose was requested. | Route through the identity decision point with the required credential + approval linkage. |
| `DATABRICKS_PRINCIPAL_ALREADY_BOUND` | 409 | add-databricks-control-plane P0b | The Databricks principal is already bound to a different Hub account on this workspace. | The account owner must unbind (revoke) the existing binding first. |
| `DATABRICKS_SSO_UNAVAILABLE` | 400 | add-databricks-control-plane P0b | Sign-in with Databricks was attempted on a GCP workspace — U2M is unsupported there. | Use PAT/M2M credentials for this workspace instead of SSO. |
| `DATABRICKS_WAREHOUSE_STATE_ERROR` | 409 | add-databricks-sql-warehouses P3 | The compute client could not reason about a warehouse's lifecycle state: the compute API reported a missing or unknown state, or the requested action is impossible in the current state (e.g. START on a DELETING warehouse). | Wait for the warehouse to leave the transitional state (or refresh the mirror), then retry. |
| `DATABRICKS_JOB_TASK_FORBIDDEN` | 403 | add-databricks-jobs P4 | The jobs client's task allowlist or cluster-policy guard refused a job definition BEFORE any jobs API call: a task outside the allowlist (Spark SQL / notebook / SQL warehouse; Python flag-gated), an ambiguous/unknown/malformed task shape, or a job cluster without a cluster policy id. | Use an allowlisted task kind; enable `databricks_jobs_python_tasks_enabled` for Python tasks; attach a cluster policy to every job cluster. |
| `DELTA_SHARE_SNAPSHOT_FAILED` | 500 | add-delta-sharing-server P5 | The snapshot job (task 5.4) failed: the source read, the Parquet/delta-log materialization, or the snapshot stamp did not complete — no snapshot row is served. | Inspect the Hub Job's error_message for the classified cause; the refresh path retries on the next request. |
| `DATABRICKS_DELTA_SHARE_QUERY_UNAVAILABLE` | 400 | add-delta-sharing-server P5 | The JSON-mode query endpoint (task 5.3) refused before any connector call: the table ref failed the identifier guard, or the asset's warehouse connection vanished after listing. | Use the table name the catalog listed; re-check the asset's warehouse connection. |
| `DATABRICKS_SSO_DISABLED` | 403 | add-databricks-control-plane P0b | The tenant's `databricks_sso_enabled` flag (or its kill switch) is off. | Ask a tenant admin to enable Sign-in with Databricks. |
| `DATABRICKS_SSO_STATE_MISMATCH` | 400 | add-databricks-control-plane P0b | The SSO callback's signed state was missing, invalid, expired, reused, or bound to another tenant/IP class. | Restart the sign-in flow from the beginning. |
| `DATABRICKS_OBO_DISABLED` | 403 | add-databricks-control-plane P0b | The tenant's `databricks_obo_enabled` flag (or its kill switch) is off. | Ask a tenant admin to enable On-Behalf-Of execution. |
| `DATABRICKS_CLIENT_SECRET_REQUIRED` | 400 | add-databricks-control-plane P0 | OAuth M2M credential config lacks client_id/client_secret. | Re-issue the credential with a client secret. |
| `DATABRICKS_WAREHOUSE_TIER_FORBIDDEN` | 403 | add-databricks-sql-warehouses P3 | The requested warehouse size (or serverless) is outside the tenant's plan-tier allowlist (`databricks.warehouse.create` chain, tier gate — refused before any compute call). | Request a size the plan allows, or upgrade the tenant's plan. |
| `DATABRICKS_WAREHOUSE_QUOTA_EXCEEDED` | 403 | add-databricks-sql-warehouses P3 | The tenant is at its `max_databricks_warehouses` plan cap (FREE=2, PRO=10, ENTERPRISE=unlimited). | Stop or delete an existing warehouse, or upgrade the tenant's plan. |
| `DATABRICKS_WAREHOUSE_INVALID_CONFIG` | 400 | add-databricks-sql-warehouses P3 | The create request is malformed: no name, a missing/unknown classic size, a serverless+size contradiction, or a bad auto-stop window. | Correct the payload (name, size XOR serverless, non-negative integer auto_stop_mins). |
| `DATABRICKS_WAREHOUSE_POOL_EXHAUSTED` | 429 | add-databricks-sql-warehouses P3 | The tenant's SQL-warehouse connection pool is at its per-tenant borrow bound (20 by default) — other tenants are unaffected (per-tenant semaphore). | Release an outstanding borrow and retry, or raise the tenant's pool bound. |
| `DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH` | 500 | add-databricks-sql-warehouses P3 | The pool's hand-out re-check caught a tenant mismatch — a pooled connection (or a factory result) carries a different tenant than the borrow request. The connection is closed, never served. | A server-side defect: inspect the pool registry and the caller's factory; report with the audit trail. |
| `WAREHOUSE_TABLE_NOT_FOUND` | 404 | warehouses | Table not found in warehouse. | Verify the table name/catalog/schema; check the connection points at the right warehouse. |
| `WAREHOUSE_CONNECTION_FAILED` | 502 | warehouses | Warehouse connection could not be established. | Verify the connection config and network path; check the workspace status. |
| `WAREHOUSE_CONNECTION_REQUIRED` | 409 | wire-databricks-dlt-movement P6 | A movement run has no warehouse connection (or the connection stores no credential config) — the real query runner fails closed before any connector work. | Attach a configured warehouse connection to the source asset; never a silently empty read. |
| `WAREHOUSE_CREDENTIAL_EXPIRED` | 502 | warehouses | Warehouse credentials have expired. | Rotate the credential in the control plane and re-derive the connection. |
| `DLT_CREDENTIAL_NOT_RESOLVED` | 409 | wire-databricks-dlt-movement P6 | The Databricks export path has no scoped write credential material for the UC staging target (no PAT token resolved; an M2M-shaped config awaits the 6.6 connection-backed resolver). The pipeline refuses to run without one. | Attach a `credential_ref` that resolves to a token, or wait for the `WarehouseConnection` resolver; never a credential-less UC write. |
| `DLT_CREDENTIAL_SCOPE_VIOLATION` | 403 | wire-databricks-dlt-movement P6 | A scoped write credential was used for a target outside its bound staging target (`catalog.schema.volume`). | Re-bind the credential to the correct staging target; the scope check fails before any work runs. |
| `DATABRICKS_SOURCE_INCREMENTAL_ERROR` | 500 | wire-databricks-dlt-movement P6 | A DATABRICKS_SOURCE ingestion carries an invalid table ref or cursor field — the incremental SQL builder's identifier guard refused it fail-closed before any warehouse work. | Fix the ingestion's `source_config` (`table` / `cursor_field` are identifiers only — never SQL fragments). |
| `DLT_PIPELINE_SCOPE_VIOLATION` | 403 | wire-databricks-dlt-movement P6 | The read-only-guard bypass scope was entered without an executor-minted token (or nested inside an active scope). | The bypass exists ONLY inside the pipeline executor — never enter it from the API boundary. |
| `WAREHOUSE_COST_BUDGET_EXCEEDED` | 429 | add-databricks-cost-guardrails P7 | The tenant's rolling-hour cost window reached the BLOCK-mode budget — the query failed closed BEFORE any warehouse work. | Raise the budget or wait for the rolling window to drain; the 429 carries the audit row, never a warehouse query. |
| `WAREHOUSE_COST_BUDGET_NEAR_EXCEEDED` | 200 | add-databricks-cost-guardrails P7 | The ALERT-mode budget was reached (or the window cache was unavailable and the ledger fallback ran) — the query proceeded and the near-exceeded alert fired. | Review the tenant's budget; the alert path never blocks the movement. |
| `DATABRICKS_WORKSPACE_PROVISIONING_DISABLED` | 403 | add-databricks-account-plane P8 | The target tenant's `databricks_workspace_provisioning_enabled` flag is off — provisioning refused with ZERO network calls (registration-first stays the default). | A tenant admin enables the flag (and a DPO/Legal signoff is recorded on the account row) before any provisioning. |
| `SOURCE_DOWNLOAD_FAILED` | 500 | oss-release-remediation W3.8 | The dlt ingestion spine could not download a source file's content for catalog-record creation (the connector failed or returned a non-SUCCESS status). The file counts as failed and the run retries it. | Fix the source connector credentials/config; the processed keys stay unmarked so the next run retries the whole batch. |
| `CATALOG_RECORD_CREATION_FAILED` | 500 | oss-release-remediation W3.8 | The dlt spine's catalog-record creation for an ingested file failed (plan limits, schema inference rejection, storage outage, …). The file counts as failed and the run retries it. | Inspect the run's error_message for the classified cause; the per-source-key idempotency guard keeps the retry duplicate-free. |
| `CATALOG_FILE_NAME_COLLISION` | 400 | oss-release-remediation W3.8 | An ingested file's basename collides with an existing ACTIVE file for the tenant (the unique-active-name constraint) — the File/Dataset creation is refused loudly instead of leaking an IntegrityError. | Rename the source file or retire the existing catalog entry; never a silent skip. |
| `CONTRACT_VERSION_CONFLICT` | 409 | oss-release-remediation W4.4 | A contract version for the asset was allocated twice concurrently — the `unique_contract_version_per_asset` constraint fired and the deterministic translation answered 409 instead of a raw 500. | Retry the request — the locked allocation serializes concurrent creates per asset. |
| `EMPTY_FILE` | 400 | oss-release-remediation W3.8 | The shared catalog-record core refused a zero-byte file payload before creating any File/Dataset row. | Fix the source file; an empty payload never becomes a catalog row. |
| `DATABRICKS_PROVISIONING_SIGNOFF_MISSING` | 403 | add-databricks-account-plane P8 | The account row carries no COMPLETE DPO/Legal signoff (by + at + evidence URL) — provisioning refused with ZERO network calls. | Record the signoff on the account row with its evidence URL before any provisioning. |
| `DATABRICKS_ACCOUNT_ALREADY_LINKED` | 409 | add-databricks-account-plane P8 | The Databricks account id is already linked (the platform table's unique constraint — a duplicate link is refused, never re-linked). | Reuse the existing linked account; a re-link requires deleting the existing row first. |
| `DATABRICKS_DLT_SPEC_UNMAPPABLE` | 400 | add-databricks-dlt-pipelines P10 | The Hub-config → DLT-spec mapping compiler refused a config bit it cannot represent in a DLT spec (a key outside the mappable set, a wrong source/destination type, a missing target, an unmappable ODCS rule) — the refusal names the bit; a spec with the setting silently absent is never emitted. | Correct the config (or the contract rule) to the mappable set and recompile. |
| `DATABRICKS_DLT_PIPELINES_DISABLED` | 403 | add-databricks-dlt-pipelines P10 | The tenant's `databricks_dlt_pipelines_enabled` flag is off (design D7) — the DLT management surface (the U5 page + the `dlt` CLI) is inert. | A tenant admin enables the flag (default-off for new AND existing tenants). |
| `DATABRICKS_DLT_UPDATE_CONFLICT` | 409 | add-databricks-dlt-pipelines P10 | A second update start while one is active (a non-terminal update on the mirror) — the fail-fast conflict gate refused with ZERO Pipelines API calls (design D4; the API's own one-active-update rejection is the authoritative backstop). | Wait for the active update to reach a terminal state, then retry. |
| `DATABRICKS_ML_ASSETS_DISABLED` | 403 | add-databricks-ml-assets P12 | The tenant's `databricks_ml_assets_enabled` flag is off (design D5) — the ML-assets surface (models/versions/aliases/feature tables + the serving/vector endpoints) is inert and the refusal made ZERO workspace API calls. | A tenant admin enables the flag (default-off for new AND existing tenants). |
| `DATABRICKS_UC_OBJECT_NOT_FOUND` | 404 | add-databricks-ml-assets P12 | An ML-asset operation targeted a Unity Catalog object the mirror does not know (a model/table row missing from the workspace's chain) OR the workspace's API reported 404 — the UC-DB-019 error table's classified code. | Register/sync the object first (the P1 mirror sync refreshes the estate), then retry. |
| `DATABRICKS_ML_INVALID_FULL_NAME` | 400 | add-databricks-ml-assets P12 | The model-register payload's `full_name` is missing or not the three-part `catalog.schema.name` shape — refused with ZERO workspace API calls. | Provide the three-part full name of the target catalog/schema/model. |
| `DATABRICKS_ML_INVALID_CONFIG` | 400 | add-databricks-ml-assets P12 | A serving/vector create or version-log payload is malformed (a missing/blank name, a non-object config, a missing source, or a non-integer version_num) — refused with ZERO workspace API calls. | Fix the payload and resubmit. |
| `DATABRICKS_DLT_SETTING_FORBIDDEN` | 400 | add-databricks-dlt-pipelines P10 | The `databricks.dlt.create` chain refused a pipeline setting outside the allowlist (or a malformed settings envelope) — classified with the key named, ZERO Pipelines API calls. | Remove the unallowlisted setting (or fix the envelope) and resubmit. |
| `DATABRICKS_EXECUTION_TARGET_INVALID` | 400 | run-transformation-on-databricks P11 | A transformation run config carries an execution target outside the D1 vocabulary (`local` / `databricks_warehouse` / `databricks_job`) — refused with the value named, NEVER a silent local fallback. | Correct the target to the vocabulary (or omit it — `local` is the unchanged default). |
| `DATABRICKS_DBT_PROFILE_RESOLVER_UNAVAILABLE` | 500 | run-transformation-on-databricks P11 | The warehouse-direct target has no estate profile resolver wired (`_resolve_databricks_warehouse_profile` — the 11.3 wiring binds the real one) — the run refuses before any subprocess/network work, in the execution result envelope. | Wire the estate credential resolution (the 11.3 workspace/connection paths) before selecting the warehouse-direct target. |
| `DATABRICKS_DBT_RUNNER_JOB_MISSING` | 500 | run-transformation-on-databricks P11 | The dbt-as-job target's dispatch context is incomplete — the tenant/workspace/runner-job ids are missing, the workspace is not registered for the tenant, or the runner job is not mirrored — refused with ZERO API calls. | Provide the dispatch context (tenant + workspace + a mirrored runner job) before selecting the job target. |
| `DATABRICKS_DBT_JOB_DISPATCH_UNAVAILABLE` | 500 | run-transformation-on-databricks P11 | No provider dispatcher is registered into the dbt-as-job facade (the `databricks_admin` app-ready registration) — the job target refuses rather than falling back to a local run. | Ensure the databricks_admin app is loaded (its `ready()` registers the real dispatcher). |
| `EXPORT_CONTRACT_VALIDATION_FAILED` | 409 | wire-databricks-dlt-movement P6 | Pre-export ODCS validation failed: a source asset lacks an ACTIVE ODCS contract (or its validation status is INVALID/ERROR/unvalidated). The run failed BEFORE the first write. | Fix or validate the source contract (VALID/WARNING_ONLY), or remove the asset from the export scope. |
| `READ_ONLY_VIOLATION` | 403 | warehouses | Write operations are forbidden on warehouse connections. | Use a read-only query; writes require the scoped pipeline path. |
| `DATA_RESIDENCY_REGION_MISMATCH` | 400 | warehouses | Warehouse region does not match tenant data residency region. | Choose a warehouse in a region within the tenant's residency regime. |
| `WAREHOUSE_UNSUPPORTED_DIALECT` | 400 | warehouses | Unsupported warehouse type. | Use a supported warehouse type (SNOWFLAKE/BIGQUERY/DATABRICKS/ATHENA). |
| `WAREHOUSE_PERMISSION_DENIED` | 403 | warehouses | Permission denied on warehouse resource. | Grant the required warehouse permissions to the connection credential. |
| `WAREHOUSE_CONCURRENCY_EXCEEDED` | 429 | warehouses | Per-tenant concurrent warehouse query limit reached. | Wait for the `Retry-After` window and retry. |
| `WAREHOUSE_QUERY_TIMEOUT` | 504 | warehouses | Warehouse query timed out. | Retry; tune the query or increase the statement timeout. | 
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
| `IDEMPOTENCY_ERROR` | 400 | 250.1.D | The idempotency-key validation base error — a failure not covered by a more specific `IDEMPOTENCY_KEY_*` code. | Follow the specific code's guidance; verify the key/body shape per ADR-AST-005. |

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
| `NOT_FOUND` | 404 | (existing) | The requested resource id is unknown or not visible to the caller. | Verify the id and the tenant scope. |
| `AUTH_REQUIRED` | 401 | (existing) | Authentication is required for this endpoint. | Authenticate and retry. |
| `NO_TENANT` | 403 | (existing) | No tenant context could be resolved for the request. | Ensure the request carries valid tenant credentials. |
| `VALIDATION_ERROR` | 400 | (existing) | Generic validator-failed. `details` enumerates field-level errors. | Fix the request body. |
| `RATE_LIMIT_EXCEEDED` | 429 | (existing) | DRF throttle scope exceeded. | Honour `Retry-After`. |
| `CONNECTION_ERROR` | 503 | (existing) | The service layer's connection-error default — a backend service could not be reached. | Retry; verify the target service's health and connectivity. |
| `INVALID_TRANSITION` | 400 | oss-release-remediation W3.1 | A status write violated the resource's guarded state-machine matrix (e.g. a terminal scheduled run PATCHed to COMPLETED). `details.from_status` / `details.to_status` name the rejected hop. | Terminal states are final — reconcile manually or create a new resource. |
| `RUN_CANCELLED` | 400 | oss-release-remediation W3.1 | A worker attempted to process items for a cancelled scheduled run. | The run was cancelled; no further items are accepted. 

---

## Backfilled codes (Phase 250 debt sweep)

Rows generated by the catalogue backfill sweep: every code the CI gate
flagged as emitted-but-uncatalogued now has a row. Phase is `(existing)` —
these predate the Phase 250.0.13 catalogue contract; statuses are inferred
from the code name (NOT_FOUND→404, TIMEOUT→504, RATE_LIMIT→429, DENIED/FORBIDDEN/PERMISSION→403, FAILED/ERROR→500, else 400).

### api

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `AUTH_FORBIDDEN` | 403 | (existing) | Auth Forbidden. | See the app's runbook / logs for the failure detail. |
| `AUTH_UNAUTHORIZED` | 400 | (existing) | Auth Unauthorized. | See the app's runbook / logs for the failure detail. |
| `CONFLICT_ERROR` | 500 | (existing) | Conflict Error. | See the app's runbook / logs for the failure detail. |
| `ERROR_CODE` | 500 | (existing) | Error Code. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_CONFLICT` | 400 | (existing) | Idempotency Conflict. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_KEY_EXPIRED` | 400 | (existing) | Idempotency Key Expired. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `INVALID_IDEMPOTENCY_KEY` | 400 | (existing) | Invalid Idempotency Key. | See the app's runbook / logs for the failure detail. |
| `REQUEST_TOO_LARGE` | 400 | (existing) | Request Too Large. | See the app's runbook / logs for the failure detail. |
| `REQUIRED` | 400 | (existing) | Required. | See the app's runbook / logs for the failure detail. |
| `SERVICE_UNAVAILABLE` | 400 | (existing) | Service Unavailable. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_API_VERSION` | 400 | (existing) | Unsupported Api Version. | See the app's runbook / logs for the failure detail. |
| `VALIDATION_FAILED` | 500 | (existing) | Validation Failed. | See the app's runbook / logs for the failure detail. |

### assets

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ASSET_ACTIVATION_BLOCKED` | 400 | (existing) | Asset Activation Blocked. | See the app's runbook / logs for the failure detail. |
| `ASSET_ALREADY_ACTIVE` | 400 | (existing) | Asset Already Active. | See the app's runbook / logs for the failure detail. |
| `ASSET_ALREADY_RETIRED` | 400 | (existing) | Asset Already Retired. | See the app's runbook / logs for the failure detail. |
| `ASSET_CONCURRENT_MODIFICATION` | 400 | (existing) | Asset Concurrent Modification. | See the app's runbook / logs for the failure detail. |
| `ASSET_INVALID_STATE_FOR_RETIREMENT` | 400 | (existing) | Asset Invalid State For Retirement. | See the app's runbook / logs for the failure detail. |
| `ASSET_KEY_EXISTS` | 400 | (existing) | Asset Key Exists. | See the app's runbook / logs for the failure detail. |
| `ASSET_KEY_RETIRED` | 400 | (existing) | Asset Key Retired. | See the app's runbook / logs for the failure detail. |
| `ASSET_RETIRED` | 400 | (existing) | Asset Retired. | See the app's runbook / logs for the failure detail. |
| `BAD_REQUEST` | 400 | (existing) | Bad Request. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_SERVICE_UNAVAILABLE` | 400 | (existing) | Compliance Service Unavailable. | See the app's runbook / logs for the failure detail. |
| `DOWNLOAD_FAILED` | 500 | (existing) | Download Failed. | See the app's runbook / logs for the failure detail. |
| `FIELD_REMOVED` | 400 | (existing) | Field Removed. | See the app's runbook / logs for the failure detail. |
| `HEALTH_SCORE_CALCULATION_FAILED` | 500 | (existing) | Health Score Calculation Failed. | See the app's runbook / logs for the failure detail. |
| `HEALTH_SCORE_THRESHOLD_NOT_MET` | 400 | (existing) | Health Score Threshold Not Met. | See the app's runbook / logs for the failure detail. |
| `HEALTH_SCORE_UPDATE_REQUIRED` | 400 | (existing) | Health Score Update Required. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_REQUEST_IN_PROGRESS` | 400 | (existing) | Idempotency Request In Progress. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `INVALID_CONTRACT_TYPE` | 400 | (existing) | Invalid Contract Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_HEALTH_SCORE_CALCULATION` | 400 | (existing) | Invalid Health Score Calculation. | See the app's runbook / logs for the failure detail. |
| `INVALID_REQUEST` | 400 | (existing) | Invalid Request. | See the app's runbook / logs for the failure detail. |
| `INVALID_STATE` | 400 | (existing) | Invalid State. | See the app's runbook / logs for the failure detail. |
| `LENGTH_REQUIRED` | 400 | (existing) | Length Required. | See the app's runbook / logs for the failure detail. |
| `NOT_FEDERATED_ASSET` | 400 | (existing) | Not Federated Asset. | See the app's runbook / logs for the failure detail. |
| `ODPS_SOURCE_REQUIRED` | 400 | (existing) | Odps Source Required. | See the app's runbook / logs for the failure detail. |
| `PAYLOAD_TOO_LARGE` | 400 | (existing) | Payload Too Large. | See the app's runbook / logs for the failure detail. |
| `PRECONDITION_FAILED` | 500 | (existing) | Precondition Failed. | See the app's runbook / logs for the failure detail. |
| `PRECONDITION_REQUIRED` | 400 | (existing) | Precondition Required. | See the app's runbook / logs for the failure detail. |
| `QUOTA_EXCEEDED` | 400 | (existing) | Quota Exceeded. | See the app's runbook / logs for the failure detail. |
| `RESOURCE_NOT_FOUND` | 404 | (existing) | Resource Not Found. | See the app's runbook / logs for the failure detail. |
| `STORAGE_UPLOAD_FAILED` | 500 | (existing) | Storage Upload Failed. | See the app's runbook / logs for the failure detail. |
| `WORKFLOW_FAILED` | 500 | (existing) | Workflow Failed. | See the app's runbook / logs for the failure detail. |
| `WORKFLOW_INCOMPLETE` | 400 | (existing) | Workflow Incomplete. | See the app's runbook / logs for the failure detail. |
| `WORKFLOW_NOT_FOUND` | 404 | (existing) | Workflow Not Found. | See the app's runbook / logs for the failure detail. |

### auth

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `BAD_REQUEST` | 400 | (existing) | Bad Request. | See the app's runbook / logs for the failure detail. |
| `EMAIL_ALREADY_EXISTS` | 400 | (existing) | Email Already Exists. | See the app's runbook / logs for the failure detail. |
| `EMAIL_NOT_VERIFIED` | 400 | (existing) | Email Not Verified. | See the app's runbook / logs for the failure detail. |
| `REGISTRATION_FAILED` | 500 | (existing) | Registration Failed. | See the app's runbook / logs for the failure detail. |
| `REGISTRATION_JOIN_DENIED` | 403 | W1.1 (R2-B1) | Registration is for personal accounts only; a payload carrying `tenant_id` is a denied tenant-join attempt (audited — never accepted). | Join a tenant via an invitation instead. |
| `SERVICE_UNAVAILABLE` | 400 | (existing) | Service Unavailable. | See the app's runbook / logs for the failure detail. |
| `TOKEN_EXPIRED` | 400 | (existing) | Token Expired. | See the app's runbook / logs for the failure detail. |
| `TOKEN_INVALIDATED` | 400 | (existing) | Token Invalidated. | See the app's runbook / logs for the failure detail. |
| `USER_INACTIVE` | 400 | (existing) | User Inactive. | See the app's runbook / logs for the failure detail. |

### baas

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ALREADY_REVOKED` | 400 | (existing) | Already Revoked. | See the app's runbook / logs for the failure detail. |
| `API_KEY_CREATION_VALIDATION_FAILED` | 500 | (existing) | Api Key Creation Validation Failed. | See the app's runbook / logs for the failure detail. |
| `API_KEY_USAGE_INVALID` | 400 | (existing) | Api Key Usage Invalid. | See the app's runbook / logs for the failure detail. |
| `API_KEY_SCOPE_MINT_DENIED` | 400 | W1.3a (R2-B2) | The requested API-key scopes fall outside the requester's role allowlist (`"*"` is PLATFORM_ADMIN-only; `scheduled_ingestion:internal` is never mintable via the public API). | Mint only scopes your roles grant; contact a platform admin for `"*"`. |
| `CROSS_TENANT_FORBIDDEN` | 403 | (existing) | Cross Tenant Forbidden. | See the app's runbook / logs for the failure detail. |
| `ROLE_ASSIGNMENT_FORBIDDEN` | 403 | W1.2 (oss-release-remediation) | Role assignment outside the requester-assignable set (tenant admins assign only their own tenant's roles; platform-level roles are escalation). | See the app's runbook / logs for the failure detail. |
| `INVALID_STATUS_TRANSITION` | 400 | (existing) | Invalid Status Transition. | See the app's runbook / logs for the failure detail. |
| `PERMISSION_CHECK_FAILED` | 403 | (existing) | Permission Check Failed. | See the app's runbook / logs for the failure detail. |
| `QUOTA_CHECK_FAILED` | 500 | (existing) | Quota Check Failed. | See the app's runbook / logs for the failure detail. |
| `REPORT_IMMUTABLE` | 400 | (existing) | Report Immutable. | See the app's runbook / logs for the failure detail. |
| `TENANT_MISMATCH` | 400 | (existing) | Tenant Mismatch. | See the app's runbook / logs for the failure detail. |
| `TENANT_REQUIRED` | 400 | (existing) | Tenant Required. | See the app's runbook / logs for the failure detail. |
| `USAGE_TRACKING_INVALID` | 400 | (existing) | Usage Tracking Invalid. | See the app's runbook / logs for the failure detail. |

### billing

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `DUPLICATE_SUBSCRIPTION` | 400 | (existing) | Duplicate Subscription. | See the app's runbook / logs for the failure detail. |
| `EMAIL_REQUIRED` | 400 | (existing) | Email Required. | See the app's runbook / logs for the failure detail. |
| `INVALID_AMOUNT` | 400 | (existing) | Invalid Amount. | See the app's runbook / logs for the failure detail. |
| `INVALID_PERIOD` | 400 | (existing) | Invalid Period. | See the app's runbook / logs for the failure detail. |
| `INVALID_PLAN_CATEGORY` | 400 | (existing) | Invalid Plan Category. | See the app's runbook / logs for the failure detail. |
| `INVALID_REASON` | 400 | (existing) | Invalid Reason. | See the app's runbook / logs for the failure detail. |
| `STRIPE_ERROR` | 500 | (existing) | Stripe Error. | See the app's runbook / logs for the failure detail. |
| `STRIPE_NOT_AVAILABLE` | 400 | (existing) | Stripe Not Available. | See the app's runbook / logs for the failure detail. |
| `STRIPE_NOT_CONFIGURED` | 400 | (existing) | Stripe Not Configured. | See the app's runbook / logs for the failure detail. |

### compliance

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_RUN_NOT_DISPATCHABLE` | 400 | (existing) | Compliance Run Not Dispatchable. | See the app's runbook / logs for the failure detail. |
| `INVALID_STATUS` | 400 | (existing) | Invalid Status. | See the app's runbook / logs for the failure detail. |
| `JOB_NOT_CANCELLABLE` | 400 | (existing) | Job Not Cancellable. | See the app's runbook / logs for the failure detail. |
| `REGULATION_NOT_LICENSED` | 400 | (existing) | Regulation Not Licensed. | See the app's runbook / logs for the failure detail. |
| `WAREHOUSE_SCAN_MODE_REQUIRED` | 400 | (existing) | Warehouse Scan Mode Required. | See the app's runbook / logs for the failure detail. |

### consent

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `CONSENT_PURPOSE_NOT_CONFIGURED` | 400 | (existing) | Consent Purpose Not Configured. | See the app's runbook / logs for the failure detail. |
| `CONSENT_REQUIRED` | 400 | (existing) | Consent Required. | See the app's runbook / logs for the failure detail. |
| `FORBIDDEN` | 400 | (existing) | Forbidden. | See the app's runbook / logs for the failure detail. |
| `PROOF_VERIFICATION_FAILED` | 500 | (existing) | Proof Verification Failed. | See the app's runbook / logs for the failure detail. |
| `PURPOSE_INACTIVE` | 400 | (existing) | Purpose Inactive. | See the app's runbook / logs for the failure detail. |
| `SIGNING_KEYS_MISSING` | 400 | (existing) | Signing Keys Missing. | See the app's runbook / logs for the failure detail. |
| `SIGNUP_CONSENT_REQUIRED` | 400 | (existing) | Signup Consent Required. | See the app's runbook / logs for the failure detail. |
| `TENANT_MISMATCH` | 400 | (existing) | Tenant Mismatch. | See the app's runbook / logs for the failure detail. |

### contracts

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ASSET_MISMATCH` | 400 | (existing) | Asset Mismatch. | See the app's runbook / logs for the failure detail. |
| `AS_OF_AND_VERSION_MUTUALLY_EXCLUSIVE` | 400 | (existing) | As Of And Version Mutually Exclusive. | See the app's runbook / logs for the failure detail. |
| `AUTHENTICATION_REQUIRED` | 400 | (existing) | Authentication Required. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `CIRCULAR_REFERENCE` | 400 | (existing) | Circular Reference. | See the app's runbook / logs for the failure detail. |
| `CONTRACT_EVENT_PUBLISH_FAILED` | 500 | (existing) | Contract Event Publish Failed. | See the app's runbook / logs for the failure detail. |
| `CONTRACT_ID_MISMATCH` | 400 | (existing) | Contract Id Mismatch. | See the app's runbook / logs for the failure detail. |
| `CONTRACT_NAME_MISMATCH` | 400 | (existing) | Contract Name Mismatch. | See the app's runbook / logs for the failure detail. |
| `CONTRACT_NOT_FOUND` | 404 | (existing) | Contract Not Found. | See the app's runbook / logs for the failure detail. |
| `CROSS_TENANT_EDGE_FORBIDDEN` | 403 | (existing) | Cross Tenant Edge Forbidden. | See the app's runbook / logs for the failure detail. |
| `CROSS_TENANT_FORBIDDEN` | 403 | (existing) | Cross Tenant Forbidden. | See the app's runbook / logs for the failure detail. |
| `EDIT_LINEAGE_FORBIDDEN` | 403 | (existing) | Edit Lineage Forbidden. | See the app's runbook / logs for the failure detail. |
| `EVENT_REQUIRED` | 400 | (existing) | Event Required. | See the app's runbook / logs for the failure detail. |
| `INCOMPATIBLE_CONTRACTS` | 400 | (existing) | Incompatible Contracts. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `INVALID_ANCHOR` | 400 | (existing) | Invalid Anchor. | See the app's runbook / logs for the failure detail. |
| `INVALID_AS_OF` | 400 | (existing) | Invalid As Of. | See the app's runbook / logs for the failure detail. |
| `INVALID_CONTRACT_TYPE` | 400 | (existing) | Invalid Contract Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_EDGE_ENDPOINTS` | 400 | (existing) | Invalid Edge Endpoints. | See the app's runbook / logs for the failure detail. |
| `INVALID_FORMAT` | 400 | (existing) | Invalid Format. | See the app's runbook / logs for the failure detail. |
| `INVALID_ODCS_LINK` | 400 | (existing) | Invalid Odcs Link. | See the app's runbook / logs for the failure detail. |
| `INVALID_ODCS_LINK_TYPE` | 400 | (existing) | Invalid Odcs Link Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_ODPS_LINK` | 400 | (existing) | Invalid Odps Link. | See the app's runbook / logs for the failure detail. |
| `INVALID_ODPS_LINK_TYPE` | 400 | (existing) | Invalid Odps Link Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_OPERATION` | 400 | (existing) | Invalid Operation. | See the app's runbook / logs for the failure detail. |
| `INVALID_ORDERING` | 400 | (existing) | Invalid Ordering. | See the app's runbook / logs for the failure detail. |
| `INVALID_SEVERITY_THRESHOLD` | 400 | (existing) | Invalid Severity Threshold. | See the app's runbook / logs for the failure detail. |
| `INVALID_SPEC` | 400 | (existing) | Invalid Spec. | See the app's runbook / logs for the failure detail. |
| `INVALID_SUBSCRIPTION_SOURCE` | 400 | (existing) | Invalid Subscription Source. | See the app's runbook / logs for the failure detail. |
| `INVALID_TENANT_ID` | 400 | (existing) | Invalid Tenant Id. | See the app's runbook / logs for the failure detail. |
| `INVALID_USER_ID` | 400 | (existing) | Invalid User Id. | See the app's runbook / logs for the failure detail. |
| `INVALID_VERSION` | 400 | (existing) | Invalid Version. | See the app's runbook / logs for the failure detail. |
| `INVALID_YAML` | 400 | (existing) | Invalid Yaml. | See the app's runbook / logs for the failure detail. |
| `JSONSCHEMA_NOT_AVAILABLE` | 400 | (existing) | Jsonschema Not Available. | See the app's runbook / logs for the failure detail. |
| `LINEAGE_CYCLE` | 400 | (existing) | Lineage Cycle. | See the app's runbook / logs for the failure detail. |
| `LINEAGE_FIELD_NOT_FOUND` | 404 | (existing) | Lineage Field Not Found. | See the app's runbook / logs for the failure detail. |
| `LINEAGE_TYPE_MISMATCH` | 400 | (existing) | Lineage Type Mismatch. | See the app's runbook / logs for the failure detail. |
| `MISSING_FROM_ANCHOR` | 400 | (existing) | Missing From Anchor. | See the app's runbook / logs for the failure detail. |
| `MISSING_HUB_CONTRACT` | 400 | (existing) | Missing Hub Contract. | See the app's runbook / logs for the failure detail. |
| `NORMALIZATION_FAILED` | 500 | (existing) | Normalization Failed. | See the app's runbook / logs for the failure detail. |
| `ODCS_CONTRACT_NOT_FOUND` | 404 | (existing) | Odcs Contract Not Found. | See the app's runbook / logs for the failure detail. |
| `ODPS_CONTRACT_ID_REQUIRED` | 400 | (existing) | Odps Contract Id Required. | See the app's runbook / logs for the failure detail. |
| `ODPS_CONTRACT_NOT_FOUND` | 404 | (existing) | Odps Contract Not Found. | See the app's runbook / logs for the failure detail. |
| `ODPS_EVENT_PUBLISH_FAILED` | 500 | (existing) | Odps Event Publish Failed. | See the app's runbook / logs for the failure detail. |
| `ODPS_FORMAT_REQUIRED` | 400 | (existing) | Odps Format Required. | See the app's runbook / logs for the failure detail. |
| `ODPS_INVALID_CONTRACT_SPEC` | 400 | (existing) | Odps Invalid Contract Spec. | See the app's runbook / logs for the failure detail. |
| `ODPS_LINKED_EVENT_PUBLISH_FAILED` | 500 | (existing) | Odps Linked Event Publish Failed. | See the app's runbook / logs for the failure detail. |
| `ODPS_MISSING_CONTRACT` | 400 | (existing) | Odps Missing Contract. | See the app's runbook / logs for the failure detail. |
| `ODPS_MISSING_ORIGINAL_RAW` | 400 | (existing) | Odps Missing Original Raw. | See the app's runbook / logs for the failure detail. |
| `ODPS_MISSING_PRODUCT` | 400 | (existing) | Odps Missing Product. | See the app's runbook / logs for the failure detail. |
| `ODPS_NORMALIZATION_ERROR` | 500 | (existing) | Odps Normalization Error. | See the app's runbook / logs for the failure detail. |
| `ODPS_NOT_NORMALIZED` | 400 | (existing) | Odps Not Normalized. | See the app's runbook / logs for the failure detail. |
| `ODPS_PARSE_FAILED` | 500 | (existing) | Odps Parse Failed. | See the app's runbook / logs for the failure detail. |
| `ODPS_RAW_REQUIRED` | 400 | (existing) | Odps Raw Required. | See the app's runbook / logs for the failure detail. |
| `ODPS_ROLLBACK_FAILED` | 500 | (existing) | Odps Rollback Failed. | See the app's runbook / logs for the failure detail. |
| `ODPS_SOURCE_REQUIRED` | 400 | (existing) | Odps Source Required. | See the app's runbook / logs for the failure detail. |
| `ODPS_VALIDATION_FAILED` | 500 | (existing) | Odps Validation Failed. | See the app's runbook / logs for the failure detail. |
| `PAYLOAD_TOO_LARGE` | 400 | (existing) | Payload Too Large. | See the app's runbook / logs for the failure detail. |
| `PRECONDITION_FAILED` | 500 | (existing) | Precondition Failed. | See the app's runbook / logs for the failure detail. |
| `REFERENTIAL_INTEGRITY_VIOLATION` | 400 | (existing) | Referential Integrity Violation. | See the app's runbook / logs for the failure detail. |
| `SCHEMA_BUILD_FAILED` | 500 | (existing) | Schema Build Failed. | See the app's runbook / logs for the failure detail. |
| `SCHEMA_INVALID` | 400 | (existing) | Schema Invalid. | See the app's runbook / logs for the failure detail. |
| `SCHEMA_LOAD_ERROR` | 500 | (existing) | Schema Load Error. | See the app's runbook / logs for the failure detail. |
| `SCHEMA_NOT_FOUND` | 404 | (existing) | Schema Not Found. | See the app's runbook / logs for the failure detail. |
| `SCHEMA_TOO_DEEP` | 400 | (existing) | Schema Too Deep. | See the app's runbook / logs for the failure detail. |
| `SCHEMA_VALIDATION_FAILED` | 500 | (existing) | Schema Validation Failed. | See the app's runbook / logs for the failure detail. |
| `SERIALIZATION_CONFLICT` | 400 | (existing) | Serialization Conflict. | See the app's runbook / logs for the failure detail. |
| `STRUCTURELESS_CONTRACT` | 400 | (existing) | Structureless Contract. | See the app's runbook / logs for the failure detail. |
| `SUBSCRIPTION_ALREADY_EXISTS` | 400 | (existing) | Subscription Already Exists. | See the app's runbook / logs for the failure detail. |
| `SUBSCRIPTION_CAP_EXCEEDED` | 400 | (existing) | Subscription Cap Exceeded. | See the app's runbook / logs for the failure detail. |
| `TENANT_ID_REQUIRED` | 400 | (existing) | Tenant Id Required. | See the app's runbook / logs for the failure detail. |
| `TENANT_MISMATCH` | 400 | (existing) | Tenant Mismatch. | See the app's runbook / logs for the failure detail. |
| `TENANT_NOT_FOUND` | 404 | (existing) | Tenant Not Found. | See the app's runbook / logs for the failure detail. |
| `UNEXPECTED_ERROR` | 500 | (existing) | Unexpected Error. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_ODPS_VERSION` | 400 | (existing) | Unsupported Odps Version. | See the app's runbook / logs for the failure detail. |
| `USER_NOT_FOUND` | 404 | (existing) | User Not Found. | See the app's runbook / logs for the failure detail. |
| `VERSION_NOT_FOUND` | 404 | (existing) | Version Not Found. | See the app's runbook / logs for the failure detail. |

### core

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `BUSINESS_RULE_EXECUTION_FAILED` | 500 | (existing) | Business Rule Execution Failed. | See the app's runbook / logs for the failure detail. |
| `ERROR_CODE` | 500 | (existing) | Error Code. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_KEY_MALFORMED` | 400 | (existing) | Idempotency Key Malformed. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_KEY_MISMATCH` | 400 | (existing) | Idempotency Key Mismatch. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_KEY_TENANT_MISMATCH` | 400 | (existing) | Idempotency Key Tenant Mismatch. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_REQUEST_IN_PROGRESS` | 400 | (existing) | Idempotency Request In Progress. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `INVALID_ID` | 400 | (existing) | Invalid Id. | See the app's runbook / logs for the failure detail. |
| `METHOD_NOT_FOUND` | 404 | (existing) | Method Not Found. | See the app's runbook / logs for the failure detail. |
| `REPLAY_ERROR` | 500 | (existing) | Replay Error. | See the app's runbook / logs for the failure detail. |
| `RESOLVE_FAILED` | 500 | (existing) | Resolve Failed. | See the app's runbook / logs for the failure detail. |
| `RETRY_FAILED` | 500 | (existing) | Retry Failed. | See the app's runbook / logs for the failure detail. |
| `SERVICE_CALL_ERROR` | 500 | (existing) | Service Call Error. | See the app's runbook / logs for the failure detail. |

### datasets

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `DATASET_ALREADY_RETIRED` | 400 | (existing) | Dataset Already Retired. | See the app's runbook / logs for the failure detail. |
| `DATASET_FILE_PURPOSE_CONFLICT` | 400 | (existing) | Dataset File Purpose Conflict. | See the app's runbook / logs for the failure detail. |
| `DATASET_REFRESH_NO_FILE` | 400 | (existing) | Dataset Refresh No File. | See the app's runbook / logs for the failure detail. |
| `DATASET_REFRESH_REQUIRES_ASSET` | 400 | (existing) | Dataset Refresh Requires Asset. | See the app's runbook / logs for the failure detail. |
| `DATASET_REFRESH_SAME_FILE` | 400 | (existing) | Dataset Refresh Same File. | See the app's runbook / logs for the failure detail. |
| `DATASET_RETIRED_REFRESH_NOT_ALLOWED` | 400 | (existing) | Dataset Retired Refresh Not Allowed. | See the app's runbook / logs for the failure detail. |
| `DATASET_VERSION_CONFLICT` | 400 | (existing) | Dataset Version Conflict. | See the app's runbook / logs for the failure detail. |
| `EXTERNAL_REF_NOT_API_SETTABLE` | 400 | (existing) | External Ref Not Api Settable. | See the app's runbook / logs for the failure detail. |
| `FILE_ENCODING_UNSUPPORTED` | 400 | (existing) | File Encoding Unsupported. | See the app's runbook / logs for the failure detail. |
| `FILE_INFECTED` | 400 | (existing) | File Infected. | See the app's runbook / logs for the failure detail. |
| `FILE_NOT_IN_STORAGE` | 409 | W7.4 | File Not In Storage. The object's upload was never completed in object storage — complete the upload before retrying. | Re-run the upload completion flow (init → PUT → complete); see the files runbook. |
| `FILE_NOT_FOUND` | 404 | (existing) | File Not Found. | See the app's runbook / logs for the failure detail. |
| `FILE_NOT_READY` | 400 | (existing) | File Not Ready. | See the app's runbook / logs for the failure detail. |
| `FILE_NOT_READY_FOR_DATASET` | 400 | (existing) | File Not Ready For Dataset. | See the app's runbook / logs for the failure detail. |
| `FILE_SCAN_NOT_CLEAN` | 400 | (existing) | File Scan Not Clean. | See the app's runbook / logs for the failure detail. |
| `FILE_SCAN_PENDING` | 400 | (existing) | File Scan Pending. | See the app's runbook / logs for the failure detail. |
| `FILE_SCAN_UNAVAILABLE` | 503 | W1.18 (oss-release-remediation) | A SCAN_UNAVAILABLE file was refused at the dataset-source or download gate under `SCAN_UNAVAILABLE_POLICY=block` (ClamAV outage policy — see docs/runbooks/file-virus-scan-incident.md). | Restore ClamAV and re-scan (or temporarily set `SCAN_UNAVAILABLE_POLICY=allow` with the outage recorded in the CHANGELOG). |
| `FILE_TOO_LARGE_FOR_INFERENCE` | 400 | (existing) | File Too Large For Inference. | See the app's runbook / logs for the failure detail. |
| `FILE_TOO_LARGE` | 400 | W1.14 (R2-S7) | A worker internal upload exceeded `WORKER_INTERNAL_MAX_FILE_BYTES`. Rejected before the full body was read. | Reduce the file size or raise the configured cap. |
| `INVALID_DATASET_ID` | 400 | (existing) | Invalid Dataset Id. | See the app's runbook / logs for the failure detail. |
| `INVALID_SEMANTIC_VERSION` | 400 | (existing) | Invalid Semantic Version. | See the app's runbook / logs for the failure detail. |
| `NO_WAREHOUSE_CONNECTION` | 400 | (existing) | No Warehouse Connection. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_FILE_FORMAT` | 400 | (existing) | Unsupported File Format. | See the app's runbook / logs for the failure detail. |
| `VERSIONING_DISABLED` | 400 | (existing) | Versioning Disabled. | See the app's runbook / logs for the failure detail. |
| `VERSION_COMPATIBILITY_FAILED` | 500 | (existing) | Version Compatibility Failed. | See the app's runbook / logs for the failure detail. |
| `VERSION_CREATION_FAILED` | 500 | (existing) | Version Creation Failed. | See the app's runbook / logs for the failure detail. |
| `VERSION_DELETION_FAILED` | 500 | (existing) | Version Deletion Failed. | See the app's runbook / logs for the failure detail. |
| `VERSION_LINEAGE_MISMATCH` | 400 | (existing) | Version Lineage Mismatch. | See the app's runbook / logs for the failure detail. |

### dq

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ADVANCED_DQ_DISABLED` | 400 | (existing) | Advanced Dq Disabled. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `WAREHOUSE_ENGINE_REQUIRED` | 400 | (existing) | Warehouse Engine Required. | See the app's runbook / logs for the failure detail. |

### files

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `FILENAME_COLLISION` | 400 | (existing) | Filename Collision. | See the app's runbook / logs for the failure detail. |
| `FILE_FORMAT_MISMATCH` | 400 | (existing) | File Format Mismatch. | See the app's runbook / logs for the failure detail. |
| `FILE_INFECTED` | 400 | (existing) | File Infected. | See the app's runbook / logs for the failure detail. |
| `FILE_METADATA_TOO_LARGE` | 400 | (existing) | File Metadata Too Large. | See the app's runbook / logs for the failure detail. |
| `FILE_SCAN_PENDING` | 400 | (existing) | File Scan Pending. | See the app's runbook / logs for the failure detail. |
| `MULTIPART_COMPOSE_FAILED` | 500 | (existing) | Multipart Compose Failed. | See the app's runbook / logs for the failure detail. |
| `MULTIPART_INCOMPLETE` | 400 | (existing) | Multipart Incomplete. | See the app's runbook / logs for the failure detail. |
| `MULTIPART_LIST_FAILED` | 500 | (existing) | Multipart List Failed. | See the app's runbook / logs for the failure detail. |
| `MULTIPART_NO_PARTS` | 400 | (existing) | Multipart No Parts. | See the app's runbook / logs for the failure detail. |
| `MULTIPART_UPLOAD_NOT_ACTIVE` | 400 | (existing) | Multipart Upload Not Active. | See the app's runbook / logs for the failure detail. |
| `MULTIPART_UPLOAD_NO_LONGER_EXISTS` | 400 | (existing) | Multipart Upload No Longer Exists. | See the app's runbook / logs for the failure detail. |
| `QUOTA_PLAN_RESOLUTION_FAILED` | 500 | (existing) | Quota Plan Resolution Failed. | See the app's runbook / logs for the failure detail. |
| `TENANT_REQUIRED` | 400 | (existing) | Tenant Required. | See the app's runbook / logs for the failure detail. |
| `UPLOAD_ALREADY_COMPLETED` | 400 | (existing) | Upload Already Completed. | See the app's runbook / logs for the failure detail. |

### gdpr

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ERASURE_IN_PROGRESS` | 400 | (existing) | Erasure In Progress. | See the app's runbook / logs for the failure detail. |
| `EXPORT_IN_PROGRESS` | 400 | (existing) | Export In Progress. | See the app's runbook / logs for the failure detail. |

### governance

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ABAC_POLICY_DENIED` | 403 | (existing) | Abac Policy Denied. | See the app's runbook / logs for the failure detail. |
| `ASSET_REQUIRED` | 400 | (existing) | Asset Required. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_NOT_ALLOWED_TO_STORE` | 400 | (existing) | Compliance Not Allowed To Store. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_RUN_REQUIRED` | 400 | (existing) | Compliance Run Required. | See the app's runbook / logs for the failure detail. |
| `DATASET_NOT_FOUND` | 404 | (existing) | Dataset Not Found. | See the app's runbook / logs for the failure detail. |
| `DUPLICATE_DELEGATION` | 400 | (existing) | Duplicate Delegation. | See the app's runbook / logs for the failure detail. |
| `FILE_NOT_FOUND` | 404 | (existing) | File Not Found. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `INVALID_REGIME` | 400 | (existing) | Invalid Regime. | See the app's runbook / logs for the failure detail. |
| `REVOCATION_REASON_REQUIRED` | 400 | (existing) | Revocation Reason Required. | See the app's runbook / logs for the failure detail. |
| `USER_NOT_FOUND` | 404 | (existing) | User Not Found. | See the app's runbook / logs for the failure detail. |

### graphql_graphene

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `GRAPHQL_ERROR` | 500 | (existing) | Graphql Error. | See the app's runbook / logs for the failure detail. |
| `QUERY_COMPLEXITY_EXCEEDED` | 400 | (existing) | Query Complexity Exceeded. | See the app's runbook / logs for the failure detail. |

### graphql_ld

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `GRAPHQL_COMPLEXITY_EXCEEDED` | 400 | (existing) | Graphql Complexity Exceeded. | See the app's runbook / logs for the failure detail. |
| `GRAPHQL_DEPTH_EXCEEDED` | 400 | (existing) | Graphql Depth Exceeded. | See the app's runbook / logs for the failure detail. |
| `GRAPHQL_EXECUTION_ERROR` | 500 | (existing) | Graphql Execution Error. | See the app's runbook / logs for the failure detail. |
| `GRAPHQL_QUERY_TIMEOUT` | 504 | (existing) | Graphql Query Timeout. | See the app's runbook / logs for the failure detail. |
| `GRAPHQL_SYNTAX_ERROR` | 500 | (existing) | Graphql Syntax Error. | See the app's runbook / logs for the failure detail. |

### integrations

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `AUTH_BEARER_INVALID` | 400 | (existing) | Auth Bearer Invalid. | See the app's runbook / logs for the failure detail. |
| `AUTH_HMAC_INVALID` | 400 | (existing) | Auth Hmac Invalid. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `CONSUMER_TENANT_NOT_FOUND` | 404 | (existing) | Consumer Tenant Not Found. | See the app's runbook / logs for the failure detail. |
| `CROSS_REGION_CONSENT_REQUIRED` | 400 | (existing) | Cross Region Consent Required. | See the app's runbook / logs for the failure detail. |
| `DATASETS_LIMIT_EXCEEDED` | 400 | (existing) | Datasets Limit Exceeded. | See the app's runbook / logs for the failure detail. |
| `FORBIDDEN_ADMIN_ONLY` | 400 | (existing) | Forbidden Admin Only. | See the app's runbook / logs for the failure detail. |
| `INVALID_JSON` | 400 | (existing) | Invalid Json. | See the app's runbook / logs for the failure detail. |
| `JOB_TERMINAL` | 400 | (existing) | Job Terminal. | See the app's runbook / logs for the failure detail. |
| `KEY_NOT_FOUND` | 404 | (existing) | Key Not Found. | See the app's runbook / logs for the failure detail. |
| `MISSING_RUN_ID` | 400 | (existing) | Missing Run Id. | See the app's runbook / logs for the failure detail. |
| `OPENLINEAGE_VALIDATION_FAILED` | 500 | (existing) | Openlineage Validation Failed. | See the app's runbook / logs for the failure detail. |
| `PAYLOAD_TOO_LARGE` | 400 | (existing) | Payload Too Large. | See the app's runbook / logs for the failure detail. |
| `SSRF_VIOLATION` | 400 | (existing) | Ssrf Violation. | See the app's runbook / logs for the failure detail. |

### jobs

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `JOB_RATE_LIMITED` | 429 | (existing) | Job Rate Limited. | See the app's runbook / logs for the failure detail. |
| `PREFECT_SUBMISSION_ORPHAN` | 400 | (existing) | Prefect Submission Orphan. | See the app's runbook / logs for the failure detail. |
| `TIMEOUT` | 504 | (existing) | Timeout. | See the app's runbook / logs for the failure detail. |
| `UNKNOWN_ERROR` | 500 | (existing) | Unknown Error. | See the app's runbook / logs for the failure detail. |

### marketplace

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ASSET_ELIGIBILITY_FAILED` | 500 | (existing) | Asset Eligibility Failed. | See the app's runbook / logs for the failure detail. |
| `ASSET_MISSING` | 400 | (existing) | Asset Missing. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_FORCE_PUBLISH_DENIED` | 403 | (existing) | Compliance Force Publish Denied. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_NOT_ALLOWED_TO_STORE` | 400 | (existing) | Compliance Not Allowed To Store. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_RUN_REQUIRED` | 400 | (existing) | Compliance Run Required. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_THRESHOLD_EXCEEDED` | 400 | (existing) | Compliance Threshold Exceeded. | See the app's runbook / logs for the failure detail. |
| `DUPLICATE_NAME` | 400 | (existing) | Duplicate Name. | See the app's runbook / logs for the failure detail. |
| `INVALID_CONTRACT_TYPE` | 400 | (existing) | Invalid Contract Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_DETAIL` | 400 | (existing) | Invalid Detail. | See the app's runbook / logs for the failure detail. |
| `INVALID_ENTITLEMENT_STATUS` | 400 | (existing) | Invalid Entitlement Status. | See the app's runbook / logs for the failure detail. |
| `INVALID_MAX_DEPTH` | 400 | (existing) | Invalid Max Depth. | See the app's runbook / logs for the failure detail. |
| `INVALID_ORDER_STATUS` | 400 | (existing) | Invalid Order Status. | See the app's runbook / logs for the failure detail. |
| `LISTING_INCOMPLETE` | 400 | (existing) | Listing Incomplete. | See the app's runbook / logs for the failure detail. |
| `LISTING_METADATA_FAILED` | 500 | (existing) | Listing Metadata Failed. | See the app's runbook / logs for the failure detail. |
| `LISTING_PUBLICATION_FAILED` | 500 | (existing) | Listing Publication Failed. | See the app's runbook / logs for the failure detail. |
| `LISTING_UNIQUENESS_FAILED` | 500 | (existing) | Listing Uniqueness Failed. | See the app's runbook / logs for the failure detail. |
| `METADATA_MISSING` | 400 | (existing) | Metadata Missing. | See the app's runbook / logs for the failure detail. |
| `ODPS_LINKING_ERROR` | 500 | (existing) | Odps Linking Error. | See the app's runbook / logs for the failure detail. |
| `ODPS_NORMALIZATION_ERROR` | 500 | (existing) | Odps Normalization Error. | See the app's runbook / logs for the failure detail. |
| `RATE_LIMITED` | 429 | (existing) | Rate Limited. | See the app's runbook / logs for the failure detail. |
| `SELF_ORDER` | 400 | (existing) | Self Order. | See the app's runbook / logs for the failure detail. |
| `STRUCTURELESS_CONTRACT` | 400 | (existing) | Structureless Contract. | See the app's runbook / logs for the failure detail. |
| `TENANT_KYC_NOT_VERIFIED` | 400 | (existing) | Tenant Kyc Not Verified. | See the app's runbook / logs for the failure detail. |
| `TENANT_MISSING` | 400 | (existing) | Tenant Missing. | See the app's runbook / logs for the failure detail. |
| `TRUST_SIGNALS_DISABLED` | 400 | (existing) | Trust Signals Disabled. | See the app's runbook / logs for the failure detail. |

### mesh

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `DOMAIN_NAME_EXISTS` | 400 | (existing) | Domain Name Exists. | See the app's runbook / logs for the failure detail. |

### ml

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `CONFLICT_ERROR` | 500 | (existing) | Conflict Error. | See the app's runbook / logs for the failure detail. |
| `ENTITLEMENT_REQUIRED` | 400 | (existing) | Entitlement Required. | See the app's runbook / logs for the failure detail. |
| `INPUT_VALIDATION_FAILED` | 500 | (existing) | Input Validation Failed. | See the app's runbook / logs for the failure detail. |
| `ML_CONTRACT_CREATION_FAILED` | 500 | (existing) | Ml Contract Creation Failed. | See the app's runbook / logs for the failure detail. |
| `MODEL_DATASET_LINKING_INVALID` | 400 | (existing) | Model Dataset Linking Invalid. | See the app's runbook / logs for the failure detail. |
| `MODEL_LINKING_INVALID` | 400 | (existing) | Model Linking Invalid. | See the app's runbook / logs for the failure detail. |
| `MODEL_SYNC_INVALID` | 400 | (existing) | Model Sync Invalid. | See the app's runbook / logs for the failure detail. |
| `TRAINING_JOB_VALIDATION_FAILED` | 500 | (existing) | Training Job Validation Failed. | See the app's runbook / logs for the failure detail. |

### notifications

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ODPS_NORMALIZATION_ERROR` | 500 | (existing) | Odps Normalization Error. | See the app's runbook / logs for the failure detail. |

### observability

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `INVALID_UUID` | 400 | (existing) | Invalid Uuid. | See the app's runbook / logs for the failure detail. |

### orchestration

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `INVALID_SPEC_FORMAT` | 400 | (existing) | Invalid Spec Format. | See the app's runbook / logs for the failure detail. |
| `MISSING_SOURCES` | 400 | (existing) | Missing Sources. | See the app's runbook / logs for the failure detail. |
| `NO_SOURCES` | 400 | (existing) | No Sources. | See the app's runbook / logs for the failure detail. |
| `QUERY_EXECUTION_FAILED` | 500 | (existing) | Query Execution Failed. | See the app's runbook / logs for the failure detail. |
| `SPARQL_EXECUTION_FAILED` | 500 | (existing) | Sparql Execution Failed. | See the app's runbook / logs for the failure detail. |
| `WORKFLOWS_DISABLED` | 400 | (existing) | Workflows Disabled. | See the app's runbook / logs for the failure detail. |
| `WORKFLOW_NOT_FOUND` | 404 | (existing) | Workflow Not Found. | See the app's runbook / logs for the failure detail. |

### ropa

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `MISSING_PROCESSING_PURPOSES` | 400 | (existing) | Missing Processing Purposes. | See the app's runbook / logs for the failure detail. |
| `MISSING_RECIPIENT_CATEGORIES` | 400 | (existing) | Missing Recipient Categories. | See the app's runbook / logs for the failure detail. |
| `MISSING_RETENTION_POLICY` | 400 | (existing) | Missing Retention Policy. | See the app's runbook / logs for the failure detail. |
| `MISSING_SUBJECT_CATEGORIES` | 400 | (existing) | Missing Subject Categories. | See the app's runbook / logs for the failure detail. |
| `ROPA_DISABLED` | 400 | (existing) | Ropa Disabled. | See the app's runbook / logs for the failure detail. |

### scheduled_export

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ACCESS_DENIED` | 403 | (existing) | Access Denied. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `DEPLOYMENT_NOT_FOUND` | 404 | (existing) | Deployment Not Found. | See the app's runbook / logs for the failure detail. |
| `EXPORT_NOT_ACTIVE` | 400 | (existing) | Export Not Active. | See the app's runbook / logs for the failure detail. |
| `FORBIDDEN` | 400 | (existing) | Forbidden. | See the app's runbook / logs for the failure detail. |
| `IDEMPOTENCY_REQUEST_IN_PROGRESS` | 400 | (existing) | Idempotency Request In Progress. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `INVALID_STATUS` | 400 | (existing) | Invalid Status. | See the app's runbook / logs for the failure detail. |
| `ITEM_NOT_IN_SCOPE` | 400 | (existing) | Item Not In Scope. | See the app's runbook / logs for the failure detail. |
| `ITEM_REQUIRED` | 400 | (existing) | Item Required. | See the app's runbook / logs for the failure detail. |
| `MULTIPLE_ITEMS` | 400 | (existing) | Multiple Items. | See the app's runbook / logs for the failure detail. |
| `TENANT_REQUIRED` | 400 | (existing) | Tenant Required. | See the app's runbook / logs for the failure detail. |
| `TRIGGER_FAILED` | 500 | (existing) | Trigger Failed. | See the app's runbook / logs for the failure detail. |

### scheduled_ingestion

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ASSET_KEY_RETIRED` | 400 | (existing) | Asset Key Retired. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `DEPLOYMENT_NOT_READY` | 400 | (existing) | Deployment Not Ready. | See the app's runbook / logs for the failure detail. |
| `DQ_ERROR` | 500 | (existing) | Dq Error. | See the app's runbook / logs for the failure detail. |
| `DQ_VALIDATION_ERROR` | 500 | (existing) | Dq Validation Error. | See the app's runbook / logs for the failure detail. |
| `FORBIDDEN` | 400 | (existing) | Forbidden. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `SCHEMA_INCOMPATIBLE` | 400 | (existing) | Schema Incompatible. | See the app's runbook / logs for the failure detail. |
| `TENANT_REQUIRED` | 400 | (existing) | Tenant Required. | See the app's runbook / logs for the failure detail. |
| `TRIGGER_FAILED` | 500 | (existing) | Trigger Failed. | See the app's runbook / logs for the failure detail. |

### search

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `CROSS_TENANT_FORBIDDEN` | 403 | (existing) | Cross Tenant Forbidden. | See the app's runbook / logs for the failure detail. |
| `INVALID_INPUT` | 400 | (existing) | Invalid Input. | See the app's runbook / logs for the failure detail. |
| `QUERY_REQUIRED` | 400 | (existing) | The `q` query parameter is required — an empty query is rejected rather than matching everything. | Supply a non-empty `q`. |
| `QUERY_TOO_LONG` | 400 | (existing) | Query Too Long. | See the app's runbook / logs for the failure detail. |
| `SEARCH_VALIDATION_FAILED` | 500 | (existing) | Search Validation Failed. | See the app's runbook / logs for the failure detail. |
| `TENANT_REQUIRED` | 400 | (existing) | Tenant Required. | See the app's runbook / logs for the failure detail. |

### semantic

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `CROSS_TENANT_FORBIDDEN` | 403 | (existing) | Cross Tenant Forbidden. | See the app's runbook / logs for the failure detail. |
| `DUPLICATE_ENDPOINT_URL` | 400 | (existing) | Duplicate Endpoint Url. | See the app's runbook / logs for the failure detail. |
| `EXPORT_FORMAT_INVALID` | 400 | (existing) | Export Format Invalid. | See the app's runbook / logs for the failure detail. |
| `FEDERATION_TIMEOUT` | 504 | (existing) | Federation Timeout. | See the app's runbook / logs for the failure detail. |
| `INTERNAL_ERROR` | 500 | (existing) | Internal Error. | See the app's runbook / logs for the failure detail. |
| `INVALID_FIELD_ID` | 400 | (existing) | Invalid Field Id. | See the app's runbook / logs for the failure detail. |
| `INVALID_RESOURCE_TYPE` | 400 | (existing) | Invalid Resource Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_UUID` | 400 | (existing) | Invalid Uuid. | See the app's runbook / logs for the failure detail. |
| `LDN_AUTH_FAILED` | 500 | (existing) | Ldn Auth Failed. | See the app's runbook / logs for the failure detail. |
| `LDN_PAYLOAD_TOO_LARGE` | 400 | (existing) | Ldn Payload Too Large. | See the app's runbook / logs for the failure detail. |
| `LDN_RATE_LIMITED` | 429 | (existing) | Ldn Rate Limited. | See the app's runbook / logs for the failure detail. |
| `ONTOLOGY_NAMESPACE_DUPLICATE` | 400 | (existing) | Ontology Namespace Duplicate. | See the app's runbook / logs for the failure detail. |
| `ONTOLOGY_NAME_OR_NAMESPACE_DUPLICATE` | 400 | (existing) | Ontology Name Or Namespace Duplicate. | See the app's runbook / logs for the failure detail. |
| `ONTOLOGY_PARSE_ERROR` | 500 | (existing) | Ontology Parse Error. | See the app's runbook / logs for the failure detail. |
| `ONTOLOGY_RESERVED_NAMESPACE` | 400 | (existing) | Ontology Reserved Namespace. | See the app's runbook / logs for the failure detail. |
| `ONTOLOGY_TOO_LARGE` | 400 | (existing) | Ontology Too Large. | See the app's runbook / logs for the failure detail. |
| `ONTOLOGY_TOO_MANY_TRIPLES` | 400 | (existing) | Ontology Too Many Triples. | See the app's runbook / logs for the failure detail. |
| `ONTOLOGY_UNSUPPORTED_FORMAT` | 400 | (existing) | Ontology Unsupported Format. | See the app's runbook / logs for the failure detail. |
| `RESOURCE_NOT_FOUND` | 404 | (existing) | Resource Not Found. | See the app's runbook / logs for the failure detail. |
| `SEMANTIC_FEATURE_DISABLED` | 400 | (existing) | Semantic Feature Disabled. | See the app's runbook / logs for the failure detail. |
| `SEMANTIC_SERVICE_UNAVAILABLE` | 400 | (existing) | Semantic Service Unavailable. | See the app's runbook / logs for the failure detail. |
| `SERVICE_ERROR` | 500 | (existing) | Service Error. | See the app's runbook / logs for the failure detail. |
| `SERVICE_UNAVAILABLE` | 400 | (existing) | Service Unavailable. | See the app's runbook / logs for the failure detail. |
| `SPARQL_FEDERATION_NOT_ALLOWED` | 400 | (existing) | Sparql Federation Not Allowed. | See the app's runbook / logs for the failure detail. |
| `TENANT_REQUIRED` | 400 | (existing) | Tenant Required. | See the app's runbook / logs for the failure detail. |

### social

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ALREADY_MEMBER` | 400 | (existing) | Already Member. | See the app's runbook / logs for the failure detail. |
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `COMMUNITY_NOT_FOUND` | 404 | (existing) | Community Not Found. | See the app's runbook / logs for the failure detail. |
| `DUPLICATE_COMMUNITY_NAME` | 400 | (existing) | Duplicate Community Name. | See the app's runbook / logs for the failure detail. |
| `PARENT_COMMENT_NOT_FOUND` | 404 | (existing) | Parent Comment Not Found. | See the app's runbook / logs for the failure detail. |

### tenants

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `ADMIN_EMAIL_DUPLICATE` | 400 | (existing) | Admin Email Duplicate. | See the app's runbook / logs for the failure detail. |
| `ALREADY_DELETED` | 400 | (existing) | Already Deleted. | See the app's runbook / logs for the failure detail. |
| `ALREADY_ENDED` | 400 | (existing) | Already Ended. | See the app's runbook / logs for the failure detail. |
| `DATASETS_DISABLED` | 400 | (existing) | Datasets Disabled. | See the app's runbook / logs for the failure detail. |
| `DSAR_RESTRICTION_ACTIVE` | 400 | (existing) | Dsar Restriction Active. | See the app's runbook / logs for the failure detail. |
| `DUPLICATE_SLUG` | 400 | (existing) | Duplicate Slug. | See the app's runbook / logs for the failure detail. |
| `EMAIL_EXISTS` | 400 | (existing) | Email Exists. | See the app's runbook / logs for the failure detail. |
| `FILES_DISABLED` | 400 | (existing) | Files Disabled. | See the app's runbook / logs for the failure detail. |
| `IMPERSONATION_NOT_ENABLED` | 400 | (existing) | Impersonation Not Enabled. | See the app's runbook / logs for the failure detail. |
| `INVALID_REQUEST` | 400 | (existing) | Invalid Request. | See the app's runbook / logs for the failure detail. |
| `LEGAL_HOLD_ACTIVE` | 400 | (existing) | Legal Hold Active. | See the app's runbook / logs for the failure detail. |
| `MAX_MINUTES_OUT_OF_RANGE` | 400 | (existing) | Max Minutes Out Of Range. | See the app's runbook / logs for the failure detail. |
| `PLAN_NOT_FOUND` | 404 | (existing) | Plan Not Found. | See the app's runbook / logs for the failure detail. |
| `SELF_APPROVAL_FORBIDDEN` | 403 | (existing) | Self Approval Forbidden. | See the app's runbook / logs for the failure detail. |
| `SESSION_ID_MISMATCH` | 400 | (existing) | Session Id Mismatch. | See the app's runbook / logs for the failure detail. |
| `SLUG_EXISTS` | 400 | (existing) | Slug Exists. | See the app's runbook / logs for the failure detail. |
| `TARGET_HAS_NO_TENANT` | 400 | (existing) | Target Has No Tenant. | See the app's runbook / logs for the failure detail. |
| `TARGET_INACTIVE` | 400 | (existing) | Target Inactive. | See the app's runbook / logs for the failure detail. |
| `TARGET_IS_PLATFORM_ADMIN` | 400 | (existing) | Target Is Platform Admin. | See the app's runbook / logs for the failure detail. |
| `TAX_ID_INPUT_INVALID` | 400 | (existing) | Tax Id Input Invalid. | See the app's runbook / logs for the failure detail. |
| `TAX_ID_SUBMISSION_FAILED` | 500 | (existing) | Tax Id Submission Failed. | See the app's runbook / logs for the failure detail. |
| `TENANT_CREATE_COLLISION` | 400 | (existing) | Tenant Create Collision. | See the app's runbook / logs for the failure detail. |
| `TENANT_DELETED` | 400 | (existing) | Tenant Deleted. | See the app's runbook / logs for the failure detail. |
| `TENANT_NOT_FOUND` | 404 | (existing) | Tenant Not Found. | See the app's runbook / logs for the failure detail. |
| `TENANT_NOT_SUSPENDED` | 400 | (existing) | Tenant Not Suspended. | See the app's runbook / logs for the failure detail. |
| `TENANT_SLUG_DUPLICATE` | 400 | (existing) | Tenant Slug Duplicate. | See the app's runbook / logs for the failure detail. |
| `UNKNOWN_FLAG` | 400 | (existing) | Unknown Flag. | See the app's runbook / logs for the failure detail. |

### transformation

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `COMPENSATION_COMPLETED` | 400 | (existing) | Compensation Completed. | See the app's runbook / logs for the failure detail. |

### users

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `EMAIL_EXISTS` | 400 | (existing) | Email Exists. | See the app's runbook / logs for the failure detail. |
| `USER_ALREADY_EXISTS` | 400 | (existing) | User Already Exists. | See the app's runbook / logs for the failure detail. |

### virtualization

| Code | HTTP status | Phase | Meaning | Remediation |
|---|---|---|---|---|
| `BUSINESS_RULES_VALIDATION` | 400 | (existing) | Business Rules Validation. | See the app's runbook / logs for the failure detail. |
| `COMPLIANCE_VIOLATION` | 400 | (existing) | Compliance Violation. | See the app's runbook / logs for the failure detail. |
| `CROSS_TENANT_ACCESS_DENIED` | 403 | (existing) | Cross Tenant Access Denied. | See the app's runbook / logs for the failure detail. |
| `CSV_PARSE_ERROR` | 500 | (existing) | Csv Parse Error. | See the app's runbook / logs for the failure detail. |
| `DANGEROUS_SPARQL_OPERATION` | 400 | (existing) | Dangerous Sparql Operation. | See the app's runbook / logs for the failure detail. |
| `DANGEROUS_SQL_OPERATION` | 400 | (existing) | Dangerous Sql Operation. | See the app's runbook / logs for the failure detail. |
| `DATASET_CREATION_FAILED` | 500 | (existing) | Dataset Creation Failed. | See the app's runbook / logs for the failure detail. |
| `DATASET_NOT_ACTIVE` | 400 | (existing) | Dataset Not Active. | See the app's runbook / logs for the failure detail. |
| `EMPTY_QUERY` | 400 | (existing) | Empty Query. | See the app's runbook / logs for the failure detail. |
| `EXECUTION_CANNOT_BE_CANCELLED` | 400 | (existing) | Execution Cannot Be Cancelled. | See the app's runbook / logs for the failure detail. |
| `EXECUTION_ID_MISMATCH` | 400 | (existing) | Execution Id Mismatch. | See the app's runbook / logs for the failure detail. |
| `EXECUTION_NOT_COMPLETED` | 400 | (existing) | Execution Not Completed. | See the app's runbook / logs for the failure detail. |
| `EXTERNAL_RESOURCE_DOWNLOAD_FAILED` | 500 | (existing) | External Resource Download Failed. | See the app's runbook / logs for the failure detail. |
| `EXTERNAL_RESOURCE_NOT_FOUND` | 404 | (existing) | External Resource Not Found. | See the app's runbook / logs for the failure detail. |
| `FEDERATED_ASSET_QUERY_FAILED` | 500 | (existing) | Federated Asset Query Failed. | See the app's runbook / logs for the failure detail. |
| `FORBIDDEN_SPARQL_KEYWORD` | 400 | (existing) | Forbidden Sparql Keyword. | See the app's runbook / logs for the failure detail. |
| `FORBIDDEN_SQL_KEYWORD` | 400 | (existing) | Forbidden Sql Keyword. | See the app's runbook / logs for the failure detail. |
| `GRAPHQL_EXECUTION_FAILED` | 500 | (existing) | Graphql Execution Failed. | See the app's runbook / logs for the failure detail. |
| `INVALID_ASSET_ID` | 400 | (existing) | Invalid Asset Id. | See the app's runbook / logs for the failure detail. |
| `INVALID_ASSET_TYPE` | 400 | (existing) | Invalid Asset Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_CACHE_CONFIG` | 400 | (existing) | Invalid Cache Config. | See the app's runbook / logs for the failure detail. |
| `INVALID_CACHING_CONFIGURATION` | 400 | (existing) | Invalid Caching Configuration. | See the app's runbook / logs for the failure detail. |
| `INVALID_CROSS_SOURCE_COMPATIBILITY` | 400 | (existing) | Invalid Cross Source Compatibility. | See the app's runbook / logs for the failure detail. |
| `INVALID_FEDERATED_EXECUTION` | 400 | (existing) | Invalid Federated Execution. | See the app's runbook / logs for the failure detail. |
| `INVALID_JSON_STRUCTURE` | 400 | (existing) | Invalid Json Structure. | See the app's runbook / logs for the failure detail. |
| `INVALID_PAGINATION` | 400 | (existing) | Invalid Pagination. | See the app's runbook / logs for the failure detail. |
| `INVALID_QUERY_LANGUAGE_COMPATIBILITY` | 400 | (existing) | Invalid Query Language Compatibility. | See the app's runbook / logs for the failure detail. |
| `INVALID_QUERY_MAPPING` | 400 | (existing) | Invalid Query Mapping. | See the app's runbook / logs for the failure detail. |
| `INVALID_QUERY_SYNTAX` | 400 | (existing) | Invalid Query Syntax. | See the app's runbook / logs for the failure detail. |
| `INVALID_QUERY_TYPE` | 400 | (existing) | Invalid Query Type. | See the app's runbook / logs for the failure detail. |
| `INVALID_SCHEMA_ALIGNMENT` | 400 | (existing) | Invalid Schema Alignment. | See the app's runbook / logs for the failure detail. |
| `INVALID_SCHEMA_FORMAT` | 400 | (existing) | Invalid Schema Format. | See the app's runbook / logs for the failure detail. |
| `INVALID_SOURCE_COMPATIBILITY` | 400 | (existing) | Invalid Source Compatibility. | See the app's runbook / logs for the failure detail. |
| `INVALID_SOURCE_CONFIG` | 400 | (existing) | Invalid Source Config. | See the app's runbook / logs for the failure detail. |
| `INVALID_SOURCE_CONFIGURATION` | 400 | (existing) | Invalid Source Configuration. | See the app's runbook / logs for the failure detail. |
| `INVALID_SOURCE_CONNECTION` | 400 | (existing) | Invalid Source Connection. | See the app's runbook / logs for the failure detail. |
| `INVALID_SPARQL_STRUCTURE` | 400 | (existing) | Invalid Sparql Structure. | See the app's runbook / logs for the failure detail. |
| `INVALID_SPARQL_SYNTAX` | 400 | (existing) | Invalid Sparql Syntax. | See the app's runbook / logs for the failure detail. |
| `INVALID_SQL_STRUCTURE` | 400 | (existing) | Invalid Sql Structure. | See the app's runbook / logs for the failure detail. |
| `INVALID_SQL_SYNTAX` | 400 | (existing) | Invalid Sql Syntax. | See the app's runbook / logs for the failure detail. |
| `INVALID_STORAGE_FORMAT` | 400 | (existing) | Invalid Storage Format. | See the app's runbook / logs for the failure detail. |
| `INVALID_TIMEOUT` | 504 | (existing) | Invalid Timeout. | See the app's runbook / logs for the failure detail. |
| `JSON_PARSE_ERROR` | 500 | (existing) | Json Parse Error. | See the app's runbook / logs for the failure detail. |
| `MISSING_ASSET_ID` | 400 | (existing) | Missing Asset Id. | See the app's runbook / logs for the failure detail. |
| `MISSING_DATABASE_CONFIG` | 400 | (existing) | Missing Database Config. | See the app's runbook / logs for the failure detail. |
| `MISSING_DEPENDENCY` | 400 | (existing) | Missing Dependency. | See the app's runbook / logs for the failure detail. |
| `MISSING_GRAPHQL_CONFIG` | 400 | (existing) | Missing Graphql Config. | See the app's runbook / logs for the failure detail. |
| `MISSING_RESOURCE_CONFIG` | 400 | (existing) | Missing Resource Config. | See the app's runbook / logs for the failure detail. |
| `MISSING_RESOURCE_ID` | 400 | (existing) | Missing Resource Id. | See the app's runbook / logs for the failure detail. |
| `MISSING_REST_CONFIG` | 400 | (existing) | Missing Rest Config. | See the app's runbook / logs for the failure detail. |
| `MISSING_TENANT_ID` | 400 | (existing) | Missing Tenant Id. | See the app's runbook / logs for the failure detail. |
| `MISSING_USER_ID` | 400 | (existing) | Missing User Id. | See the app's runbook / logs for the failure detail. |
| `NO_RESOURCES_AVAILABLE` | 400 | (existing) | No Resources Available. | See the app's runbook / logs for the failure detail. |
| `NO_SOURCES` | 400 | (existing) | No Sources. | See the app's runbook / logs for the failure detail. |
| `PARQUET_PARSE_ERROR` | 500 | (existing) | Parquet Parse Error. | See the app's runbook / logs for the failure detail. |
| `QUERY_EXECUTION_ERROR` | 500 | (existing) | Query Execution Error. | See the app's runbook / logs for the failure detail. |
| `QUERY_OPTIMIZATION_FAILED` | 500 | (existing) | Query Optimization Failed. | See the app's runbook / logs for the failure detail. |
| `RESOURCE_NOT_ACCESSIBLE` | 400 | (existing) | Resource Not Accessible. | See the app's runbook / logs for the failure detail. |
| `REST_EXECUTION_FAILED` | 500 | (existing) | Rest Execution Failed. | See the app's runbook / logs for the failure detail. |
| `RESULTS_NOT_FOUND` | 404 | (existing) | Results Not Found. | See the app's runbook / logs for the failure detail. |
| `SOURCE_ASSET_NOT_FOUND` | 404 | (existing) | Source Asset Not Found. | See the app's runbook / logs for the failure detail. |
| `SOURCE_CONNECTIVITY_ERROR` | 500 | (existing) | Source Connectivity Error. | See the app's runbook / logs for the failure detail. |
| `SOURCE_CONNECTIVITY_FAILED` | 500 | (existing) | Source Connectivity Failed. | See the app's runbook / logs for the failure detail. |
| `SOURCE_EXECUTION_FAILED` | 500 | (existing) | Source Execution Failed. | See the app's runbook / logs for the failure detail. |
| `SPARQL_EXECUTION_FAILED` | 500 | (existing) | Sparql Execution Failed. | See the app's runbook / logs for the failure detail. |
| `SQL_SAFETY_REJECTED` | 400 | W7.4 | SQL Safety Rejected. The submitted SQL failed the warehouse safety validation gate. | Rewrite the query within the allowed operations; see the DQ runbook. |
| `SQL_EXECUTION_FAILED` | 500 | (existing) | Sql Execution Failed. | See the app's runbook / logs for the failure detail. |
| `STORAGE_SIZE_CHECK_FAILED` | 502 | W7.4 | Storage Size Check Failed. The stored object's size does not match the uploaded metadata. | Re-upload the object; see the files runbook. |
| `STORAGE_VERIFICATION_FAILED` | 502 | W7.4 | Storage Verification Failed. The stored object's checksum does not match the uploaded metadata. | Re-upload the object; see the files runbook. |
| `STORAGE_RETRIEVAL_FAILED` | 500 | (existing) | Storage Retrieval Failed. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_DATABASE_TYPE` | 400 | (existing) | Unsupported Database Type. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_FILE_FORMAT` | 400 | (existing) | Unsupported File Format. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_FORMAT` | 400 | (existing) | Unsupported Format. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_HTTP_METHOD` | 400 | (existing) | Unsupported Http Method. | See the app's runbook / logs for the failure detail. |
| `UNSUPPORTED_QUERY_TYPE` | 400 | (existing) | Unsupported Query Type. | See the app's runbook / logs for the failure detail. |

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
