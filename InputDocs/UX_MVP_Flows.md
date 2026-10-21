# UX MVP Flows

This document describes the **UX flows and screen sketches** for the Interoperable Data Hub **MVP**.

It translates:

- Personas  
- System requirements  
- User journeys  

into concrete **screens** and **navigation flows** for the first version of the product.

The goal is to give designers and engineers a shared picture of **what the UI should do**, without locking us into pixel-perfect design.

---

## 0. Global UX Principles (MVP)

- **Tenant-aware:** Everything the user sees is implicitly scoped to their organization (tenant).
- **Persona-sensitive:**  
  - Data Product Owners & Data Engineers see **authoring and onboarding** features.  
  - Data Consumers see **browse & purchase** first.  
  - Compliance/Audit roles see **risk & logs** views.
- **Explain-first for errors:**  
  - Contract validation, DQ, and compliance errors must be **clear, grouped, and actionable**.
- **Safe defaults:**  
  - No data with compliance issues is stored.  
  - No asset is public by default.
- **Progressive disclosure:**  
  - Show summaries first (quality badges, compliance badges) with drill-downs for detailed reports.

---

## 1. Main Navigation & Layout

### 1.1 Top-Level Navigation

For authenticated users (Data Provider / Tenant Admin / Auditor):

- **Logo / Product Name** (top left)
- **Global Nav (left sidebar or top tabs):**
  1. **Assets** (catalog of tenant assets)
  2. **Data Onboarding** (shortcut into intake flows)
  3. **DQ & Compliance** (runs & reports)
  4. **Marketplace** (browse public listings)
  5. **Audit Logs** (for users with `AUDITOR` role)
  6. **Admin / Settings** (for `TENANT_ADMIN`)

- **Top-right:**  
  - Tenant name  
  - User avatar/menu (Profile, API keys, Logout)

For Data Consumer users in a buyer-only tenant, nav can collapse to:

- Marketplace
- Entitlements
- Profile / Billing

**Status Standardization:**  
All UX references to asset states must align with the canonical `Asset.status` enum defined in System Requirements §14.3:  
`Draft`, `Active`, `Public`, `Retired`.  
These states are to be used consistently in UI filters, labels, and flow diagrams.

---

## 2. Flow A – Data-First Onboarding (Data Product Owner)

### 2.1 Screen A1 – New Asset (Data-First) Entry

**Entry points:**

- Button “**New Asset**” in Assets list.
- Button “**Onboard Data**” on home/dashboard.

**Wireframe (textual)**

- Page title: `Create New Asset (Data First)`
- Left column: **Basic metadata**
  - [Text] Asset Name
  - [Text] Slug (auto-generated, editable)
  - [Textarea] Description
  - [Select] Domain (Sales, Marketing, etc.)
- Right column: **Onboarding mode**
  - Radio:
    - (●) Data first
    - (○) Contract first
    - (○) Contract only
- Bottom:
  - Primary button: **Continue →** (goes to file upload)
  - Secondary: Cancel / Back to Assets

**Key states:**

- Validation on required fields (asset name at minimum).
- Auto-slug generation on blur.

---

### 2.2 Screen A2 – Upload Data File

After asset metadata is captured.

**Wireframe**

- Breadcrumb: `Assets > Customer Orders > Onboarding (Data First)`
- Section: **Upload Data File**
  - Dropzone: “Drag & drop your file here or click to browse”
  - Supported formats: CSV, Parquet, JSON (message)
  - File info preview once chosen: name, size, type
- Sidebar (right):
  - Info card: “What happens next?”
    - 1. File is uploaded.
    - 2. Schema is inferred.
    - 3. DQ & Compliance checks run.
    - 4. You review and edit the contract.

- Buttons:
  - Primary: **Upload & Analyze**
  - Secondary: Back

**Behavior:**

- On click “Upload & Analyze”:
  - Calls `/files/init` then uploads.
  - On success, calls `/files/{id}/complete` with `ingestion_mode = DATA_FIRST`, `run_dq = true`, `run_compliance = true`.
  - Transitions to **A3 – Analyzing…** state.

---

### 2.3 Screen A3 – Analyzing Data (loading + background jobs)

**Wireframe**

- Title: `Analyzing Data for "Customer Orders"`
- Progress indicator (stepper):
  1. Upload file – **Done**
  2. Infer schema – **In progress / Done**
  3. Run data quality checks – **In progress / Done**
  4. Run compliance checks – **In progress / Done**
  5. Prepare contract draft – **Pending / Done**

- Center:
  - Spinner or progress bar.
  - Messages:
    - “Inferring schema…”
    - “Running basic data quality checks…”
    - “Running compliance checks (GDPR, LGPD)…”
- Side panel:
  - “You can navigate away; this analysis will continue in the background” (optional for MVP, but for now assume user stays).

**Error UX (critical):**

- If **compliance fails with `allowed_to_store = false`**:
  - Show red panel:
    - Icon: ⚠️
    - Title: `Data cannot be stored due to compliance risks`
    - Text: short explanation + link “View compliance findings”
  - Actions:
    - “View findings” – modal with summary.
    - “Delete uploaded data” (or automatic).
    - Disable “Continue to contract” (user cannot proceed).

- If **DQ fails** but compliance allows storage:
  - Show yellow panel:
    - “Data quality issues detected”
    - Allow user to proceed to contract, but highlight issues.

Once all jobs succeed:

- Auto-navigate (or show button) to **A4 – Contract Editor (pre-filled)**.

---

### 2.4 Screen A4 – Contract Editor (Pre-filled from Data)

**Purpose:** user reviews & edits contract; must pass CLI validation before continuing.

**Wireframe**

Layout:

- Left-side: **Contract Summary / Form View**
  - Tabs:
    - Overview
    - Schema
    - Quality
    - Compliance
  - Example:

    - **Overview:**
      - Name, description, owner, domain.
      - Data classification, SLAs, retention.

    - **Schema tab:**
      - Table:
        - Column name | Type | Nullable | Description | PII? (readonly from detection)
      - Ability to edit descriptions and high-level logical types.

- Right-side: **Raw Contract (YAML/JSON) & Validation Panel**
  - Toggle: `View: [Form] [Raw YAML]`
  - Editable text area showing normalized HubContract YAML/JSON.
  - Validation panel:
    - Status badge: `Not validated`, `Valid`, `Errors`, `Warnings`.
    - List of error/warning messages with clickable anchors to fields.

Bottom bar:

- Button: **Run Contract Validation (DataContract CLI)**
- Status text: last validation at <time>, CLI version.
- Primary: **Save & Activate Asset** (disabled until `validation_status = VALID` or `WARNING_ONLY` per policy).
- Secondary: **Save as Draft**

**Interactions:**

- On “Run Contract Validation”:
  - Calls `/contracts/{id}/validate`.
  - Updates validation panel.
  - If errors:
    - Show grouped by category (syntax, required fields, spec compatibility).
- On “Save & Activate Asset”:
  - If validation is not VALID or WARNING_ONLY → block with message.
  - If OK:
    - Asset status set to `ACTIVE`.u
    - Redirect to Asset Detail page.

---

## 3. Flow B – Contract-First Onboarding

### 3.1 Screen B1 – Upload Contract

**Entry:** “New Asset → Contract First” from initial create screen.

**Wireframe**

- Title: `Create New Asset (Contract First)`
- Left: Asset metadata (same as A1).
- Right: Contract file block:
  - File dropzone: “Upload ODCS/DataContract contract (JSON/YAML)”
  - Optional: text area to paste contract.
  - Select:
    - [Select] Spec Type: `ODCS | DataContract.com`
    - [Select] Spec Version (based on type).
- Checkbox:
  - “Validate contract immediately using DataContract CLI” (checked by default).

Buttons:

- **Upload & Validate Contract** (primary)
- Back

**Behavior:**

- After upload, call `POST /contracts` with `validate=true`.
- On success:
  - Show result:
    - `VALID` → green banner.
    - `WARNING_ONLY` → yellow banner.
    - `INVALID` → red banner with errors.
- If valid, user is prompted to upload data (go to B2).

---

### 3.2 Screen B2 – Upload Data File (Contract-First)

Almost identical to A2, with added context:

- Banner at top:
  - “Contract validated (ODCS v3.0.2). Next: upload data and reconcile schema.”
- After upload and `files/{id}/complete`, same analyzing state (A3), but with an additional step:

**Additional step in the progress timeline:**

5. **Compare schema (contract vs inferred)**

For comparison results:

- Show summary panel:
  - “3 differences detected between contract schema and inferred schema.”
  - List with status:
    - Column `customer_email`: contract type `string`, inferred `string` + flagged PII.
    - Column `price`: present in contract, missing in data (or vice versa).
- Provide a “View details” modal or a table.

Recommendations:

- Label differences as:
  - **Critical mismatch** (data cannot be safely used).
  - **Minor mismatch** (e.g., description differences).

Then transition to B3: Contract editor with both contract details and data inference info.

---

### 3.3 Screen B3 – Contract Editor (Contract-First)

Same layout as A4, with **extra hints**:

- In Schema tab:
  - Extra column: “Inferred” vs “Contract”.
  - Icons:
    - ✅ Match
    - ⚠️ Mismatch (on hover: show details)

User can:

- Adjust the contract schema to match data.
- Or change data classification/priorities but maintain contract schema.

Validation button and save/activate workflow is identical to A4.

---

## 4. Flow C – Contract-Only Onboarding

### 4.1 Screen C1 – Upload Contract (Contract-Only)

**Entry:** “New Asset → Contract Only”.

Identical to B1 but with no subsequent data upload step.

Post-validation:

- If contract is `VALID`:
  - Show info: “This is a contract-only asset. You can attach data later from the Asset Detail page.”
  - Primary action:
    - **Save & Create Asset**
- If `INVALID`:
  - Show error list; allow redraft and re-upload.

### 4.2 Screen C2 – Asset Detail (Contract-Only)

Once asset is created:

- Header:
  - Asset name, domain, status (`ACTIVE`/`DRAFT`).
- Tabs:
  - Overview
  - Contract
  - (Datasets) – shows a message “No datasets attached yet.”
  - DQ & Compliance – empty states.
- Button:
  - **Attach Data File** → reuses Data upload and analyze flow (A2 / A3) with compliance & DQ.

---

## 5. Flow D – Asset Catalog & Detail

### 5.1 Screen D1 – Assets List

**Audience:** Data Product Owners, Engineers.

**Wireframe**

- Header: `Assets`
- Filters:
  - Status: [All | Draft | Active | Public | Retired]
  - Domain: multi-select
  - Search box (by name, slug, description).
- Table columns:
  - Asset Name
  - Domain
  - Status
  - Quality: badge (`Unknown`, `Pass`, `Warn`, `Fail`)
  - Compliance: badge (`Unknown`, `Pass`, `Warn`, `Fail`)
  - Updated at
  - Actions: [View], [Edit], [More...]

Floating button: **+ New Asset**.

---

### 5.2 Screen D2 – Asset Detail

**Wireframe**

- Header:
  - Name, domain
  - Status badge
  - Buttons:
    - **Edit Metadata**
    - **Open Contract Editor**
    - **Attach / Replace Data**
    - **Open in Marketplace** (if listing exists)

- Summary cards:
  1. **Contract**  
     - Status: VALID / INVALID / WARNING_ONLY  
     - Spec type/version (if external origin)  
     - Button: “View / Edit Contract”
  2. **Data Quality**  
     - Latest run summary (score, status)  
     - Link: “View all DQ runs”
  3. **Compliance**  
     - Latest compliance status & risk level  
     - Link: “View details”
  4. **Marketplace**  
     - If listed: listing status, price model  
     - If not: “Not listed on marketplace”

- Tabs:
  - Overview
  - Schema
  - DQ Runs
  - Compliance Runs
  - Audit Log (filtered to this asset)

---

## 6. Flow E – DQ & Compliance Reports

### 6.1 Screen E1 – DQ Runs List

**Audience:** Data Product Owners, Engineers.

- Header: `Data Quality Runs`
- Filters:
  - Asset
  - Status (Pending, Running, Succeeded, Failed)
  - Profile (e.g., `intake_basic`)
  - Date range
- Table:
  - Asset name
  - Dataset ID / Version
  - Profile key
  - Overall status
  - Score
  - Started at, Completed at
  - Link: “View report”

### 6.2 Screen E2 – DQ Run Detail

**Wireframe**

- Header:
  - “DQ Run for Asset: Customer Orders, Dataset: v1”
- Summary card:
  - Overall status (Pass/Warn/Fail)
  - Quality score
  - Row count analyzed
  - Execution time
- Sections:
  - **Check Summary** (table)
    - Check name
    - Category (Completeness/Validity/Uniqueness)
    - Status
    - Details (thresholds, metrics)
  - **Fields View**
    - Table: Column, Issues, Null ratio, Distinct count

---

### 6.3 Screen E3 – Compliance Run Detail

**Audience:** Compliance Officer, Product Owner.

**Wireframe**

- Header:
  - “Compliance Run for Asset: Customer Orders”
- Summary card:
  - Overall status (Pass/Warn/Fail)
  - Risk level (Low/Medium/High)
  - `allowed_to_store` flag
  - Applicable regimes (GDPR, LGPD, etc.)

- Sections:
  - **Data Categories Detected**
    - Chips: PII_EMAIL, PII_NAME, etc.
  - **Column Findings**
    - Table:
      - Column name
      - Detected categories
      - Risk comments
      - Recommendations
  - **Actions** (depending on role):
    - For Compliance Officer:
      - Mark dataset as “Approved” / “Rejected” in an internal policy context (future).
    - For Product Owner:
      - “Open Contract” to adjust contract-level legal fields.

---

## 7. Flow F – Marketplace Browse & Purchase (Data Consumer)

### 7.1 Screen F1 – Marketplace Home

**Audience:** Data Consumer / Buyer.

**Wireframe**

- Header: `Marketplace`
- Search bar: “Search by keyword, field, or domain”
- Filters:
  - Domain
  - Price model (Free, One-time, Subscription)
  - Quality status (Pass/Warn/Fail)
  - Compliance status (Pass/Warn)
- Listing cards:
  - Title
  - Short description
  - Provider name
  - Quality badge, Compliance badge
  - Price (e.g., “$99 one-time” or “Free”)
  - Button: “View details”

---

### 7.2 Screen F2 – Listing Detail

**Wireframe**

- Header:
  - Listing title
  - Provider / Tenant name
- Sections:
  - **What’s inside**
    - Schema preview (list of key fields)
    - Sample rows (if allowed)
  - **Quality & Compliance**
    - Latest summary badges & short description
  - **Usage & License**
    - Human-readable license summary
  - **Price & Purchase**
    - Price details
    - Button: `Request Access` or `Buy Now` (depending on billing integration readiness)

On `Request Access` click:

- Create marketplace order and show: “Your request has been submitted.” (MVP may auto-approve).

---

### 7.3 Screen F3 – My Data / Entitlements

**Audience:** Data Consumer.

- Header: `My Data`
- Table:
  - Asset name
  - Provider
  - Entitlement status (Active / Expired / Revoked)
  - Access type (Download / API)
  - Actions: `Open asset`, `Download`, `View contract`

---

## 8. Flow G – Audit Logs & Compliance View (Auditor)

### 8.1 Screen G1 – Audit Log Overview

**Audience:** Auditor, Tenant Admin.

**Wireframe**

- Header: `Audit Logs`
- Filters:
  - Event type (Asset Created, Contract Validated, DQ Run Completed, Compliance Run Completed, Marketplace Order Created, etc.)
  - Asset
  - User
  - Date range
- Table:
  - Timestamp (UTC, explicit)
  - Event type
  - Actor (user)
  - Resource (Asset/Contract/Run)
  - Short details
- Button: `Export CSV`

Clicking a row → opens detail drawer:

- Shows structured JSON-ish view of `details_json`.

---

### 8.2 Screen G2 – Asset-Centric Audit View

From Asset Detail → “Audit Logs” tab:

- Same table but pre-filtered to this asset.

---

## 9. Flow H – Minimal Admin (Tenant Settings)

### 9.1 Screen H1 – Tenant Settings (MVP)

**Audience:** Tenant Admin.

- Tabs:
  - General
  - DQ & Compliance Defaults
  - API Keys

**DQ & Compliance Defaults:**

- Toggle: “Run DQ checks on every data intake” (on/off).
- Toggle: “Run compliance checks on every data intake” (on/off).
- Dropdown: “Default regimes for intake” (e.g., GDPR + LGPD).

**API Keys:**

- List of keys:
  - Name, created at, last used.
- Buttons:
  - `Create new key`
  - `Revoke`

---

## 10. Notes for Design & Implementation

- All screens above are **wireframes**, not visual design.  
- UI components should be consistent across:
  - Tables
  - Filters
  - Badges
  - Tabs and cards
- Contract editing **must** clearly distinguish:
  - Normalized HubContract view (source of truth for platform)  
  - Original spec view (ODCS/DataContract.com), if exposed later to advanced users.
- Jobs (DQ/Compliance) should always expose:
  - “Last run” summary in asset and listing screens,  
  - With deep links to detailed run pages for debugging.

This document should be used together with:

- `Personas.md`  
- `SystemRequirements.md`  
- `MVP_Scope.md`  
- `Domain_Model.md`  
- `API_Spec_v1.md`  

to drive the first UI design and frontend implementation.
"""
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

"/mnt/data/UX_MVP_Flows.md"
