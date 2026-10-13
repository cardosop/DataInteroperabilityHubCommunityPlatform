# Databricks Control Plane — Operator Guide

Bring-your-own (BYO) Databricks workspace operations guide: what the Hub
can do with a registered Databricks estate, how each control-plane
surface works, and where its operations runbooks live. Tenants register
their existing workspaces (registration-first — the Hub never
provisions by default); the Hub then manages the workspace estate
through the version-pinned Databricks APIs with per-tenant isolation
(RLS) and per-tenant circuit breakers.

## The control-plane surfaces (P0–P9)

### P0 — Control-plane foundation

Workspace registration and the transport layer everything else rides on.

- **Workspace registry** — `POST /api/v1/databricks/workspaces/` (create/list/detail, TENANT_ADMIN) with the SSRF + residency validation (`hub/apps/databricks_admin/validation.py` — the host must be on an allowed family: `.cloud.databricks.com`, `.azuredatabricks.net`, `.gcp.databricks.com`, `.databricks.us`); `{id}/test/` probes the live workspace. The registration wizard lives in the frontend `WorkspaceManagementPage`.
- **Credentials** — `DatabricksCredential` per workspace, `auth_mode` `PAT` or `OAUTH_M2M`, config encrypted at rest (`hub/apps/integrations/encryption.py`); `POST /api/v1/databricks/workspaces/{id}/credentials/{cid}/rotate/` rotates (PAT: token-management on-behalf-of + delete-old).
- **Transport** — `DatabricksApiClient` (`hub/apps/databricks_admin/client.py`): retries with exponential backoff, circuit breaker channel `databricks_admin_{tenant_id}`, error classification. SQL statements run through `SqlStatementExecutor` (`hub/apps/databricks_admin/sql_statements.py`).
- **Egress** — the platform's warehouse egress allowlist (`helm/templates/networkpolicy/allow-warehouse-egress.yaml`) covers the allowed Databricks host families; see [RB-SEC-003](../runbooks/RB-SEC-003-databricks-egress-credential-rotation.md).

### P0b — BYO identity (SSO / OBO)

Sign-in with Databricks (OAuth **App connection**), on-behalf-of token
vaulting, hybrid identity enforcement, and the GCP fallback. The
customer-side setup steps are below — **App connection registration**
and the **GCP fallback** sections.

### P1 — Unity Catalog read

- **Mirror models** — `UCCatalog` / `UCSchema` / `UCTable` / `UCView` / `UCVolume` / `UCExternalLocation` / `UCStorageCredential` / `UCModel` (tenant-scoped, RLS).
- **Browse** — `GET /api/v1/databricks/workspaces/{id}/uc/...` including table detail with columns and effective permissions; the frontend CatalogBrowserPage.
- **Search + lineage** — the UC search API feeds the Hub search index; a delta-diff metadata sync job (`JobType.DATABRICKS_UC_METADATA_SYNC`) keeps the mirror fresh; lineage-tracking reads land in `contracts/lineage_sync.py`.
- **Version pins** — every Databricks call resolves through `hub/apps/databricks_admin/api_paths.py` (2.0 vs 2.1 per-call pins, enforced at import time).

### P2 — Unity Catalog write

- **Change requests** — `UCChangeRequest` state machine (`DRAFT → PENDING_APPROVAL → APPROVED → EXECUTING → EXECUTED / FAILED / ROLLED_BACK`) with multi-step approval chains.
- **Executor** — `UCChangeExecutor`: REST DDL (catalogs/schemas/tables/views/MVs/streaming tables/volumes/external locations/storage credentials/models) + SQL DDL; a denylist (`DROP CATALOG` flag-gated), identifier validation, and idempotent existence checks.
- **Grants** — `UCPPrincipal`/`UCGrantBinding`: ABAC plan → diff → apply (REST PATCH, SQL fallback) → verify; never OWNERSHIP.

### P3 — SQL warehouses

- `DatabricksSqlWarehouse` mirror with live state refresh; `GET /api/v1/databricks/workspaces/{id}/sql-warehouses/` + `{warehouse_id}/start|stop/`.
- The frontend workspace + warehouse picker replaces the legacy free-text `http_path` for Databricks sources (the derived `/sql/1.0/warehouses/{id}` path is what the backend accepts).

### P4 — Jobs

- `DatabricksJob` / `DatabricksJobRun` over the version-pinned `/api/2.1/jobs/*` surface; the Hub's reads at `GET /api/v1/databricks/workspaces/{id}/jobs/` + `{job_id}/runs/`.
- Run-now dispatches a Hub `Job` (`JobType.DATABRICKS_JOB_RUN`) with a poller to terminal state, audit events, OpenLineage, and a duration×size cost estimate. Webhook `databricks.job.run.failed`; task allowlist enforced (Spark SQL / notebook / SQL warehouse; Python flag-gated).

### P5 — Delta Sharing server

- Native Delta Sharing 1.0 endpoints served by the Hub: profile, shares, schemas, tables, metadata, query (JSON), data (Parquet snapshot/presigned URL) — see `hub/apps/databricks_admin/delta_sharing_views.py`.
- `DeltaShareRecipient` / `DeltaShareToken` (hashed, per-recipient-token throttling); the `DATABRICKS_DELTA_SHARE_SNAPSHOT` job refreshes TTL-bound snapshots. The `delta-sharing` python package is a dev-only protocol oracle.

### P6 — DLT movement

- dlt-based export/ingestion dispatched from the worker-run lifecycles (`execute_dlt_export` / `execute_dlt_ingestion`); managed-volume staging is the default (`staging_volume_name`, auto `_dlt_staging_load_volume`); S3 external-location staging is tenant opt-in.
- Per-tenant staging schema + scoped write credential; the read-only guard is bypassed only inside the pipeline; pre-export ODCS contract validation.

### P7 — Cost guardrails

- `DatabricksCostBudget` / `DatabricksCostLedger`; the hourly `system.billing.usage` sync (`JobType.DATABRICKS_COST_SYNC`) is the truth source.
- Redis rolling-window enforcement — BLOCK (HTTP 429 + `WAREHOUSE_COST_BUDGET_EXCEEDED`) vs ALERT; webhook `databricks.budget.exceeded`; the budget page shows the progress bar.

### P8 — Account plane

- `DatabricksAccount` (platform table, admin-DB access per the tenant-isolation conventions); metastore ops + workspace provisioning via the account API (flag-gated `workspace_provisioning` — DPO/Legal signoff required); cross-tenant estate summary at `GET /api/v1/databricks/estate-summary/`.

### P9 — Live CI sandbox

- The env-gated nightly workflow `.github/workflows/databricks-e2e-nightly.yml` provisions a disposable `meshant_e2e_*` workspace, runs the control-plane journey + contract suites (`tests/integration/databricks_e2e/`) with a hard budget pre-flight (`scripts/databricks_e2e/budget.py`), and auto-destroys the sandbox in an `always()` step (`scripts/databricks_e2e/sandbox.py`).
- The gate is the repository variable `DATABRICKS_E2E=1` plus the OIDC-federated `DATABRICKS_E2E_*` secrets in the `databricks-e2e` GitHub Environment; the run's `report/e2e_report.json` is the PASS/FAIL evidence.
- Operations: [RB-SEC-003](../runbooks/RB-SEC-003-databricks-egress-credential-rotation.md) (egress allowlist, OIDC trust setup, rotation cadence) and [REAL_MARKETPLACE_E2E](../runbooks/REAL_MARKETPLACE_E2E.md) (the marketplace connector E2E record — the Databricks row is the nightly workflow's PASS evidence).

## App connection registration (0b.9)

Sign-in with Databricks uses an OAuth **App connection** registered in
the customer's Databricks account console. Register it once per
workspace (or per account, if Databricks supports account-level apps for
your plan):

1. **Open the account console** — In the Databricks account console, go
   to **Settings → App connections** and click **Add app connection**.
   (On some plans this lives under the workspace admin settings —
   **Settings → Developer → OAuth apps**.)
2. **Name the app** — e.g. `Meshant Hub`.
3. **Set the redirect URI** — the Hub's SSO callback:
   `https://<your-hub-host>/auth/databricks/callback`
   (this is the `redirect_uri` the Hub registers in the workspace's SSO
   config; the browser must be able to reach your Hub host).
4. **Choose the scopes** — select exactly:
   - `sql` — run SQL statements on the user's behalf,
   - `all-apis` — call Databricks REST APIs on the user's behalf,
   - `offline_access` — receive a refresh token so the Hub can keep the
     user's session working without re-prompting,
   - (optional) `openid`, `email`, `profile` — identity scopes; the Hub
     appends these only when the tenant enables
     `include_openid_scopes`.
5. **Copy the client id** — the generated OAuth **client id** goes into
   the workspace's SSO config (`sso_config.databricks.client_id`). Keep
   the client secret in the Databricks console — the Hub's
   authorization-code flow never needs it.
6. **Token TTLs** (Databricks defaults, verify against your account):
   - access token: **1 hour** — the Hub silently refreshes at **half**
     the TTL using the refresh token and caches the new access token
     with a TTL that never exceeds the real expiry;
   - refresh token: Databricks rotates it on every use; the Hub stores
     only the latest one, encrypted at rest;
   - absolute session lifetime: near the workspace's configured absolute
     lifetime the Hub shows a non-blocking **countdown** (default
     **5 minutes**) and stops refreshing — the user signs in again,
     which rebinds the (user, workspace) token pair. The Hub session
     itself is never invalidated by Databricks token expiry.

## GCP fallback (0b.8)

Google Cloud Databricks workspaces do **not** support user-to-machine
(U2M) OAuth SSO. On GCP:

- "Sign in with Databricks" is unavailable — an SSO attempt surfaces
  `DATABRICKS_SSO_UNAVAILABLE` (HTTP 400), and GCP workspaces are
  excluded from the sign-in workspace chooser.
- Execution falls back to the workspace's **PAT / OAuth M2M** service
  credential on interactive paths too — the D12 identity decision point
  resolves the credential directly (fail-closed when none is registered).
- The Hub session is unaffected; only the Databricks identity mechanism
  changes.

Register at least one PAT or OAuth M2M credential for every GCP
workspace you add to the Hub.

## CLI (datahub)

Every control-plane surface the API exposes has a `datahub databricks`
command that issues the SAME endpoints the frontend uses
(`cli/datahub_cli/commands/databricks.py`; the route↔command parity map
is pinned by `cli/tests/unit/test_commands_databricks_parity.py`).
Mirror-first reads are tenant-scoped by the backend's RLS; the CLI
never echoes credential material (the backend returns metadata only).

```text
datahub databricks workspaces register|list|test|rotate|delete
datahub databricks workspaces credentials ls|add <workspace-id>
datahub databricks uc ls|table|external-locations|storage-credentials
datahub databricks uc changes list|inbox|show|create|submit|approve|reject|timeline|comment
datahub databricks warehouses ls|start|stop
datahub databricks jobs list|runs
datahub databricks budgets list
datahub databricks dlt list|create|update|delete|start|stop
datahub databricks ml models|register-model|log-version|alias|feature-tables|feature-tag|serving-endpoints|vector-endpoints
datahub databricks accounts list|create|metastores|provision-workspace|estate
datahub databricks sso workspaces|login-url|session
```

Notes:

- `uc changes create`, `accounts create`, `dlt create/update`, and the
  `ml ... create/register` commands take a `--file` JSON payload — the
  server's guards validate it (the 2.4 denylist + identifier rules for
  UC changes; the 10.4 chain for DLT).
- The account plane (`accounts`, `estate`) is PLATFORM_ADMIN-only — a
  tenant admin gets the classified `PERMISSION_DENIED`.
- The SSO surface is AllowAny and resolves the tenant from the query
  string: `sso workspaces` and `sso login-url` require `--tenant`. The
  OAuth callback itself is a browser redirect flow — not a CLI command.
- `workspaces delete`, `dlt delete`, and `ml serving-endpoints delete`
  prompt for confirmation.
- Real-API coverage lives in
  `cli/tests/integration/test_databricks_parity_real_api.py` (W16-gated:
  CI raises when the stack is unreachable, local runs skip).

## Operations runbooks

- [RB-SEC-003 — Databricks egress + credential rotation](../runbooks/RB-SEC-003-databricks-egress-credential-rotation.md) — egress allowlist, the nightly OIDC trust setup, rotation cadence.
- [RB-SEC-001 — Credential rotation](../runbooks/RB-SEC-001-credential-rotation.md) — the platform-wide credential rotation procedures (INTERNAL_API_KEY, warehouse credentials, webhook keys).
- [REAL_MARKETPLACE_E2E](../runbooks/REAL_MARKETPLACE_E2E.md) — real marketplace E2E validation records; the Databricks row is the nightly workflow's PASS evidence.
