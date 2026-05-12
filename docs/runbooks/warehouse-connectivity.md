# Warehouse Connectivity Runbook (Phase 275)

## Trivy Scan Budget (275.A.11)

New SDKs add transitive deps to the Hub image:
- `snowflake-connector-python` — pure Python, no new C deps
- `google-cloud-bigquery` — gRPC, protobuf
- `databricks-sql-connector` — thrift, sqlalchemy (~15 new packages)
- `pyathena` — boto3 (already vendored)
- `dlt` — pyarrow + sqlalchemy (already vendored)
- `delta-sharing` — requests + pandas (already vendored)

Budget: `.trivyignore` expected to grow ~30 lines for new CVE entries.
If growth exceeds 60 lines, split warehouse connectors into a separate
Docker image to isolate scan surface.

## TLS Pinning (275.A.20)

Every driver MUST:
1. `verify_ssl=True` (or equivalent driver-level setting)
2. Min TLS 1.2
3. Cipher allow-list (defaults are acceptable for cloud warehouses)

CI check: `grep -r "verify=False\|verify_ssl=False\|ssl_verify=False" hub/apps/warehouses/` must return empty.

## KMS Key Policy (275.A.20)

Only Hub api-service + worker pods can decrypt `WarehouseConnection.config`.
KMS key alias: `alias/meshant-warehouse-credentials`.
Documented in `infrastructure/terraform/modules/warehouse-iam/`.

## CI Sandbox Accounts (275.A.12)

Provision in Snowflake/BigQuery/Databricks/Athena. Rotate via ExternalSecrets.
Per-CI-run cost-budget cap: $5/run. Finance sign-off required.

## Rolling Deploy Order (Phase 275.17)

1. Deploy migration (additive — no backfill)
2. Deploy api-service with warehouse app
3. Flip `Tenant.warehouse_connectivity_enabled` per-tenant after 14d stability
4. Connector-specific flags: `warehouse_snowflake_enabled`, etc.
EOF
