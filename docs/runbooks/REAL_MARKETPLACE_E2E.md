# Real Marketplace E2E Runbook

This runbook describes how to run **real end-to-end** marketplace flows (create connection → PULL/PUSH → verify assets/mappings) using **real credentials**. It is intended for **manual or environment-gated** runs only. **No credentials must be stored in the repository.**

## Purpose and scope

- **Goal:** Validate marketplace connectors (AWS, GCP, Azure, Databricks, Snowflake, CKAN) with real provider credentials and document one successful real E2E run per provider (or a documented skip reason).
- **Out of scope:** Automated CI with secrets; mock/stub credentials.
- **References:** [Marketplace API Reference](../MARKETPLACE_API_REFERENCE.md), [Marketplace Connector Deployment](marketplace-connector-deployment.md).

## Prerequisites

- Hub API running (e.g. `docker compose up -d`; API base URL known, e.g. `http://localhost:8000`).
- Authenticated user with `integrations:write` (e.g. DATA_PROVIDER or TENANT_ADMIN).
- Tenant context for the authenticated user.
- Real provider credentials available **only via environment variables or a secrets manager** (never committed).

## General flow (all providers)

1. **Set provider-specific env vars** (see per-provider sections). Do not commit or log secret values.
2. **Create a marketplace connection** via API (or UI if implemented):
   - `POST /api/v1/integrations/marketplace/connections/`
   - Body: `marketplace_type`, `name`, `config` (config shape per provider below).
3. **Optional:** Test the connection: `POST /api/v1/integrations/marketplace/connections/{id}/test/`.
4. **Run a PULL sync:**
   - `POST /api/v1/integrations/marketplace/sync/`
   - Body: `connection_id`, `direction: "PULL"`, optional `listing_ids`, `filters`, `options` (e.g. `data_strategy: "METADATA_ONLY"`).
5. **Wait and poll** until the sync job completes: `GET /api/v1/integrations/marketplace/sync/{id}/`.
6. **Verify:** List assets and mappings (see [Marketplace API Reference](../MARKETPLACE_API_REFERENCE.md)):
   - Mappings: `GET /api/v1/integrations/marketplace/mappings/?connection_id={connection_id}` — confirms hub assets linked to marketplace listings.
   - Assets: `GET /api/v1/assets/` (or tenant-scoped equivalent per your API version) — filter by source if supported to see created/federated assets.
7. **PUSH (if supported):** For providers that support PUSH, run a PUSH sync with `direction: "PUSH"` and `asset_ids`, then verify listings/mappings on the provider side.

Connection config must be built from env vars (or secrets) at run time; the runbook only documents **env var names** and **config shapes**.

**Optional scripted path (Snowflake, dados.gov.br, Azure):** For these providers you can use the management command with real credentials from the environment (no credentials in repo):

```bash
# From project root, with env vars set (e.g. SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_TOKEN)
docker compose exec api-service python manage.py test_connectors_e2e --source snowflake --limit 5 --verify-assets

# Or dados.gov.br (DADOS_GOV_BR_API_KEY set)
docker compose exec api-service python manage.py test_connectors_e2e --source dados_gov_br --limit 5 --verify-assets

# Or Azure (AZURE_MARKETPLACE_API_KEY or AZURE_CATALOG_API_KEY set)
docker compose exec api-service python manage.py test_connectors_e2e --source azure --limit 5 --verify-assets
```

All other providers (AWS, GCP, Databricks, custom CKAN) use the API flow above (create connection → sync → verify).

---

## Per-provider configuration and steps

### AWS Data Exchange

- **Marketplace type:** `AWS_DATA_EXCHANGE`
- **Environment variables (names only; set externally, never in repo):**
  - `AWS_ACCESS_KEY_ID` — IAM access key
  - `AWS_SECRET_ACCESS_KEY` — IAM secret key
  - `AWS_SESSION_TOKEN` — (optional) temporary session token
  - `AWS_REGION` — (optional) e.g. `us-east-1`
  - `AWS_ROLE_ARN` — (optional) role to assume
- **Connection `config` shape:**  
  `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token` (optional), `region_name` (optional), `role_arn` (optional). Populate from the env vars above when creating the connection (e.g. via a small script or CI env that reads env and calls the API).
- **Steps:** Create connection → Test (optional) → Create PULL sync → Poll job → Verify assets and mappings. PUSH support: see connector implementation; if supported, run PUSH and verify on AWS side.

---

### Google Cloud (GCP) Marketplace

- **Marketplace type:** `GOOGLE_CLOUD_MARKETPLACE`
- **Environment variables (names only):**
  - `GCP_PROJECT_ID` — GCP project ID (required)
  - `GCP_CREDENTIALS_JSON` — (optional) full JSON key content; if not set, use Application Default Credentials (ADC) in that environment
  - `GCP_LOCATION` — (optional) e.g. `US`
  - `GCP_USE_ADC` — (optional) set to `true` to use ADC instead of JSON key
- **Connection `config` shape:**  
  `project_id` (required), `credentials_json` (optional), `location` (optional), `use_adc` (optional boolean).
- **Steps:** Create connection → Test (optional) → PULL sync → Poll → Verify assets/mappings. PUSH if supported by connector.

---

### Azure Marketplace

- **Marketplace type:** `AZURE_MARKETPLACE`
- **Connector:** Azure Commercial Marketplace Catalog API (harvest-only, PULL). Auth: X-API-Key ([Discovery API keys](https://aka.ms/DiscoveryAPI/keys)).
- **Environment variables (names only):**
  - `AZURE_MARKETPLACE_BASE_URL` — (optional) Catalog API base URL; default `https://catalogapi.azure.com` if unset
  - `AZURE_MARKETPLACE_API_KEY` or `AZURE_CATALOG_API_KEY` — X-API-Key for the Catalog API (required for real API calls; management command accepts either)
  - `AZURE_MARKETPLACE_API_VERSION` — (optional) API version query param; default `2025-05-01`
- **Connection `config` shape:**  
  `base_url` (optional), `api_key` (required for real E2E), `api_version` (optional). Populate from the env vars above when creating the connection.
- **Steps:** Same as above (create connection → test → PULL → verify). Optional scripted path: `python manage.py test_connectors_e2e --source azure --limit N` (env: `AZURE_MARKETPLACE_API_KEY` or `AZURE_CATALOG_API_KEY`). PUSH is not supported (harvest-only); document skip reason in the validation table if you do not run (e.g. no API key).

---

### Databricks Marketplace

- **Marketplace type:** `DATABRICKS_MARKETPLACE`
- **Environment variables (names only):**
  - `DATABRICKS_HOST` — workspace host, e.g. `https://<workspace>.azuredatabricks.net`
  - `DATABRICKS_TOKEN` — workspace or PAT token
  - `DATABRICKS_CLUSTER_ID` — (optional) cluster ID if needed by the connector
- **Connection `config` shape:**  
  `host` (required), `token` (required), `cluster_id` (optional).
- **Steps:** Create connection → Test (optional) → PULL sync → Poll → Verify assets/mappings. PUSH: see connector (e.g. may raise `NotImplementedError` for push; document in gaps if so).

---

### Snowflake Data Marketplace

- **Marketplace type:** `SNOWFLAKE_DATA_MARKETPLACE`
- **Environment variables (names only):**
  - `SNOWFLAKE_ACCOUNT` — account identifier
  - `SNOWFLAKE_USER` — user name
  - `SNOWFLAKE_TOKEN` — auth token (or password; see connector docs)
  - `SNOWFLAKE_WAREHOUSE` — (optional)
  - `SNOWFLAKE_ROLE` — (optional)
  - `SNOWFLAKE_DATABASE` — (optional)
- **Connection `config` shape:**  
  `account`, `user`, `token`, `warehouse` (optional), `role` (optional), `database` (optional).
- **Steps:** Create connection → Test (optional) → PULL sync → Poll → Verify assets/mappings. Optional: use management command `python manage.py test_connectors_e2e --source snowflake --limit N` for a scripted path (still requires env-set credentials).

---

### CKAN (e.g. dados.gov.br or custom instance)

- **Marketplace type:** `CKAN_INSTANCE`
- **Environment variables (names only):**
  - For **dados.gov.br:** `DADOS_GOV_BR_API_KEY` or `CKAN_DADOS_GOV_BR_API_KEY` (JWT/API key).
  - For **custom CKAN:** `CKAN_BASE_URL`, `CKAN_API_KEY`; optional `CKAN_SWAGGER_SPEC_URL` if the connector uses it.
  - Optional: `CKAN_TEST_URL`, `CKAN_TEST_API_KEY` for a dedicated test instance.
- **Connection `config` shape:**  
  CKAN uses instance-based config (e.g. `base_url`, `api_key` or `jwt_token`, optional `swagger_spec_url`). For instance-backed setup, see [Marketplace Connector Deployment](marketplace-connector-deployment.md) and `hub/apps/integrations/config/marketplace_instances.py` / `ckan_instances.py`.
- **Steps:** Create connection (via instance or explicit config) → Test (optional) → PULL sync → Poll → Verify assets/mappings. PUSH support: check connector (some CKAN connectors are harvest-only).

---

## Validation checklist (3.2.2)

Use this section to record **one successful real E2E run per provider** or a **documented skip reason**. No credentials in repo; runs are manual or env-gated.

| Provider        | Last E2E run (date) | Result (OK / SKIP / FAIL) | Notes / skip reason / gaps |
|-----------------|---------------------|---------------------------|----------------------------|
| AWS             |                     |                           |                            |
| GCP             |                     |                           |                            |
| Azure           |                     |                           | PULL only; document skip reason if no API key. |
| Databricks      |                     |                           |                            |
| Snowflake       |                     |                           |                            |
| CKAN (e.g. dados.gov.br) |             |                           |                            |

**How to validate:**

1. Set only the env vars for one provider.
2. Create the connection (API or UI) using config derived from those env vars.
3. Run a PULL sync; wait until the job completes.
4. Verify at least one asset and one mapping (or document why none expected).
5. If the connector supports PUSH, run PUSH and verify on the provider side.
6. Record date, result (OK/SKIP/FAIL), and any gaps in the table above.

**Documented gaps (to update as found):**

- **Azure:** Connector is implemented (`hub/apps/integrations/connectors/azure_marketplace_connector.py`; factory has dedicated `AZURE_MARKETPLACE` handling). Config: `base_url`, `api_key`, `api_version`. PULL only. If you skip real E2E (e.g. no Catalog API key), document the skip reason in the table.
- **Push operations:** Several connectors are PULL-only (e.g. Azure, CKAN/dados.gov.br raise `NotImplementedError` for push). Document per connector in notes when validating.
- **Rate limits / quotas:** Real provider limits may cause failures; document in notes and retry or back off as needed.

---

## Security

- **Never** commit credentials, API keys, or tokens to the repository.
- Use environment variables or a secrets manager; inject at deploy/time of run.
- Prefer short-lived tokens (e.g. AWS session, GCP ADC, Databricks PAT with expiry) where possible.
