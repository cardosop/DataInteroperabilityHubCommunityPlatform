# Pilot Quickstart — Your Data Pipeline on the Hub

This is the hands-on guide for the pilot company's data engineers. It
walks the pilot's end-to-end story — login, connect your Databricks
workspace, ingest, verify, publish, consume — using the exact surfaces
verified live during the pilot rehearsal (tasks 2.2, 2.3, 3.1–3.3 of
`openspec/changes/pilot-readiness`). Every command and route below is
the real product surface; no mocked steps.

The pilot scope is 20 journeys/use cases selected from the critical
registry — see `docs/runbooks/PILOT_SCOPE.md` for the manifest.

## Prerequisites

- An account on the pilot tenant. You were invited by email, or you log
  in with SSO (your company's Databricks identity — `UC-AUTH-006`).
- Python 3.10+ and the CLI:

```bash
pip install datahub
datahub config set --api-url https://stagingmeshant-internal.example.com/api/v1 --token <YOUR_TOKEN>
datahub health check   # expect: Status: healthy
```

## 1. Log in (SSO)

Open the app, choose your tenant, and click **Continue with
Databricks SSO**. The login completes against your company IdP and
lands you in the pilot tenant (`JOURNEY-AUTH-001`, `UC-AUTH-006`). No
SSO button on the login page means the tenant hint is missing — tell
your tenant admin. Invited (non-SSO) users log in with email +
password or `datahub auth login`.

## 2. Connect your Databricks workspace

**UI:** Settings → Databricks → **Register workspace** — paste the
workspace host, pick the cloud, and save (`UC-DB-001`). Then create
the warehouse connection and run the connection test (`UC-DB-003`).

**CLI:**

```bash
datahub databricks workspaces register \
  --name pilot-workspace --host dbc-<your-workspace>.cloud.databricks.com \
  --cloud AWS --region us-east-1

datahub warehouses connections create \
  --name pilot-dbx --warehouse-type DATABRICKS \
  --config '{"host": "dbc-<your-workspace>.cloud.databricks.com", "http_path": "/sql/1.0/warehouses/<warehouse-id>"}'

datahub warehouses connections test <connection-id>
```

The platform consumes your account's native Unity Catalog — nothing to
install (the `PILOT_SCOPE.md` UC/Delta-Sharing decision).

## 3. Register your data products

Create the asset and its data contract. The contract is the machine
contract everything downstream keys on (`JOURNEY-DE-001`):

```bash
datahub assets create --name "Pilot CRM" --key pilot-crm --domain sales
datahub contracts create --file contract.yaml --asset-id <asset-id>
```

Example `contract.yaml`:

```yaml
apiVersion: meshant/v1
kind: DataContract
metadata:
  name: pilot-crm
  domain: sales
  version: "1.0.0"
  owner: de-team@yourcompany.com
spec:
  schema:
    fields:
      - name: customer_id
        type: string
        nullable: false
        unique: true
      - name: email
        type: string
        nullable: false
```

## 4. Ingest with the dlt spine

Create a scheduled ingestion bound to the source (`UC-INGEST-001`,
`UC-INGEST-002`):

```bash
datahub scheduled-ingestion create \
  --name pilot-crm-daily \
  --source-type S3 \
  --source-config '{"bucket": "<source-bucket>", "prefix": "crm/"}' \
  --cron-expression "0 3 * * *" \
  --asset-id <asset-id> --auto-activate

datahub scheduled-ingestion trigger <ingestion-id>
datahub scheduled-ingestion runs <ingestion-id>         # monitor (UC-INGEST-003)
datahub scheduled-ingestion run-detail <ingestion-id> <run-id>
```

The ingestion is the real dlt pipeline verified live in 2.3
(warehouse-resident data: bounded SELECT → dlt → destination). Its
incremental cursor advances **only after a successful load** — a failed
run leaves the cursor exactly where the last success put it, so retries
are always safe (`JOURNEY-INGESTION-001`, `JOURNEY-INGESTION-003`).

Destinations today: the dev S3 estate. When the pilot leaves the dev
estate, the same schedule points at your company's S3 bucket
(`docs/runbooks/CREDENTIAL_PROVISIONING.md` §6.3 has the bucket
policy).

## 5. Verify quality and compliance

Set DQ checks on the ingested asset under **Data Quality**
(`JOURNEY-DE-003`) and the compliance scan under **Compliance**
(`JOURNEY-DE-004`). Both run per-ingestion and their runs are visible
in the UI; the CLI verifies:

```bash
datahub dq scorecard <asset-id>
datahub compliance list
```

## 6. Export and transform

- **Recurring export** to your own destination (`JOURNEY-EXPORT-001`,
  `UC-EXPORT-001`, `UC-EXPORT-002`):

```bash
datahub scheduled-export create \
  --name pilot-crm-export \
  --destination-type S3 \
  --destination-config '{"bucket": "<destination-bucket>", "prefix": "exports/"}' \
  --schedule-config '{"cron": "0 5 * * *"}' \
  --source-scope '{"asset_ids": ["<asset-id>"]}'

datahub scheduled-export trigger <export-id>
datahub scheduled-export runs <export-id>               # monitor (JOURNEY-EXPORT-002)
```

- **Export to Databricks** (`JOURNEY-DB-013`, `UC-DB-013`): create a
  `DATABRICKS_TABLE` export — the platform writes through the dlt
  spine into your workspace catalog. Transform with dbt-databricks
  against the same warehouse (the 2.3 live run materialized a view
  from the workspace catalog).

## 7. Publish and consume

Publish the asset to the marketplace from the asset page, and your
consumers discover and order it (`JOURNEY-DC-001`). Consumers browse
the marketplace, place the order, and receive the entitlement;
consumption goes through the contract + export surfaces.

## What is ON for the pilot

Per the capability manifest (`PILOT_SCOPE.md`): lineage snapshots and
change notifications are ON for the pilot tenant; cross-tenant
marketplace, field-level lineage, and OpenLineage export are OFF for
P1. The non-flagged MVP surface (warehouses, dlt movement, contracts,
marketplace, billing) is ON as-is.

## Privacy posture

The pilot tenant carries an APPROVED DPIA, a COMPLETED RoPA
generation, and an ACTIVE DPA record — see
`docs/runbooks/PILOT_PRIVACY_PACK.md`. Data subject rights (export /
erasure) are self-service under your account settings.

## Troubleshooting

- `datahub health check` first — it classifies the failure.
- Ingestion runs: `datahub scheduled-ingestion runs <id>` then
  `datahub scheduled-ingestion run-detail <id> <run-id>` for the
  error.
- Warehouse auth: re-test the connection
  (`datahub warehouses connections test`) — the pilot account's
  queryTag policy requires the per-connection opt-out where noted in
  the smoke report.
- Still stuck: `docs/runbooks/PILOT_SMOKE_REPORT.md` (per-path
  results), `docs/runbooks/PILOT_ONCALL_AND_ESCALATION.md`.
