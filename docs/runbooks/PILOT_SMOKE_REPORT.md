# Pilot Live-Verification Smoke Report

- **Pass date:** 2026-10-05
- **Account class:** Databricks FREE EDITION (P1 dev) + AWS account
  REDACTED-ACCOUNT-ID (C1 redaction — the identifier lives only in the
  gitignored `.env.test`)
- **Change:** `openspec/changes/pilot-readiness` — task 2.3 execution
- **Masked-reporting contract:** this report contains NO credential
  material — no tokens, secrets, keys, account identifiers, or raw
  response bodies. Failure classes are named, values never are.
  Enforced by `scripts/check_smoke_report.py` (GATE-44).

## Exercised paths

| # | Surface / path | What ran | Result |
|---|---|---|---|
| 1 | `GET https://<host>/api/2.0/clusters/list` (workspace PAT) | verify-pilot-creds `databricks` probe | PASS (PAT) |
| 2 | `POST https://<host>/oidc/v1/token` (client_credentials, scope=all-apis) + probe | verify-pilot-creds M2M leg | PASS (M2M) |
| 3 | `GET /api/2.0/sql/warehouses/{id}` (state) | verify-pilot-creds `warehouse` probe | PASS (state=STOPPED; no compute started) |
| 4 | `POST /api/2.0/sql/warehouses/{id}/start` | warehouse live classes' start flow | 401 — ADVISORY (see mismatches #3) |
| 5 | AWS STS `GetCallerIdentity` | verify-pilot-creds `aws` probe | PASS (account=REDACTED-ACCOUNT-ID) |
| 6 | S3 write/delete roundtrip (`.datahub-pilot-probe/`) | verify-pilot-creds `dlt` probe vs MinIO | PASS |
| 7 | Account token endpoint (workspace SP) + workspace budget surfaces ×3 | verify-pilot-creds `budgets` probe | 400 / 404 ×3 → declared RESCOPE (see mismatches #1) |
| 8 | `make test-connectors-e2e` (marketplace connectors) | full suite in the API container | 12 skipped / 0 failed, exit 0 (credential-gated) |
| 9 | `TestDatabricksLiveIntegration` — `SELECT 1` + `reflect_schema` | live warehouse classes vs the real workspace | 2 passed (real SQL executed) |
| 10 | `execute_dlt_ingestion` (DATABRICKS_SOURCE): bounded SELECT `samples.nyctaxi.trips` → dlt → `s3://hub-files` | real ingest spine | files_processed=1, datasets_created=1, error=null |
| 11 | `dbt run` (dbt-databricks 1.12.6) → view `workspace.pilot_dbt_23.pilot_smoke` | real transformation vs the live workspace | PASS=1 ERROR=0 (trip_count=21932) |
| 12 | `DatabricksCostLedger` row for the executed SELECT | cost-recording seam | 1 row: source=query, units=2.459955 dbu |

## Results summary

- Credential gate: 4×PASS + 1 declared RESCOPE, exit 0.
- Warehouse live classes: 2/2 passed (both previously skip/fail classes
  now green — see mismatches #3).
- One real ingest end-to-end: live workspace read → dlt load → MinIO
  dataset → pipeline state object verified in the bucket.
- One real dbt transformation: view materialized and read back on the
  customer workspace.
- Cost ledger: one row per executed query, tenant-scoped, quantized
  (round-half-up) to the field precision.

## API-shape mismatches

1. **No account plane (free edition).** The account token endpoint
   rejects every workspace principal (HTTP 400); all three workspace
   budget surfaces (`/api/2.0/budgets/limits`, `/api/2.0/budgets`,
   `/api/2.1/budgets`) return 404. Classified STOP-THE-LINE; product
   owner re-scoped the guardrail: declared RESCOPE
   (`free-edition-no-billing`) for this account; a PAID account must
   show real budget policies.
2. **`spark.databricks.queryTag.*` session keys rejected**
   (`CONFIG_NOT_AVAILABLE.WITHOUT_SUGGESTION`, SQLSTATE 42K0I). Fixed
   with the explicit `session_tags_enabled: false` connection-config
   opt-out (observability remains default-on).
3. **Warehouse start endpoint 401 while SQL connect works.** The
   explicit start is denied by account policy, but direct SQL connects
   auto-resume the serverless warehouse. The live tests now treat the
   start outcome as advisory; the bounded connect is the verdict.
4. **Catalog layout differs from the code's assumptions.** `samples`
   is read-only (`PERMISSION_DENIED: CREATE SCHEMA`), catalog `main`
   does not exist (`NO_SUCH_CATALOG_EXCEPTION`); the writable catalog
   is `workspace` — live dbt profiles must target it.
5. **Real cost values exceed the ledger field's 6 decimal places.**
   The ledger write now quantizes round-half-up instead of dropping
   the row.
6. **`s3://` dlt destinations require `s3fs`** — added to
   requirements.txt and the API test image rebuilt.

## Gaps

- **Marketplace connector E2E**: Dados.gov.br and Snowflake remain
  credential-gated (12 skips) — their acquisition is a product-owner
  scope decision, not a code gap.
- **dbt-as-job dispatch** (the transformation facade) requires
  Databricks Jobs compute, which the free tier does not offer; the
  real venv `dbt run` above is the transformation evidence for this
  account class.
- **CI nightly arm**: pending the customer-account dlt bucket secret
  (the dev MinIO endpoint does not exist in GitHub runners); the gate
  variable stays OFF so the job keeps skipping instead of going RED.
- **Free-tier compute quota**: the start endpoint's denial class may
  cap heavier compute; watch for quota resets before large 3.x runs.
- **Warehouse left STOPPED**: no compute was left running after the
  pass (by design — the budget guardrail contract).
