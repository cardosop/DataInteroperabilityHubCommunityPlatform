# Domain Model (MVP)

This document defines the **core domain model** for the Interoperable Data Hub MVP:

- Entities & relationships
- Multi-tenant boundaries
- Canonical **HubContract** model & normalization from ODCS / DataContract.com
- JSON shapes for key artifacts (contracts, DQ, compliance, jobs, audit)
- Status enums used across the platform

It is **conceptual**, not a DB schema. The database design, APIs and semantic mappings must be consistent with this model.

---

## 0. Conventions

- All IDs are **UUIDv4** strings (e.g. `"a4b2c3d4-..."`).
- All timestamps are **UTC** ISO 8601 strings.
- All entities are **multi-tenant** unless explicitly global.
- Fields marked **[MVP]** are required for v1; others are future-friendly.
- JSON examples are indicative of **API-level shapes**; internal storage may differ.

---

## 1. Identity & Tenancy

### 1.1 Tenant

Represents an organization (company, team, or individual account) using the hub.

**Fields**

- `id` (UUID)
- `name` (string)
- `slug` (string) – URL-safe, unique.
- `status` (enum):
  - `ACTIVE`
  - `SUSPENDED`
  - `DELETED`   **[MVP: lifecycle state for soft deletion]**
- `kyc_status` (enum):  
  - `UNVERIFIED`
  - `VERIFIED`   **[MVP: only these two]**
- `created_at` (datetime)
- `updated_at` (datetime)
- `deleted_at` (datetime, nullable)   **[MVP: timestamp when tenant was marked for deletion]**

**Notes**

- Only tenants with `kyc_status = VERIFIED` are allowed to publish **public/marketplace** assets.
- **Suspended Tenant Behavior**:
  - `status = SUSPENDED` blocks **write operations** for that tenant:
    - Cannot create/edit assets, contracts, datasets.
    - Cannot upload files.
    - Cannot trigger DQ/compliance jobs.
    - Cannot create marketplace listings.
    - Cannot approve/reject orders.
  - **Read operations are allowed** (for data export/backup):
    - Can read/view existing assets, contracts, datasets.
    - Can download files (via `GET /files/{id}/download`).
    - Can view audit logs.
    - Can access marketplace (browse, but cannot create listings).
  - **User management**:
    - Cannot create new users.
    - Existing users can log in but are limited to read-only operations.
  - **Reactivation**: Suspended tenants can be reactivated by Platform Admin (sets `status = ACTIVE`).
  - **Timeline**: Suspension is temporary; if not reactivated within a configurable period (e.g., 90 days), Platform Admin may proceed with deletion.

**Tenant Suspension Notification Flow**

When a tenant is suspended (`status = SUSPENDED`), the following notification process is executed:

- **Immediate notification** (within 5 minutes of suspension):
  - **Email to tenant admins**: All users with `TENANT_ADMIN` role receive email notification
  - **Email content**:
    - Subject: "Your tenant account has been suspended"
    - Body includes:
      - Tenant name and ID
      - Reason for suspension (if available)
      - Impact summary (read-only access, no write operations)
      - Contact information for support
      - Instructions for reactivation (if applicable)
  - **In-app notification**: Users see a banner/notification when they log in indicating tenant suspension
  - **Audit event**: `TENANT_SUSPENDED` audit event is emitted with suspension reason

- **Grace period notification** (if applicable):
  - If suspension has a grace period before deletion:
    - **30 days before deletion**: Email reminder to tenant admins
    - **7 days before deletion**: Final warning email
    - **On deletion**: Final notification email (if tenant is deleted)

- **User notification** (non-admin users):
  - **Email notification** (optional, configurable):
    - All active users in the tenant may receive email notification
    - Email includes:
      - Tenant suspension notice
      - Impact on their access (read-only)
      - Contact information for questions
  - **In-app notification**: Users see suspension banner when accessing the platform

- **Notification delivery**:
  - Notifications are sent asynchronously (within 5 minutes of suspension)
  - Notification failures are logged but do not affect suspension process
  - Retry mechanism: Failed notifications are retried up to 3 times with exponential backoff

- **Reactivation notification**:
  - When tenant is reactivated (`status = ACTIVE`):
    - **Email to tenant admins**: Notification that tenant has been reactivated
    - **Email content**:
      - Subject: "Your tenant account has been reactivated"
      - Body includes:
        - Tenant name
        - Confirmation that all services are restored
        - Any changes that occurred during suspension
    - **Audit event**: `TENANT_REACTIVATED` audit event is emitted

---

### 1.2 User

Represents a human user belonging to a tenant.

**Fields**

- `id` (UUID)
- `tenant_id` (UUID)
- `email` (string) – unique within tenant.
- `name` (string)
- `status` (enum):
  - `ACTIVE`
  - `INVITED`
  - `DISABLED`
- `created_at` (datetime)
- `updated_at` (datetime)

---

### 1.3 Role & Membership

Roles control a user’s permissions inside a tenant.

**Enum: `RoleKey`**

- `TENANT_ADMIN`
- `DATA_PROVIDER`  (Data Product Owner / Data Engineer)
- `DATA_CONSUMER`
- `AUDITOR`        (Compliance/Privacy roles)

**UserRoleMembership**

- `id` (UUID)
- `tenant_id` (UUID)
- `user_id` (UUID)
- `role_key` (`RoleKey`)

**Notes**

- A user can hold multiple roles in the same tenant (e.g. `TENANT_ADMIN` + `DATA_PROVIDER`).
- Platform-level admins (Marketplace Operator) are handled separately (e.g. via special tenant or out-of-band config).

---

## 2. Contract & Normalization Domain

### 2.1 Design Principles

- The hub **accepts contracts in multiple external standards and versions**:
  - ODCS versions (e.g. v2.2.2, v3.x).
  - DataContract.com specification versions.
- The hub **internally uses a single canonical model**: **HubContract v1**.
- We must never lose information:
  - The original contract file is stored verbatim.
  - All mappable concepts are normalized into HubContract.
  - Extra fields are preserved under `extensions` in the canonical JSON.
- We track separately:
  - **Spec-level validity** (via DataContract CLI) → `validation_status`.
  - **Normalization success** → `normalization_status`.

### 2.2 Contract Entity

Represents a data contract in the hub, including original spec and normalized HubContract.

**Fields**

- `id` (UUID)
- `tenant_id` (UUID)
- `asset_id` (UUID) – for MVP each contract **belongs to exactly one asset**.
- `status` (enum) – **lifecycle state** (user-controlled):
  - `DRAFT` – Contract is being created/edited, not yet active
  - `ACTIVE` – Contract is validated and in use (requires `validation_status = VALID` or `WARNING_ONLY`)
  - `RETIRED` – Contract is no longer in use but retained for audit/history 

- **Original Specification Metadata**

  - `original_spec_type` (enum):
    - `ODCS`
    - `DATACONTRACT_COM`
  - `original_spec_version` (string)  
    - e.g. `"3.0.2"`, `"2.2.2"`, `"0.4.0"`.
  - `original_format` (enum):
    - `JSON`
    - `YAML`
  - `original_raw` (text) – entire contract file as uploaded.
  - `original_file_name` (string, optional).

- **CLI Validation Result**

  - `validation_status` (enum) – **CLI validation result** (system-determined):
    - `VALID` – CLI succeeded, contract is valid
    - `INVALID` – CLI succeeded, contract fails validation
    - `WARNING_ONLY` – CLI succeeded, contract is technically valid but with warnings
    - `ERROR` – CLI failed to run, timed out, or produced unknown output
    - `null` – Contract has not been validated yet
  - `validation_errors` (JSON array)
  - `validation_warnings` (JSON array)
  - `cli_version` (string) – version of DataContract CLI used.
  - `last_validated_at` (datetime)

- **Normalization to HubContract**

  - `hub_contract_version` (int) – e.g. `1` for HubContract v1.
  - `hub_contract_json` (JSON) – canonical HubContract representation (see 2.3).
  - `normalization_status` (enum):
    - `NOT_NORMALIZED`        – e.g. just uploaded, not processed.
    - `NORMALIZED_OK`         – fully mapped, no issues.
    - `NORMALIZED_WITH_WARNINGS` – mapped but some fields only in `extensions`.
    - `NORMALIZATION_FAILED`  – mapping could not produce a consistent HubContract.
  - `normalization_errors` (JSON array)
  - `normalization_warnings` (JSON array)

- **Audit Metadata**

  - `created_by_user_id` (UUID)
  - `created_at` (datetime)
  - `updated_at` (datetime)

**Rules (MVP)**

**Contract Status vs Validation Status:**
- `status` (lifecycle): User-controlled state (`DRAFT`, `ACTIVE`, `RETIRED`)
- `validation_status` (CLI result): System-determined from DataContract CLI execution
- **Relationship:**
  - A contract can have `status = DRAFT` and `validation_status = VALID` (validated but not yet activated)
  - A contract can have `status = ACTIVE` only if `validation_status = VALID` or `WARNING_ONLY` (per tenant policy)
  - `status = ACTIVE` requires both:
    - `validation_status in { VALID, WARNING_ONLY }`
    - `normalization_status in { NORMALIZED_OK, NORMALIZED_WITH_WARNINGS }`

**Asset Activation Rules:**
- An **asset** can be `ACTIVE` only if:
  - It has a **single primary contract** with:
    - `status = ACTIVE` (contract lifecycle state)
    - `validation_status = VALID` OR `WARNING_ONLY` (per tenant policy)
    - `normalization_status in { NORMALIZED_OK, NORMALIZED_WITH_WARNINGS }`
  - If asset has a dataset:
    - `dq_status in { PASS, WARN }` (not `FAIL` or `UNKNOWN`)
    - `compliance_status in { PASS, WARN }` (not `FAIL` or `UNKNOWN`)
  - Dataset is optional: Asset can be `ACTIVE` without a dataset (contract-only asset)

- We **never overwrite** `original_raw`; updates produce new content and update timestamps, but API should keep previous version content accessible via audit/history (full version history can be deferred but not contradicted).

---

### 2.3 HubContract v1 – Canonical JSON Shape

`hub_contract_json` follows a stable internal schema (**HubContract v1**). It is **not** ODCS or DataContract.com; it is our normalized internal model.

**Validation Rules**

HubContract JSON MUST conform to the following validation rules:

**Required Fields**:
- `hub_contract_version` (integer): Must be `1` for HubContract v1.
- `id` (string): Contract identifier (non-empty, max 255 characters).
- `info` (object): Metadata section (required).
  - `info.name` (string): Contract name (required, non-empty).
- `schema` (object): Schema definition (required).
  - `schema.fields` (array): Array of field definitions (required, non-empty).

**Optional Fields**:
- `info.description` (string, nullable)
- `info.version` (string, nullable)
- `info.owners` (array, nullable)
- `info.tags` (array, nullable)
- `schema.primary_key` (array, nullable)
- `schema.unique_constraints` (array, nullable)
- `schema.indexes` (array, nullable)
- `quality` (object, nullable)
- `privacy_compliance` (object, nullable)
- `lifecycle` (object, nullable)
- `marketplace` (object, nullable)
- `extensions` (object, nullable)

**Field Type Constraints**:
- `hub_contract_version`: Must be integer `1` (for v1).
- `id`: Must be non-empty string, max 255 characters.
- `info.name`: Must be non-empty string, max 255 characters.
- `info.version`: If present, must be valid semantic version string (e.g., `"1.0.0"`).
- `schema.fields`: Must be non-empty array. Each field must have:
  - `name` (string, required): Field name (non-empty, max 255 characters).
  - `data_type` (string, required): One of `string`, `integer`, `float`, `boolean`, `date`, `datetime`, `timestamp`.
  - `nullable` (boolean, required): Whether field can be null.
- `quality.rules`: If present, must be array. Each rule must have:
  - `rule_id` (string, required): Unique rule identifier.
  - `dimension` (string, required): One of `completeness`, `accuracy`, `consistency`, `timeliness`, `validity`, `uniqueness`.
  - `expression` (string, required): Rule expression (SQL-like or domain-specific).
  - `severity` (string, required): One of `ERROR`, `WARNING`, `INFO`.

**Enum Value Validation**:
- `schema.fields[].data_type`: Must be one of: `string`, `integer`, `float`, `boolean`, `date`, `datetime`, `timestamp`.
- `quality.rules[].dimension`: Must be one of: `completeness`, `accuracy`, `consistency`, `timeliness`, `validity`, `uniqueness`.
- `quality.rules[].severity`: Must be one of: `ERROR`, `WARNING`, `INFO`.
- `privacy_compliance.jurisdictions[]`: If present, must be array of strings from: `GDPR`, `LGPD`, `CCPA`, `HIPAA`, `SOX`.
- `privacy_compliance.legal_bases[]`: If present, must be array of strings from: `CONSENT`, `CONTRACT`, `LEGAL_OBLIGATION`, `VITAL_INTERESTS`, `PUBLIC_TASK`, `LEGITIMATE_INTERESTS`.

**Cross-Field Validation Rules**:
- `schema.primary_key`: If present, all referenced field names must exist in `schema.fields[].name`.
- `schema.unique_constraints`: If present, each constraint's field names must exist in `schema.fields[].name`.
- `schema.indexes`: If present, each index's field names must exist in `schema.fields[].name`.
- `privacy_compliance.contains_personal_data`: If `true`, `privacy_compliance.personal_data_categories` must be non-empty array.

**JSON Schema Definition**

A formal JSON Schema definition for HubContract v1 is maintained at:
- **Schema location**: `/schemas/hubcontract-v1.json` (relative to project root).
- **Schema version**: `1.0.0`.
- **Validation**: All `hub_contract_json` values MUST validate against this schema before being stored in the database.

**Top-level structure (simplified)**

```json
{
  "hub_contract_version": 1,
  "id": "contract-internal-id-or-name",
  "info": {
    "name": "Customer Orders",
    "description": "Orders data product for analytics.",
    "version": "1.0.0",
    "owners": [
      {
        "name": "Data Platform Team",
        "email": "dataplatform@example.com"
      }
    ],
    "tags": ["sales", "orders", "analytics"]
  },
  "schema": {
    "fields": [
      {
        "name": "order_id",
        "data_type": "string",
        "nullable": false,
        "description": "Unique identifier for the order.",
        "semantic_type": "ORDER_ID",
        "metadata": {}
      }
    ],
    "primary_key": ["order_id"],
    "unique_constraints": [],
    "indexes": []
  },
  "quality": {
    "default_profile_key": "intake_basic",
    "rules": [
      {
        "rule_id": "not_null_order_id",
        "dimension": "completeness",
        "expression": "order_id IS NOT NULL",
        "severity": "ERROR"
      }
    ]
  },
  "privacy_compliance": {
    "contains_personal_data": true,
    "personal_data_categories": [
      "PII_DIRECT_EMAIL",
      "PII_DIRECT_PHONE"
    ],
    "jurisdictions": ["GDPR", "LGPD"],
    "legal_bases": ["CONSENT", "CONTRACT"],
    "retention_policy": {
      "period": "P5Y",
      "notes": "5 years retention after contract end."
    }
  },
  "lifecycle": {
    "data_source": "OLTP.orders",
    "refresh_cadence": "DAILY",
    "slas": {
      "availability": "99.0",
      "latency_ms_p95": 5000
    }
  },
  "marketplace": {
    "license_summary": "Internal only; external with NDA.",
    "intended_use": [
      "analytics",
      "machine_learning"
    ],
    "restricted_use": [
      "credit_scoring",
      "individual-level marketing"
    ]
  },
  "extensions": {
    "odcs": {
      "...": "fields from ODCS that have no direct HubContract mapping"
    },
    "datacontract_com": {
      "...": "fields from DataContract.com that have no direct mapping"
    }
  }
}
