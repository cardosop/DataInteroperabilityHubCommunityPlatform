# User Journeys (MVP)

This document describes the **core user journeys for MVP v1** of the Interoperable Data Hub, based on:

- Personas (DPO, DE, CPO, DC, MPA, DEV)
- System Requirements
- MVP Scope

Each journey is described as:

- **Context & Goal**
- **Preconditions**
- **Main Flow (happy path)**
- **Alternate / Error Flows**
- **Back-end / Services touched**

---

## 1. Data Product Owner (DPO) Journeys

### Journey DPO-1: Onboard New Asset via Data-First Flow (UI)

**Context & Goal**

A Data Product Owner has a CSV/Parquet file and wants to turn it into a **data product** in the hub: validated contract, quality/compliance-checked data, and an internal asset (optionally later published to marketplace).

**Preconditions**

- DPO is authenticated as a **Data Provider** in a tenant.
- Tenant is active and allowed to store data.
- DPO has local access to the data file (≤ UI upload size limit).

**Main Flow (Happy Path)**

1. **Start ingestion**
   - DPO navigates to “Create new asset” → selects **Data-first**.
   - Provides basic metadata (asset name, description, domain) and clicks “Next”.

2. **Upload data file**
   - DPO uploads a data file via browser.
   - UI shows upload progress and then a “Processing data…” state.

3. **Format validation & schema inference**
   - Ingestion service:
     - Validates file format (CSV, JSON, Parquet).
     - Reads sample data and infers schema (columns, types, sample rows).
   - UI shows schema preview and sample rows.

4. **Compliance check (mandatory gate)**
   - Backend triggers a **Compliance Job** for this file.
   - Compliance service scans for PII/sensitive data and returns:
     - `overall_status`, `risk_level`, `detected_categories`, `allowed_to_store`.
   - If `allowed_to_store = true`, processing continues.
   - UI shows a “Compliance: PASS/WARN” panel with high-level summary.

5. **Data Quality check (mandatory gate)**
   - Backend triggers a **DQ Job** using the `intake_basic` profile.
   - DQ service returns `overall_status`, `quality_score`, and checks list.
   - UI shows “Quality: PASS/WARN” and key metrics.

6. **Create draft asset & contract editor**
   - If both compliance and DQ gates pass:
     - Ingestion service creates a **draft Asset** and attaches:
       - Inferred schema and sample.
       - DQ results.
       - Compliance report.
     - Contract service creates a **draft HubContract** pre-filled with:
       - Schema from inference.
       - Basic metadata (name, description).
   - UI moves DPO to the **Contract Editor** screen.

7. **Edit contract & metadata**
   - DPO:
     - Reviews schema and descriptions.
     - Fills in required fields (owners, SLAs, usage rights, etc.).
     - Adds tags/ontology selections (domain, data categories).
   - DPO saves edits, which updates the draft HubContract.

8. **Run DataContract validation (CLI)**
   - DPO clicks “Validate contract”.
   - Contract service calls DataContract CLI via `datacontract-service` to:
     - Validate the contract for the selected spec/version.
   - A **Job** is created (type `CONTRACT_VALIDATION`).
   - UI shows “Validating…” and then fetches job result.

9. **Validation success**
   - Validation job returns `VALID`.
   - UI:
     - Shows “Contract status: VALID”.
     - Allows DPO to mark asset as **Active** (internal).

10. **Asset created**
    - Asset is now **active** in the tenant’s catalog:
      - Data stored (since it passed gates).
      - Contract is `VALID`.
      - Semantic mapping is triggered in background (RDF/JSON-LD).

**Alternate / Error Flows**

- **A1: Compliance check fails**
  - Compliance returns `allowed_to_store = false`.
  - Backend:
    - Does not store the file; marks ingestion as rejected.
    - Creates a Compliance Job with `FAILED` / `FAIL`.
    - Writes audit event `DATA_FILE_REJECTED_COMPLIANCE`.
  - UI:
    - Shows “Data rejected by compliance gate” with report summary.
    - Offers option to download/see detailed report and shows “No data stored” note.
    - DPO can cancel or retry with a different file (after external remediation).

- **A2: DQ check fails (quality too low)**
  - DQ returns `FAIL` (based on profile rules).
  - Platform policy may still allow storage with strong warning or may block.
    - For MVP, assume gate is strict and file is not stored on `FAIL`.
  - UI:
    - Shows “Data rejected by quality gate” and DQ report summary.
    - DPO must fix data externally and retry.

- **A3: Contract CLI validation errors**
  - CLI returns `INVALID` with error messages.
  - UI:
    - Shows validation errors (missing fields, schema mismatch, etc.).
    - DPO edits and re-runs validation until `VALID`.

- **A4: CLI/Compliance/DQ timeout or crash**
  - Job marked `FAILED` with internal error.
  - For compliance: fail-closed (file not stored).
  - UI:
    - Shows error message (“Service unavailable, please try again”).
    - DPO can retry later.

**Services Touched**

- Ingestion service
- Compliance service
- DQ service
- Contract (HubContract) service + DataContract CLI service
- Job service
- Audit service
- Semantic service (background)
- Auth/tenant service

---

### Journey DPO-2: Onboard Asset via Contract-First Flow (UI)

**Context & Goal**

DPO already has a data contract file (ODCS/DataContract.com) and wants to use it as the primary source of truth, then attach data that must pass DQ/compliance gates and align with the contract.

**Preconditions**

- DPO authenticated in a tenant with **Data Provider** role.
- Contract file available locally.

**Main Flow (Happy Path)**

1. **Start ingestion**
   - DPO clicks “Create new asset” → selects **Contract-first**.

2. **Upload contract file**
   - DPO uploads contract JSON/YAML.
   - Contract service:
     - Stores original file as draft.
     - Calls DataContract CLI via `datacontract-service` for validation.
   - A `CONTRACT_VALIDATION` job is created.
   - UI shows “Validating contract…”.

3. **Validation success**
   - Job returns `VALID` (or `WARNING_ONLY` under policy).
   - Contract service normalizes to **HubContract** and shows the contract editor.
   - DPO can make adjustments if desired.

4. **Upload data file**
   - DPO proceeds to “Attach data”.
   - Uploads data file via UI.
   - Ingestion validates format, infers schema & sample.

5. **Compliance & DQ gates**
   - Same as Data-first:
     - Compliance Job → must pass (`allowed_to_store = true`).
     - DQ Job (`intake_basic`) → must pass/meet policy.
   - UI shows compliance & DQ summary.

6. **Schema comparison**
   - Backend compares:
     - Inferred schema vs contract schema from HubContract.
   - UI displays:
     - Fields matching.
     - Extra/missing fields.
     - Type mismatches.
   - DPO decides:
     - Update contract schema, or
     - Fix data & re-upload (if mismatch is unacceptable).

7. **Finalize contract & validation**
   - Once DPO is satisfied:
     - DPO saves contract.
     - DPO runs DataContract CLI validation again.
   - If `VALID`:
     - Asset becomes **active** with data and contract in sync.

**Alternate / Error Flows**

- **B1: Initial contract validation fails**
  - CLI returns `INVALID` or `ERROR`.
  - UI shows errors. DPO must fix contract and re-upload or edit until `VALID`.

- **B2: Data fails compliance or DQ**
  - Same as DPO-1 A1/A2:
    - No data stored.
    - DPO sees detailed reports and must remediate externally.

- **B3: Persistent schema mismatches**
  - If contract intentionally differs from inferred schema:
    - DPO can choose to keep contract as canonical and accept discrepancies.
    - Platform still requires contract to be `VALID`.
    - UI shows warnings but allows asset to be active if checks pass.

**Services Touched**

Same as DPO-1, plus more schema comparison logic in the contract/ingestion services.

---

### Journey DPO-3: Attach Data to a Contract-Only Asset

**Context & Goal**

DPO created a contract-only asset earlier and now has data to attach.

**Preconditions**

- Contract-only asset exists and contract is `VALID`.
- DPO is authorized on that asset.

**Main Flow**

1. **Open asset**
   - DPO navigates to asset details (currently no dataset attached).

2. **Attach data**
   - Clicks “Upload data” (or “Attach dataset”).
   - Uploads file via UI or selects an external reference (if supported).

3. **Compliance & DQ gates**
   - Same as in DPO-1 and DPO-2:
     - Compliance Job (mandatory).
     - DQ Job (`intake_basic`).
   - If both pass:
     - DataFile and Dataset record are attached to asset.
     - Asset now has data + contract.

4. **Optional schema check**
   - If contract already has a schema:
     - Backend compares inferred schema and shows differences (like DPO-2).
   - DPO can adjust contract or leave as-is (with warnings if needed).

5. **Asset remains active**
   - If contract is still `VALID`, asset stays active with new dataset.
   - Semantic mapping updated.

**Alternate / Error Flows**

Same gate failures as previous journeys.

---

### Journey DPO-4: Publish / Unpublish Asset to Marketplace

**Context & Goal**

DPO wants to make an internal asset discoverable by other tenants via the marketplace.

**Preconditions**

- Asset exists, contract is `VALID`, and data (if any) passed gates.
- Tenant’s KYC status is “verified” (as set by Platform Admin).
- Tenant policy allows marketplace publishing.

**Main Flow**

1. **Open asset details**
   - DPO opens asset in catalog.

2. **Configure marketplace metadata**
   - Switch to “Marketplace” tab.
   - Fill in:
     - Public title & description.
     - High-level use cases.
     - Price model (for MVP: simple static price or “request access”).
     - License summary.

3. **Publish request**
   - DPO toggles “Publish to marketplace”.
   - Under the hood:
     - Marketplace service creates/updates a **Product/Listing** linked to asset.
     - Asset is marked as `public` / `marketplace-visible`.
   - Some deployments could require Platform Admin approval; for MVP, assume auto-approval if tenant is verified.

4. **Visibility**
   - Asset appears in marketplace search for other tenants.
   - DPO sees status = “Public (Marketplace)”.

5. **Unpublish**
   - At any time, DPO can toggle “Unpublish from marketplace”.
   - Marketplace service hides listing; asset remains available internally.

**Alternate / Error Flows**

- Tenant not verified:
  - UI shows “You must be a verified seller to publish assets”.
  - DPO is instructed to contact Platform Admin/support.
- Platform Admin “suspends” asset:
  - Asset is visible as restricted/unlisted despite DPO setting.

---

## 2. Data Engineer / Contract Author (DE) Journeys

### Journey DE-1: Programmatic Contract-First Onboarding via API/SDK

**Context & Goal**

DE wants to integrate the hub into existing pipelines, using contract-first approach with CI/CD, via Python/JS SDK.

**Preconditions**

- DE has tenant-scoped API credentials with **Data Provider** role.
- Contract file in Git or local file.

**Main Flow**

1. **Validate contract locally (optional)**
   - DE uses DataContract CLI locally to validate contract.
   - Fixes any issues before pushing.

2. **Call API to create contract**
   - Using SDK:
     - `POST /contracts` with original contract file + spec/version info.
   - Contract service:
     - Stores contract.
     - Triggers CLI validation job.
   - SDK polls `GET /jobs/{job_id}`.

3. **Check validation results**
   - Job status becomes `SUCCEEDED` with `validation_status = VALID`.
   - SDK receives normalized HubContract + contract ID.
   - DE records contract ID in pipeline config.

4. **Attach data programmatically**
   - Pipeline step:
     - Uploads data via `POST /files` (or multi-part).
     - Calls `POST /assets/{asset_id}/datasets` (or similar) referencing contract ID & file.
   - Ingestion service:
     - Starts Compliance & DQ Jobs.

5. **Monitor gates**
   - SDK polls `jobs` API for compliance and DQ runs.
   - If both Jobs `SUCCEEDED` with acceptable statuses:
     - Asset is activated.

6. **Handle success**
   - DE logs asset/contract IDs.
   - Downstream systems can now query catalog or semantic metadata.

**Alternate / Error Flows**

- Contract validation fails:
  - Job `FAILED` with `validation_status = INVALID`.
  - SDK surfaces errors; pipeline fails; manual or automated fix required.

- Compliance fails:
  - `allowed_to_store = false`.
  - Pipeline step logs failure and triggers alert.
  - DE modifies upstream data process or masks PII.

- DQ fails:
  - Pipeline fails or flags as degraded quality, based on policy.

---

### Journey DE-2: External Compliance Scan-Only (No Storage)

**Context & Goal**

DE wants to use hub’s compliance engine to scan external datasets **without storing them** (e.g., as part of internal ETL pipeline).

**Preconditions**

- Tenant has access to compliance service.
- Data may be large and/or sensitive.

**Main Flow**

1. **Call scan API**
   - DE uses SDK:
     - `POST /compliance-runs` with:
       - File upload or temporary storage link.
       - `scan_mode = "external"` (no storage).
       - `applicable_regimes` (optional; if omitted, tenant defaults are used).

2. **Compliance Job**
   - Compliance service:
     - Reads data into ephemeral storage.
     - Runs detection.
     - Deletes raw data after scanning.
   - Job created (`COMPLIANCE_CHECK` with `external = true`).

3. **Fetch results**
   - SDK polls job status.
   - On completion:
     - Receives compliance report:
       - `overall_status`, `risk_level`, `detected_categories`, etc.
   - No Asset or Dataset is created; only a report and audit entry exist.

4. **Action**
   - DE:
     - Uses report to adjust ETL (mask fields, anonymize).
     - May re-run after changes.

**Alternate / Error Flows**

- Compliance service timeout/failure:
  - Job `FAILED` with error.
  - Pipeline logs and possibly retries or fails.

---

## 3. Compliance & Privacy Officer (CPO) Journeys

### Journey CPO-1: Review Compliance for an Asset

**Context & Goal**

CPO wants to inspect the regulatory risk of an asset that is being used internally or considered for external publishing.

**Preconditions**

- CPO has **Auditor/Compliance** role in tenant.
- Asset exists with at least one dataset and compliance run.

**Main Flow**

1. **Navigate to asset**
   - CPO logs in and opens “Assets”.
   - Filters or searches to find target asset.

2. **Open Compliance tab**
   - CPO clicks “Compliance” tab on asset details.

3. **View latest compliance report**
   - UI shows:
     - `overall_status`, `risk_level`.
     - List of **detected categories** (e.g., PII, financial, health).
     - Per-column highlights (top N findings).
     - Applicable regulations (GDPR, LGPD, etc.).
   - CPO can expand to see the full report (details_json).

4. **Check DQ context**
   - CPO might switch to “Quality” tab to understand DQ results and quality score.

5. **Decide and annotate**
   - CPO can set a **business-level label** like:
     - “Approved for internal use only”.
     - “Not approved for external sharing”.
     - “Under review”.
   - This label does **not** override the technical compliance gate; it’s governance metadata.

6. **Optionally log notes**
   - CPO can add a comment or “compliance note” for future reference (stored in metadata).

**Alternate / Error Flows**

- Asset has no compliance run:
  - UI shows “No compliance checks run yet” and offers to trigger a new compliance run (subject to role/policy).

---

### Journey CPO-2: Use Audit Log to Investigate a Dataset

**Context & Goal**

CPO needs to know what happened with a particular dataset after a potential incident or question from management/regulators.

**Preconditions**

- CPO has read access to tenant’s audit logs.
- Asset ID or name is known.

**Main Flow**

1. **Open audit log UI**
   - CPO navigates to “Audit Logs”.
   - Filters by:
     - Asset ID or name.
     - Date range.
     - Event types (e.g. compliance, DQ, data uploads).

2. **Review events**
   - UI shows entries such as:
     - `DATA_FILE_UPLOADED`
     - `COMPLIANCE_CHECK_COMPLETED`
     - `DATA_FILE_REJECTED_COMPLIANCE`
     - `QUALITY_CHECK_COMPLETED`
     - `ASSET_PUBLISHED`
   - Each entry includes timestamp, user, job ID, summary outcome.

3. **Drill down**
   - CPO clicks an event to view details:
     - For compliance: `overall_status`, `risk_level`, top findings.
     - For DQ: `quality_score`, profile name.
   - CPO can open associated asset or job pages.

4. **Export**
   - If needed, CPO exports selected events as CSV/JSON for reporting.

---

## 4. Data Consumer / Buyer (DC) Journeys

### Journey DC-1: Discover and Evaluate a Marketplace Asset

**Context & Goal**

DC wants to find a dataset for analysis or product usage, evaluate its quality and compliance, and decide whether to request or purchase access.

**Preconditions**

- DC has **Data Consumer** role in a tenant.
- Some public marketplace assets exist.

**Main Flow**

1. **Browse marketplace**
   - DC navigates to “Marketplace”.
   - Uses filters:
     - Domain/industry.
     - Geography.
     - Keywords.
   - Sees asset cards with:
     - Name, short description.
     - Provider / tenant name.
     - Basic metadata (rows, time coverage).
     - Quality & compliance badges.

2. **Open asset details**
   - Clicks on an asset card.
   - Sees:
     - Detailed description.
     - Schema preview (column names, types).
     - Sample rows.
     - DQ summary (score, last checked date).
     - Compliance summary (e.g., “No direct PII stored”, “GDPR considerations”).
     - Licensing & price model (for MVP: simple price or “request access”).

3. **Decide**
   - If the dataset looks suitable and allowed for their use case, DC proceeds to **request/purchase access**.

---

### Journey DC-2: Request / Purchase Access and Use the Dataset

**Context & Goal**

After evaluating an asset, DC wants to get access and then use the data.

**Preconditions**

- DC is authenticated in their tenant.
- Asset is public and published.

**Main Flow**

1. **Request/Purchase access**
   - On asset details page, DC clicks:
     - “Request access” or “Purchase” (depending on MVP billing approach).
   - For MVP:
     - This may create an **Order/Access Request** with minimal payment integration or just an internal approval flow.

2. **Approval / Fulfillment**
   - Marketplace service:
     - Creates an Order/Entitlement record.
   - Depending on configuration:
     - Automatic approval (MVP simple mode), or
     - Manual review by provider or Platform Admin (future or configuration).

3. **Entitlement granted**
   - Once approved:
     - DC’s tenant gains an **Entitlement** to this asset.
     - Asset appears in “My Assets / Purchased” for DC.

4. **Access dataset**
   - DC can:
     - Download data directly (if allowed).
     - Use API/SDK:
       - Access credentials/token authorized for that asset.
       - Query endpoints or download from object storage via signed URLs.

5. **Track usage**
   - DC can view:
     - Assets they own.
     - Basic usage metrics (if available, future).

---

## 5. Marketplace Operator / Platform Admin (MPA) Journeys

### Journey MPA-1: Onboard Tenant and Set KYC Status

**Context & Goal**

Platform Admin needs to onboard a new tenant and decide whether they can publish public assets.

**Preconditions**

- Platform Admin role available.
- Business-level KYC/KYB process is managed externally or manually.

**Main Flow**

1. **Create tenant**
   - Admin uses a simple admin UI or backend tool to:
     - Create a tenant record (name, contact, region).
     - Set initial admin user.

2. **Set KYC status**
   - After KYC process off-platform:
     - Admin sets tenant’s `kyc_status` to `verified` or `unverified`.
   - If `verified`:
     - Tenant is allowed to publish public assets.
   - If `unverified`:
     - Tenant may use internal catalog but not publish to marketplace.

3. **Configure defaults**
   - Admin may set:
     - Default compliance regimes (e.g., GDPR+LGPD).
     - Default rate limits/quotas for DQ/compliance runs.

---

### Journey MPA-2: Monitor Global Health and Usage

**Context & Goal**

Platform Admin wants to see how the platform is performing: workloads, errors, and marketplace usage.

**Preconditions**

- Admin has platform-level dashboards.

**Main Flow**

1. **Open admin dashboard**
   - Admin sees metrics:
     - Number of tenants (verified/unverified).
     - Number of assets (internal/public).
     - DQ/compliance runs per day.
     - Success/failure rates.
     - High-level infra cost approximations (if available).

2. **Inspect anomalies**
   - Admin filters to:
     - Tenants with unusually high compliance failures.
     - Assets frequently failing DQ.
     - Spikes in usage (possible abuse).

3. **Take action**
   - Admin may:
     - Contact tenants with abnormal patterns.
     - Adjust default thresholds (in consultation with legal/compliance).
     - Temporarily suspend or restrict specific tenants or assets if abusive or risky.

---

## 6. External Developer / Integrator (DEV) Journeys

### Journey DEV-1: Build a Custom Ingestion Portal

**Context & Goal**

DEV builds a custom UI in their company that uses the hub as backend for contracts, DQ, and compliance.

**Preconditions**

- DEV has API keys/credentials and test tenant access.
- Basic API docs & SDKs exist.

**Main Flow**

1. **Understand API & auth**
   - DEV reads `API_Spec_v1`, learns:
     - How to authenticate as tenant.
     - How to create assets/contracts.
     - How to upload files.
     - How to trigger and check Jobs.

2. **Implement custom UI flow**
   - DEV’s app:
     - Collects metadata from users.
     - Uploads files to hub using SDK or signed URLs.
     - Calls ingestion APIs.

3. **Handle jobs & status**
   - DEV’s frontend polls:
     - `/jobs/{job_id}` for validation, DQ, and compliance.
   - Shows progress and results in their own UI.

4. **Persist IDs**
   - DEV stores asset/contract IDs in their own system.
   - Users can click through to hub UI if needed.

---

### Journey DEV-2: Integrate Semantic Search

**Context & Goal**

DEV wants to integrate concept-based search into an internal catalog, using the hub’s semantic API and SPARQL endpoint.

**Preconditions**

- Some assets in hub have semantic metadata (URIs, RDF).

**Main Flow**

1. **Resolve URIs**
   - DEV’s app receives hub URIs (e.g., from webhooks or prior API calls).
   - Calls:
     - `GET /id/contract/{id}` to get JSON-LD.

2. **Query SPARQL endpoint**
   - DEV uses SPARQL endpoint to:
     - Find assets tagged with certain ontology classes (like PII, domain concepts).
   - Integrates results into internal search UI.

3. **Link assets**
   - Internal metadata store links to hub’s URIs/IDs.
   - Users can navigate from internal catalog to hub asset detail.

---

_End of User Journeys (MVP)._
