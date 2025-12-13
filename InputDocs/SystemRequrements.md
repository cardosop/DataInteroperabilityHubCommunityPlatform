# System Requirements

This document structures the system requirements for the **Interoperable Data Hub**:  
a platform centered on data contracts, data quality & compliance as services, semantic/ontology coverage, and a data marketplace.

---

## 1. Data Contract Standards & Compliance

### 1.1 Supported Standards and Versions

The platform **MUST** support and enforce the following data contract standards and versions:

- Open Data Contract Standard (ODCS) v3.0.2+:
  - https://bitol-io.github.io/open-data-contract-standard/v3.0.2  
  - https://bitol-io.github.io/open-data-contract-standard/v3.0.1  
  - https://bitol-io.github.io/open-data-contract-standard/v3.0.0  
  - https://bitol-io.github.io/open-data-contract-standard/v3.0.0-preview  
  - https://bitol-io.github.io/open-data-contract-standard/v2.2.2  

**Note:** The Data Contract Specification (DCS) has been deprecated. Only ODCS contracts are supported.  

### 1.2 Example Contracts

- The system **MUST** be able to validate and work with ODCS example contracts conforming to the Open Data Contract Standard v3.0.2+  

### 1.3 Validation, Linting & Conversion

- The **DataContract CLI** **MUST** be used for:
  - Linting data contracts.
  - Validating data contracts.
  - Converting between supported formats/versions.

- Official references:
  - CLI website: https://cli.datacontract.com  
  - GPT reference: https://gpt.datacontract.com/sources/cli.datacontract.com  
  - GitHub: https://github.com/datacontract/datacontract-cli  

- The platform **MUST** integrate DataContract CLI as a core validation mechanism via an internal service/API (see §1.5).

### 1.4 Internal Canonical Model & Versioning

The platform **MUST** be able to receive, store, edit/manage, and export contracts while remaining compliant with the supported standards and versions.

- **Canonical internal model ("HubContract")**
  - Define a canonical JSON model able to represent all required fields from:
    - ODCS v2.2.2–v3.x
  - The **UI, APIs, semantic layer, search, and audits** operate on this canonical model.

- **Preservation of original contract**
  - For every contract, the system MUST store:
    - `original_spec_type` (e.g. `odcs`)
    - `original_spec_version` (e.g. `3.0.2`)
    - `original_raw` (original JSON/YAML as uploaded)
    - `normalized_contract` (canonical HubContract JSON)

- **HubContract versioning**
  - The canonical model MUST include a `hub_contract_version` field.
  - When the internal model evolves incompatibly, a new `hub_contract_version` is introduced.
  - The platform MUST remain capable of:
    - Reading older `hub_contract_version`s.
    - Migrating/upgrading them via controlled migration scripts when required.

- **Multi-version support**
  - Multiple ODCS versions MUST be supported in parallel.
  - Internally, the canonical model SHOULD shield other components from version differences.

- **Version selection for new contracts**
  - For **new contracts created in the UI**, the default version MUST be:
    - The most recent supported ODCS version (e.g. currently `v3.0.2`).
  - Users MUST be able to choose:
    - A different supported ODCS version, at creation time.
  - Conversion between versions MUST be mediated by DataContract CLI.

- **Conversions**
  - Any conversion between:
    - Original → canonical
    - Canonical → target spec/version
  - MUST rely on **DataContract CLI** (no custom spec-specific parsing/rewrites).

### 1.4.1 Complete Normalization Requirements

The platform **MUST** perform complete normalization of all contract sections to ensure full information preservation and comprehensive semantic mapping.

- **Complete Section Coverage**
  - Normalization MUST extract and preserve ALL sections from source contracts:
    - **Info section**: name, description, version, owners (array with name/email), tags (array)
    - **Schema section**: fields (with all properties: name, data_type, nullable, description, semantic_type, format, pattern, enum, default, min/max length/value, metadata), primary_key, unique_constraints, indexes
    - **Quality section**: default_profile_key, rules (with rule_id, dimension, expression, severity)
    - **Privacy/Compliance section**: contains_personal_data, personal_data_categories, jurisdictions, legal_bases, retention_policy (period, notes)
    - **Lifecycle section**: data_source, refresh_cadence, slas (availability, latency_ms_p95)
    - **Marketplace section**: license_summary, intended_use, restricted_use
    - **Extensions section**: Unmappable fields preserved in extensions.odcs

- **Field-Level Property Extraction**
  - Normalization MUST extract ALL field properties from source contracts:
    - Required: name, data_type, nullable
    - Optional: description, semantic_type, format, pattern, enum, default, min_length, max_length, minimum, maximum, metadata
  - No field-level information MUST be lost (all properties either mapped or in extensions)

- **Normalization Status Tracking**
  - Normalization status MUST accurately reflect completeness:
    - `NORMALIZED_OK`: All sections mapped successfully
    - `NORMALIZED_WITH_WARNINGS`: Some sections preserved in extensions
    - `NORMALIZATION_FAILED`: Critical sections missing or invalid

- **Information Preservation**
  - The original contract file (`original_raw`) MUST be preserved verbatim
  - All mappable concepts MUST be normalized into HubContract canonical structure
  - Unmappable fields MUST be preserved in `extensions.{source_spec}` section
  - Normalization MUST never lose information (all source fields either mapped or preserved)

### 1.5 DataContract CLI Integration Model - The CLI is wrapped by an internal microservice (e.g. `datacontract-service`) exposing HTTP endpoints: - `POST /validate` → runs `datacontract validate` - `POST /lint` → runs `datacontract lint` - `POST /convert` → runs `datacontract convert ...` - **Invocation** - The hub backend calls this service synchronously for small/normal contracts. - For heavy operations, it may call asynchronously via a job queue with polling from the UI (see §13). - **Error severity & validation status** - The platform MUST interpret CLI output into a `validation_status`: - `VALID` - `INVALID` - `WARNING_ONLY` - `ERROR` (internal error, timeout, or unexpected failure) - Rules: - Only `VALID` contracts can become “active”. - `WARNING_ONLY` MAY be allowed as active but MUST be clearly marked in the UI. - `INVALID` and `ERROR` MUST block activation until resolved. - **Timeouts & failures** - Each CLI call has a configurable timeout (e.g. 30–60 seconds). - On timeout or non-zero exit: - Mark validation as `ERROR`. - Return a user-visible message (“validation service unavailable; please try again”). - Log the error in system logs and audit trail. - **Concurrency** - The service MUST handle concurrent validation requests. - Heavy or long-running validations SHOULD be processed via background jobs. - **CLI versioning** - CLI version is pinned by container/image tag and updated **manually**. - Each validation result SHOULD store: - `cli_version_used` for future audit and debugging.

#### 1.5.1 Service Wrapper & Invocation

- The CLI is wrapped by an internal microservice (e.g. `datacontract-service`) exposing HTTP endpoints:
  - `POST /validate` → runs `datacontract validate …`
  - `POST /lint` → runs `datacontract lint …`
  - `POST /convert` → runs `datacontract convert …`

- The hub backend NEVER shells out to the CLI directly; it only calls this service.

- Invocation model:
  - For **small/normal contracts** (typical files, up to a configured size limit):
    - Backend calls the service **synchronously**, expecting a response within a timeout (e.g. 30–60s).
  - For **heavy operations** (very large contracts, mass conversions, bulk migration tools):
    - The backend MUST use **asynchronous** jobs:
      - Create a Job record.
      - Call the service in background.
      - UI/API polls `/jobs/{id}` for completion.

- Concurrency:
  - The service MUST handle multiple validations concurrently.
  - For protection, it MUST enforce:
    - Max concurrent CLI processes per node.
    - Queueing/backpressure for bursts.

#### 1.5.2 Error Handling, Timeouts & Retry Policy

- The platform MUST interpret CLI results into a `validation_status` on the Contract:

  - `VALID`          – CLI succeeded and contract is valid.
  - `INVALID`        – CLI succeeded, but contract fails validation.
  - `WARNING_ONLY`   – CLI succeeded, contract is technically valid but with warnings.
  - `ERROR`          – CLI did not complete successfully (timeout, crash, unexpected output).

- **Timeouts & failures**

  - Each CLI call has a configurable timeout (e.g. 30–60 seconds for sync calls).
  - If the CLI process:
    - Exits with a non-zero code that indicates **user error** (invalid contract/spec):
      - Map to `validation_status = INVALID`.
      - Include structured error messages from CLI output.
    - Exits with a non-zero code that indicates **internal/technical error** (crash, I/O error, etc.) OR times out:
      - Treat as **transient failure**.
      - Map to `validation_status = ERROR`.

- **Retry logic (technical failures only)**

  - The service MUST implement a small, bounded retry policy for **transient** errors:
    - Example:
      - Up to 2 retries with exponential backoff (e.g. 1s, 3s).
    - Only retry when:
      - The error is clearly NOT due to contract content (invalid user input).
      - The error code / stderr indicates infra issues (timeout, resource exhaustion, unexpected exception).
  - No retries for:
    - `INVALID` contracts (user must fix).
    - Clearly deterministic spec errors (unsupported version, etc.).

- **Result recording**

  - For every CLI call, the service MUST record:
    - `cli_exit_code`
    - `cli_stdout` and `cli_stderr` (or safely redacted summaries) in internal logs.
    - `validation_status` on Contract.
  - User-facing error messages MUST be:
    - Derived from CLI output but cleaned up and localized.
    - Non-leaky (no internal paths, stack traces, or secrets).

#### 1.5.3 Contract Validation Error Reporting Format

**Error Response Structure**

When contract validation fails, the API MUST return structured error responses that enable clients to:
- Display user-friendly error messages
- Highlight specific fields or sections with errors
- Group errors by category (syntax, schema, business rules)
- Provide actionable guidance for fixing errors

**Standard Error Response Format**

```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "The data contract is not valid.",
    "http_status": 400,
    "request_id": "req-1234567890",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "validation_status": "INVALID",
      "cli_version": "0.9.0",
      "original_spec_type": "ODCS",
      "original_spec_version": "1.0.0",
      "errors": [
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.fields[0].name",
          "message": "Field name is required.",
          "rule_id": "field_name_required"
        },
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.fields[1].data_type",
          "message": "Invalid data type 'stringy'. Must be one of: string, integer, float, boolean, date, datetime, timestamp.",
          "rule_id": "data_type_enum",
          "suggestion": "Use 'string' instead of 'stringy'."
        },
        {
          "severity": "WARNING",
          "category": "QUALITY",
          "path": "$.quality.rules[0].expression",
          "message": "Quality rule expression may be inefficient for large datasets.",
          "rule_id": "quality_rule_performance"
        }
      ],
      "warnings": [
        {
          "severity": "WARNING",
          "category": "METADATA",
          "path": "$.info.description",
          "message": "Description is missing. Consider adding a description for better discoverability.",
          "rule_id": "description_recommended"
        }
      ],
      "summary": {
        "total_errors": 2,
        "total_warnings": 2,
        "errors_by_category": {
          "SCHEMA": 2,
          "QUALITY": 0,
          "METADATA": 0
        }
      }
    }
  }
}
```

**Error Object Structure**

Each error in the `errors` array contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `severity` | string (enum) | Yes | `ERROR`, `WARNING`, `INFO` |
| `category` | string (enum) | Yes | `SCHEMA`, `METADATA`, `QUALITY`, `COMPLIANCE`, `SYNTAX`, `BUSINESS_RULE` |
| `path` | string (JSONPath) | Yes | JSONPath to the field/object with the error (e.g., `$.schema.fields[0].name`) |
| `message` | string | Yes | Human-readable error message (user-facing, no stack traces) |
| `rule_id` | string | No | Identifier of the validation rule that failed (for reference) |
| `suggestion` | string | No | Actionable suggestion for fixing the error |
| `line_number` | integer | No | Line number in source file (if applicable, for YAML/JSON files) |
| `column_number` | integer | No | Column number in source file (if applicable) |

**Error Categories**

| Category | Description | Examples |
|----------|-------------|----------|
| `SYNTAX` | JSON/YAML parsing errors | Invalid JSON, missing quotes, trailing commas |
| `SCHEMA` | Schema definition errors | Missing required fields, invalid field types, invalid enum values |
| `METADATA` | Metadata errors | Missing description, invalid version format, missing owners |
| `QUALITY` | Quality rule errors | Invalid quality rule expressions, unsupported dimensions |
| `COMPLIANCE` | Compliance configuration errors | Invalid jurisdiction codes, missing legal bases |
| `BUSINESS_RULE` | Business logic validation errors | Circular dependencies, invalid references |

**Severity Levels**

| Severity | Meaning | Impact on Contract Status |
|----------|---------|--------------------------|
| `ERROR` | Contract is invalid and cannot be activated | `validation_status = INVALID` |
| `WARNING` | Contract is valid but has issues | `validation_status = WARNING_ONLY` (if no errors) |
| `INFO` | Informational message (best practices) | `validation_status = VALID` (no impact) |

**CLI Error Mapping**

The platform MUST map DataContract CLI output to the structured error format:

**CLI Output Example**:
```
Error: Field 'customer_id' in schema.fields[0] has invalid data_type 'stringy'
  at schema.fields[0].data_type (line 15, column 8)
  Rule: data_type_enum
```

**Mapped Error**:
```json
{
  "severity": "ERROR",
  "category": "SCHEMA",
  "path": "$.schema.fields[0].data_type",
  "message": "Invalid data type 'stringy'. Must be one of: string, integer, float, boolean, date, datetime, timestamp.",
  "rule_id": "data_type_enum",
  "line_number": 15,
  "column_number": 8,
  "suggestion": "Use 'string' instead of 'stringy'."
}
```

**Error Grouping**

Errors SHOULD be grouped by category for easier navigation:

```json
{
  "errors_by_category": {
    "SCHEMA": [
      { "path": "$.schema.fields[0].name", "message": "..." },
      { "path": "$.schema.fields[1].data_type", "message": "..." }
    ],
    "METADATA": [
      { "path": "$.info.description", "message": "..." }
    ]
  }
}
```

**Validation Status Determination**

The `validation_status` is determined by error severity:

- **`VALID`**: No errors, only INFO messages (or no messages)
- **`WARNING_ONLY`**: Only WARNING and INFO messages, no ERROR messages
- **`INVALID`**: At least one ERROR message
- **`ERROR`**: CLI failed to execute (timeout, crash, unexpected output)

**API Response Examples**

**Example 1: Invalid Contract (Multiple Errors)**
```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "The data contract is not valid. Found 3 errors.",
    "http_status": 400,
    "details": {
      "validation_status": "INVALID",
      "errors": [
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.fields[0].name",
          "message": "Field name is required.",
          "rule_id": "field_name_required"
        },
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.primary_key[0]",
          "message": "Primary key field 'order_id' does not exist in schema.fields.",
          "rule_id": "primary_key_reference"
        },
        {
          "severity": "ERROR",
          "category": "SYNTAX",
          "path": "$",
          "message": "Invalid JSON: Unexpected token ',' at line 42.",
          "line_number": 42
        }
      ],
      "summary": {
        "total_errors": 3,
        "total_warnings": 0
      }
    }
  }
}
```

**Example 2: Valid Contract with Warnings**
```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "The data contract is valid but has warnings.",
    "http_status": 400,
    "details": {
      "validation_status": "WARNING_ONLY",
      "errors": [],
      "warnings": [
        {
          "severity": "WARNING",
          "category": "METADATA",
          "path": "$.info.description",
          "message": "Description is missing. Consider adding a description for better discoverability.",
          "rule_id": "description_recommended"
        },
        {
          "severity": "WARNING",
          "category": "QUALITY",
          "path": "$.quality.rules[0].expression",
          "message": "Quality rule expression may be inefficient for large datasets.",
          "rule_id": "quality_rule_performance",
          "suggestion": "Consider using indexed columns or sampling for better performance."
        }
      ],
      "summary": {
        "total_errors": 0,
        "total_warnings": 2
      }
    }
  }
}
```

**Example 3: CLI Execution Error**
```json
{
  "error": {
    "code": "CONTRACT_CLI_ERROR",
    "message": "Contract validation service is temporarily unavailable.",
    "http_status": 502,
    "details": {
      "validation_status": "ERROR",
      "cli_exit_code": -1,
      "error_type": "TIMEOUT",
      "retry_after_seconds": 60
    }
  }
}
```

- **Audit**

  - Each validation attempt (including retries) MUST generate an AuditEvent with:
    - Contract ID.
    - `validation_status`.
    - Whether it was a retry or first attempt.
    - `cli_version_used`.
    - Error summary (count of errors/warnings by category).

#### 1.5.3 CLI Versioning & Upgrade Strategy

- **Version pinning**

  - The DataContract CLI version used in production MUST be **pinned**:
    - E.g. via container image tag or explicit version in dependency management.
  - The `datacontract-service` MUST expose its current CLI version via:
    - Health/metadata endpoint (e.g. `GET /health` or `GET /meta`).
  - Each validation MUST store:
    - `cli_version_used` on the Contract (or in `validation_metadata`).

- **Upgrade process**

  - New CLI versions MUST go through a controlled rollout:
    1. **Staging environment**:
       - Deploy new CLI version.
       - Run regression tests using:
         - Official example contracts.
         - A sample of real (anonymized/synthetic) contracts saved from production.
    2. Compare results:
       - Number and type of VALID/INVALID/WARNING outputs.
       - Any new or removed warnings.
    3. Decide upgrade:
       - If differences are acceptable, promote to production.
       - If not, roll back and/or adjust configs.

  - In production:
    - Upgrades are **manual and explicit** (no auto-update).
    - A CLI upgrade MUST be recorded in platform release notes and internal change logs.

- **Backward compatibility & revalidation**

  - When CLI is upgraded:
    - **Existing contracts** are NOT automatically revalidated.
    - On next edit or explicit “Revalidate” action:
      - The new CLI version is used.
      - `cli_version_used` is updated.
    - Optionally, a background batch job MAY revalidate selected critical contracts and record differences (future enhancement).

#### 1.5.4 Validation Caching & Idempotency

- Goal: avoid unnecessary repeated CLI calls for contracts that haven’t changed.

- **Contract fingerprint**

  - For each contract, the platform MUST compute a **deterministic hash** (fingerprint) of:
    - `original_spec_type`
    - `original_spec_version`
    - `original_format`
    - `original_raw` (or the normalized canonical representation used for validation)
  - Example: `contract_hash = SHA256(spec_type + spec_version + format + raw_bytes)`.

- **Cache key**

  - A validation result can be uniquely identified by:
    - `(tenant_id, contract_hash, cli_version_used)`
  - If a new validation request has the **same**:
    - `tenant_id`
    - `contract_hash`
    - `cli_version_used`
  - Then:
    - The service SHOULD return the **cached result** (validation status + errors/warnings) without re-running the CLI.

- **Cache invalidation**

  - The cache MUST be invalidated when:
    - The contract content changes (different `contract_hash`).
    - The CLI version changes (`cli_version_used` differs).
    - Validation configuration changes in a way that affects behavior (e.g. new flags).
  - A user’s explicit “Force re-validate” action MUST bypass the cache and re-run the CLI.

- **Storage of cached results**

  - Cached validation results can be:
    - Stored alongside the Contract record (e.g. last CLI result).
    - Or stored in a dedicated key–value cache (e.g. Redis) keyed by `(tenant_id, contract_hash, cli_version)`.
  - In all cases, the Contract SHOULD always reflect the **latest** validation result used for business logic and UI.

- **Idempotent API behavior**

  - Repeated calls to `POST /contracts/{id}/validate` with unchanged content and same CLI version:
    - MUST return the same `validation_status` and error list (modulo timestamp).
  - This idempotency MUST hold even across retries and restarts (thanks to caching).

#### 1.5.5 Handling CLI Output Format Changes

The platform MUST be robust to changes in the DataContract CLI’s output format.

**Requirements**

- **Schema contract for CLI output**
  - The wrapper MUST validate CLI output (JSON/YAML) against a known
    schema (or shape) before using it.
  - If validation fails, the wrapper MUST:
    - treat the run as `VALIDATION_ERROR` (or equivalent),
    - surface a clear, machine-readable error code
      (e.g. `DATACONTRACT_CLI_OUTPUT_INCOMPATIBLE`),
    - log the raw output (or a redacted version) for debugging.

- **Version–format compatibility matrix**
  - Maintain a simple compatibility table in code/config, e.g.:
    - `cli_version = 0.4.x → output_schema_v1`
    - `cli_version = 0.5.x → output_schema_v2`
  - The wrapper MUST reject (or run in “safe mode”) for CLI versions that
    are **unknown** or explicitly marked as incompatible.

- **Upgrade process for breaking output changes**
  - Before upgrading the CLI version in any environment, the team MUST:
    - run the CLI against a regression set of sample contracts,
    - verify that the wrapper can parse the new output,
    - update the mapping logic (if needed) and the compatibility matrix.
  - CLI upgrades that introduce breaking output changes MUST be treated as
    a **controlled release**:
    - rolled out first to non-production,
    - monitored via metrics (CLI errors, parse failures).

- **Graceful degradation**
  - If an output format change is detected at runtime:
    - the system MUST fail the validation gracefully (no partial writes),
    - keep the contract in a safe status (e.g. `DRAFT` / `INVALID`),
    - emit an AuditEvent indicating an incompatible CLI output version.

---

## 2. Data Quality as a Service

### 2.1 Purpose

- Provide **Data Quality (DQ)** as a service that can be invoked during:
  - Data intake (ingestion).
  - Ongoing data management (re-ingestion, refresh, manual checks, scheduled checks).
- DQ results must be:
  - Integrated into the **data contract’s quality section**, where applicable.
  - Available in the **application backend** for reporting, scoring, and UI.
- The DQ service MUST support:
  - Batch file-based datasets (initial MVP focus).
  - A pluggable engine model so different DQ frameworks can be used for different tenants/profiles in the future.

### 2.2 Engines & Technology Strategy (Great Expectations + Soda)

The platform MUST support **both** Great Expectations and Soda as DQ engines.

1. **Supported engines (MVP)**

   - **Great Expectations (GX)**
     - Mandatory for MVP.
     - Primary choice for **file-based** datasets (CSV, Parquet, etc.).
   - **Soda**
     - Also mandatory for MVP.
     - MUST be fully integrated as an alternative engine that can be chosen via configuration.
     - Initially may be used for:
       - The same file-based sources (through Soda checks), and/or
       - Future SQL/warehouse backends.

2. **Engine abstraction**

   The DQ service MUST expose a single **engine-agnostic interface**:

   - Input:
     - Dataset reference (`asset_id`, `dataset_id`, and/or `data_file_id`).
     - `profile_key` (e.g. `intake_basic_gx`, `intake_basic_soda`).
     - Optional overrides or additional expectations.
   - Output:
     - A **normalized DQ result** stored in `DQRun` (`overall_status`, `quality_score`, `checks_json`, `details_json`), independent of engine.

   Internally this is implemented via **engine adapters**:

   - `GreatExpectationsAdapter`
   - `SodaAdapter`

   Both adapters MUST be implemented in MVP.

3. **Per-profile engine selection**

   - Each DQ profile MUST specify:
     - `engine_type`: `GX` or `SODA` (or future engines).
   - Built-in profiles for MVP:
     - `intake_basic_gx`:
       - Uses **Great Expectations**.
       - Default for intake flows unless tenant overrides.
     - `intake_basic_soda` (optional but recommended):
       - Uses **Soda** with equivalent/analogous checks.
   - Per-tenant configuration MAY choose which profile is used by default at intake (e.g. GX vs Soda).

4. **Engine metadata**

   - Every DQ run MUST store:
     - `engine_type`: `GX` or `SODA`.
     - `engine_version`: framework version string.
     - `ruleset_version` or identifier of the expectation set/check definitions used.

5. **Engine selection guidelines (GX vs Soda)**

   The platform SHOULD provide clear guidance on when to use each engine for a
   given DQ profile or tenant.

   - **Default (MVP)**
     - Great Expectations SHOULD be the default engine for:
       - file-based intake flows (CSV/Parquet in object storage),
       - initial \"intake basic\" profiles (`intake_basic_gx`),
       - teams that primarily run checks from Python-based tooling.
     - Soda MAY be enabled on a per-profile or per-tenant basis when needed.

   - **Prefer Great Expectations when…**
     - The primary data source is **files** landed into the hub (rather than
       long-lived warehouse tables).
     - You need rich, Python-centric expectations and local development
       workflows (notebooks, data docs).
     - You want tight coupling with contract-driven schemas where expectations
       are generated from metadata.

   - **Prefer Soda when…**
     - You are primarily checking **SQL/warehouse** datasets (future phase) and
       want push-down execution close to the data.
     - You need built-in **monitoring and alerting** features (e.g. via Soda
       Cloud/SaaS) for production DQ SLAs.
     - You want lightweight checks integrated into existing data pipelines
       that already use Soda syntax.

   - **Performance considerations**
     - For small/medium intake datasets the performance difference between GX
       and Soda is expected to be minor compared to I/O and parsing cost.
     - For very large datasets, prefer the engine that can execute **closest to
       the data** (e.g. warehouse-native Soda vs file-based GX), as defined by
       the technical design for that source type.
     - The DQ technical design MUST document any observed performance
       differences and MAY recommend engine-specific profiles for large or
       latency-sensitive workloads.

   - **Configuration**
     - Engine choice for a given profile (e.g. `intake_basic_*`) MUST be
       explicit and visible in configuration.
     - Per-tenant overrides SHOULD be allowed but controlled, to avoid a
       combinatorial explosion of unique configs.

### 2.3 Inputs & Behavior

- The DQ service will take as input:

  - Data-quality rules present in the **data contract** (if defined), or
  - A **basic quality check profile** for intake when no explicit rules are present, e.g.:
    - `intake_basic_gx` (GX-based)
    - `intake_basic_soda` (Soda-based)

**DQ Profile Selection Logic**

Profile selection follows this priority order:

1. **Explicit `profile_key` in request** (highest priority)
   - If the API request includes `profile_key` (e.g., `POST /dq-runs` with `{ "profile_key": "intake_basic_soda" }`), that profile is used.
   - Users can override the default profile per request.

2. **Tenant default profile** (from tenant configuration)
   - Each tenant can configure a default DQ profile (e.g., `intake_basic_gx` or `intake_basic_soda`).
   - This is stored in tenant configuration and applied when no explicit `profile_key` is provided.

3. **Platform default** (fallback)
   - If no tenant default is configured, the platform default is `intake_basic_gx`.

**Contract Rules Integration**

- If a contract specifies DQ rules (in `hub_contract_json.quality.rules`):
  - Contract rules are **merged** with the selected profile.
  - **Priority**: Contract rules take precedence over profile defaults.
  - **Fallback**: Profile provides baseline checks if contract has no rules.
  - **Combination**: Both contract rules and profile checks are executed; results are combined.

- Example:
  - Profile: `intake_basic_gx` (includes null ratio, uniqueness, type checks)
  - Contract: Specifies custom rule `order_id IS NOT NULL`
  - Result: Both profile checks and contract rule are executed

- The DQ service **MUST**:

  - Validate data before it is accepted into the platform (for intake flows).
  - Return structured results suitable for:
    - Updating relevant quality metadata on the contract/asset.
    - Storing in the backend for reporting and audit.
  - Work in **asynchronous job mode** for non-trivial datasets:
    - `/dq-runs` creates a run and associated `Job`.
    - Clients poll `/jobs/{id}` or `/dq-runs/{id}`.

### 2.4 Output Structure & Normalized Result Format

Regardless of whether the underlying engine is Great Expectations or Soda, the DQ service MUST map outcomes to a **single normalized format**.

1. **Top-level fields on DQRun**

   - `overall_status`: `PASS` | `FAIL` | `WARN` | `UNKNOWN`
   - `quality_score`: numeric (e.g. 0–100) summarizing overall quality.
   - `profile_key`: e.g. `intake_basic_gx`, `intake_basic_soda`.
   - `engine_type`: `GX` | `SODA`
   - `engine_version`: engine version string.
   - `ruleset_version`: identifier or hash of the expectations/checks used.

2. **Checks list (`checks_json`)**

   - Each check result MUST include at least:

     ```json
     {
       "check_id": "string",
       "name": "not_null_customer_id",
       "category": "COMPLETENESS | VALIDITY | UNIQUENESS | CONSISTENCY | CUSTOM",
       "status": "PASS | WARN | FAIL",
       "severity": "INFO | LOW | MEDIUM | HIGH",
       "target": {
         "level": "COLUMN | TABLE | DATASET",
         "column_name": "customer_id"
       },
       "metrics": {
         "observed_value": 0.0,
         "expected_min": 0.0,
         "expected_max": 0.01,
         "row_count": 120000,
         "observed_null_ratio": 0.0
       },
       "engine_raw": {
         "...": "engine-specific original payload from GX or Soda"
       }
     }
     ```

   - `engine_raw` is optional and used only for debugging; UI and logic MUST rely on the normalized fields.

3. **Details (`details_json`)**

   - `details_json` MAY contain:

     - Column summaries (null ratios, distinct counts, etc.).
     - Sampling information (if sampling was used).
     - Per-category statistics.

   - Example:

     ```json
     {
       "columns": {
         "order_id": {
           "null_ratio": 0.0,
           "distinct_count": 120000,
           "failed_checks": ["uniqueness_check"]
         },
         "total_amount": {
           "null_ratio": 0.01,
           "failed_checks": ["non_negative_check"]
         }
       },
       "sampling": {
         "strategy": "RANDOM_ROWS",
         "sample_size": 100000,
         "population_estimate": 50000000
       }
     }
     ```

4. **Mapping from Great Expectations**

   - Example mappings:

     - `expect_column_values_to_not_be_null`
       - `category = COMPLETENESS`
       - `status = PASS/WARN/FAIL` based on `success` and thresholds.
     - `expect_column_values_to_be_unique`
       - `category = UNIQUENESS`.
     - `expect_column_values_to_be_between`
       - `category = VALIDITY`.

   - GX’s `success` and metric fields must be converted into:
     - `status`
     - `metrics.observed_value`, etc.

5. **Mapping from Soda**

   - Soda check results (pass/warn/fail, metrics) MUST be mapped into the same normalized structure.
   - Engine-specific details remain inside `engine_raw` for debugging.

### 2.5 Data Sampling vs Full Scan & Performance

1. **Full scan vs sampling**

   - For **small/medium datasets** (up to a configurable size/row count):
     - Default: **full scan** for all checks.
   - For **large datasets**:
     - DQ MAY use **sampling** to reduce runtime and cost.
     - Strategies:
       - First N rows (for quick intake sanity checks).
       - Random rows (for more representative quality metrics).
     - The sampling strategy MUST be recorded in `details_json.sampling`.

2. **Configurable thresholds**

   - The following MUST be configurable (globally, and per-tenant in future):

     - Maximum file size / row count for full scan.
     - Default sample size or fraction for large datasets.
     - Allocation of different profiles for different dataset sizes (e.g. `intake_basic_gx_small`, `intake_basic_gx_large`).

3. **Resource & time limits**

   - The DQ service MUST enforce:

     - Max execution time per run (timeout).
     - Max memory/CPU for engine containers.

   - On timeout or resource exhaustion:

     - DQRun and Job MUST be marked `FAILED` or `UNKNOWN`.
     - An explicit error code (e.g. `DQ_TIMEOUT`, `DQ_INPUT_TOO_LARGE`) MUST be returned.
     - An AuditEvent MUST be recorded.

4. **Streaming / chunked processing**

   - For file-based inputs stored in object storage:
     - The DQ service SHOULD read data via streaming or batched reads where supported.
     - Temporary local copies MUST be deleted after the run completes.

### 2.6 Triggers

DQ checks MAY be triggered in three ways:

1. **Intake (automatic)**

   - During data-first and contract-first flows, **before** storing data.
   - Default DQ profile:
     - `intake_basic_gx` (or tenant-chosen equivalent such as `intake_basic_soda`).

2. **Manual (on demand)**

   - A user or an API/SDK call explicitly triggers a DQ run on an existing asset/dataset.
   - The caller chooses:
     - `profile_key` (and therefore engine type).
     - Optional overrides.

3. **Scheduled (future)**

   - Periodic checks per asset or per tenant are part of the conceptual design but MAY be implemented in later phases.
   - The model and APIs should **not** prevent this future extension.

### 2.7 Billing & Audit

- Data quality checks are:

  - **Billable events**.
  - **Regulatory-relevant checks** (must be provable later).

- Each DQ invocation MUST generate an **audit trail entry** including:

  - Who requested it (user, tenant).
  - When it was run.
  - Which dataset/contract (IDs and versions).
  - `engine_type` and `engine_version`.
  - `overall_status`, `quality_score`, and key summary metrics (e.g. null ratios, number of failed checks).

- The billing subsystem MUST be able to:

  - Count DQ runs per tenant.
  - Estimate processing cost based on:
    - Rows inspected/sample size.
    - Runtime duration.
    - Engine type (GX vs Soda).
  - Associate each DQ run with a **Job** and **AuditEvent**.

### 2.8 Quality Profiles

- The platform MUST define at least one default **intake profile** for each engine:

  - `intake_basic_gx`:
    - Implemented with Great Expectations.
    - Checks:
      - Type/conformance against schema.
      - Null ratio checks on key fields.
      - Uniqueness checks on identifier/primary key columns (if known).
      - Basic range checks for numeric/date columns where feasible.
      - Row count and distribution sanity checks.

  - `intake_basic_soda`:
    - Implemented with Soda.
    - Functionally similar checks mapped to Soda’s model.

- In the future, additional profiles MAY be introduced, such as:

  - `full_profile_gx`, `full_profile_soda` for deeper checks.

#### 2.8.1 DQ Run Retention Policy

DQ run results are retained for audit, compliance, and historical analysis purposes.

**Retention Period**

- **Default retention**: **3 years** from `dq_runs.created_at` (aligned with audit log retention)
- **Configurable per tenant**: Can be overridden via `tenant_config.dq_retention_days` (minimum: 90 days, maximum: 7 years)
- **Retention is independent of asset lifecycle**:
  - DQ runs for deleted assets are retained for the full retention period
  - DQ runs for deleted datasets are retained for the full retention period

**Retention Tiers**

- **Hot tier (operational)**:
  - Recent DQ runs (last 6 months)
  - Stored in primary database with full indexing
  - Fast query performance for dashboards and reports
- **Warm tier (historical)**:
  - Older DQ runs (6 months to 3 years)
  - May be:
    - Kept in primary database but partitioned/compressed, or
    - Moved to cheaper storage optimized for read-mostly workloads
- **Archive tier (beyond retention)**:
  - DQ runs older than retention period are:
    - Exported to long-term storage (e.g., S3 as Parquet/CSV) if required by compliance
    - Deleted from primary database
  - Archive exports are compressed and stored by tenant/month for efficient retrieval

**Data Preserved**

- **Full DQ run records**:
  - `dq_runs` table records (status, overall_status, quality_score, etc.)
  - `checks_json` (detailed check results)
  - `details_json` (engine versions, sample sizes, etc.)
- **Linked records**:
  - Job records (`jobs` table) are retained if linked to DQ runs
  - Audit events (`audit_events`) are retained per audit retention policy (3 years minimum)

**Cleanup Process**

- **Automated cleanup job**:
  - Runs daily at 2 AM UTC (same as audit log cleanup)
  - Identifies DQ runs older than retention period
  - Exports to archive storage (if configured)
  - Deletes from primary database
  - Emits audit event: `DQ_RUN_RETENTION_CLEANUP_COMPLETED`
- **Manual cleanup**:
  - Platform admins can trigger manual cleanup via admin API (future enhancement)
  - Cleanup respects tenant-specific retention periods

**Exceptions**

- **Regulatory requirements**: If a tenant has specific regulatory requirements (e.g., 7-year retention for SOX), retention can be extended via `tenant_config.dq_retention_days`
- **Legal hold**: DQ runs can be marked for legal hold (prevents deletion even after retention period)
- **Active investigations**: DQ runs involved in active compliance investigations are retained until investigation closes
  - Domain-specific profiles (e.g. finance, healthcare).

- Profiles MUST be:

  - Referenced by `profile_key` in the API.
  - Documented so tenants know:
    - Which engine they use.
    - Which checks are included.

---

### 2.9 DQ Profile Configuration Format

DQ profiles define the set of quality checks to be executed for a dataset. Profiles are stored as JSON configuration files and referenced by `profile_key`.

#### 2.9.1 Profile Storage

- **Built-in profiles**: Stored in codebase or configuration files (e.g., `/config/dq-profiles/intake_basic_gx.json`).
- **Custom profiles**: May be stored in database (future) or tenant configuration (future).
- **Profile registry**: Platform maintains a registry of available profiles with metadata.

#### 2.9.2 Profile Definition Schema

**Profile JSON Structure**

```json
{
  "profile_key": "intake_basic_gx",
  "engine_type": "GX",
  "version": "1.0.0",
  "description": "Basic intake profile using Great Expectations",
  "checks": [
    {
      "check_id": "not_null_primary_key",
      "name": "Primary key not null",
      "category": "COMPLETENESS",
      "severity": "ERROR",
      "target": {
        "level": "COLUMN",
        "column_pattern": ".*_id$"
      },
      "expectation": {
        "type": "expect_column_values_to_not_be_null",
        "params": {}
      }
    },
    {
      "check_id": "null_ratio_threshold",
      "name": "Null ratio within threshold",
      "category": "COMPLETENESS",
      "severity": "WARN",
      "target": {
        "level": "COLUMN"
      },
      "expectation": {
        "type": "expect_column_null_ratio_to_be_less_than",
        "params": {
          "threshold": 0.01
        }
      }
    },
    {
      "check_id": "type_conformance",
      "name": "Type conformance",
      "category": "VALIDITY",
      "severity": "ERROR",
      "target": {
        "level": "COLUMN"
      },
      "expectation": {
        "type": "expect_column_values_to_be_of_type",
        "params": {}
      }
    }
  ],
  "metadata": {
    "created_at": "2025-01-01T00:00:00Z",
    "created_by": "system",
    "ruleset_version": "1.0.0"
  }
}
```

**Profile Schema Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_key` | string | Yes | Unique identifier (e.g., `intake_basic_gx`). |
| `engine_type` | string (enum) | Yes | `GX` or `SODA`. |
| `version` | string | Yes | Profile version (semantic versioning). |
| `description` | string | No | Human-readable description. |
| `checks` | array | Yes | List of quality checks (see check structure below). |
| `metadata` | object | No | Profile metadata (creation date, author, etc.). |

**Check Structure**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `check_id` | string | Yes | Unique identifier within profile. |
| `name` | string | Yes | Human-readable check name. |
| `category` | string (enum) | Yes | `COMPLETENESS`, `VALIDITY`, `UNIQUENESS`, `CONSISTENCY`, `CUSTOM`. |
| `severity` | string (enum) | Yes | `INFO`, `LOW`, `MEDIUM`, `HIGH`. |
| `target` | object | Yes | Target specification (column, table, dataset). |
| `expectation` | object | Yes | Engine-specific expectation definition. |

**Engine-Specific Expectations**

- **Great Expectations**: Uses GX expectation types (e.g., `expect_column_values_to_not_be_null`).
- **Soda**: Uses Soda check syntax (e.g., `checks for orders: - missing_count(customer_id) = 0`).

#### 2.9.3 Profile Selection and Merging

- **Selection**: See §2.3 (DQ Profile Selection Logic).
- **Merging with contract rules**: Contract-defined DQ rules are merged with profile checks:
  - Contract rules take precedence (override profile checks with same `check_id`).
  - Both contract rules and profile checks are executed.
  - Results are combined in the final DQ report.

---

## 3. Data Compliance Check as a Service

### 3.1 Purpose & Guarantee

- Provide **Data Compliance** as a service focused on:
  - Data regulations: **GDPR, LGPD, CCPA, HIPAA, SOX**, and similar frameworks.
  - At intake: **reducing legal risk** by blocking obviously non-compliant datasets from being stored.

**Platform design goal:**

> The compliance gate is designed to prevent storage of obviously non-compliant datasets that contain identifiable personal or highly sensitive regulated data according to the configured rules. Detection is heuristic; zero risk cannot be absolutely guaranteed, but all ingested data must pass the configured compliance checks.

Additionally:

- The same compliance engine can be used **as a standalone service** (“scan-only”) for external assets that are **not stored** in the hub. This mode is **chargeable**.

### 3.2 Regulatory Scope (v1 Minimum)

Covered frameworks (conceptually):

- GDPR (EU), LGPD (BR), CCPA/CPRA (US-CA), HIPAA (US health), SOX (financial/audit trail).

**Minimum technical detection scope:**

1. **Direct personal identifiers**
   - Emails, phone numbers, postal addresses.
   - Government IDs (national IDs, SSNs, passport numbers).
   - Customer IDs that clearly identify an individual.

2. **Financial/payment data**
   - Credit/debit card numbers.
   - Bank account / IBAN / routing numbers.
   - Card security codes and expiry dates when linked to card numbers.

3. **Health-related data (HIPAA-like)**
   - Medical record/insurance numbers.
   - Diagnosis or treatment data linked to an identifiable subject.

4. **Special categories of personal data (GDPR-style)**
   - Race/ethnicity, religion, political opinions, union membership, sexual orientation, etc., when linked to an identifiable person.

5. **Free-text PII risk**
   - Free-text columns that statistically appear to contain PII (emails, phone numbers, IDs) even if generically named (“notes”, “comments”).

**Policy:**

- **Allowed to store**:
  - Aggregated or anonymized datasets where no individual is identifiable (within configured thresholds).
- **Blocked from storage**:
  - Any dataset where direct identifiers or highly sensitive regulated data are detected above a **configurable threshold** (see §3.5).
  - The user receives a detailed compliance report and can:
    - Transform data externally and re-upload, or
    - Use only the scan-only service (no storage).

**Compliance Fail-Closed Behavior**

The compliance gate implements a **strict fail-closed policy** to prevent storage of non-compliant data. The following table defines the behavior for all compliance outcomes:

| Compliance Result | `allowed_to_store` | Data Storage | Override Allowed | Notes |
|-------------------|-------------------|--------------|------------------|-------|
| `PASS` | `true` | ✅ Stored | N/A | Data passes all compliance checks |
| `WARN` | `true` (with warnings) | ✅ Stored | N/A | Data passes but has warnings (e.g., low-risk PII detected) |
| `FAIL` | `false` | ❌ Not stored | ❌ No override (fail-closed) | Data fails compliance checks; storage is blocked |
| `FAILED` (job error) | `false` | ❌ Not stored | ❌ No override (fail-closed) | Compliance service crashed or encountered an error; storage is blocked |
| `TIMEOUT` | `false` | ❌ Not stored | ❌ No override (fail-closed) | Compliance job exceeded timeout; storage is blocked |

**Key Rules:**
- **No user override**: Even `TENANT_ADMIN` cannot override a compliance failure. This is a hard gate to ensure legal compliance.
- **Fail-closed on errors**: If the compliance service crashes, times out, or encounters any error, the default behavior is to **block storage** (fail-closed).
- **WARN is acceptable**: Compliance results with `WARN` status are stored, but warnings are clearly displayed in the UI and audit logs.
- **Retry allowed**: Users can retry compliance checks after fixing data externally, but cannot bypass the gate.

### 3.3 Inputs & Outputs

**Inputs**

- Data file (required for checks):
  - Formats: CSV, JSON, Parquet, etc.
- Optional:
  - Data contract metadata (schema, field classifications) if available.
- Context:
  - Tenant ID, user ID, and intended asset/contract ID (for audit).
  - `applicable_regimes`:
    - For **intake**: derived from tenant config (e.g. `["GDPR","LGPD"]`).
    - For **chargeable external service**: caller MAY specify any supported regimes.

**Outputs**

- A **compliance report** with at least:
  - `overall_status`: `PASS` | `FAIL` | `WARN`
  - `risk_level`: `NONE` | `LOW` | `MEDIUM` | `HIGH`
  - `detected_categories`: list (e.g. `["PII_DIRECT_EMAIL", "PAYMENT_CARD"]`)
  - `column_findings`: per-column summary (patterns, estimated % of offending values).
  - `regulation_mapping`: mapping of findings to regulations (GDPR, LGPD, CCPA, etc.).
  - `recommendations`: high-level remediation (anonymize, aggregate, mask, etc.).

- A **decision signal**:
  - For platform ingestion:
    - `allowed_to_store: true/false`
      - No user override allowed.
  - For standalone scan service:
    - Only the report and decision; no storage takes place.

- All reports MUST be persisted and linked to the associated asset (or external job) and tenant for future audits.

#### 3.3.1 Compliance Report Storage Format

Compliance reports are stored in the `compliance_runs` table with the following JSONB field structures:

**`pii_summary` JSONB Structure**

Stores high-level PII detection summary:

```json
{
  "detected_categories": [
    {
      "category": "PII_DIRECT_EMAIL",
      "count": 1250,
      "percentage": 12.5,
      "confidence": "HIGH"
    },
    {
      "category": "PAYMENT_CARD",
      "count": 50,
      "percentage": 0.5,
      "confidence": "MEDIUM"
    }
  ],
  "total_rows_scanned": 10000,
  "total_columns_scanned": 15,
  "scan_strategy": "FULL_SCAN",
  "scan_duration_seconds": 45.2
}
```

**`details_json` JSONB Structure**

Stores detailed per-column findings and rule results:

```json
{
  "engine_version": "1.2.3",
  "ruleset_version": "2025.01.15",
  "scan_metadata": {
    "sample_size": 10000,
    "full_scan": true,
    "scan_duration_seconds": 45.2
  },
  "column_findings": [
    {
      "column_name": "customer_email",
      "detected_categories": [
        {
          "category": "PII_DIRECT_EMAIL",
          "count": 1250,
          "percentage": 12.5,
          "confidence": "HIGH",
          "patterns_matched": ["email_regex", "domain_validation"],
          "sample_values": ["user@example.com", "admin@company.com"]
        }
      ],
      "risk_level": "HIGH",
      "recommendations": ["Anonymize", "Encrypt at rest"]
    },
    {
      "column_name": "credit_card",
      "detected_categories": [
        {
          "category": "PAYMENT_CARD",
          "count": 50,
          "percentage": 0.5,
          "confidence": "MEDIUM",
          "patterns_matched": ["luhn_validation"],
          "sample_values": ["****-****-****-1234"]
        }
      ],
      "risk_level": "MEDIUM",
      "recommendations": ["Mask", "Tokenize"]
    }
  ],
  "regulation_mapping": [
    {
      "regime_code": "GDPR",
      "applicable": true,
      "blocking_rules_triggered": [
        {
          "rule_id": "gdpr_direct_identifier_block",
          "severity": "HIGH",
          "threshold_exceeded": true
        }
      ],
      "recommendations": ["Require explicit consent", "Implement data minimization"]
    }
  ],
  "thresholds_applied": {
    "direct_identifier_percentage": 0.01,
    "special_category_percentage": 0.01
  }
}
```

**Field Definitions**

| Field | Type | Description |
|-------|------|-------------|
| `detected_categories` | array | List of PII categories detected across all columns |
| `column_findings` | array | Per-column detection results with detailed metadata |
| `regulation_mapping` | array | Mapping of findings to applicable regulations |
| `thresholds_applied` | object | Threshold values used for blocking decisions |
| `engine_version` | string | Version of compliance engine used |
| `ruleset_version` | string | Version of detection rules used |

#### 2.4.1 DQ Report Storage Format

DQ reports are stored in the `dq_runs` table with the following JSONB field structures:

**`result_summary` JSONB Structure**

Stores high-level quality metrics:

```json
{
  "overall_status": "PASS",
  "quality_score": 95.2,
  "total_checks": 15,
  "passed_checks": 14,
  "failed_checks": 0,
  "warning_checks": 1,
  "total_rows": 100000,
  "total_columns": 12,
  "scan_strategy": "FULL_SCAN",
  "scan_duration_seconds": 120.5
}
```

**`issues` JSONB Structure**

Stores detailed check results and failures:

```json
{
  "engine_version": "0.18.5",
  "profile_version": "intake_basic_gx_v1",
  "checks": [
    {
      "check_id": "expect_column_values_to_not_be_null",
      "check_name": "Null Check: order_id",
      "column_name": "order_id",
      "status": "PASS",
      "severity": "ERROR",
      "result": {
        "element_count": 100000,
        "null_count": 0,
        "null_percentage": 0.0,
        "unexpected_count": 0
      },
      "metadata": {
        "expectation_type": "column_values_to_not_be_null",
        "expectation_config": {
          "column": "order_id"
        }
      }
    },
    {
      "check_id": "expect_column_values_to_be_unique",
      "check_name": "Uniqueness Check: order_id",
      "column_name": "order_id",
      "status": "WARN",
      "severity": "WARNING",
      "result": {
        "element_count": 100000,
        "unique_count": 99995,
        "unique_percentage": 99.995,
        "unexpected_count": 5,
        "unexpected_list": ["ORD-001", "ORD-002", "ORD-003", "ORD-004", "ORD-005"]
      },
      "metadata": {
        "expectation_type": "column_values_to_be_unique",
        "expectation_config": {
          "column": "order_id"
        }
      }
    },
    {
      "check_id": "expect_column_values_to_be_of_type",
      "check_name": "Type Check: amount",
      "column_name": "amount",
      "status": "FAIL",
      "severity": "ERROR",
      "result": {
        "element_count": 100000,
        "unexpected_count": 10,
        "unexpected_percentage": 0.01,
        "unexpected_list": ["invalid", "N/A", "null"]
      },
      "metadata": {
        "expectation_type": "column_values_to_be_of_type",
        "expectation_config": {
          "column": "amount",
          "type_": "float"
        }
      }
    }
  ],
  "column_summary": [
    {
      "column_name": "order_id",
      "total_checks": 3,
      "passed_checks": 2,
      "failed_checks": 0,
      "warning_checks": 1,
      "quality_score": 95.0
    },
    {
      "column_name": "amount",
      "total_checks": 2,
      "passed_checks": 1,
      "failed_checks": 1,
      "warning_checks": 0,
      "quality_score": 50.0
    }
  ],
  "sampling_metadata": {
    "sample_size": 100000,
    "full_scan": true,
    "sample_method": "SEQUENTIAL"
  }
}
```

**Field Definitions**

| Field | Type | Description |
|-------|------|-------------|
| `overall_status` | string | `PASS`, `WARN`, `FAIL`, `UNKNOWN` |
| `quality_score` | number | Overall quality score (0-100) |
| `checks` | array | Detailed results for each DQ check executed |
| `column_summary` | array | Per-column quality summary |
| `engine_version` | string | Version of DQ engine (Great Expectations or Soda) |
| `profile_version` | string | Version of DQ profile used |
| `sampling_metadata` | object | Information about data sampling strategy |

**Check Result Structure**

Each check in the `checks` array contains:

| Field | Type | Description |
|-------|------|-------------|
| `check_id` | string | Unique identifier for the check |
| `check_name` | string | Human-readable check name |
| `column_name` | string | Column being checked (if applicable) |
| `status` | string | `PASS`, `WARN`, `FAIL` |
| `severity` | string | `ERROR`, `WARNING`, `INFO` |
| `result` | object | Check-specific result data (varies by check type) |
| `metadata` | object | Check configuration and metadata |

- All reports MUST be persisted and linked to the associated asset (or external job) and tenant for future audits.

### 3.4 External Scan-Only Mode & Data Retention

For **external scan-only** jobs (assets not stored in the hub):

- Raw data files MUST be stored only in **ephemeral/temporary storage**.
- Raw data MUST be deleted as soon as the compliance scan completes, or within a short fixed window (e.g. X minutes) required for system reliability.
- Only the **report** and **non-reversible hashes/checksums** of input are retained long-term.

### 3.5 Thresholds & Classification Logic

- By default, the platform applies a global threshold, for example:
  - If **≥1%** of rows in any column contain direct identifiers or highly sensitive values, then:
    - `allowed_to_store = false`
- Thresholds MUST be:
  - Configurable per tenant or per policies.
  - Documented as part of compliance configuration.
- Thresholds and classification rules SHOULD be captured in the compliance engine metadata and referenced in the audit logs.

### 3.5.1 Compliance Regime Configuration

Compliance regimes (GDPR, LGPD, CCPA, HIPAA, SOX) are configured per tenant and applied during compliance checks.

#### 3.5.1.1 Regime Definition Schema

**Regime JSON Structure**

```json
{
  "regime_code": "GDPR",
  "name": "General Data Protection Regulation",
  "version": "2018",
  "jurisdiction": "EU",
  "detection_categories": [
    "PII_DIRECT_EMAIL",
    "PII_DIRECT_PHONE",
    "PII_DIRECT_ADDRESS",
    "PII_GOVERNMENT_ID",
    "PII_SPECIAL_CATEGORY"
  ],
  "thresholds": {
    "direct_identifier_percentage": 0.01,
    "special_category_percentage": 0.01
  },
  "blocking_rules": [
    {
      "rule_id": "gdpr_direct_identifier_block",
      "condition": "direct_identifier_percentage >= 0.01",
      "action": "BLOCK",
      "severity": "HIGH"
    }
  ]
}
```

**Regime Schema Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `regime_code` | string | Yes | Unique code: `GDPR`, `LGPD`, `CCPA`, `HIPAA`, `SOX`. |
| `name` | string | Yes | Human-readable name. |
| `version` | string | Yes | Regulation version/year. |
| `jurisdiction` | string | Yes | Geographic jurisdiction. |
| `detection_categories` | array | Yes | PII categories detected for this regime. |
| `thresholds` | object | Yes | Thresholds for blocking decisions. |
| `blocking_rules` | array | Yes | Rules that determine `allowed_to_store = false`. |

#### 3.5.1.2 Tenant Regime Configuration

- **Allowed regimes**: Configured in `TenantConfig.allowed_compliance_regimes` (see `API_Spec_v1.md` §13).
- **Default regimes**: Configured in `TenantConfig.default_compliance_regimes` (applied to intake flows).
- **Platform defaults**: All tenants have access to all supported regimes by default.
- **Restriction**: Tenants can only use regimes in their `allowed_compliance_regimes` list.

#### 3.5.1.3 Regime Application Logic

- **Intake flows**: Uses `TenantConfig.default_compliance_regimes` (unless overridden in request).
- **External scan-only**: Caller specifies `applicable_regimes` in request (must be subset of tenant's allowed regimes).
- **Override**: API requests can specify `applicable_regimes` to override defaults.

### 3.6 Safe Failure Behavior

- If the compliance check fails unexpectedly (internal error, timeout, or engine crash):
  - The platform MUST **fail closed**:
    - `allowed_to_store = false`.
    - The data file MUST NOT be persisted as an asset.
  - The user sees an error and may retry later.
  - An audit entry MUST record that the failure occurred and that storage was blocked.

### 3.7 Integration with Lifecycle & UX

- Compliance checks run **only when a data file is involved**.

- **Data-first flow**:
  - User uploads data file.
  - Platform runs:
    - Compliance check (mandatory gate).
    - Data quality check (mandatory gate).
  - If either check fails:
    - File is not stored.
    - Reports are shown to the user.
  - Only on `PASS` or acceptable `WARN` (policy-defined) can the process proceed to the contract editor.

- **Contract-first flow**:
  - Contract is uploaded and validated with DataContract CLI.
  - When data file is uploaded:
    - Compliance check runs (mandatory gate).
    - Data quality check runs.
  - If the user later replaces the data file:
    - Compliance + quality MUST re-run before the new file becomes active.
  - No compliance check is run on contract metadata alone.

- **Contract-only flow**:
  - No data file at creation → **no compliance or quality checks**.
  - When a data file is attached in future:
    - It MUST pass the same compliance + quality gate as in other flows before being stored.

- **No "accept risk" override**:
  - Users cannot override or accept compliance failures.

#### 3.7.1 Compliance Run Retention Policy

Compliance run results are retained for audit, compliance, and regulatory purposes.

**Retention Period**

- **Default retention**: **3 years** from `compliance_runs.created_at` (aligned with audit log retention)
- **Configurable per tenant**: Can be overridden via `tenant_config.compliance_retention_days` (minimum: 90 days, maximum: 7 years)
- **Regulatory alignment**: Retention period aligns with regulatory requirements (e.g., GDPR: 3 years, SOX: 7 years)
- **Retention is independent of asset lifecycle**:
  - Compliance runs for deleted assets are retained for the full retention period
  - Compliance runs for deleted datasets are retained for the full retention period
  - Compliance runs for scan-only files (external scans) are retained for the full retention period

**Retention Tiers**

- **Hot tier (operational)**:
  - Recent compliance runs (last 6 months)
  - Stored in primary database with full indexing
  - Fast query performance for dashboards and compliance reports
- **Warm tier (historical)**:
  - Older compliance runs (6 months to 3 years)
  - May be:
    - Kept in primary database but partitioned/compressed, or
    - Moved to cheaper storage optimized for read-mostly workloads
- **Archive tier (beyond retention)**:
  - Compliance runs older than retention period are:
    - Exported to long-term storage (e.g., S3 as Parquet/CSV) if required by compliance
    - Deleted from primary database
  - Archive exports are compressed and stored by tenant/month for efficient retrieval
  - Archive retention: Exported compliance runs are retained in archive storage for an additional period (configurable, default: 10 years) for regulatory compliance

**Data Preserved**

- **Full compliance run records**:
  - `compliance_runs` table records (status, overall_status, risk_level, allowed_to_store, etc.)
  - `column_findings_json` (per-column PII detection results)
  - `details_json` (engine versions, detection rules, sample sizes, etc.)
  - `applicable_regimes` (regulatory regimes applied)
  - `detected_categories` (PII categories detected)
- **Linked records**:
  - Job records (`jobs` table) are retained if linked to compliance runs
  - Audit events (`audit_events`) are retained per audit retention policy (3 years minimum)

**Cleanup Process**

- **Automated cleanup job**:
  - Runs daily at 2 AM UTC (same as audit log cleanup)
  - Identifies compliance runs older than retention period
  - Exports to archive storage (if configured)
  - Deletes from primary database
  - Emits audit event: `COMPLIANCE_RUN_RETENTION_CLEANUP_COMPLETED`
- **Manual cleanup**:
  - Platform admins can trigger manual cleanup via admin API (future enhancement)
  - Cleanup respects tenant-specific retention periods

**Exceptions**

- **Regulatory requirements**: If a tenant has specific regulatory requirements (e.g., 7-year retention for SOX, 5-year retention for HIPAA), retention can be extended via `tenant_config.compliance_retention_days`
- **Legal hold**: Compliance runs can be marked for legal hold (prevents deletion even after retention period)
- **Active investigations**: Compliance runs involved in active compliance investigations are retained until investigation closes
- **Failed compliance runs**: Compliance runs with `allowed_to_store = false` are retained for the full retention period (critical for audit trail)
  - The platform always refuses to store non-compliant data.

### 3.8 Billing & Audit

- Compliance checks are:
  - **Billable events**, whether on platform assets or external assets.
  - **Regulatory checks** requiring traceability.

- Therefore:
  - Each compliance check MUST create an audit record including:
    - Who requested it (user, tenant).
    - When it ran.
    - Which file/asset/contract it applied to.
    - `overall_status`, `risk_level`, main detected categories.
    - Whether `allowed_to_store` was true or false.

### 3.9 Detection Approach & Libraries (Implementation Guidance)

The compliance engine MUST be designed around a **deterministic, explainable detection pipeline**, with optional ML-based extensions later. For MVP:

1. **Detection stages**

   1. **Schema- and name-based hints**
      - Use column **names**, **descriptions**, and contract metadata (if available) to derive hints:
        - e.g. `email`, `e_mail`, `mail_address` → hint: `PII_EMAIL`
        - `cc_number`, `card`, `iban`, `routing` → hint: `PAYMENT_CARD`, `BANK_ACCOUNT`
      - Hints alone are NOT sufficient to classify a column as PII, but they influence confidence.

   2. **Pattern-based detection (primary)**
      - For each column with string-like values:
        - Apply curated **regular expressions** and simple validators for:
          - Email addresses (RFC-ish regex + structural checks).
          - Phone numbers (E.164-like patterns plus region-specific variants).
          - Postal codes (per region, where feasible).
          - Credit card numbers (length + BIN patterns + Luhn check).
          - Bank accounts / IBAN patterns.
          - Government IDs for supported jurisdictions (e.g. CPF/CNPJ, SSN, etc.).
        - For numeric/date columns:
          - Only apply patterns where appropriate (e.g. numeric IDs, date of birth formats).

   3. **Dictionary / keyword matching**
      - Use controlled **dictionaries** / keyword lists for:
        - Special categories (religion, ethnicity, union membership, political affiliation).
        - Health-related terms (diagnosis codes, common medical terms).
      - For free-text columns (`notes`, `comments`):
        - Tokenize values.
        - Flag occurrences of dictionary terms.
        - Keep counts of matches vs total rows.

   4. **Optional ML-based NER (future enhancement)**
      - The architecture MUST allow plug-in of Named Entity Recognition (NER) models (e.g., spaCy/transformer models) in a later phase.
      - For MVP, ML-based detectors are optional; if used, they MUST provide:
        - Per-entity confidence.
        - Per-column aggregated confidence and coverage.

2. **Per-column scoring**

   For each column and each detected category (e.g. `PII_EMAIL`, `PAYMENT_CARD`, `HEALTH_DATA`), the engine MUST compute:

   - `support_count`: number of rows that matched this category.
   - `sample_size`: number of rows examined.
   - `support_ratio = support_count / sample_size`.
   - `confidence` (0–1):
     - Derived from:
       - Strength of pattern match (e.g. credit card + Luhn = high).
       - Agreement between name-hints and value-patterns.
       - For ML models (if used): average model confidence.

   These aggregated metrics form the basis for risk classification and thresholds (§3.5).

3. **Engine architecture**

   - The compliance engine MUST operate in a **streaming or batched** mode over rows:
     - It never needs to fully materialize the whole file in memory for detection.
   - All detection rules (regexes, dictionaries, category definitions) MUST be:
     - Versioned.
     - Logged in the report metadata (`details_json`) with `ruleset_version`.

### 3.10 False Positives / False Negatives Handling

Because detection is heuristic, the engine MUST explicitly model **uncertainty** and encourage conservative decisions on storage.

1. **Confidence levels**

   Based on `confidence` and `support_ratio`, each (column, category) finding MUST be assigned a qualitative level:

   - `HIGH_CONFIDENCE`
     - Strong pattern + validation (e.g. card number with valid Luhn; email with valid structure).
   - `MEDIUM_CONFIDENCE`
     - Good pattern match but weaker validation or ambiguous name.
   - `LOW_CONFIDENCE`
     - Weak hints, rare matches, or only name-based hints.

   These levels MUST appear in `column_findings` for transparency.

2. **Gating vs reporting**

   - **Storage gate** (`allowed_to_store`) MUST rely **only** on:
     - `HIGH_CONFIDENCE` (and possibly `MEDIUM_CONFIDENCE`) findings,
     - AND support ratios exceeding configured thresholds (§3.5).
   - `LOW_CONFIDENCE` detections MUST NOT, by themselves, block storage:
     - They MUST be surfaced as `WARN` and included in the report as potential issues.

3. **Bias toward safety (false negatives vs false positives)**

   - The engine MUST be tuned to **minimize false negatives** for high-risk categories (direct identifiers, payment data, health data), even at the cost of some false positives.
   - For lower-risk categories (e.g. free-text that *might* contain PII), the engine SHOULD:
     - Prefer `WARN` over `FAIL` and encourage manual review.

4. **User-facing explanation**

   - Reports MUST explicitly explain:
     - That detection is heuristic and may not find **all** PII.
     - Why a column was classified (e.g. “95% of sampled values look like email addresses and the column name contains `email`”).

5. **Tuning and feedback (future)**

   - The design SHOULD allow:
     - Per-tenant feedback loops (e.g. “mark this column as false positive”).
     - Future rule adjustments and ML retraining based on aggregated feedback.

### 3.11 Threshold Configuration (Global vs Per-Tenant)

Thresholds determine when detections translate into `WARN` vs `FAIL` and whether `allowed_to_store` is true or false.

1. **Configuration model**

   There MUST be a structured configuration model, e.g.:

   ```json
   {
     "default": {
       "high_risk_categories": ["PII_DIRECT", "PAYMENT_CARD", "HEALTH_DATA"],
       "warn_risk_categories": ["PII_INDIRECT", "FREE_TEXT_PII"],
       "fail_threshold_ratio": 0.01,
       "warn_threshold_ratio": 0.0001,
       "minimum_confidence_for_fail": 0.8,
       "minimum_confidence_for_warn": 0.3
     },
     "per_regime_overrides": {
       "GDPR": { "...": "..." },
       "HIPAA": { "...": "..." }
     },
     "per_tenant_overrides": {
       "<tenant_id>": { "...": "..." }
     }
   }

### 3.12 Scan-Only Mode & Large Files

Scan-only mode allows tenants to use the compliance service on **external assets** without storing data in the hub.

1. **Input options**

   The API MUST support, at minimum:

   - Direct file upload (for moderate-size files).
   - Storage-by-reference (recommended for large files), such as:
     - Pre-signed URLs for cloud object storage (e.g. S3/GCS/Azure Blob).
     - Short-lived credentials to read from a specified path.

2. **Handling large files (streaming)**

   - For large scan-only inputs, the engine MUST:
     - Read the file in **streaming mode**, processing chunks sequentially.
     - Avoid loading the entire file into memory.
     - Avoid permanent storage:
       - Only ephemeral temp locations are allowed and MUST be cleaned up.

   - Two strategies MUST be supported conceptually:

     1. **Full streaming scan**  
        - Process all rows, maintaining only:
          - Counts, ratios, and summary statistics.
        - Recommended when throughput and cost allow.

     2. **Sampling-based scan**  
        - For extremely large files:
          - Sample a configurable number of rows (e.g. random X rows or up to N million rows).
          - Compute detection metrics on the sample.
        - The sampling strategy (method, fraction, limits) MUST be recorded in the report.

3. **Retention & deletion**

   - In scan-only mode:
     - Any raw file copied into the hub’s storage MUST be treated as **ephemeral**:
       - Delete as soon as scan completes, or within a short fixed window (e.g. ≤ 60 minutes).
     - Only the **compliance report** + **non-reversible hashes/checksums** MUST be retained long-term.

4. **Limits & errors**

   - The service SHOULD enforce:
     - Maximum file size limits per call (configurable).
     - Maximum processing time per job (timeout).
   - If limits are exceeded:
     - The job MUST fail gracefully with an explicit error (e.g. `FILE_TOO_LARGE`, `TIMEOUT`).
     - An audit entry MUST record the failure.
     - No raw data MUST be kept beyond the timeout window.

5. **Consistency with internal intake**

   - For **internal (ingestion) mode**, the same detection and threshold logic MUST be used as in scan-only mode.
   - The only differences are:
     - In internal mode, successful `allowed_to_store = true` leads to dataset persistence.
     - In scan-only mode, no dataset is created and the raw input is always deleted.

### 3.13 Compliance Performance Benchmarks (MVP Targets)

To keep the compliance gate practical at scale, the platform MUST define and
measure concrete performance targets for the Compliance Service.

**Throughput (row-level checks)**

- The Compliance Service SHOULD be able to process at least an **MVP baseline**
  of:
  - **5k–10k rows/second** on a single worker node,
  - assuming a typical schema (10–30 columns) and a mix of:
    - deterministic pattern-based checks (regexes, dictionaries),
    - light-weight statistical checks (frequency-based, entropy checks).
- These numbers are **targets**, not hard limits:
  - They MUST be measured and tuned in a realistic staging environment.
  - The technical design MUST document:
    - test datasets used,
    - hardware profile (CPU, RAM),
    - observed p50/p95 latencies and throughput.

**File size & sampling strategy**

- For large files (e.g. 1–2 GB browser uploads, larger via SDK/API):
  - The Compliance Service MAY use **sampling** strategies to estimate PII risk,
    as long as the sampling approach and confidence level are documented.
  - For \"scan-only\" mode, providers SHOULD be able to request **full scan** vs
    **sampled scan**, with clear trade-offs in cost and latency.
- Compliance performance expectations MUST be consistent with the overall
  intake and job timeouts defined in §11.1.

**SLOs (Service Level Objectives)**

- For ingestion-gating compliance checks:
  - Target p95 end-to-end time (from job submission to decision):
    - **≤ 5 minutes** for files up to ~1 GB (exact thresholds to be calibrated).
  - Longer-running jobs MUST:
    - expose progress via Jobs/Audit,
    - be clearly surfaced in the UI and API responses.

> These benchmarks are starting points for MVP and MUST be revisited once
> empirical performance data is available from staging/perf testing.

### 3.14 ML-based NER – When to Introduce

ML-based Named Entity Recognition (NER) can significantly improve detection
quality, but adds operational and explainability complexity. It SHOULD therefore
be introduced in stages.

**MVP position**

- MVP MAY include **ML-based NER** only as an **optional, non-blocking** signal,
  or be deferred entirely until:
  - deterministic rules (regex/dictionary/pattern checks) are stable, and
  - baseline false-positive/false-negative rates are understood.

**Criteria to introduce ML-based NER as a blocking signal**

ML-based NER SHOULD graduate from \"advisory\" to \"blocking\" only when:

- There is a sufficient **labeled dataset** of real or synthetic examples to:
  - measure precision/recall for key PII categories,
  - evaluate model behaviour across languages and edge cases.
- The organization is comfortable with:
  - how to **explain** decisions to users (e.g. highlighted spans, reasons),
  - how to handle **model drift** and regular re-training.
- The Compliance technical design defines:
  - model selection (e.g. spaCy, transformer-based models, vendor APIs),
  - hosting and scaling strategy,
  - monitoring for model performance and failures.

**Operational safeguards**

- Even when ML-based NER is enabled:
  - Deterministic rules MUST remain in place as a baseline safety net.
  - The system MUST log which detector(s) (regex vs ML) contributed to each
    finding so that:
    - false positives/negatives can be analyzed,
    - ML-specific issues can be rolled back if needed.
- Enabling/disabling ML-based NER SHOULD be:
  - feature-flagged,
  - configurable per environment, and potentially per tenant in later phases.

---

## 4. Audit Trails

### 4.1 Requirements

- The platform **MUST** provide persistent audit logs for key actions, including but not limited to:
  - Data Quality checks.
  - Compliance checks.
  - Contract creation/update/validation.
  - Data file intake/replacement/rejection.
  - Publishing/unpublishing assets for sale.
  - Marketplace actions (listing, unlisting, purchases).
  - Access/purchase/download events.

- The platform must provide ways to:
  - **Request** audit logs via API.
  - **View** audit logs in the UI with filters.
  - **Read/export** logs (CSV/JSON/Report).
  - **Validate/check** them for regulatory or internal review.

- Audit logs must be:
  - As tamper-resistant as reasonably possible (append-only model).
  - Filterable by:
    - Time period.
    - User/organization (tenant).
    - Asset/contract ID.
    - Event type/action.

### 4.2 No PII in Logs

- Audit logs and system logs **MUST NOT** contain raw PII or sensitive values from data files.
- Only **derived metrics** and **non-reversible hashes/checksums** are allowed.
- Any accidental inclusion of PII in logs MUST be treated as a security incident and:
  - Redacted, with the redaction itself logged as an audit event.

### 4.3 Events in Scope (Minimum Set)

Minimum events to capture:

- Contract lifecycle:
  - `CONTRACT_CREATED`, `CONTRACT_UPDATED`, `CONTRACT_VALIDATED`,  
    `CONTRACT_PUBLISHED`, `CONTRACT_UNPUBLISHED`.
- Data ingestion:
  - `DATA_FILE_UPLOADED`, `DATA_FILE_REPLACED`,  
    `DATA_FILE_REJECTED_COMPLIANCE`, `DATA_FILE_REJECTED_QUALITY`.
- Quality:
  - `QUALITY_CHECK_STARTED`, `QUALITY_CHECK_COMPLETED`.
- Compliance:
  - `COMPLIANCE_CHECK_STARTED`, `COMPLIANCE_CHECK_COMPLETED`.
- Marketplace:
  - `ASSET_LISTED`, `ASSET_UNLISTED`, `ASSET_PURCHASED`.
- Access:
  - `DATA_ACCESS_GRANTED`, `DATA_ACCESS_DENIED`, `DATA_DOWNLOAD`.

### 4.3.1 Audit Event details_json Structure

The `details_json` field in `audit_events` contains event-specific metadata. The structure varies by event type but follows a standardized pattern.

#### Standard Structure

```json
{
  "event_specific_field_1": "value",
  "event_specific_field_2": 123,
  "metadata": {
    "request_id": "req-123456",
    "ip_address": "203.0.113.10",
    "user_agent": "Chrome/123.0"
  }
}
```

#### Event Type-Specific Structures

**Contract Events**

- `CONTRACT_CREATED`, `CONTRACT_UPDATED`:
```json
{
  "contract_id": "uuid",
  "contract_name": "Customer Orders",
  "original_spec_type": "ODCS",
  "validation_status": "VALID"
}
```

- `CONTRACT_VALIDATED`:
```json
{
  "contract_id": "uuid",
  "validation_status": "VALID",
  "validation_errors": [],
  "validation_warnings": ["Field 'description' is missing"]
}
```

**Asset Events**

- `ASSET_CREATED`, `ASSET_UPDATED`:
```json
{
  "asset_id": "uuid",
  "asset_name": "Customer Orders",
  "asset_status": "ACTIVE",
  "primary_contract_id": "uuid"
}
```

- `ASSET_PUBLISHED`:
```json
{
  "asset_id": "uuid",
  "listing_id": "uuid",
  "visibility": "PUBLIC"
}
```

**DQ Events**

- `QUALITY_CHECK_STARTED`, `QUALITY_CHECK_COMPLETED`:
```json
{
  "dq_run_id": "uuid",
  "job_id": "uuid",
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "profile_key": "intake_basic_gx",
  "engine_type": "GX",
  "overall_status": "PASS",
  "quality_score": 95.2
}
```

**Compliance Events**

- `COMPLIANCE_CHECK_STARTED`, `COMPLIANCE_CHECK_COMPLETED`:
```json
{
  "compliance_run_id": "uuid",
  "job_id": "uuid",
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "applicable_regimes": ["GDPR", "LGPD"],
  "overall_status": "PASS",
  "risk_level": "LOW",
  "allowed_to_store": true,
  "detected_categories": ["PII_DIRECT_EMAIL"]
}
```

**Marketplace Events**

- `MARKETPLACE_ORDER_CREATED`, `MARKETPLACE_ORDER_APPROVED`, `MARKETPLACE_ORDER_REJECTED`:
```json
{
  "order_id": "uuid",
  "listing_id": "uuid",
  "consumer_tenant_id": "uuid",
  "provider_tenant_id": "uuid",
  "price_model": "FREE",
  "status": "APPROVED"
}
```

- `ENTITLEMENT_GRANTED`, `ENTITLEMENT_REVOKED`:
```json
{
  "entitlement_id": "uuid",
  "asset_id": "uuid",
  "consumer_tenant_id": "uuid",
  "provider_tenant_id": "uuid",
  "status": "ACTIVE"
}
```

**Access Events**

- `DATA_ACCESS_GRANTED`, `DATA_ACCESS_DENIED`:
```json
{
  "asset_id": "uuid",
  "file_id": "uuid",
  "operation_type": "DOWNLOAD_DATA",
  "entitlement_id": "uuid",
  "deny_reason": "ENTITLEMENT_REQUIRED"
}
```

**General Rules**

- All `details_json` MUST be valid JSON.
- No raw PII or sensitive data in `details_json` (only metadata, IDs, summaries).
- Common fields (e.g., `request_id`, `ip_address`) are included in `metadata` object when available.
- Event-specific fields are at the top level for easy querying.

### 4.4 Audit Log Storage Strategy & Retention

#### 4.4.1 Storage architecture

- Audit logs MUST be stored in a **log-optimized store** that is logically separate from:
  - The main application OLTP database (Assets, Contracts, Datasets, etc.).
- Acceptable implementations (MVP):
  - A dedicated **schema / database** in the same relational engine (e.g. `audit_log` schema in Postgres), with:
    - Separate connection pool.
    - Separate retention policies.
  - And/or a log-optimized store (e.g. time-series / columnar DB or search engine) for fast querying.
- Requirements:
  - Audit log tables MUST be **append-only**:
    - No in-place updates to event payloads (except for technical corrections under strict admin procedures).
  - Each log entry MUST include at minimum:
    - `id` (UUID)
    - `tenant_id`
    - `event_type`
    - `occurred_at` (UTC)
    - `actor_type` (`USER`, `SYSTEM`, `SERVICE`, etc.)
    - `actor_id` (user id or service id)
    - `resource_type` (e.g. `ASSET`, `CONTRACT`, `DQ_RUN`, `COMPLIANCE_RUN`, `LISTING`, `ENTITLEMENT`, `ORDER`)
    - `resource_id`
    - `details_json` (structured metadata; **no raw PII**)

#### 4.4.2 Retention policy

- Audit events MUST be retained for **at least 3 years** from `occurred_at`.
- Retention is **independent of asset lifecycle**:
  - Deleting an Asset/Dataset/Contract MUST NOT delete its historic audit events.
- Post 3 years:
  - Platform policy MAY:
    - Hard-delete events, or
    - Move them to longer-term archival storage (e.g. cold object storage).
  - This policy MUST be documented and configurable at the platform level (future: per-tenant options).

- Retention MUST honor data protection / privacy regulations:
  - Logs MUST NOT store raw PII values, so longer retention is less risky.
  - If a regulation or contract demands earlier removal, tenant-level exceptions MUST be supported (future).

#### 4.4.3 Hot vs warm vs archive tiers (conceptual)

- **Hot tier (operational)**:
  - Recent events (e.g. last 3–6 months).
  - Stored in the primary audit DB with full indexing for fast queries.
- **Warm tier (historical)**:
  - Older events (e.g. 6–36 months).
  - May be:
    - Kept in the same store but partitioned and compressed, or
    - Moved to cheaper log store optimized for read-mostly workloads.
- **Archive tier (optional, beyond 3 years)**:
  - Compressed exports in object storage (e.g. `ndjson`/`parquet` by month/tenant).
  - Only used for rare forensic access; not part of normal queries.

### 4.5 Log Volume & Query Performance

#### 4.5.1 Volume assumptions

- The system MUST be designed to handle:
  - At least **millions of AuditEvents per year** across all tenants.
  - Bursts during high-activity periods (e.g. bulk onboarding, large marketplace usage).
- Audit ingestion MUST be **non-blocking** for business operations:
  - Writing an AuditEvent MUST NOT materially slow down the main transaction.

#### 4.5.2 Data model & partitioning

- Audit log tables MUST be:
  - **Time-partitioned** (e.g. by day/month on `occurred_at`) AND
  - **Tenant-partitioned** or at least heavily indexed on `tenant_id`.
- Minimum indexes:
  - `(tenant_id, occurred_at DESC)`
  - `(tenant_id, event_type, occurred_at DESC)`
  - `(tenant_id, resource_type, resource_id, occurred_at DESC)`

This enables common queries:

- “All events for tenant X in the last 30 days”
- “All compliance runs for asset Y this quarter”
- “All marketplace orders for tenant Z between these dates”

#### 4.5.3 Query API behavior

- `/audit-events` endpoint MUST:
  - Require at least:
    - `tenant_id` (implied from token)
    - Time-window filters (`from`, `to`) OR a default (e.g. last 30 days).
  - Support filters on:
    - `event_type`
    - `resource_type`
    - `resource_id`
  - Be **paginated**:
    - `limit` and `cursor`/`offset` model.
- API MUST enforce **sensible limits**:
  - Max `limit` per request (e.g. 100–1000).
  - Max time window (e.g. 90 days) unless explicitly overridden by admin roles.

### 4.6 Log Export, Backup & Recoverability

#### 4.6.1 Export capabilities

- The platform MUST provide mechanisms for tenants and platform admins to:

  - Export audit logs for a given tenant and time range in standard formats:
    - `CSV`, `JSON`/`NDJSON`, or `Parquet`.
  - Export can be:
    - Direct download (for small ranges).
    - Asynchronously generated file placed in object storage, with a link returned via Job (`/jobs/{id}`).

- Export operations themselves MUST be audited:
  - `AUDIT_EXPORT_REQUESTED`
  - `AUDIT_EXPORT_COMPLETED`

#### 4.6.2 Backup & disaster recovery

- Audit log stores MUST be included in the platform’s **backup strategy**:

  - Regular backups (snapshot + WAL/archive logs) according to RPO/RTO requirements.
  - Backups MUST be:
    - Encrypted at rest.
    - Tested for recoverability periodically.

- In disaster recovery scenarios:
  - It MUST be possible to restore audit logs independently of the main application DB (if needed).
  - Retention guarantees (≥3 years) MUST take into account backup retention policies.

#### 4.6.3 Cross-system integration (future)

- The design MUST allow future streaming of AuditEvents to external systems, for example:
  - SIEM / security monitoring.
  - Centralized logging platforms.
  - Customer-owned compliance tools.

- Such integrations MUST:
  - Preserve `tenant_id` and core fields.
  - Respect “no raw PII in logs” constraint.
  - Not break internal audit log retention guarantees (internal store remains source of truth).


---

## 5. Semantic Layer & Ontologies

### 5.1 URI / IRI / Data DNS

The system **MUST** provide stable, publicly resolvable **URIs/IRIs** for:

- Data contracts.
- Data assets/datasets.
- Internal components (logical models, fields, rules, quality runs, compliance assessments).

Example patterns:

- Contracts: `https://{hub-domain}/id/contract/{contract_uuid}`
- Datasets: `https://{hub-domain}/id/dataset/{dataset_uuid}`
- Contract versions: `https://{hub-domain}/id/contract/{contract_uuid}/version/{version}`

URIs MUST:

- Be stable over time.
- Be dereferenceable:
  - `GET` returns at least a **JSON-LD** representation.
  - Optionally other RDF serializations (e.g. Turtle) via `Accept` headers.

### 5.2 Base Ontologies & RDF Support

The platform **MUST** support:

- RDF and related semantic web standards.
- A custom ontology that:
  - **Extends DCAT** (for catalogs, datasets, distributions).
  - Optionally aligns with **schema.org** (`Dataset`, `Organization`, etc.).
  - Introduces hub-specific classes/properties for:
    - Data contracts (ODCS/DataContract concepts).
    - Quality rules and run results.
    - Compliance assessments and findings.
    - Marketplace concepts (products, offers, licenses) in future.

All data contracts and internal components MUST be:

- Represented as ontology entities:
  - Classes, properties, or individuals.
- Accessible via semantic interfaces (JSON-LD, RDF, SPARQL, REST).

### 5.2.1 Enhanced Ontology with Standard Vocabularies

The platform **MUST** leverage standard vocabularies to maximize interoperability and reuse established patterns.

- **Standard Vocabulary Integration**
  - The platform MUST integrate and use the following standard vocabularies:
    - **DQV (Data Quality Vocabulary)**: For quality rules and dimensions (completeness, accuracy, consistency, timeliness, validity, uniqueness)
    - **DPV (Data Privacy Vocabulary)**: For compliance, jurisdictions, legal bases, personal data categories (GDPR, LGPD, CCPA, HIPAA, SOX)
    - **PROV-O (Provenance Ontology)**: For data source and lifecycle relationships
    - **ODRL (Open Digital Rights Language)**: For marketplace permissions and prohibitions
    - **SHACL (Shapes Constraint Language)**: For field validation rules (pattern, min/max length/value)
    - **FOAF (Friend of a Friend)**: For contract owners (agents with name/email)
    - **Schema.org**: For field semantic types (EmailAddress, PostalAddress, PhoneNumber, etc.)
  - The hub: ontology MUST extend and complement standard vocabularies (not duplicate)
  - JSON-LD context MUST include all standard vocabulary prefixes

- **Enhanced Ontology Classes**
  - The platform MUST define additional ontology classes:
    - `hub:QualityRule`: Individual quality rule with DQV links
    - `hub:CompliancePolicy`: Compliance and privacy policy with DPV links
    - `hub:LifecyclePolicy`: Data lifecycle and operational policies with PROV-O links
    - `hub:MarketplacePolicy`: Marketplace licensing and usage policies with ODRL links
    - `hub:Owner`: Contract owners (uses FOAF vocabulary)
    - `hub:Tag`: Contract tags (also exposed via dcat:keyword)

- **Enhanced Ontology Properties**
  - The platform MUST define additional ontology properties:
    - Field validation: `hub:fieldSemanticType`, `hub:fieldFormat`, `hub:fieldPattern`, `hub:fieldEnum`, `hub:fieldMinLength`, `hub:fieldMaxLength`, `hub:fieldMinimum`, `hub:fieldMaximum`, `hub:fieldDefault`
    - Schema constraints: `hub:isPrimaryKey`, `hub:isUnique`, `hub:isIndexed`
    - Contract metadata: `hub:hasOwner`, `hub:hasTag`, `hub:ownerName`, `hub:ownerEmail`
    - Quality rules: `hub:hasQualityRule`, `hub:ruleId`, `hub:ruleDimension`, `hub:ruleExpression`, `hub:ruleSeverity`, `hub:defaultQualityProfile`
    - Compliance policy: `hub:hasCompliancePolicy`, `hub:containsPersonalData`, `hub:hasPersonalDataCategory`, `hub:hasJurisdiction`, `hub:hasLegalBasis`, `hub:retentionPeriod`, `hub:retentionNotes`
    - Lifecycle policy: `hub:hasLifecyclePolicy`, `hub:dataSource`, `hub:refreshCadence`, `hub:availabilitySLA`, `hub:latencySLA`
    - Marketplace policy: `hub:hasMarketplacePolicy`, `hub:licenseSummary`, `hub:intendedUse`, `hub:restrictedUse`

- **Complete RDF Mapping**
  - The platform MUST map ALL HubContract sections to RDF:
    - Contract metadata (spec type, version, format, title, description, identifier)
    - Owners (FOAF agents, linked via `hub:hasOwner`)
    - Tags (hub:Tag resources, linked via `hub:hasTag`, also `dcat:keyword`)
    - Schema fields (all properties, constraints, validation rules)
    - Quality rules (hub:QualityRule with DQV links)
    - Compliance policy (hub:CompliancePolicy with DPV links)
    - Lifecycle policy (hub:LifecyclePolicy with PROV-O links)
    - Marketplace policy (hub:MarketplacePolicy with ODRL links)
  - All triples MUST be stored in the triple store (Fuseki)
  - Mapping MUST be complete (no sections skipped)

### 5.3 Contracts as Semantic Assets

- A data contract is a **semantic asset**.
- The system MUST:
  - Map canonical contract structure into RDF using the custom ontology.
  - Maintain semantic links between:
    - Contracts ↔ datasets/assets.
    - Contracts ↔ quality runs/results.
    - Contracts ↔ compliance assessments.
    - Contracts/assets ↔ marketplace products (future).

### 5.4 Semantic APIs & SPARQL

- The platform MUST provide:
  - A **SPARQL endpoint** for semantic querying.
  - **JSON-LD/REST-based APIs** for:
    - Resolving URIs to their semantic descriptions.
    - Querying key semantic metadata without needing SPARQL.

### 5.5 Mapping Triggers

- On every **contract save** (create or update):
  - The platform MUST:
    - Transform the canonical contract into an RDF graph.
    - Upsert the corresponding triples into the RDF/triple store.
- On relevant dataset/marketplace changes:
  - Update DCAT/schema.org triples accordingly.

### 5.6 Localization & Scale Expectations

- Initial implementation:
  - UI and textual metadata are primarily in **English**.
- The ontology and metadata model SHOULD allow later additions of:
  - Multilingual labels and descriptions for concepts and assets.

- Scale expectations (initial target):
  - Up to **1 million assets** in early phases.
  - The semantic infrastructure MUST be designed to scale horizontally beyond this, as the interoperability hub grows.

---

## 6. Interoperable Data Hub – Core Functionality

The goal is to create an **interoperability data hub** that provides:

- Standard schemas.
- APIs.
- Ontologies.
- A unified way to register, manage, and expose data assets.

### 6.1 Data Asset Registration Flows

The system must support **three primary ways** to register a data asset (data + contract).

#### 6.1.1 Flow 1 – Data First

1. User uploads a **data file**.
2. System:
   - Validates that the file is in a supported and correct format.
   - Reads the data.
   - Infers schema and extracts a sample.
3. Before storing the file as an asset:
   - Runs **compliance validation** (mandatory gate).
   - Runs **basic data quality checks** (`intake_basic`).
4. If checks fail:
   - The file is not stored.
   - User receives reports and can correct/remediate data externally before retrying.
5. If checks pass (or pass with acceptable warnings per policy):
   - System presents a **data contract editing screen**:
     - Pre-loaded with:
       - User information.
       - Data-derived metadata (schema, sample).
       - Quality check results.
       - Compliance check results.
6. User can edit and refine the contract.
7. User triggers **DataContract CLI** validation (lint + validate):
   - If errors:
     - Errors are shown.
     - User must fix and re-run validation.
   - Only after `VALID` status can the process continue.
8. After successful validation:
   - The contract + dataset are registered in the **user’s catalog**.
   - The contract and asset are mapped into the semantic layer.

#### 6.1.2 Flow 2 – Contract First

1. User uploads a **data contract file**.
2. System runs **DataContract CLI** validation:
   - If `INVALID` or `ERROR`:
     - User is asked to upload/fix the file.
   - If `VALID` or `WARNING_ONLY` (per policy):
     - Contract is normalized and stored as a draft.
3. User uploads the **data file**:
   - System validates file format.
   - Reads data, infers schema, extracts a sample.
4. Before storing the file:
   - Runs **compliance validation** (mandatory gate).
   - Runs **basic data quality checks** (`intake_basic`).
5. If checks fail:
   - The file is not stored.
   - User receives reports for remediation.
6. If checks pass:
   - System compares:
     - Inferred schema vs. contract schema.
   - The contract schema is the **source of truth**, but:
     - Any discrepancies MUST be highlighted as warnings in the UI.
7. System presents a **data contract editing screen**:
   - Pre-loaded with:
     - Original contract metadata.
     - Data-derived metadata (schema, sample).
     - Quality results.
     - Compliance results.
8. User can edit and refine the contract.
9. User triggers **DataContract CLI** validation again:
   - Errors are shown; user must fix and re-run until `VALID`.
10. After successful validation:
    - The asset (data + contract) is included in the **user’s catalog** and semantic layer.

#### 6.1.3 Flow 3 – Contract Only

1. User uploads a **data contract file** (no data file).
2. System runs **DataContract CLI** validation:
   - If `INVALID` or `ERROR`:
     - User is asked to upload/fix the file.
   - If `VALID` or `WARNING_ONLY` (per policy):
     - Contract is normalized and stored.
3. System presents a **data contract editing screen**:
   - Pre-loaded with:
     - User information.
     - Contract-derived metadata.
4. User can edit the contract.
5. User triggers **DataContract CLI** validation:
   - Errors are shown; user must fix and re-run until `VALID`.
6. After successful validation:
   - The contract-only asset is included in the **user’s catalog** and semantic layer.
7. Later, when data is attached/added:
   - The data file goes through the **same compliance + quality gate** as in the other flows before being stored.

---

## 7. User Catalog Behavior

Once assets are in the user’s catalog:

1. **Data Contract Editing**
   - Any field in the data contract **can be edited**.
   - After edits:
     - The contract **MUST** be re-validated with **DataContract CLI**.
     - Only `VALID` contracts are considered “active/valid”.
     - `WARNING_ONLY` MAY be considered active with clearly visible warnings.

2. **Data Attachment / Replacement**
   - For contract-only assets:
     - Users can later **add/attach data**.
   - For existing assets:
     - Data can be **replaced/updated**.
   - Every new or replaced data file:
     - **MUST** go through:
       - Compliance checks (mandatory gate).
       - Data quality checks (`intake_basic` or chosen profile).
     - Only compliant and quality-checked data is stored.

3. **Semantic Status & Partial Failures**
   - If semantic mapping (RDF/ontology) fails while contract and data are otherwise valid:
     - The asset’s `semantic_status` is marked as **`DEGRADED`**.
     - A background retry mechanism SHOULD attempt to repair the semantic mapping.
     - The asset remains usable for non-semantic features; semantic APIs may show partial results.

4. **Marketplace / Shelf Status**
   - Assets can be:
     - Put up for sale / “on the shelf”.
     - Removed from sale.
   - The platform MUST track:
     - Which assets are visible in the marketplace (possibly cross-tenant, if marked public).
     - Which assets are internal-only per tenant.

---

## 8. Developer Experience & APIs

### 8.1 CLI/SDK Support

Because data contracts are **semantic assets**, the platform **MUST** provide:

- CLI tools.
- SDKs at least for:
  - **JavaScript**
  - **Python**

These tools MUST support:

- Managing data contracts and assets (create, update, validate).
- Triggering and retrieving results from:
  - Data quality services.
  - Compliance services.
- Accessing semantic/ontology information:
  - URIs/IRIs for contracts, datasets, fields.
  - JSON-LD/RDF metadata.
- Interacting with:
  - The catalog (search, list, get).
  - The marketplace (where appropriate).

### 8.2 API Style & Versioning

- The platform SHOULD provide:
  - A **REST API** as the primary interface:
    - Versioned base paths, e.g. `/api/v1/...` (v1 from launch).
  - A **GraphQL API** for advanced integrations and marketplace/catalog queries:
    - A single `/graphql` endpoint with schema versioning.

- Backward compatibility:
  - Within a major API version (v1), breaking changes MUST be avoided.
  - New features SHOULD be additive (new fields, new endpoints).
  - Future major versions (v2, etc.) MAY deprecate older patterns with a clear migration path.

---

## 9. Ecommerce & Marketplace Requirements

### 9.1 Data Marketplace

- The platform **SHOULD** enable buying and selling of data assets:
  - Intermediating the **data market** between providers and consumers.
  - Supporting:
    - **Companies** (organizations/tenants).
    - **Individuals** (who may also be tenants or members of tenants).

### 9.2 Multi-Tenant Model

- The platform is **multi-tenant**:
  - Each organization is a **tenant** with its own catalog and users.
  - Assets belong primarily to a tenant (provider).
  - Assets can be flagged as:
    - **Internal** (visible only within the tenant).
    - **Public/marketplace** (visible across tenants, subject to access rights).

- Multiple users per tenant:
  - Roles such as provider, consumer, admin, auditor SHOULD be supported (see §9.6).

### 9.3 Ecommerce Framework Options

The following frameworks are **candidates** for the ecommerce layer (to be evaluated):

- Medusa: https://github.com/medusajs/medusa  
- EverShop: https://github.com/evershopcommerce/evershop  
- Django-Oscar: https://github.com/django-oscar/django-oscar  
- Saleor: https://github.com/saleor/saleor  

Final choice and integration approach are still open.

### 9.4 Integration Layer – Ecommerce & Data Contracts

Open topics to design:

- Representation of data assets as **products/SKUs**, including:
  - Links to contract IDs and dataset IDs.
  - Plans/pricing (one-off, subscription, usage-based for DQ/compliance/API calls).

- Billing integration:
  - Billing MUST be transparent and tied to measurable operations:
    - e.g. per DQ run, per compliance run, per dataset access, per API usage.
  - The platform SHOULD track operational cost drivers (infra/cloud/compute) per operation to support a cost-plus pricing model.

- Entitlement management:
  - Who can access which datasets under which contract/license.
  - How purchases, subscriptions, and cancellations affect entitlements.

- Interaction between ecommerce events and core systems:
  - Data contract layer (e.g. license fields, usage rights).
  - Data storage layer (e.g. enabling/disabling data access endpoints).
  - Audit trails (purchase, billing, and access events).

### 9.5 Marketplace Entitlement Model (MVP)

For the MVP, **entitlement management IS in scope**, but **billing/payment is NOT**.  
This section defines how access to data assets is granted via the marketplace.

#### 9.5.1 Core concepts

- **Listing**
  - Marketplace representation of an `Asset`.
  - Has visibility and access settings.
  - Can be browsed by other tenants (depending on visibility).

- **Order**
  - Represents a **request for access** to a listing by a consumer tenant.
  - Exists even when there is no billing/payment, for auditability.

- **Entitlement**
  - Represents **granted access** from a provider tenant to a consumer tenant for a given asset/listing.
  - Controls whether a consumer can:
    - See the asset in “My Data”.
    - Download or access via API.

#### 9.5.2 Listing access modes (MVP)

Each listing MUST specify an `access_mode`, at least:

- `FREE_AUTO_APPROVE`
  - Anyone (within allowed audience) can click **“Get access”** and immediately receive an entitlement.
  - No manual approval and no payment.

- `REQUEST_APPROVAL`
  - Consumers click **“Request access”**.
  - An `Order` is created in status `REQUESTED`.
  - Provider (or Marketplace Operator) must **manually approve or reject**.
  - When approved, an `Entitlement` is created.

(Future: add paid modes like `PAID_ONE_TIME`, `PAID_SUBSCRIPTION`, etc.)

#### 9.5.3 Entitlement lifecycle (MVP)

- Status values (minimum):

  - `PENDING`   – Request created, waiting for provider action.
  - `ACTIVE`    – Access granted.
  - `REVOKED`   – Access explicitly withdrawn.
  - `EXPIRED`   – Access expired (future; e.g., time-limited licenses).

- Entitlement creation:

  - **FREE_AUTO_APPROVE**:
    - UI/API action `Get access`:
      - Creates `Order` with `status = COMPLETED` and `billing_status = NOT_APPLICABLE`.
      - Creates `Entitlement` with `status = ACTIVE`.
  - **REQUEST_APPROVAL**:
    - `Request access` creates:
      - `Order` with `status = REQUESTED`.
      - No entitlement yet.
    - Provider’s approve action:
      - Updates `Order.status = APPROVED`.
      - Creates `Entitlement.status = ACTIVE`.

- Entitlement usage / enforcement:

  - All **data access** APIs (downloads / data reads) MUST check that:
    - An `Entitlement` exists for `(provider_tenant, consumer_tenant, asset_id)`.
    - `Entitlement.status = ACTIVE`.
  - If no active entitlement:
    - Access is denied (`403`/`401`), even if listing is visible in Marketplace.

**Entitlement Checking Flow**

Entitlement checks are performed **as middleware** in the API gateway or access layer, not via a dedicated endpoint. The flow is as follows:

1. **Request Interception**:
   - All data access endpoints (e.g., `GET /files/{id}/download`, `GET /datasets/{id}/data`) are intercepted by the entitlement middleware.
   - Middleware extracts:
     - `tenant_id` from bearer token (consumer tenant).
     - `asset_id` from request (derived from `file_id` or `dataset_id` via database lookup).

2. **Same-Tenant Check** (Fast Path):
   - If `files.tenant_id = token.tenant_id` (or `datasets.tenant_id = token.tenant_id`):
     - **No entitlement check required**.
     - Access is granted if user has appropriate role (`DATA_PROVIDER`, `TENANT_ADMIN`, or `AUDITOR`).
     - Request proceeds to handler.

3. **Cross-Tenant Check** (Entitlement Required):
   - If `files.tenant_id != token.tenant_id`:
     - Middleware queries `entitlements` table:
       ```sql
       SELECT * FROM entitlements
       WHERE tenant_id = <consumer_tenant_id>
         AND asset_id = <asset_id>
         AND status = 'ACTIVE'
         AND (expires_at IS NULL OR expires_at > NOW())
       ```
     - **If entitlement exists and is active**:
       - Request proceeds to handler.
     - **If no entitlement or entitlement is expired/revoked**:
       - Request is rejected with `403 Forbidden` and error code:
         - `ENTITLEMENT_REQUIRED` (if no entitlement exists).
         - `ENTITLEMENT_EXPIRED` (if entitlement exists but `expires_at < NOW()`).
         - `ENTITLEMENT_REVOKED` (if entitlement exists but `status = REVOKED`).

4. **Caching** (Performance Optimization):
   - Entitlement checks are cached for **5 minutes** (configurable via `ENTITLEMENT_CACHE_TTL_SECONDS`).
   - Cache key: `entitlement:{consumer_tenant_id}:{asset_id}`.
   - Cache invalidation: On entitlement creation, update, or revocation (via message bus or cache invalidation endpoint).

5. **Audit Logging**:
   - All entitlement checks (successful and failed) are logged as `AuditEvent`:
     - `DATA_ACCESS_GRANTED` (successful check).
     - `DATA_ACCESS_DENIED` (failed check with reason: `ENTITLEMENT_REQUIRED`, `ENTITLEMENT_EXPIRED`, `ENTITLEMENT_REVOKED`).

**Error Codes**

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `ENTITLEMENT_REQUIRED` | 403 Forbidden | Cross-tenant access requires an active entitlement. |
| `ENTITLEMENT_EXPIRED` | 403 Forbidden | Entitlement exists but has expired (`expires_at < NOW()`). |
| `ENTITLEMENT_REVOKED` | 403 Forbidden | Entitlement exists but has been revoked (`status = REVOKED`). |

---

### 9.6 "Request Access" Flow Without Billing

Because billing is out of scope for MVP, **“Request access” does not charge money**, but it still creates a traceable order and entitlement.

#### 9.6.1 FREE_AUTO_APPROVE flow

1. Consumer opens listing page.
2. Clicks **“Get access”**.
3. Backend:
   - Creates `Order`:
     - `status = COMPLETED`
     - `billing_status = NOT_APPLICABLE`
     - `price_amount = 0`
   - Creates `Entitlement`:
     - `status = ACTIVE`
     - `provider_tenant_id`, `consumer_tenant_id`, `asset_id`, `listing_id`.
4. Consumer is redirected / informed:
   - “Access granted.”
   - Asset appears in **“My Data”**.
5. All actions are logged as `AuditEvent`s:
   - `MARKETPLACE_ORDER_CREATED`
   - `ENTITLEMENT_GRANTED`.

#### 9.6.2 REQUEST_APPROVAL flow

1. Consumer opens listing page.
2. Clicks **“Request access”**.
3. Backend:
   - Creates `Order`:
     - `status = REQUESTED`
     - `billing_status = NOT_APPLICABLE` (for MVP)
   - No entitlement yet.
4. Provider (or Marketplace Operator) sees pending requests in a **“Requests”** or **“Orders”** UI.
5. Provider chooses **Approve** or **Reject**:

   - **Approve**:
     - `Order.status = APPROVED`
     - Create `Entitlement.status = ACTIVE`
   - **Reject**:
     - `Order.status = REJECTED`
     - No entitlement created.

6. Consumer sees:
   - In **My Requests / My Orders**:
     - Status `APPROVED` or `REJECTED`.
   - In **My Data**:
     - Asset appears only if entitlement is `ACTIVE`.

7. Audit events:
   - `MARKETPLACE_ORDER_CREATED`
   - `MARKETPLACE_ORDER_APPROVED` / `MARKETPLACE_ORDER_REJECTED`
   - `ENTITLEMENT_GRANTED` (on approval)
   - `ENTITLEMENT_REVOKED` (if revoked later).

> Note: In MVP, all these actions are free; “Orders” are used purely for workflow + audit.

---

### 9.7 Future Billing Integration Points

Billing and payments are **explicitly out of scope** for MVP, but the design MUST anticipate integration with external billing systems later.

#### 9.7.1 Price & SKU metadata on Listing

- Each listing SHOULD already carry billing-relevant metadata, even if unused in MVP, such as:

  - `price_model`  – `"FREE" | "ONE_TIME" | "SUBSCRIPTION" | "USAGE_BASED" | "EXTERNAL"`
  - `price_amount` – numeric (for non-free modes)
  - `currency`     – ISO currency code
  - `external_product_id` / `sku` – optional link to billing provider product

- In MVP:
  - `price_model = "FREE"` and `price_amount = 0` for all active listings.
  - These fields are still stored and exposed via API for future compatibility.

#### 9.7.2 Order & Billing Status Fields

- `Order` MUST have billing-related fields, even if not used at MVP:

  - `billing_status`:
    - `NOT_APPLICABLE` (MVP default)
    - `PENDING_PAYMENT`
    - `PAID`
    - `FAILED`
    - `REFUNDED`
  - `billing_provider` (e.g. `"STRIPE"`, `"ADYEN"`, `"INTERNAL"`)
  - `billing_external_id` (ID of payment object in external system)

- In MVP:
  - `billing_status = NOT_APPLICABLE`
  - `billing_provider` and `billing_external_id` are null.

#### 9.7.3 Entitlement vs Payment – Future Behavior

In a future billing-enabled version:

- For paid listings (`price_model != FREE`):

  - `Request access` → creates `Order` with:
    - `status = REQUESTED`
    - `billing_status = PENDING_PAYMENT` or `NOT_APPLICABLE` if “manual invoice”.
  - The hub or external checkout flow will:
    - Process the payment.
    - On payment **success**:
      - Update `Order.status = COMPLETED`
      - `billing_status = PAID`
      - Create `Entitlement.status = ACTIVE`.
    - On payment **failure**:
      - `billing_status = FAILED`
      - `Order.status = REJECTED` or `CANCELLED`
      - No entitlement created.

- For subscriptions:
  - Entitlement renewal/expiry will depend on subscription status in billing system.
  - Revoking a subscription leads to `Entitlement.status = EXPIRED` or `REVOKED`.

The MVP design MUST ensure:

- Entitlements can be created **only** when business rules are satisfied (currently “free + approved”; later “paid + approved”).
- The code path for creating entitlements has clearly defined hooks where payment checks can be inserted without API breaking changes.

#### 9.7.4 Integration surfaces

Future billing integrations will primarily use:

1. **Synchronous API calls** from the hub to billing provider:
   - Create/update product/price (out of band).
   - Create payment session / invoice for an order.
2. **Webhook or callback endpoints**:
   - Billing provider calls back to hub when payments succeed/fail.
   - Hub updates `Order` + `Entitlement` accordingly.
3. **Reporting & reconciliation**:
   - Hub emits usage/entitlement events for downstream billing/finops systems.

In all cases:

- Entitlements remain the **source of truth for data access**.
- Billing systems become the **source of truth for money**.
- Audit trails MUST capture both order and entitlement transitions for compliance and dispute handling.


---

## 10. Integration with the Semantic Layer

### 10.1 Ecommerce & Semantic Layer

Open topics:

- Representation of marketplace concepts in the ontology:
  - Products, offers, prices, licenses.
  - Relationships such as:
    - `Product` → `Dataset/Contract` it refers to.
    - `Tenant/Organization` → `Assets` they provide or consume.

- Semantic search over the marketplace:
  - Allow discovery of assets by concept/domain, not just name.
  - Use ontology (domains, PII tags, quality/compliance tags) to refine search.

### 10.2 Code & Infrastructure Requirements (High-Level)

To support semantic + ecommerce integration, the platform will require:

- **Code**
  - Services to:
    - Map data contracts, datasets, and marketplace products into ontology entities.
    - Maintain URIs/IRIs and RDF/JSON-LD representations.
  - APIs/SDKs for:
    - Resolving URIs to contracts/products.
    - Querying semantic metadata for discovery and governance.

- **Infrastructure**
  - RDF/triple store or graph database for semantic data.
  - APIs or gateways for:
    - SPARQL queries.
    - JSON-LD/RDF representations.
  - Integration components between:
    - Core data/contract backend.
    - Ecommerce engine.
    - Semantic/ontology store.

---

## 11. Non-Functional Requirements

### 11.1 Performance & Scalability

- The platform SHOULD be designed to support:
  - At least **1 million assets** in early phases, with a roadmap to scale beyond.
  - Multiple tenants, each with their own catalogs and users.

#### 11.1.1 File Size & Ingestion

**File Size Limit Configuration**

All file size limits are defined in the following table and can be configured per tenant or globally:

| Limit Type | Environment Variable | Default Value | Per-Tenant Override | Description |
|------------|---------------------|---------------|---------------------|-------------|
| **Browser upload max size** | `MAX_BROWSER_UPLOAD_SIZE_BYTES` | `1073741824` (1 GB) | `tenant_config.max_browser_upload_size_bytes` | Maximum file size for browser-based uploads via UI |
| **SDK/CLI upload max size** | `MAX_SDK_UPLOAD_SIZE_BYTES` | `10737418240` (10 GB) | `tenant_config.max_sdk_upload_size_bytes` | Maximum file size for SDK/CLI-based uploads |
| **Simple upload threshold** | `SIMPLE_UPLOAD_THRESHOLD_BYTES` | `67108864` (64 MB) | - | Files below this size use simple upload; above use chunked |
| **Min chunk size** | `MIN_CHUNK_SIZE_BYTES` | `5242880` (5 MB) | - | Minimum chunk size for chunked uploads |
| **Max chunk size** | `MAX_CHUNK_SIZE_BYTES` | `67108864` (64 MB) | - | Maximum chunk size for chunked uploads |
| **Target chunk count** | `TARGET_CHUNK_COUNT` | `1000` | - | Target number of chunks for chunked uploads |
| **Max chunk count** | `MAX_CHUNK_COUNT` | `10000` | - | Maximum number of chunks allowed |

**Configuration Priority**:
1. Tenant-specific override (if configured in `tenant_config`).
2. Global environment variable.
3. Default value (from table above).

**Per-Tenant Configuration**:
- File size limits can be overridden per tenant via `PATCH /tenants/{id}/config` (see `API_Spec_v1.md` §13).
- Example:
  ```json
  {
    "max_browser_upload_size_bytes": 2147483648,  // 2 GB for this tenant
    "max_sdk_upload_size_bytes": 21474836480     // 20 GB for this tenant
  }
  ```

- **General targets (MVP)**  
  - The platform MUST support:
    - **Small to medium files** via browser UI upload (up to `MAX_BROWSER_UPLOAD_SIZE_BYTES`, default 1 GB).
    - Larger files (up to `MAX_SDK_UPLOAD_SIZE_BYTES`, default 10 GB) via SDK/CLI and direct-to-object-storage APIs.
  - The platform MUST NOT promise "any size upload" via browser; limits MUST be:
    - Configurable.
    - Communicated clearly in the UI.
  - Very large datasets MAY require:
    - Chunked upload (protocol defined in **API_Spec_v1.md – §5 Files API (Upload & Intake)**).
    - Storage-by-reference (e.g. S3 URLs).
    - These are future enhancements and not mandatory for MVP.

- **Browser uploads**
  - Browser uploads MUST use **pre-signed URLs** obtained from `/files/init`.
  - For medium/large files, the platform SHOULD support **chunked / multi-part uploads** even in MVP to avoid failures on flaky networks.
  - `/files/init` MUST:
    - Enforce `MAX_BROWSER_UPLOAD_SIZE_BYTES` limit (default 1 GB, configurable per tenant).
    - Return parameters describing:
      - Whether multi-part upload is required or optional.
      - Recommended `max_chunk_size_bytes` (calculated based on file size and chunk configuration).
  - The UI SHOULD:
    - Show progress indicators.
    - Show clear error messages for:
      - `UPLOAD_FILE_TOO_LARGE`
      - `UPLOAD_TIMEOUT`
      - Unsupported type.

- **SDK/CLI uploads**
  - SDK/CLI ingestion MUST support **multi-part/chunked uploads** to object storage by default for large files.
  - Upload SHOULD go **directly to object storage**, not via the API server as a proxy.
  - After completing upload, client MUST call `/files/{id}/complete` to register the file and trigger downstream jobs.

- **Handling network interruptions (resumable uploads)** - For medium/large files, the upload model SHOULD be **resumable** rather than "all-or-nothing": - Browser and SDK clients SHOULD upload data in **chunks/multi-part** with a stable `upload_id`. - The backend/object storage MUST allow resuming an interrupted upload by re-sending only missing chunks. - `/files/init` MUST return any identifiers needed to resume: - `file_id` and `upload_id` (or equivalent object-storage upload token). - Expiration/validity window for the resumable upload. - On **client-side interruption** (network drop, tab close, process crash): - Clients SHOULD attempt automatic retries for individual chunks with backoff. - The UI SHOULD clearly indicate when an upload was interrupted and whether it can be resumed. - On **server-side timeout or abort**: - The platform MUST mark the upload as `INTERRUPTED` or `FAILED` in internal state. - Any partial data in object storage MUST be: - either re-used on a subsequent resume (if within the allowed window), or - cleaned up by a background process once the upload expires. - `/files/{id}/complete` MUST: - verify that all required chunks have been successfully uploaded, - fail with a clear error (e.g. `UPLOAD_INCOMPLETE`) if the file is only partially present, - avoid triggering downstream DQ/compliance on incomplete files. 

- **Chunked upload session TTL & cleanup**
  - Chunked upload sessions (partial file + associated chunks) MUST have a maximum lifetime of **24 hours**.
  - After 24 hours:
    - The session MUST be considered expired.
    - Partial chunk data MUST be deleted by a background cleanup job.
  - A cleanup job MUST run at least **once per hour** to:
    - Identify expired upload sessions.
    - Delete any associated partial chunks and temporary metadata.
  - Expired sessions MUST surface as `410 Gone` errors in the API with a clear `UPLOAD_SESSION_EXPIRED` code.

#### 11.1.1.2 Object Storage Outage Handling

The platform MUST handle object storage unavailability gracefully to minimize data loss and provide clear feedback to users.

**Outage Detection**

- **Health checks**: Services that depend on object storage MUST perform periodic health checks (every 30 seconds)
- **Circuit breaker**: Object storage calls MUST be wrapped in a circuit breaker:
  - **Failure threshold**: 5 consecutive failures or 50% failure rate over 1 minute
  - **Open state**: Circuit opens, all object storage operations fail fast
  - **Half-open state**: After 60 seconds, circuit enters half-open state and allows one test request
  - **Closed state**: Circuit closes when test request succeeds

**During Upload Initialization (`POST /files/init`)**

- **If object storage is unavailable**:
  - API returns `503 Service Unavailable` with error code `SYSTEM_UNAVAILABLE`
  - Error response includes:
    ```json
    {
      "error": {
        "code": "SYSTEM_UNAVAILABLE",
        "message": "Object storage is temporarily unavailable. Please try again later.",
        "details": {
          "component": "object_storage",
          "retry_after_seconds": 60
        }
      }
    }
    ```
  - **Request is rejected** (not queued); client must retry
  - **No file record is created** (prevents orphaned records)

**During Active Uploads (SIMPLE mode)**

- **If object storage becomes unavailable mid-upload**:
  - Pre-signed URL upload fails (client receives error from object storage)
  - Client retries upload to pre-signed URL (if URL is still valid)
  - **If pre-signed URL expires during outage**:
    - Client must call `POST /files/init` again to get new pre-signed URL
    - Previous `file_id` is marked as `FAILED` (if exists)
    - Client starts new upload session

**During Active Uploads (CHUNKED mode)**

- **If object storage becomes unavailable mid-upload**:
  - Individual chunk uploads fail (client receives error from object storage)
  - **Client behavior**:
    - Client retries failed chunks with exponential backoff
    - Client calls `GET /files/{id}/chunks` to verify server state
    - If outage persists > 5 minutes, client may pause upload and retry later
  - **Server behavior**:
    - Server does not mark chunks as uploaded if object storage write fails
    - `GET /files/{id}/chunks` returns accurate state (only successfully uploaded chunks)
    - Upload session TTL (24 hours) continues to count down
  - **After outage recovery**:
    - Client resumes uploading missing chunks
    - Server accepts chunks normally once object storage is available

**During Upload Finalization (`POST /files/{id}/complete`)**

- **If object storage is unavailable**:
  - API returns `503 Service Unavailable` with error code `SYSTEM_UNAVAILABLE`
  - **File record remains in `UPLOADING` or `PENDING_FINALIZE` state**
  - Client can retry `POST /files/{id}/complete` (idempotent operation)
  - **No downstream processing** (schema inference, DQ, compliance) is triggered until finalization succeeds

**During File Downloads (`GET /files/{id}/download`)**

- **If object storage is unavailable**:
  - API returns `503 Service Unavailable` with error code `SYSTEM_UNAVAILABLE`
  - Error response includes `Retry-After` header (estimated recovery time)
  - **No data is returned**; client must retry later

**During Background Jobs (DQ, Compliance, Schema Inference)**

- **If object storage is unavailable when job tries to read file**:
  - Job is marked as `FAILED` with error code `SYSTEM_UNAVAILABLE`
  - Job can be retried (up to 3 retries with exponential backoff)
  - **No partial results are stored** if file cannot be read

**Recovery Procedures**

- **Automatic recovery**:
  - Circuit breaker automatically transitions to half-open state after 60 seconds
  - Test request verifies object storage availability
  - If test succeeds, circuit closes and normal operations resume
- **Manual recovery** (if automatic recovery fails):
  - Operations team can manually reset circuit breaker via admin API (future enhancement)
  - Operations team can verify object storage connectivity and configuration
- **Notification**:
  - When object storage outage is detected, alert is sent to operations team
  - Alert includes: duration, affected operations, estimated impact
  - When recovery is confirmed, resolution notification is sent

**Monitoring and Alerting**

- **Metrics**:
  - `object_storage_availability` (gauge): 1 if available, 0 if unavailable
  - `object_storage_operation_errors_total{operation}` (counter): Failed operations by type
  - `object_storage_circuit_breaker_state` (gauge): 0=closed, 1=open, 2=half-open
- **Alerts**:
  - **Warning**: Circuit breaker opens (object storage unavailable)
  - **Critical**: Circuit breaker open for > 5 minutes
  - **Resolution**: Circuit breaker closes (object storage recovered)

#### 11.1.2 Async Processing & Timeouts for Large Files - **Non-blocking intake** - `/files/init` and `/files/{id}/complete`: - MUST return quickly (e.g. < 5–10 seconds). - MUST NOT execute heavy work inline (no full DQ/compliance/schema inference during the HTTP request). - MUST create **Job** records and enqueue DQ/compliance/inference work for background processing. - **Job timeouts** - Each DQ and Compliance job MUST have: - A **maximum runtime** (timeout), e.g. 15–30 minutes (configurable). - Resource limits (CPU/memory) at container/process level. - If a job exceeds its limits: - Mark Job as `FAILED` or `UNKNOWN` with clear codes: - `DQ_TIMEOUT`, `COMPLIANCE_TIMEOUT`, `DQ_INPUT_TOO_LARGE`, `COMPLIANCE_INPUT_TOO_LARGE`, etc. - Emit an `AuditEvent` describing the failure. - For intake: - **Do not** create/attach the Dataset if compliance did not complete with `allowed_to_store = true`. - **User experience** - For large files, the UI MUST: - Immediately show that the file upload completed and intake is in progress. - Poll `/jobs/{id}` for DQ/compliance/schema statu



#### 11.1.3 DQ & Compliance Throughput on Large Datasets

- **Concurrency**
  - The system SHOULD be able to process multiple DQ/compliance checks concurrently for multiple tenants.
  - Per-tenant rate limits and max concurrent jobs MUST be configurable to protect overall system stability.

- **Full scan vs sampling**
  - For files up to a configurable **full-scan threshold**:
    - DQ and Compliance SHOULD attempt **full scans** (all rows).
  - For files above that threshold:
    - DQ and Compliance MAY use **sampling** strategies (first-N rows, random sample, etc.).
    - The sampling strategy MUST be recorded in `details_json` of `DQRun` and `ComplianceRun`:
      - `strategy`, `sample_size`, `estimated_population_size`, etc.
    - Where feasible, DQ and Compliance SHOULD share the same row sample for consistency.

#### 11.1.3 Schema Inference Algorithm

Schema inference is performed during file intake to automatically detect the structure, data types, and constraints of uploaded data files.

**Supported Formats**

- **CSV** (Comma-Separated Values):
  - Delimiter detection: comma, semicolon, tab, pipe (`|`)
  - Header row detection: First row is assumed to be headers if it contains non-numeric values
  - Encoding detection: UTF-8 (default), UTF-16, Latin-1, Windows-1252
- **JSON** (JSON Lines / NDJSON):
  - Each line is a JSON object
  - Schema inferred from first N objects
  - Nested objects are flattened with dot notation (e.g., `user.name`)
- **Parquet**:
  - Schema is read directly from Parquet metadata
  - Type mapping: Parquet types → HubContract types
- **JSON (single object or array)**:
  - If single object: schema inferred from object structure
  - If array: schema inferred from first N array elements

**Inference Algorithm**

1. **Sample Selection**:
   - **Default sample size**: First **10,000 rows** (or all rows if file has fewer than 10,000 rows).
   - **Configurable threshold**: For files larger than 100 MB, sample size can be reduced to 5,000 rows (configurable via `SCHEMA_INFERENCE_SAMPLE_SIZE`).
   - **Sampling strategy**: Sequential (first N rows), not random (to preserve ordering and detect patterns).

2. **Type Inference**:
   - **String detection**: If column contains any non-numeric, non-boolean values → `string`.
   - **Integer detection**: If all sampled values are integers (no decimals) → `integer`.
   - **Float detection**: If any sampled value contains decimal point → `float`.
   - **Boolean detection**: If all sampled values are `true`/`false`, `1`/`0`, `yes`/`no` → `boolean`.
   - **Date/Time detection**: If values match common date/time patterns (ISO 8601, `YYYY-MM-DD`, etc.) → `datetime` or `date`.
   - **Null handling**: `null`/empty values are counted but don't affect type inference (unless all values are null → type is `string` with `nullable: true`).

3. **Constraint Detection**:
   - **Nullable**: Column is nullable if any sampled value is `null` or empty.
   - **Unique**: Column is marked as potentially unique if all sampled values are distinct (heuristic, not guaranteed).
   - **Primary key candidate**: Single column with all unique, non-null values is flagged as a potential primary key.

4. **Schema Output**:
   - Inferred schema is stored in `datasets.schema_inferred` as JSONB:
     ```json
     {
       "fields": [
         {
           "name": "order_id",
           "data_type": "string",
           "nullable": false,
           "sample_values": ["ORD-001", "ORD-002", "ORD-003"]
         },
         {
           "name": "amount",
           "data_type": "float",
           "nullable": true,
           "sample_values": [99.99, 150.50, null]
         }
       ],
       "primary_key_candidates": ["order_id"],
       "row_count_estimated": 10000,
       "inference_metadata": {
         "sample_size": 10000,
         "strategy": "first_n_rows",
         "format": "CSV",
         "encoding": "UTF-8",
         "delimiter": ","
       }
     }
     ```

**Error Handling**

- **Malformed files**:
  - If file cannot be parsed (invalid CSV, invalid JSON, corrupted Parquet):
    - Schema inference job is marked as `FAILED`.
    - Error details are stored in `datasets.schema_inferred` as:
      ```json
      {
        "error": "PARSE_ERROR",
        "message": "Invalid CSV format: unexpected quote at line 42",
        "line_number": 42
      }
      ```
    - **API error response**: When schema inference fails during `POST /files/{id}/complete` or `POST /assets/{id}/datasets`:
      - Returns `400 Bad Request` with error code `SCHEMA_INFERENCE_FAILED`
      - Error response includes:
        ```json
        {
          "error": {
            "code": "SCHEMA_INFERENCE_FAILED",
            "message": "Schema inference failed: Invalid CSV format at line 42.",
            "http_status": 400,
            "details": {
              "error_type": "PARSE_ERROR",
              "error_message": "Invalid CSV format: unexpected quote at line 42",
              "line_number": 42,
              "file_id": "uuid",
              "suggestion": "Fix CSV formatting errors and re-upload the file."
            }
          }
        }
        ```
    - **Retry mechanism**: Users can retry schema inference by:
      - Re-uploading the file (if file was the issue)
      - Calling `POST /assets/{id}/datasets` again with the same `data_file_id` (idempotent operation)
  - **Partial parsing**: If first N rows parse successfully but later rows fail:
    - Schema is inferred from successful rows.
    - Warning is added to `inference_metadata.warnings`:
      ```json
      {
        "warnings": [
          {
            "type": "PARTIAL_PARSE",
            "message": "Schema inferred from first 5000 rows; parsing failed at line 5001",
            "line_number": 5001,
            "rows_inferred": 5000
          }
        ]
      }
      ```
    - **API response**: Returns `200 OK` with schema, but includes warnings in response
    - Dataset is created with partial schema; user should review warnings
- **Unsupported formats**:
  - Returns error code `UNSUPPORTED_FILE_FORMAT`.
  - User must convert file to supported format before upload.
  - **Error response**:
    ```json
    {
      "error": {
        "code": "UNSUPPORTED_FILE_FORMAT",
        "message": "File format is not supported. Supported formats: CSV, JSON, Parquet.",
        "http_status": 400,
        "details": {
          "detected_format": "xlsx",
          "supported_formats": ["CSV", "JSON", "Parquet"],
          "suggestion": "Convert file to CSV, JSON, or Parquet format before uploading."
        }
      }
    }
    ```
- **File too large for inference**:
  - If file exceeds maximum size for schema inference (configurable, default: 10 GB):
    - Returns error code `FILE_TOO_LARGE_FOR_INFERENCE`
    - Error response includes `max_inference_size_bytes` in `error.details`
    - **Workaround**: Users can provide schema manually via `POST /assets/{id}/datasets` with `schema_json` parameter
- **Timeout errors**:
  - If schema inference exceeds timeout (configurable, default: 60 seconds):
    - Returns error code `SCHEMA_INFERENCE_TIMEOUT`
    - Error response includes `timeout_seconds` in `error.details`
    - Users can retry with a smaller file or provide schema manually

**Performance Targets**

- **Small files** (< 10 MB): Schema inference should complete in < 5 seconds.
- **Medium files** (10-100 MB): Schema inference should complete in < 30 seconds.
- **Large files** (> 100 MB): Schema inference uses sampling and should complete in < 60 seconds.

**Sample Data Extraction**

- **Sample size**: First **100 rows** are extracted and stored (configurable via `SAMPLE_DATA_SIZE`, default: 100).
- **Storage location**: Sample data is stored as a separate file in object storage:
  - Path: `{tenant_id}/sample/{file_id}.json`
  - Format: JSON array of objects (one object per row).
  - Reference stored in `datasets.sample_reference` as:

#### 11.1.3.1 Sample Data Extraction Format Specification

**Complete JSON Schema for Sample Data**

Sample data is stored as a JSON array where each element represents one row from the source file:

```json
{
  "sample_data": [
    {
      "order_id": "ORD-001",
      "customer_id": "CUST-123",
      "order_date": "2025-01-15",
      "amount": 99.99,
      "status": "completed"
    },
    {
      "order_id": "ORD-002",
      "customer_id": "CUST-456",
      "order_date": "2025-01-16",
      "amount": 150.50,
      "status": "pending"
    }
  ],
  "metadata": {
    "sample_size": 100,
    "total_rows": 100000,
    "extracted_at": "2025-01-15T10:30:00Z",
    "file_id": "uuid",
    "format": "CSV",
    "columns": ["order_id", "customer_id", "order_date", "amount", "status"]
  }
}
```

**Format Details**

- **Array structure**: Root element is a JSON object with two keys:
  - `sample_data`: Array of row objects (max 100 rows by default)
  - `metadata`: Object containing extraction metadata
- **Row objects**: Each row is represented as a JSON object:
  - Keys are column names (from CSV headers or inferred from data)
  - Values are JSON-typed (string, number, boolean, null, array, object)
  - Type conversion follows schema inference rules (see §11.1.3)
- **Nested data handling**:
  - For JSON/Parquet files with nested structures:
    - Nested objects are flattened with dot notation (e.g., `user.name`, `user.address.city`)
    - Arrays are preserved as JSON arrays
    - Example:
      ```json
      {
        "order_id": "ORD-001",
        "customer.name": "John Doe",
        "customer.address.city": "New York",
        "items": [{"product_id": "PROD-1", "quantity": 2}]
      }
      ```
- **Null handling**:
  - Null values are represented as `null` in JSON
  - Empty strings are represented as `""` (empty string)
  - Missing columns (for sparse data) are omitted from the row object

**Metadata Fields**

| Field | Type | Description |
|-------|------|-------------|
| `sample_size` | integer | Number of rows in sample (actual, may be less than requested if file has fewer rows) |
| `total_rows` | integer (nullable) | Total rows in file (if known, null if not computed) |
| `extracted_at` | timestamp (ISO 8601) | When sample was extracted |
| `file_id` | UUID | ID of the source file |
| `format` | string | Source file format: `CSV`, `JSON`, `Parquet` |
| `columns` | array of strings | List of column names in order |

**Storage and Access**

- **Object storage path**: `{tenant_id}/sample/{file_id}.json`
- **Access**: Sample data is accessible via:
  - `GET /datasets/{id}` response includes `sample_json` field (if available)
  - Direct object storage access (for internal services)
- **TTL**: Sample data is retained for the same period as the dataset (subject to retention policies)
- **Size limits**: Sample files are limited to 1 MB (if exceeded, sample is truncated to fit)

**Error Handling**

- **If extraction fails**:
  - `sample_reference` is set to `null`
  - `sample_json` field in API responses is `null`
  - Error is logged but does not block dataset creation
- **If file has fewer rows than sample size**:
  - All available rows are included in sample
  - `metadata.sample_size` reflects actual number of rows extracted

**Reference stored in `datasets.sample_reference` as**:
    ```json
    {
      "storage_path": "idh-prod-files/{tenant_id}/sample/{file_id}.json",
      "row_count": 100,
      "format": "json_array"
    }
    ```
- **Extraction timing**: Sample is extracted **during schema inference** (same job/process).
- **Use cases**: Sample data is used for:
  - UI preview in catalog
  - Contract editing (pre-filling field examples)
  - Data quality checks (sample validation)

- **Large-file error handling**
  - The platform MUST define and use explicit error codes related to large files:
    - `UPLOAD_FILE_TOO_LARGE`, `UPLOAD_TIMEOUT`
    - `DQ_INPUT_TOO_LARGE`, `DQ_TIMEOUT`
    - `COMPLIANCE_INPUT_TOO_LARGE`, `COMPLIANCE_TIMEOUT`
  - These codes MUST:
    - Be returned in API responses.
    - Be translated into user-friendly messages in the UI.
    - Be stored in `AuditEvent.details_json` for diagnostics.



### 11.2 Availability & SLAs (Targets)

- As a commercial product, the platform SHOULD aim for:
  - Core API (contracts, catalog, access):
    - Target availability: **≥ 99.5%** monthly.
  - DQ/Compliance services:
    - Target availability: **≥ 99%** monthly.
  - These are initial targets and may be refined into formal SLAs as the product matures.

- In case of degradation:
  - Critical gating services (compliance at intake) SHOULD fail closed (block storage).
  - Non-critical services (semantic mapping, search enhancements) MAY degrade gracefully.

### 11.3 Batch-Oriented MVP

- Initial implementation focuses on **batch ingestion** via files.
- Real-time/streaming integration is out of scope for the MVP, but the design SHOULD avoid blocking future streaming extensions.

### 11.4 Billing Measurement & Transparency

- For each **billable operation** (e.g. DQ run, Compliance run, paid dataset access, API usage), the platform MUST collect:
  - Operation type.
  - Tenant and user.
  - Relevant size metrics (e.g. number of rows, estimated bytes processed).
  - Runtime duration and engine type.
- The billing subsystem MUST be able to:
  - Associate these metrics with a **billable unit** (operation).
  - Link each billable unit to:
    - The corresponding job (see §13).
    - The relevant audit entry (see §4).
- Actual pricing formulas (e.g. cost + 250% margin) are business configuration and out of scope here, but the data to support such a model MUST be available.

---

## 12. Security & Privacy Requirements

### 12.1 Authentication & Authorization

- All APIs MUST be authenticated (e.g. via tokens, API keys, or OAuth2).
- Access MUST be controlled at tenant and user-role level:
  - Tenant isolation for assets and logs.
  - Role-based permissions (admin, provider, consumer, auditor, etc.) as described in §9.6.

### 12.2 Encryption

- **In transit**:
  - All client-to-server and inter-service communication MUST use TLS (HTTPS).
- **At rest**:
  - All data files stored in the platform (including temporary storage) MUST be encrypted at rest (e.g. via cloud provider mechanisms).
  - Databases and triple stores MUST use storage-level encryption.

### 12.3 Data Residency & Region Separation

- The platform MUST support deployment in multiple regions/jurisdictions.
- Tenant-level configuration SHOULD support:
  - Assigning tenants to regions.
  - Ensuring their data (contracts, datasets, logs) remains in that region, subject to cross-border policies.
- Cross-region replication, if any, MUST respect regulatory constraints.

### 12.4 Logging & PII

- As noted in §4.2:
  - Logs MUST NOT contain raw PII or sensitive content from data files.
  - Only metrics and non-reversible hashes are allowed.
- Any violation of this rule MUST trigger a security incident procedure, including redaction and additional audit logging.

### 12.5 Principle of Least Privilege

- Services and users MUST operate with the minimum privileges necessary.
- Internal services (DQ, compliance, ontology, CLI) SHOULD have:
  - Separate identities/credentials.
  - Restricted access only to the data/resources they need.

### 12.6 Data Lifecycle

- For ingested assets:
  - When an asset is deleted:
    - Data files may be removed from main storage according to retention policies.
    - Audit logs remain for at least 3 years.
- For scan-only external jobs:
  - Raw data MUST be deleted as soon as the scan completes (see §3.4).
  - Only reports and hashes remain.

### 12.7 Rate Limiting & Abuse Protection

- The platform SHOULD implement **rate limiting** and quotas:
  - Per API key / user / tenant.
  - Especially on DQ and Compliance endpoints to prevent abuse and uncontrolled costs.
- The platform SHOULD support:
  - Per-tenant or per-plan limits (e.g. max number of checks per day/month).
  - Clear error responses when limits are exceeded.

---

## 13. Error Handling & User Messaging

This section defines **standard error responses**, **error code taxonomy**, and basic rules for **user-facing messages**.

Goals:

- Consistent behavior across all `/api/v1` endpoints.
- Clear separation between:
  - Programmatic error codes (for SDKs/integrations).
  - Human-readable messages (for UI).
- No leakage of sensitive internal details or PII.

### 13.1 Error Response Envelope (API)

All non-2xx responses from `/api/v1` MUST follow a standard JSON envelope:

```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "The data contract is not valid.",
    "http_status": 400,
    "details": {
      "field_errors": [
        {
          "path": "$.schema.fields[0].name",
          "message": "Name is required."
        }
      ]
    },
    "request_id": "abc123",
    "timestamp": "2025-01-01T12:34:56Z"
  }
}
```

Required fields:

- `error.code`  
  - Machine-readable string, stable and documented (see §13.2).
- `error.message`  
  - Short human-readable message in English (MVP).
  - Safe to show directly in UI (no stack traces, no secrets).
- `error.http_status`  
  - Mirrors the HTTP status code (400, 401, etc.).
- `error.request_id`  
  - Unique ID for this request; used to correlate with logs.
- `error.timestamp`  
  - UTC timestamp.

Optional fields:

- `error.details`  
  - Structured JSON, may include:
    - Validation errors (list of field/path + message).
    - Limits (max file size, etc.).
    - Engine-specific info (GX/Soda/CLI) in sanitized form.
  - MUST NOT contain raw PII (emails, IDs, card numbers, etc.).

### 13.2 Error Code Taxonomy

Error codes MUST follow a consistent naming convention:

- Uppercase with underscores.
- Prefixed by functional area, e.g.:
  - `AUTH_`, `TENANT_`, `VALIDATION_`, `FILE_`, `DQ_`, `COMPLIANCE_`, `JOB_`, `MARKETPLACE_`, `SEMANTIC_`, `SYSTEM_`.

#### 13.2.1 Core error codes (MVP set)

Baseline list for MVP (can be extended, but semantics of existing codes SHOULD NOT change):

**Auth & Tenant**

- `AUTH_UNAUTHORIZED`  
  - HTTP 401  
  - No valid auth token or token expired.

- `AUTH_FORBIDDEN`  
  - HTTP 403  
  - Token valid but user/role cannot perform this action.

- `REFRESH_TOKEN_INVALID`  
  - HTTP 400  
  - Invalid refresh token format.

- `REFRESH_TOKEN_EXPIRED`  
  - HTTP 401  
  - Refresh token has expired.

- `REFRESH_TOKEN_REVOKED`  
  - HTTP 401  
  - Refresh token has been revoked.

- `TENANT_NOT_FOUND`  
  - HTTP 404  
  - Tenant referenced in token or resource does not exist.

- `TENANT_ACCESS_DENIED`  
  - HTTP 403/404  
  - Attempt to access resource belonging to another tenant.

- `TENANT_NOT_VERIFIED`  
  - HTTP 403  
  - Tenant `kyc_status` is not `VERIFIED` (required for marketplace publishing).

- `USER_ALREADY_EXISTS`  
  - HTTP 409  
  - User with this email already exists in the tenant.

- `USER_NOT_FOUND`  
  - HTTP 404  
  - User with given ID does not exist or is not in the current tenant.

- `USER_HAS_RESOURCES`  
  - HTTP 409  
  - User cannot be hard-deleted because they have associated resources (assets, contracts, etc.).

- `USER_ALREADY_ACTIVE`  
  - HTTP 400  
  - User is already `ACTIVE`; invitation not needed.

- `API_KEY_NOT_FOUND`  
  - HTTP 404  
  - API key with given ID does not exist or is not visible to tenant.

**Validation & Contracts**

- `VALIDATION_ERROR`  
  - HTTP 400  
  - Generic input validation error (missing/invalid parameters, bad payload).

- `CONTRACT_VALIDATION_FAILED`  
  - HTTP 400  
  - DataContract CLI validation (lint/validate) failed; contract is invalid.

- `CONTRACT_CLI_ERROR`  
  - HTTP 502/500  
  - CLI crashed, timed out, or returned unexpected output (technical failure, not user fault).

- `CONTRACT_NORMALIZATION_FAILED`  
  - HTTP 400  
  - Contract is valid but normalization to HubContract failed (mapping error).

- `UNSUPPORTED_SPEC_VERSION`  
  - HTTP 422  
  - `original_spec_version` is not supported for the given `original_spec_type`.

- `INVALID_SPEC_FORMAT`  
  - HTTP 422  
  - `original_format` does not match the actual content (e.g., JSON format but content is YAML).

- `UNSUPPORTED_FILE_FORMAT`  
  - HTTP 400  
  - File format is not supported (must be CSV, JSON, or Parquet).

**Files & Intake**

- `FILE_TOO_LARGE`  
  - HTTP 413  
  - File exceeds configured max size for this endpoint/upload mode.

- `FILE_UNSUPPORTED_TYPE`  
  - HTTP 400  
  - File type/extension not supported.

- `FILE_CONTENT_TYPE_MISMATCH`  
  - HTTP 400  
  - Declared `content_type` does not match actual file content (strict validation mode). Response includes `declared_content_type` and `detected_content_type` in `error.details`.

- `FILE_UPLOAD_INCOMPLETE`  
  - HTTP 400  
  - Client reported completion but underlying storage shows an incomplete or corrupted upload.

- `SCHEMA_INFERENCE_FAILED`  
  - HTTP 400  
  - Schema inference failed due to file parsing errors (malformed CSV, invalid JSON, corrupted Parquet). Response includes `error_type`, `error_message`, `line_number`, and `suggestion` in `error.details`.

- `SCHEMA_INFERENCE_TIMEOUT`  
  - HTTP 400  
  - Schema inference exceeded timeout limit. Response includes `timeout_seconds` in `error.details`. Users can retry with smaller file or provide schema manually.

- `FILE_TOO_LARGE_FOR_INFERENCE`  
  - HTTP 400  
  - File exceeds maximum size for schema inference. Response includes `max_inference_size_bytes` in `error.details`. Users can provide schema manually.

- `FILE_NOT_FOUND`  
  - HTTP 404  
  - File ID does not exist or has been deleted.

- `UPLOAD_SESSION_EXPIRED`  
  - HTTP 410  
  - Chunked upload session expired (24-hour TTL exceeded). Client must start a new upload session.

- `UPLOAD_NOT_CHUNKED`  
  - HTTP 400  
  - Chunk-related operation attempted on a SIMPLE upload (not CHUNKED mode).

- `UPLOAD_FAILED`  
  - HTTP 410  
  - Upload failed before completion (network error, storage error, etc.). Partial objects are cleaned up after 24 hours.

- `UPLOAD_INCOMPLETE`  
  - HTTP 409  
  - Missing chunks for CHUNKED upload (not all chunks uploaded before finalization).

- `CHUNK_CHECKSUM_MISMATCH`  
  - HTTP 409  
  - Chunk checksum validation failed (re-upload of same chunk_number with different content).

- `FILE_CHECKSUM_MISMATCH`  
  - HTTP 409  
  - Full-file checksum mismatch during finalization (provided checksum does not match computed value).

- `FILE_DELETED`  
  - HTTP 410  
  - File has been deleted (`files.status = DELETED`).

- `RANGE_NOT_SATISFIABLE`  
  - HTTP 416  
  - Range request is invalid (e.g., start > file size).

**DQ (Data Quality)**

- `DQ_INPUT_TOO_LARGE`  
  - HTTP 400/413  
  - Dataset too large for configured DQ profile (e.g. full scan not allowed).

- `DQ_TIMEOUT`  
  - HTTP 504  
  - DQ job exceeded configured time limit.

- `DQ_ENGINE_ERROR`  
  - HTTP 502/500  
  - Great Expectations or Soda execution crashed / unexpected failure.

**Compliance**

- `COMPLIANCE_INPUT_TOO_LARGE`  
  - HTTP 400/413  
  - Dataset too large for configured compliance scan limits.

- `COMPLIANCE_TIMEOUT`  
  - HTTP 504  
  - Compliance job exceeded configured time limit.

- `COMPLIANCE_ENGINE_ERROR`  
  - HTTP 502/500  
  - Compliance engine crashed / unexpected failure.

- `COMPLIANCE_BLOCKED`  
  - HTTP 409  
  - Compliance run completed and determined `allowed_to_store = false`.  
  - Intake is blocked to protect platform and tenant.

**Jobs & Async Operations**

- `JOB_NOT_FOUND`  
  - HTTP 404  
  - No Job with this ID.

- `JOB_ALREADY_COMPLETED`  
  - HTTP 409  
  - Trying to cancel or re-run a job that is already in a terminal state.

- `JOB_TIMEOUT`  
  - HTTP 504  
  - Job exceeded configured time limit (`timeout_seconds`). Applies even if cancellation was requested; timeout takes precedence.

- `JOB_CANCELLED`  
  - HTTP 200/202 (job status is `CANCELLED`)  
  - Job was successfully cancelled. This is not an error code but a status indicator in job responses.

**Marketplace / Entitlements**

- `LISTING_NOT_FOUND`  
  - HTTP 404  
  - No listing with this ID / not visible to caller.

- `ENTITLEMENT_NOT_FOUND`  
  - HTTP 404  
  - Caller has no entitlement for requested asset.

- `ENTITLEMENT_NOT_ACTIVE`  
  - HTTP 403  
  - Entitlement exists but is not `ACTIVE` (e.g. `REVOKED`, `EXPIRED`).

- `ENTITLEMENT_REQUIRED`  
  - HTTP 403  
  - Cross-tenant access requires an active entitlement (no entitlement exists).

- `ENTITLEMENT_EXPIRED`  
  - HTTP 403  
  - Entitlement exists but has expired (`expires_at < NOW()`).

- `ENTITLEMENT_REVOKED`  
  - HTTP 403  
  - Entitlement exists but has been revoked (`status = REVOKED`).

- `ORDER_NOT_FOUND`  
  - HTTP 404  
  - Order with given ID does not exist or is not visible to tenant.

- `ORDER_ALREADY_PROCESSED`  
  - HTTP 409  
  - Order is already `APPROVED` or `REJECTED` (cannot change status).

- `ASSET_NOT_ACTIVE`  
  - HTTP 400  
  - Asset is not `ACTIVE` (required for listing creation or asset activation).

- `ASSET_PUBLICATION_BLOCKED`  
  - HTTP 400  
  - Asset cannot be published to marketplace (missing requirements: listing, KYC verification).

- `ASSET_RETIRED`  
  - HTTP 400  
  - Asset is `RETIRED` and cannot be reactivated.

- `ASSET_DELETED`  
  - HTTP 410  
  - Asset has been deleted; operation cannot be performed.

- `ASSET_HAS_LISTINGS`  
  - HTTP 409  
  - Asset has active marketplace listings and cannot be deleted (use `force = true` to delete anyway).

- `ASSET_HAS_ENTITLEMENTS`  
  - HTTP 409  
  - Asset has active entitlements and cannot be deleted (use `force = true` to delete anyway).

- `LISTING_ALREADY_PUBLISHED`  
  - HTTP 409  
  - Cannot revert `PUBLISHED` listing to `DRAFT`.

- `TENANT_NOT_VERIFIED`  
  - HTTP 403  
  - Tenant `kyc_status` is not `VERIFIED` (required for marketplace publishing).

- `CONTRACT_IN_USE`  
  - HTTP 409  
  - Contract is referenced by assets and cannot be deleted (use `force = true` to delete anyway).

- `FILE_IN_USE`  
  - HTTP 409  
  - File is attached to a dataset and cannot be deleted (use `force = true` to delete anyway).

- `ENTITLEMENT_REACTIVATED`  
  - HTTP 200  
  - Entitlement was successfully reactivated (audit event type, not an error code).

- `AUTH_LOGOUT`  
  - HTTP 200  
  - User logged out successfully (audit event type, not an error code).

- `AUTH_LOGOUT_ALL_SESSIONS`  
  - HTTP 200  
  - All user sessions logged out successfully (audit event type, not an error code).

**SPARQL-specific errors**

- `SPARQL_PARSE_ERROR`  
  - HTTP 400  
  - SPARQL query syntax error.

- `SPARQL_QUERY_INVALID`  
  - HTTP 400  
  - Query contains unsupported operations (e.g., `INSERT`, `DELETE`).

- `SPARQL_QUERY_TOO_LARGE`  
  - HTTP 400  
  - Query string exceeds maximum length (default: 10,000 characters).

- `SPARQL_QUERY_TIMEOUT`  
  - HTTP 504  
  - Query exceeded timeout limit (30 seconds).

- `SPARQL_RESULT_TOO_LARGE`  
  - HTTP 413  
  - Query result exceeds maximum size (10,000 results).

**Rate limiting & system**

- `RATE_LIMIT_EXCEEDED`  
  - HTTP 429  
  - Tenant or user exceeded allowed request or job rate.

- `SYSTEM_UNAVAILABLE`  
  - HTTP 503  
  - Temporary outage or maintenance.

- `INTERNAL_ERROR`  
  - HTTP 500  
  - Generic unexpected server-side error (fallback).

**GraphQL-specific errors**

- `GRAPHQL_PARSE_ERROR`  
  - HTTP 400  
  - GraphQL query/mutation syntax error.

- `GRAPHQL_VALIDATION_ERROR`  
  - HTTP 400  
  - GraphQL query/mutation validation error (e.g., unknown field, type mismatch).

- `GRAPHQL_EXECUTION_ERROR`  
  - HTTP 200 (with `errors` array in response)  
  - GraphQL execution error (resolver failure, authorization denied). Response includes standard GraphQL error format.

### 13.3 Mapping HTTP Status → Error Codes

High-level mapping:

- **400** – client input issues:
  - `VALIDATION_ERROR`, `CONTRACT_VALIDATION_FAILED`, `FILE_UNSUPPORTED_TYPE`, `FILE_TOO_LARGE`, `DQ_INPUT_TOO_LARGE`, `COMPLIANCE_INPUT_TOO_LARGE`, etc.

- **401** – auth required:
  - `AUTH_UNAUTHORIZED`.

- **403** – forbidden:
  - `AUTH_FORBIDDEN`, `TENANT_ACCESS_DENIED`, `ENTITLEMENT_NOT_ACTIVE`.

- **404** – resource not found:
  - `TENANT_NOT_FOUND`, `FILE_NOT_FOUND`, `JOB_NOT_FOUND`, `LISTING_NOT_FOUND`, `ENTITLEMENT_NOT_FOUND`.

- **409** – conflict with current state:
  - `COMPLIANCE_BLOCKED`, `JOB_ALREADY_COMPLETED`.

- **413** – payload too large:
  - `FILE_TOO_LARGE`, `DQ_INPUT_TOO_LARGE`, `COMPLIANCE_INPUT_TOO_LARGE`.

- **429** – too many requests:
  - `RATE_LIMIT_EXCEEDED`.

- **500** – internal errors:
  - `INTERNAL_ERROR`, `DQ_ENGINE_ERROR`, `COMPLIANCE_ENGINE_ERROR`, `CONTRACT_CLI_ERROR`.

- **502/503/504** – upstream/system/timeouts:
  - `SYSTEM_UNAVAILABLE`, `DQ_TIMEOUT`, `COMPLIANCE_TIMEOUT`.

### 13.4 User-Facing Messaging Guidelines

User-facing messages (especially in the web UI) MUST follow these rules:

1. **No internal details**
   - Do NOT show:
     - Stack traces.
     - Internal hostnames, file paths, or container IDs.
     - Raw CLI/DQ/Compliance engine logs.
   - These may appear in internal logs but not in `error.message`.

2. **No raw PII**
   - Error messages MUST NOT include:
     - Actual email addresses, card numbers, national IDs, etc.
   - When referencing data, use:
     - Column names and categories.
     - Example: “Column `credit_card_number` contains values classified as payment card data.”

3. **Clear, actionable language**
   - Use short, direct sentences.
   - Whenever possible, suggest a next step:
     - “Please upload a smaller file under 1GB.”
     - “Please correct the highlighted fields in your contract and try again.”
     - “Ask your tenant admin to grant you access.”

4. **Consistency**
   - Same error code → same style of message.
   - Maintain a **central registry** (docs or config) mapping `error.code` → default UI message.

5. **Localization-ready**
   - MVP can use English only, but messages MUST be structured to allow localization later:
     - Avoid hard-coding long paragraphs in code.
     - Use message keys in the UI where possible.

### 13.5 Logging & Correlation

- Every error response MUST include `request_id`, and this `request_id` MUST appear in:
  - Application logs.
  - Audit events (where applicable).

- Logs MAY contain more technical details than the API response but:
  - MUST still respect “no raw PII in logs” policy.
  - MUST NOT store raw payloads for data files or samples.

### 13.6 Documentation & SDK Behavior

- Public API documentation MUST:
  - List all standard `error.code` values and their meaning.
  - Provide example error responses for common scenarios (validation failure, compliance block, rate limit, etc.).

- SDKs SHOULD:
  - Provide typed exceptions or error classes mapping `error.code` to domain-specific errors, e.g.:
    - `ContractValidationError`, `ComplianceBlockedError`, `RateLimitExceededError`, etc.
  - Expose:
    - `error.code`
    - `error.message`
    - `error.details`
    - `request_id`
  - Encourage users to show only safe, concise messages to end-users.

---

## 14. Job / Run Model

### 14.1 Job Entity

Each long-running operation (e.g. DQ run, Compliance run, contract validation, semantic mapping) MUST create a `Job` record with at least:

- `job_id` (UUID).
- `type`: e.g. `QUALITY_CHECK`, `COMPLIANCE_CHECK`, `CONTRACT_VALIDATION`, `SEMANTIC_MAPPING`.
- `status`: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.
- `tenant_id`.
- `user_id` (nullable for system-triggered jobs).
- `resource_type` (`CONTRACT`, `DATA_FILE`, `ASSET`, etc.).
- `resource_id`.
- `created_at`, `started_at`, `finished_at`.
- `details_json`:
  - Engine names/versions.
  - Progress and any error messages.

### 14.2 Job APIs

- The platform MUST provide APIs to:
  - Create and schedule jobs internally.
  - Fetch job status: `GET /jobs/{job_id}`.
  - List jobs by tenant, resource, or type.
- The UI/SDK MUST:
  - Use `job_id` to poll for status for long-running operations.
  - Show progress and completion or failure.

### 14.3 Relation to Audit & Billing

- Every job that is billable or security-relevant MUST:
  - Create or link to an appropriate **audit log entry** (§4).
  - Expose metrics needed for **billing** (§11.4).

### 14.4 Job Completion Notification & Polling Behavior

Long-running operations (DQ runs, compliance runs, large file intake, semantic mapping, etc.) are executed as **Jobs** and are observed by clients via **polling** in the MVP. The design MUST also anticipate webhooks and other push mechanisms as future enhancements.

#### 14.4.1 MVP: Polling Pattern

- For the MVP, **polling is the only supported completion notification mechanism**:
  - Clients (UI, SDK, external integrations) call:
    - `GET /jobs/{job_id}` to obtain status and progress.
    - Optionally `GET /dq-runs/{id}`, `GET /compliance-runs/{id}` once `status = SUCCEEDED`.

- Clients MUST NOT poll excessively:
  - A client MUST NOT poll more frequently than **once per second per job**.
  - Recommended pattern for UI / SDK:
    - Start with a short interval (e.g. 1–2 seconds).
    - Apply **exponential backoff** up to a max interval (e.g. 10–15 seconds).
    - Example:
      - Attempts 1–5: every 2 seconds.
      - Attempts 6–10: every 5 seconds.
      - Attempts 11+: every 10–15 seconds.

- Clients SHOULD stop polling when:
  - `job.status` is in a terminal state: `SUCCEEDED`, `FAILED`, or `CANCELLED`.
  - Or when a **client-side timeout** is reached (e.g. 30 minutes for heavy jobs, or the job’s documented SLA).

- The job resource SHOULD include:
  - `status` (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`).
  - `percent_complete` (0–100, optional but recommended).
  - `estimated_remaining_seconds` (optional; may be approximate).
  - `last_updated_at` timestamp.

#### 14.4.2 Expected Durations by Job Type (Guidance)

The platform MUST document **expected duration ranges** for key job types. These are **targets / SLOs**, not hard guarantees, and may vary with data size and infrastructure.

Indicative expectations (MVP):

- `CONTRACT_VALIDATION`
  - Typical: < 5 seconds.
  - Upper bound (large or complex contracts): < 30 seconds.

- `QUALITY_CHECK` (DQ run)
  - Small/medium file (e.g. up to ~1GB or a few million rows):
    - Typical: 30 seconds – 5 minutes.
  - Large file (full scan) or heavy profile:
    - Up to the configured job timeout (e.g. 15–30 minutes).
  - If sampling is used for very large files:
    - SHOULD complete significantly faster than full scan on the entire file.

- `COMPLIANCE_CHECK`
  - Similar to DQ:
    - Small/medium files: typically 30 seconds – a few minutes.
    - Large files: up to job timeout.
  - Scan-only mode may prioritize sampling and thus complete faster.

- `SEMANTIC_MAPPING`
  - Typically fast:
    - Most mapping jobs SHOULD complete in < 10 seconds for a single asset.
    - Bulk rebuild operations (future) may be treated as separate batch jobs.

These expectations MUST be reflected in:
- Developer documentation.
- UI copy where appropriate (e.g. “This may take a few minutes for large files”).

Job timeouts defined in §11.1 (Performance & Scalability) MUST be consistent with these expectations.

#### 14.4.3 Future: Webhooks & Push Notifications (Non-MVP)

To avoid inefficient polling for some clients, the system design MUST anticipate **webhook / push-based notifications** for job completion, even if not implemented in the MVP.

- Webhook concept (future):
  - Clients may register a **callback URL** when creating a job or triggering an operation.
  - When the job reaches a terminal state:
    - The hub posts a signed notification to the callback URL with:
      - `job_id`
      - `final_status`
      - Basic metadata (e.g., type, resource_id).
  - Webhook delivery MUST be:
    - Authenticated (e.g. HMAC signature or shared secret).
    - Retried with backoff on failures (at least a few attempts).

- Other push mechanisms (future):
  - Server-Sent Events (SSE) or WebSocket channels for live updates.
  - In-app notifications for the web UI.

For MVP:

- Webhooks and SSE/WebSockets are **out of scope**.
- The API and job model MUST be designed so that **adding webhooks later does not require breaking changes**:
  - Jobs already have stable IDs and resource references.
  - Job status and metadata are sufficient for a webhook payload.

---

## 15. MVP Scope vs Future Phases

### 15.1 In Scope for MVP v1

- Multi-tenant architecture with basic roles:
  - Tenant Admin, Data Provider, Data Consumer (Auditor may be limited initially).
- Batch file ingestion via:
  - Web UI (up to 1–2 GB).
  - CLI/SDK (larger files supported where infra allows).
- Data asset registration flows:
  - Data-first, Contract-first, Contract-only.
- DataContract CLI integration for:
  - Linting and validation.
- Data Quality & Compliance:
  - At intake (mandatory gate for data storage).
  - External scan-only mode (no storage).
- Canonical HubContract model and basic semantic mapping:
  - JSON-LD representations.
  - Minimal SPARQL endpoint.
- Basic marketplace:
  - Publishing/unpublishing assets as public/internal.
  - Simple entitlements and “request access” workflows without billing.

### 15.2 Future Phases (Out of MVP Scope)

- Advanced marketplace features:
  - Complex pricing rules, promotions, revenue sharing UI, etc.
- Scheduled DQ/Compliance checks.
- Streaming ingestion and real-time contracts.
- Full-blown semantic UI for SPARQL queries and graph exploration.
- Advanced multi-region data residency features.
- Detailed KYC workflows and integrations.
- Full billing/payment provider integration.

### 15.3 Status enum values

To standardize status handling across services and documents, the following canonical enum values MUST be used for MVP:

| Entity / Field                      | Enum values (MVP)                                   | Default | Document References |
|-------------------------------------|-----------------------------------------------------|--------|---------------------|
| `tenants.status`                    | ACTIVE, SUSPENDED, DELETED                          | ACTIVE | `Database_Schema.md` §3.1.1, `Technical_Design_Document.md` §2.2.1 |
| `users.status`                      | ACTIVE, INVITED, DISABLED                           | INVITED | `Database_Schema.md` §3.1.2, `Technical_Design_Document.md` §2.2.2 |
| `assets.status`                     | DRAFT, ACTIVE, PUBLIC, RETIRED                      | DRAFT | `Database_Schema.md` §3.2.1, `API_Spec_v1.md` §2.2, `Technical_Design_Document.md` §2.2.4 |
| `assets.visibility`                 | INTERNAL, PUBLIC                                    | INTERNAL | `Database_Schema.md` §3.2.1, `Technical_Design_Document.md` §2.2.4 |
| `assets.dq_status`                  | UNKNOWN, PASS, WARN, FAIL                            | UNKNOWN | `Database_Schema.md` §3.2.1, `Technical_Design_Document.md` §2.2.4 |
| `assets.compliance_status`          | UNKNOWN, PASS, WARN, FAIL                           | UNKNOWN | `Database_Schema.md` §3.2.1, `Technical_Design_Document.md` §2.2.4 |
| `files.status`                      | UPLOADING, READY, FAILED, DELETED                   | UPLOADING | `Database_Schema.md` §3.2.3, `Technical_Design_Document.md` §2.2.7 |
| `contracts.status`                  | DRAFT, VALID, INVALID, WARNING_ONLY                 | DRAFT | `Database_Schema.md` §3.2.4, `API_Spec_v1.md` §2.1, `Technical_Design_Document.md` §2.2.5 |
| `contracts.validation_status`       | VALID, INVALID, WARNING_ONLY, ERROR, null           | null | `Database_Schema.md` §3.2.4, `API_Spec_v1.md` §2.1 |
| `dq_runs.status`                    | PENDING, RUNNING, SUCCEEDED, FAILED                 | PENDING | `Database_Schema.md` §3.3.1, `API_Spec_v1.md` §2.4, `Technical_Design_Document.md` §2.2.8 |
| `compliance_runs.status`            | PENDING, RUNNING, SUCCEEDED, FAILED                 | PENDING | `Database_Schema.md` §3.3.2, `API_Spec_v1.md` §2.5, `Technical_Design_Document.md` §2.2.9 |
| `jobs.status`                       | PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED      | PENDING | `Database_Schema.md` §3.4.1, `API_Spec_v1.md` §2.6, `Technical_Design_Document.md` §2.2.10, `System_Architecture.md` §2.4 |
| `listings.status`                   | DRAFT, PUBLISHED, UNPUBLISHED                       | DRAFT | `Database_Schema.md` §3.5.1, `API_Spec_v1.md` §2.8 |
| `orders.status`                     | REQUESTED, APPROVED, REJECTED, CANCELLED            | REQUESTED | `Database_Schema.md` §3.5.2, `API_Spec_v1.md` §2.9 |
| `entitlements.status`               | ACTIVE, EXPIRED, REVOKED                            | ACTIVE | `Database_Schema.md` §3.5.3, `API_Spec_v1.md` §2.9 |
| `semantic_resources.status`         | ACTIVE, DEGRADED, STALE                             | ACTIVE | `Database_Schema.md` §3.6.1 |

**Canonical Asset States**

- **DRAFT** – Asset under creation, not fully validated or published.  
- **ACTIVE** – Validated and available within the provider tenant catalog.  
- **PUBLIC** – Published and discoverable on the marketplace.  
- **RETIRED** – No longer offered; kept only for lineage and audit.

**Cross-Reference Validation**

All related documents (Domain Model, System Architecture, API Spec, TDD, Database Schema, UX flows) MUST align to these values. When updating status enums:

1. Update this canonical table first.
2. Update all document references listed in the "Document References" column.
3. Update database migration scripts if enum values change.
4. Update API response examples and SDK type definitions.

Any discrepancies between documents MUST be resolved by aligning to this canonical table.

---

## 16. Glossary

To avoid ambiguity, this glossary defines key terms used in this document:

- **Tenant**  
  An organization or company space in the platform. Each tenant has its own users, catalogs, configurations, and billing.

- **User**  
  An individual account belonging to a tenant (or acting as its own tenant, for individuals).

- **Asset**  
  A logical unit registered in the hub containing:
  - A data contract.
  - Optionally, a dataset (data files or references).
  - Associated metadata (quality, compliance, pricing, etc.).

- **Dataset**  
  The actual data associated with an asset:
  - Could be one or more files (CSV, Parquet, etc.) or references to tables/objects.

- **Contract**  
  The data contract describing a dataset, conforming to ODCS v3.0.2+ specs, and represented internally as a `HubContract`.

- **HubContract**  
  The canonical internal JSON representation of a data contract used by UI, APIs, and semantic mapping.

- **Data Quality (DQ) Check**  
  A run of quality rules on a dataset using Great Expectations/Soda, producing structured metrics and a status.

- **Compliance Check**  
  A run of detection and rule logic to assess regulatory risk and presence of PII/sensitive data in a dataset.

- **Job / Run**  
  A record representing the execution of a long-running operation:
  - DQ check, Compliance check, contract validation, semantic mapping, etc.

- **Audit Log**  
  Append-only records of security- and governance-relevant events (e.g. checks, uploads, validations, purchases).

- **Semantic Layer**  
  The RDF/ontology-based representation of contracts, datasets, quality/compliance artifacts, and marketplace concepts, exposed via URIs, JSON-LD, and SPARQL.

- **Marketplace**  
  The part of the hub where public assets can be discovered and requested (and in future versions, purchased or licensed) across tenants.

## 17. Monitoring & Observability

This section defines how the platform is monitored in production: **metrics**, **logging**, **tracing**, and **alerting**. It complements the audit logging (§4) and security (§12) requirements.

### 17.1 Goals & Scope

Monitoring & observability MUST:

- Provide enough visibility to:
  - Detect and diagnose incidents (performance, reliability, security-relevant behavior).
  - Understand usage patterns (per tenant, per feature).
  - Support capacity planning (DQ/compliance workloads, storage, marketplace usage).
- Respect all **security & privacy** constraints:
  - No raw PII in logs or metrics.
  - Tenant isolation for views and alerts where appropriate.

### 17.2 Metrics

The platform MUST expose **structured metrics** (e.g. Prometheus/OpenMetrics) for:

#### 17.2.1 API & HTTP

- Request rate (`requests_total`), latency (`request_duration_seconds`), and error rate:
  - Labels/tags at least:
    - `route` (coarse grouping, e.g. `/assets`, `/dq-runs`, `/compliance-runs`, `/contracts`, `/jobs`)
    - `method` (`GET`, `POST`, etc.)
    - `status_class` (`2xx`, `4xx`, `5xx`)
- Per-endpoint metrics for critical APIs:
  - `/files/init`, `/files/{id}/complete`
  - `/assets`, `/contracts`
  - `/dq-runs`, `/compliance-runs`
  - `/jobs/{id}`

> Tenant IDs MUST NOT be high-cardinality labels in global metrics; per-tenant views are handled via logs and aggregated metrics.

#### 17.2.2 Jobs & Background Processing

- Job-level metrics:
  - `jobs_started_total` / `jobs_completed_total` / `jobs_failed_total` by:
    - `job_type` (`QUALITY_CHECK`, `COMPLIANCE_CHECK`, `CONTRACT_VALIDATION`, `SEMANTIC_MAPPING`, etc.)
  - `job_duration_seconds` histogram by `job_type` and `status`.
- Queue/worker health:
  - Queue length / backlog per `job_type`.
  - Worker/process utilization and error rates.

#### 17.2.3 DQ & Compliance

- Per-job aggregates (for internal ops, not per-row):
  - Counts of DQ/compliance runs per tenant and per job type.
  - Failure rates (`DQ_ENGINE_ERROR`, `COMPLIANCE_ENGINE_ERROR`, timeouts, input-too-large).
- High-level quality/compliance posture (for ops dashboards):
  - Number of assets with latest DQ status = `FAIL` / `WARN` / `PASS`.
  - Number of assets with latest compliance status = `FAIL` / `WARN` / `PASS`.
- All metrics MUST be free of raw PII; they only refer to **counts, statuses, and categories**.

#### 17.2.4 Dependencies & Infrastructure

- Databases / triple store:
  - Connection pool usage.
  - Query latency and error rates.
- Object storage:
  - Upload failures and latency.
- DataContract CLI service:
  - Request rate, latency, error rate.
- DQ/Compliance engines:
  - Health checks and failure counts.

##### 17.2.5 Metrics retention & aggregation

   Time-series metrics MUST follow a tiered retention and aggregation model to balance cost and query performance:

   - **Raw metrics**
     - Definition: high-resolution series (per-instance / per-pod, 10–60s scrape/emit interval), including:
       - Service latency histograms and error rates.
       - Request/response throughput for key APIs.
       - Job queue depth and processing rates.
       - Resource utilization (CPU, memory) for core services.
     - Retention: **30 days**.
     - Purpose: detailed incident analysis, short-term performance tuning.

   - **Aggregated metrics**
     - All raw metrics MUST be downsampled into coarser intervals:
       - **1-minute aggregates** (avg / p95 / p99 where applicable) retained for **7 days**.
       - **5-minute aggregates** retained for **30 days**.
       - **1-hour aggregates** retained for **13 months**.
     - Aggregations MUST preserve at least:
       - Service / component.
       - Environment (prod / non-prod).
       - High-level dimension(s) critical for capacity planning (e.g. tenant tier, region).

   - **Long-term storage strategy**
     - After the raw retention window (30 days), troubleshooting MUST rely on aggregated metrics.
     - 1-hour aggregates MAY be exported to a cheaper, long-term store (e.g. object storage or an OLAP warehouse) for:
       - Trend analysis over ≥ 12 months.
       - Capacity planning and product analytics.
     - Long-term exported metrics MUST NOT contain sensitive identifiers beyond:
       - Service/component.
       - Environment.
       - Coarse-grained categories (e.g. plan/tier), where needed.

   - **Configuration & overrides**
     - The above values (30 days raw, 7/30 days for 1m/5m, 13 months for 1h) are **minimum requirements** for production.
     - Non-production environments MAY use shorter retention for cost savings.
     - Any changes to production retention MUST be documented and MUST not break:
       - Incident investigation requirements (at least 30 days of high-resolution data).
       - SLO/SLA reporting over quarterly periods (supported by hourly aggregates).

### 17.3 Logging

Logging MUST be **structured** (JSON logs) and respect "no raw PII" constraints.

**Implementation**: Python services use `structlog` with `django-structlog` for Django integration. See `Technology_Stack_Decisions.md` for version and configuration details.

#### 17.3.1 Log Structure

Each log entry SHOULD contain:

- `timestamp` (UTC).
- `level` (`DEBUG`, `INFO`, `WARN`, `ERROR`).
- `service` / `component`.
- `message`.
- `request_id` (correlates with API responses and traces).
- `tenant_id` (where applicable).
- `user_id` (or `system` for internal jobs).
- `route` / `operation` (for API logs).
- Optional:
  - `job_id`, `job_type`.
  - `asset_id`, `contract_id`, `dataset_id`.

Logs MUST NOT include:

- Raw data values from datasets (emails, card numbers, IDs, etc.).
- Full contract bodies (except at DEBUG in non-prod environments, under strict controls).

#### 17.3.1.1 Structured Log Format JSON Schema

All log entries MUST conform to the following JSON Schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["timestamp", "level", "service", "message"],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp (e.g., '2025-01-15T10:30:00.123Z')"
    },
    "level": {
      "type": "string",
      "enum": ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"],
      "description": "Log severity level"
    },
    "service": {
      "type": "string",
      "maxLength": 100,
      "description": "Service name (e.g., 'api-service', 'worker-service', 'dq-service')"
    },
    "component": {
      "type": "string",
      "maxLength": 100,
      "description": "Component/module name within service (optional)"
    },
    "message": {
      "type": "string",
      "maxLength": 10000,
      "description": "Human-readable log message"
    },
    "request_id": {
      "type": "string",
      "pattern": "^[a-zA-Z0-9_-]+$",
      "maxLength": 100,
      "description": "Request ID for correlating logs across services (optional, required for API logs)"
    },
    "trace_id": {
      "type": "string",
      "pattern": "^[a-f0-9]{32}$",
      "description": "Distributed trace ID (optional, hex-encoded 128-bit)"
    },
    "span_id": {
      "type": "string",
      "pattern": "^[a-f0-9]{16}$",
      "description": "Span ID within trace (optional, hex-encoded 64-bit)"
    },
    "tenant_id": {
      "type": "string",
      "format": "uuid",
      "description": "Tenant UUID (optional, required for tenant-scoped operations)"
    },
    "user_id": {
      "type": "string",
      "format": "uuid",
      "description": "User UUID (optional, use 'system' for internal jobs)"
    },
    "route": {
      "type": "string",
      "maxLength": 500,
      "description": "HTTP route/path (optional, for API logs)"
    },
    "method": {
      "type": "string",
      "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
      "description": "HTTP method (optional, for API logs)"
    },
    "status_code": {
      "type": "integer",
      "minimum": 100,
      "maximum": 599,
      "description": "HTTP status code (optional, for API logs)"
    },
    "latency_ms": {
      "type": "number",
      "minimum": 0,
      "description": "Request latency in milliseconds (optional, for API logs)"
    },
    "job_id": {
      "type": "string",
      "format": "uuid",
      "description": "Job UUID (optional, for job-related logs)"
    },
    "job_type": {
      "type": "string",
      "enum": ["DQ_RUN", "COMPLIANCE_RUN", "CONTRACT_VALIDATION", "SEMANTIC_MAPPING", "CONTRACT_MIGRATION"],
      "description": "Job type (optional, for job-related logs)"
    },
    "asset_id": {
      "type": "string",
      "format": "uuid",
      "description": "Asset UUID (optional, for asset-related logs)"
    },
    "contract_id": {
      "type": "string",
      "format": "uuid",
      "description": "Contract UUID (optional, for contract-related logs)"
    },
    "dataset_id": {
      "type": "string",
      "format": "uuid",
      "description": "Dataset UUID (optional, for dataset-related logs)"
    },
    "file_id": {
      "type": "string",
      "format": "uuid",
      "description": "File UUID (optional, for file-related logs)"
    },
    "error_code": {
      "type": "string",
      "maxLength": 100,
      "description": "Error code (optional, for error logs, e.g., 'RATE_LIMIT_EXCEEDED')"
    },
    "error_details": {
      "type": "object",
      "description": "Structured error details (optional, for error logs)"
    },
    "metadata": {
      "type": "object",
      "description": "Additional context-specific metadata (optional)"
    }
  }
}
```

**Log Category-Specific Requirements**

**Access Logs** (required fields: `timestamp`, `level`, `service`, `message`, `request_id`, `route`, `method`, `status_code`):
```json
{
  "timestamp": "2025-01-15T10:30:00.123Z",
  "level": "INFO",
  "service": "api-service",
  "message": "HTTP request completed",
  "request_id": "req-1234567890",
  "route": "/api/v1/assets",
  "method": "GET",
  "status_code": 200,
  "latency_ms": 45.2,
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Application Logs** (required fields: `timestamp`, `level`, `service`, `message`):
```json
{
  "timestamp": "2025-01-15T10:30:00.123Z",
  "level": "INFO",
  "service": "dq-service",
  "component": "great_expectations",
  "message": "DQ run started",
  "request_id": "req-1234567890",
  "job_id": "770e8400-e29b-41d4-a716-446655440002",
  "job_type": "DQ_RUN",
  "asset_id": "880e8400-e29b-41d4-a716-446655440003",
  "dataset_id": "990e8400-e29b-41d4-a716-446655440004",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error Logs** (required fields: `timestamp`, `level`, `service`, `message`, `error_code`):
```json
{
  "timestamp": "2025-01-15T10:30:00.123Z",
  "level": "ERROR",
  "service": "api-service",
  "message": "Rate limit exceeded",
  "request_id": "req-1234567890",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "error_details": {
    "limit": 100,
    "window_seconds": 60,
    "retry_after_seconds": 5
  },
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Security Logs** (required fields: `timestamp`, `level`, `service`, `message`):
```json
{
  "timestamp": "2025-01-15T10:30:00.123Z",
  "level": "WARN",
  "service": "auth-service",
  "message": "Authentication failed",
  "request_id": "req-1234567890",
  "error_code": "AUTH_INVALID_CREDENTIALS",
  "metadata": {
    "ip_address": "203.0.113.10",
    "user_agent": "Mozilla/5.0...",
    "attempt_count": 3
  }
}
```

**Field Validation Rules**

- **`timestamp`**: MUST be valid ISO 8601 UTC timestamp (millisecond precision recommended)
- **`level`**: MUST be one of: `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL`
- **`service`**: MUST match canonical service name (see `System_Architecture.md` §2.5)
- **`message`**: MUST NOT contain raw PII or sensitive data
- **`request_id`**: MUST be present for all API request/response logs
- **`tenant_id`**: MUST be present for all tenant-scoped operations
- **UUID fields**: MUST be valid UUID v4 format

#### 17.3.2 Log Categories

At minimum:

- **Access logs**:
  - One entry per HTTP request/response.
  - Includes `request_id`, `route`, `method`, `status_code`, `latency_ms`, `tenant_id` (if known).
- **Application logs**:
  - Business and domain events (e.g. “DQ run started”, “Compliance blocked storage”).
  - Validation failures, engine errors, timeouts.
- **Security logs**:
  - Auth failures, rate-limit triggers, suspicious patterns.

Logs related to governance (e.g. DQ/Compliance runs, marketplace actions) are also reflected in **AuditEvents** (§4), but application logs MAY contain more technical context.

### 17.4 Tracing

The platform SHOULD implement **distributed tracing** using OpenTelemetry:

**Implementation**: Python services use `opentelemetry-instrumentation-django` for Django auto-instrumentation. See `Technology_Stack_Decisions.md` for version and configuration details.

- Each incoming HTTP request:
  - Starts a trace or joins an existing one.
  - Propagates trace context to:
    - Background job enqueuing.
    - External services (DataContract CLI, DQ/Compliance, triple store).
- Each long-running job:
  - Emits spans for major steps:
    - Input validation.
    - Data loading / sampling.
    - Engine execution.
    - Result persistence.
- Trace identifiers:
  - `trace_id` and `span_id` MUST be correlated with:
    - `request_id` in logs.
    - `job_id` for background jobs.

Traces MUST NOT record raw data payloads (PII); they can record:

- Row counts, sample sizes, statuses.
- Engine names, versions, and config identifiers.

### 17.5 Alerting

Alerts MUST be defined on **SLIs/SLOs** derived from metrics.

#### 17.5.1 Core SLOs (Guidance)

At minimum:

- **API availability**:
  - SLI: percentage of successful requests (2xx) on core APIs over a rolling window.
  - SLO target (example): 99% over 30 days for `/assets`, `/contracts`, `/dq-runs`, `/compliance-runs`, `/jobs`.

- **Job success rate**:
  - SLI: percentage of jobs with `status = SUCCEEDED` for each `job_type`.
  - Alert when failure rate exceeds threshold (e.g. >5% of jobs failing over 15 minutes).

- **CLI/DQ/Compliance engine health**:
  - SLI: error rate for calls to DataContract CLI / GX / Soda / compliance engine.
  - Alert when error/timeout rate exceeds threshold.

- **Queue backlog**:
  - SLI: queue depth and job age for each `job_type`.
  - Alert when backlog exceeds threshold (e.g. jobs waiting > N minutes) indicating processing lag.

#### 17.5.2 Alert Delivery

- Alerts SHOULD integrate with standard channels (e.g. email, Slack, PagerDuty).
- Alerts MUST include:
  - Metric that triggered.
  - Affected service/component.
  - Time range and severity.
  - Links to relevant dashboards and runbooks.

### 17.6 Dashboards

Operations dashboards MUST be provided for at least:

- **Platform overview**:
  - API traffic, latency, error rates.
  - Job rates and success/failure.
  - Dependency health (DB, object storage, triple store, CLI, DQ/compliance engines).

- **DQ & Compliance**:
  - Volume of runs per day.
  - Success/timeout/error breakdown.
  - Distribution of outcomes (PASS/WARN/FAIL) at platform level and per tenant (aggregated).

- **Marketplace & Entitlements** (high-level ops view):
  - Numbers of public listings, requests, approvals.
  - Entitlement creation/revocation trends.

Dashboards MUST avoid exposing tenant-sensitive details to other tenants; an internal ops dashboard can see global aggregates, while future tenant-facing dashboards may be scoped to that tenant only.

### 17.7 Tenant-Facing Observability (Future)

For MVP:

- Monitoring and observability are primarily **internal** (for platform operators).

The design MUST, however, anticipate future **tenant-facing observability**, e.g.:

- Tenant-specific panels for:
  - Number of assets, DQ runs, compliance runs.
  - Recent errors or failures related to that tenant’s assets.
- APIs to fetch:
  - Aggregated DQ/compliance stats per asset.
  - Job histories filtered by `tenant_id`.

Tenant-facing views MUST reuse the same metrics/logging infrastructure, filtered and aggregated per tenant, without exposing other tenants’ data.

## 18. Backup & Disaster Recovery

This section defines how the platform handles **backups** and **disaster recovery (DR)** for critical components: metadata databases, audit logs, semantic store, and data files in object storage.

The goal is to ensure:

- Data and metadata are not lost in common failure scenarios.
- Recovery is predictable and tested.
- Privacy and regulatory constraints (including “no PII in logs”) are respected.

### 18.1 Objectives & Targets

High-level objectives (initial, can be refined later):

- **RPO (Recovery Point Objective)**  
  - Control plane (metadata DB, contracts, assets, jobs): **≤ 24 hours**  
    (i.e., at most one day of changes lost in a catastrophic failure).
  - Audit logs: **≤ 24 hours** (consistent with §4 retention guarantees).
  - Data files in object storage:
    - Rely on **versioning** and replication; effective RPO close to 0 for uncorrupted scenarios.
- **RTO (Recovery Time Objective)**  
  - Control plane: platform usable again within **24 hours** of a major outage.
  - Audit logs & semantic store: restored along with control plane or shortly after.
  - Data files: accessible as soon as control plane is up and object storage is reachable.

These RPO/RTO values are initial MVP targets and MUST be documented as non-binding SLOs, not legal guarantees.

#### 18.1.1 Who can delete a tenant

- Tenant deletion is a **privileged operation**:
  - Only **Platform Admins / Marketplace Operators** can trigger tenant deletion (not regular Tenant Admins).
  - The operation MUST be:
    - Logged as an **audit event** (`TENANT_DELETION_REQUESTED`, `TENANT_DELETION_COMPLETED`) with actor, timestamp, and reason.
    - Processed as an **asynchronous job** with a `Job` record (see §13).:contentReference[oaicite:0]{index=0}

#### 18.1.2 Tenant Suspension vs Deletion

**Suspension (`status = SUSPENDED`)**

- **Purpose**: Temporary measure to restrict tenant operations (e.g., payment issues, policy violations, investigation).
- **Behavior**:
  - **Write operations blocked**: Cannot create/edit assets, contracts, datasets, upload files, trigger jobs, create listings.
  - **Read operations allowed**: Can read/view existing assets, contracts, datasets, download files, view audit logs, browse marketplace (but cannot create listings).
  - **User access**: Existing users can log in but are limited to read-only operations.
  - **Reactivation**: Can be reactivated by Platform Admin (sets `status = ACTIVE`).
  - **Timeline**: Suspension is temporary; if not reactivated within a configurable period (default: 90 days), Platform Admin may proceed with deletion.
- **Data retention**: All tenant data is preserved during suspension.

**Deletion (`status = DELETED`)**

- **Purpose**: Permanent removal of tenant and all associated data (after retention period).
- **Behavior**:
  - **All access blocked**: No read or write operations allowed.
  - **User access**: All users are disabled (`User.status = DISABLED`).
  - **Data deletion**: Physical deletion occurs after retention period (default: 30 days after `deleted_at`).
  - **Reactivation**: **Cannot be reactivated** (deletion is permanent).
- **Timeline**: 
  - **Soft delete**: Immediate (sets `status = DELETED`, `deleted_at = NOW()`).
  - **Physical delete**: After retention period (30 days default) via background job.

**Suspension → Deletion Flow**

- If tenant remains suspended for > 90 days (configurable):
  - Platform Admin is notified.
  - Platform Admin can choose to:
    - Reactivate tenant (`status = ACTIVE`).
    - Proceed with deletion (initiates soft delete process).

#### 18.1.3 Soft delete (immediate effects)

When tenant deletion is initiated, the platform MUST immediately:

- **Block access & new activity**
  - Disable all users belonging to the tenant (`User.status = DISABLED`).
  - Prevent new logins, API calls, or job creation under that tenant (`401/403`).
  - Cancel or mark as `CANCELLED` all **pending jobs** for that tenant.:contentReference[oaicite:1]{index=1}

- **Hide tenant resources from other tenants**
  - Unpublish all **marketplace listings** owned by the tenant and revoke active **entitlements** that grant other tenants access to the tenant’s assets (no new downloads/API access).
  - Remove the tenant’s assets from all cross-tenant search/catalog views.

- **Mark tenant as deleted (logical)**
  - Mark the tenant as logically deleted (e.g., set `status != ACTIVE` and `deleted_at` timestamp).
  - From this point, **no tenant-scoped resources are user-visible**, even though underlying data has not yet been fully purged.

#### 18.1.3 Cascade deletion rules (tenant-scoped data)

Tenant deletion MUST trigger cascading deletion for all entities **scoped by `tenant_id`**, except audit logs.

**Deletion Execution Order**

Deletion is performed in a **specific order** to respect foreign key constraints and minimize data integrity risks:

**Phase 1: Immediate Soft Delete (Synchronous, Transactional)**

1. **Mark tenant as deleted**:
   - Set `tenants.status = 'DELETED'`, `tenants.deleted_at = NOW()`.
   - This is a **single database transaction** to ensure atomicity.

2. **Disable tenant access**:
   - Set all `users.status = 'DISABLED'` for the tenant (single transaction).
   - Cancel all `PENDING` jobs: Set `jobs.status = 'CANCELLED'`, `jobs.cancellation_requested = true` for all jobs where `tenant_id = <deleted_tenant>` and `status = 'PENDING'`.

3. **Hide marketplace resources**:
   - Set all `listings.status = 'UNPUBLISHED'` for the tenant.
   - Revoke all active `entitlements`: Set `entitlements.status = 'REVOKED'`, `entitlements.revoked_at = NOW()` for entitlements where `tenant_id = <deleted_tenant>` (consumer) or where `asset_id` belongs to the deleted tenant (provider).

#### 18.1.3.1 Tenant Deletion and Cross-Tenant Entitlements

**Provider Tenant Deletion Impact on Consumers**

When a **provider tenant** is deleted (tenant that owns assets listed in marketplace):

- **Consumer entitlements are revoked**:
  - All entitlements where `asset_id` belongs to the deleted provider tenant are revoked
  - `entitlements.status = REVOKED`, `entitlements.revoked_at = NOW()`
  - `entitlements.revoked_reason = "PROVIDER_TENANT_DELETED"`
- **Consumer notification**:
  - **Email notification** sent to consumer tenant admins for each revoked entitlement
  - **Email content**:
    - Subject: "Data access revoked: Provider tenant deleted"
    - Body includes:
      - Asset name and listing title
      - Provider tenant name (if available)
      - Reason for revocation (provider tenant deleted)
      - Date of revocation
  - **Notification timing**: Sent within 5 minutes of tenant deletion
- **Access termination**:
  - Consumers **lose immediate access** to provider's assets
  - Downloads via `GET /files/{id}/download` return `403 Forbidden` with error code `ENTITLEMENT_REVOKED`
  - Asset metadata access via `GET /assets/{id}` may be restricted (depending on asset visibility)
- **Historical data access**:
  - **Entitlement records are preserved** for audit/compliance (not deleted)
  - Consumers can view their entitlement history via `GET /entitlements?status=REVOKED`
  - **Data already downloaded**: Consumers retain any data they downloaded before revocation (no retroactive data deletion)

**Consumer Tenant Deletion Impact on Providers**

When a **consumer tenant** is deleted (tenant that has entitlements to other tenants' assets):

- **Consumer entitlements are revoked**:
  - All entitlements where `tenant_id = <deleted_consumer_tenant>` are revoked
  - `entitlements.status = REVOKED`, `entitlements.revoked_at = NOW()`
  - `entitlements.revoked_reason = "CONSUMER_TENANT_DELETED"`
- **Provider notification** (optional, configurable):
  - **Email notification** may be sent to provider tenant admins
  - **Email content**:
    - Subject: "Consumer tenant deleted: Entitlement revoked"
    - Body includes:
      - Consumer tenant name
      - Asset name and listing title
      - Number of entitlements revoked
  - **Notification timing**: Sent within 5 minutes of tenant deletion
- **Provider impact**:
  - Providers see revoked entitlements in their entitlement list
  - No impact on provider's assets or listings (assets remain accessible to other consumers)

**Entitlement Revocation Details**

- **Revocation scope**: All entitlements are revoked, regardless of:
  - Entitlement status (`ACTIVE`, `EXPIRED`)
  - Entitlement expiration date (even if `expires_at` is in the future)
  - Entitlement type (marketplace, direct grant, etc.)
- **Revocation is immediate**: Entitlements are revoked synchronously during Phase 1 (soft delete)
- **Revocation is permanent**: Revoked entitlements cannot be reactivated after tenant deletion
- **Audit trail**: Entitlement revocation is logged in `audit_events`:
  - Event type: `ENTITLEMENT_REVOKED`
  - `details_json` includes:
    - `revoked_reason`: `"PROVIDER_TENANT_DELETED"` or `"CONSUMER_TENANT_DELETED"`
    - `deleted_tenant_id`: ID of the deleted tenant
    - `asset_id`: Asset ID (for provider deletion)
    - `consumer_tenant_id`: Consumer tenant ID (for provider deletion)
    - `provider_tenant_id`: Provider tenant ID (for consumer deletion)

**Data Retention After Tenant Deletion**

- **Entitlement records**: Preserved for audit/compliance (3-year retention minimum)
- **Order records**: Preserved for audit/compliance
- **Audit events**: Preserved for audit/compliance (3-year retention minimum)
- **Downloaded data**: Consumers retain any data downloaded before entitlement revocation (no retroactive deletion)

**Phase 2: Background Physical Deletion (Asynchronous, Best-Effort)**

The tenant deletion job processes deletions in the following order (each step is idempotent and can be retried):

1. **Marketplace entities** (no dependencies):
   - Delete `entitlements` where consumer or provider is the deleted tenant.
   - Delete `orders` where consumer is the deleted tenant.
   - Delete `listings` where provider is the deleted tenant.

2. **Jobs and runs** (depend on assets/datasets/files):
   - Cancel all `RUNNING` jobs: Set `jobs.status = 'CANCELLED'` for running jobs.
   - Delete `dq_runs` and `compliance_runs` (subject to retention policy; see §2.8.1 and §3.7.1).
   - Delete `jobs` records (except those required for audit; see below).

3. **Semantic mappings**:
   - Delete `semantic_resources` where `tenant_id = <deleted_tenant>`.
   - Delete corresponding RDF triples from triple store (via `semantic-service`).

4. **Datasets and files** (depend on assets):
   - Delete `datasets` records.
   - Delete `files` records.
   - Delete physical files from object storage (or mark for deletion if using versioning).
   - **Note**: For scan-only files, raw data is deleted; only reports/hashes may remain per §3.4.

5. **Contracts and assets** (depend on users):
   - Delete `contracts` records.
   - Delete `assets` records.

6. **Users and roles** (final cleanup):
   - Delete `user_roles` join records.
   - Delete `roles` records.
   - Delete `users` records (except those referenced in audit logs; see below).

**Failure Handling Strategy**

- **Transactional vs. Best-Effort**:
  - Phase 1 (soft delete) is **transactional**: If any step fails, the entire phase rolls back, and tenant deletion is aborted.
  - Phase 2 (physical deletion) is **best-effort**: Failures in individual steps are logged, and the deletion job retries failed steps up to a maximum number of attempts (e.g., 3 retries with exponential backoff).

- **Partial deletion handling**:
  - If deletion of one entity type fails (e.g., files cannot be deleted from object storage due to permissions):
    - The deletion job logs the failure and continues with other entity types.
    - Failed deletions are retried in subsequent runs of the deletion job.
    - A **deletion status** is maintained in the tenant record or a separate `tenant_deletion_jobs` table:
      - `status`: `IN_PROGRESS`, `COMPLETED`, `PARTIAL`, `FAILED`
      - `failed_entity_types`: Array of entity types that failed deletion
      - `retry_count`: Number of retry attempts
  - After maximum retries, remaining data is flagged for manual cleanup.

- **Data integrity guarantees**:
  - Foreign key constraints prevent deletion of parent records if child records still exist.
  - The deletion order above respects FK dependencies (children deleted before parents).
  - If FK constraints would block deletion:
    - The deletion job identifies the blocking records.
    - Logs an error with details.
    - Retries after resolving dependencies (or flags for manual intervention).

**Retention Exceptions**

The following records are **NOT deleted** even after tenant deletion:

- **AuditEvents**: Retained for ≥ 3 years per §4.4, even if they reference deleted tenants/assets.
- **Jobs with audit significance**: Jobs that are referenced in audit logs or required for compliance are retained (marked with a flag, not physically deleted).
- **Aggregated metrics**: Non-identifying billing/usage metrics may be retained for financial reconciliation.

**API behavior**
  - After Phase 1 completes, any API call referencing a resource that belonged to the deleted tenant MUST return `404 NOT_FOUND` (or equivalent) even if Phase 2 (physical deletion) has not yet completed.

#### 18.1.3.1 Physical Deletion Timeline and SLA

**Expected Timeline**

Physical deletion (Phase 2) is performed by a background job that runs continuously. The timeline depends on tenant size and system load:

| Tenant Size | Expected Completion Time | SLA Target |
|-------------|--------------------------|------------|
| **Small** (< 100 assets, < 1,000 files) | 1-4 hours | < 6 hours |
| **Medium** (100-1,000 assets, 1,000-10,000 files) | 4-12 hours | < 24 hours |
| **Large** (1,000-10,000 assets, 10,000-100,000 files) | 12-48 hours | < 48 hours |
| **Very Large** (> 10,000 assets, > 100,000 files) | 48-96 hours | < 96 hours |

**Processing Rate**

- **Batch size**: 1,000 entities per batch (configurable via `TENANT_DELETION_BATCH_SIZE`)
- **Processing rate**: ~10,000 entities per hour (depends on entity type and system load)
- **Concurrent deletions**: Up to 3 tenant deletions can run concurrently (configurable via `MAX_CONCURRENT_TENANT_DELETIONS`)

**Progress Tracking**

- **Deletion status** is tracked in `tenant_deletion_jobs` table (or equivalent):
  ```sql
  CREATE TABLE tenant_deletion_jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL,  -- IN_PROGRESS, COMPLETED, PARTIAL, FAILED
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    entities_deleted JSONB,  -- { "assets": 100, "files": 500, ... }
    entities_remaining JSONB,  -- { "assets": 0, "files": 0, ... }
    failed_entity_types TEXT[],
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
  );
  ```

- **Monitoring metrics**:
  - `tenant_deletion_duration_seconds{tenant_id, status}` (histogram)
  - `tenant_deletion_progress_percent{tenant_id}` (gauge, 0-100)
  - `tenant_deletion_entities_remaining{tenant_id, entity_type}` (gauge)
  - `tenant_deletion_failures_total{tenant_id}` (counter)

- **API endpoint** (future enhancement): `GET /admin/tenant-deletions/{id}` to query deletion progress

**SLA Guarantees**

- **Phase 1 (Soft Delete)**: Completes within **5 minutes** (synchronous, transactional)
- **Phase 2 (Physical Delete)**: Completes within SLA targets above (asynchronous, best-effort)
- **Notification**: Platform Admin is notified when Phase 2 completes (or fails after max retries)

**Failure Handling**

- **Max retries**: 3 attempts per entity type
- **Retry backoff**: Exponential backoff (1 hour, 6 hours, 24 hours)
- **After max retries**: 
  - Deletion status set to `PARTIAL` or `FAILED`
  - Platform Admin notified for manual intervention
  - Remaining data flagged for manual cleanup

#### 18.1.4 Audit logs & metrics retention

- **AuditEvents are *not* deleted with the tenant**
  - Audit logs are retained **independently of asset/tenant lifecycle**:
    - Even if a tenant, asset, or file is deleted, its related audit entries MUST be kept for at least the configured retention period (≥ 3 years).:contentReference[oaicite:5]{index=5}
  - This is consistent with existing requirements:
    - Audit logs are append-only, contain **no raw PII**, and exist to demonstrate compliance and incident traceability.:contentReference[oaicite:6]{index=6}
    - Deletion of assets/datasets already leaves audit logs intact (§12.6, §6.3).:contentReference[oaicite:7]{index=7} :contentReference[oaicite:8]{index=8}

- **Billing / usage metrics**
  - Aggregated, non-identifying billing and usage metrics (e.g., counts of DQ runs, storage usage) MAY be retained after tenant deletion for:
    - Financial reconciliation.
    - Capacity planning and product analytics.
  - These metrics MUST NOT contain raw dataset values or direct personal identifiers.

#### 18.1.5 Data retention windows (post-deletion)

To balance operational needs with privacy:

- **Content data (datasets, metadata)**
  - The platform MUST ensure all tenant-scoped content data (datasets, contracts, semantic triples, marketplace objects, jobs, etc.) are permanently deleted or irreversibly anonymized within a **configurable deletion window** (e.g., ≤ 30 days) after tenant deletion completes.
  - Implementations MAY use:
    - Background cleanup jobs.
    - Cryptographic erasure (key deletion) where encryption-at-rest is used.

- **Audit & logs**
  - Audit logs follow the existing retention policy (≥ 3 years), even after tenant deletion, provided they remain free of raw PII and are necessary for:
    - Demonstrating regulatory compliance.
    - Security investigations and incident response.:contentReference[oaicite:9]{index=9}

#### 18.1.6 GDPR “right to erasure” considerations

- The platform is designed with **data minimization** and “no PII in logs” as core principles: raw personal data is stored only in datasets, never in logs or semantic graphs; logs contain only IDs, hashes, and high-level categories.:contentReference[oaicite:10]{index=10}
- When a tenant is deleted and the above cascade + retention rules are applied:
  - All **tenant-scoped datasets and metadata** are removed within the deletion window.
  - Remaining audit records are:
    - Pseudonymized (no raw PII).
    - Retained only as necessary for **legal obligations** (e.g., demonstrating that non-compliant data was never stored, or that erasure was performed).
- For future phases (§6.4), more granular **data subject–level** erasure workflows (DSAR, per-subject deletion) MAY build on these primitives but are **not required for MVP**.:contentReference[oaicite:11]{index=11}

### 18.2 Scope & Components

Backups and DR MUST cover at least:

- **Application metadata DB**:
  - Tenants, users, assets, contracts, datasets (references), jobs, DQ/compliance runs, entitlements, marketplace listings.
- **Audit log store** (§4):
  - Append-only audit events; 3-year retention requirement.
- **Semantic store**:
  - RDF/triple store or graph DB containing semantic mappings and ontologies.
- **Object storage**:
  - Data files (in-platform assets).
  - Exported reports (DQ/compliance, audit exports).
- **Configuration & infrastructure**:
  - Application configuration (excluding secrets).
  - Infrastructure-as-code definitions (e.g. Terraform, Helm charts) – stored in version control, not only in backups.

**Secrets** (API keys, DB passwords, etc.) MUST be stored in a **dedicated secrets manager** (cloud KMS/secret store), which has its own backup guarantees.

### 18.3 Backup Strategy

#### 18.3.1 Relational Databases (Metadata & Audit)

- Primary DBs (metadata + audit schema) MUST use a combination of:
  - **Automated snapshots**:
    - Daily full snapshots with retention (e.g. 7–30 days; configurable).
  - **Point-in-time recovery**:
    - Write-ahead logs (WAL) or equivalent retained for at least the snapshot window (e.g. 7–30 days).
- Backups MUST be:
  - **Encrypted at rest** (using cloud provider mechanisms).
  - Stored in **separate storage** from the primary data volume (e.g. backup storage service or different bucket).
- Backup metadata MUST record:
  - DB name, snapshot time, retention expiration.
  - Encryption key ID (if applicable).

#### 18.3.2 Semantic Store (Triple Store / Graph DB)

- Semantic store MUST support either:
  - Native backup/export mechanisms (e.g. periodic dumps in Turtle/N-Triples/Parquet), or
  - Snapshotting at the storage layer if managed by the same DB engine.
- Backups SHOULD be:
  - Taken daily.
  - Retained for at least as long as the metadata DB snapshots.

#### 18.3.3 Object Storage (Data Files & Exports)

- **Object storage is the primary source of truth for data files.**
- Backup/DR strategy MUST rely on:
  - **Versioning** enabled on the buckets storing:
    - Data files.
    - Exported reports (DQ/compliance, audit exports).
  - Optional cross-region replication (future, depending on region/residency constraints).
- For DR, the ability to restore consists of:
  - Re-attaching same buckets to new infrastructure, OR
  - Failing over to replicated buckets in another region, subject to residency rules.

#### 18.3.4 Configuration & Code

- Application code and infrastructure definitions:
  - MUST be stored in version control (e.g. Git) with:
    - Redundant hosting (e.g. managed Git provider).
    - Access controls and backup guarantees from the provider.
- Environment configuration (non-secret):
  - MUST be reproducible from:
    - IaC (Terraform/Helm/etc.).
    - Documented parameter sets (e.g. in config files under version control).

#### 18.3.5 Backup & Restore Operational Requirements

This section defines minimum operational requirements for restore testing, point-in-time recovery, cross-region backup replication, and backup encryption at rest.

- **Restore testing frequency**
  - At least **once per year**, the team MUST execute an end-to-end **restore test** in a non-production environment, covering:
    - Restore of the **metadata/audit database** from backups.
    - Restore of a **sample of objects** from object storage (including older versions).
    - Restore of the **semantic store** from backup/export.
  - Tests MUST verify:
    - Data integrity (foreign keys, counts, basic sanity checks).
    - Consistency between control plane (metadata) and data plane (object storage / semantic store).
  - Results (success/fail, duration, issues found) MUST be documented and feed into DR/runbook improvements.
  - The platform SHOULD aim to perform these tests **at least once per 12 months** per production environment; more frequent tests (e.g. semi-annual) are encouraged but not required for MVP.

- **Point-in-time recovery (PITR) procedures**
  - The primary metadata/audit database MUST support **point-in-time recovery** within the configured WAL/transaction log retention window (see §18.3.1).
  - There MUST be a documented **runbook** for PITR in case of:
    - Bad migrations.
    - Operator errors (e.g. accidental table/row deletion).
    - Application bugs causing data corruption.
  - The PITR runbook MUST cover at least:
    - Placing the system into **protected mode** (blocking or minimizing new writes).
    - Identifying the **target restore time** (last known good point).
    - Restoring a snapshot or PITR clone to a **new DB instance**.
    - Replaying logs up to the target time (if safe and applicable).
    - Validating the restored instance (integrity and basic functional checks).
    - Switching application traffic to the restored instance and decommissioning the corrupted one.
  - Object storage and semantic store MUST rely on their own **versioning/backup mechanisms** for point-in-time restores (e.g. restoring specific object versions rather than raw block-level PITR).

- **Cross-region backup replication**
  - For metadata/audit databases and object storage, the architecture MUST allow:
    - At least one **backup copy** or **replica** in a different availability zone or region, subject to data residency constraints.
  - For MVP:
    - Cross-region replication MAY be **asynchronous** and MAY be enabled only for selected components (e.g. object storage buckets).
    - Region-level failover MAY remain **manual** with RTO > 24h, as long as it does not violate §18.1 objectives.
  - When cross-region replication is enabled:
    - Replicated backups MUST be subject to the **same encryption at rest** requirements as primary backups.
    - Data residency rules (e.g. “EU data must remain in EU region(s)”) MUST be respected; replication MUST NOT copy data to disallowed regions.
    - Runbooks MUST define how to restore from a secondary region (re-pointing apps, DNS changes, attaching replicated buckets, etc.).

- **Backup encryption at rest**
  - All backup artifacts MUST be **encrypted at rest**, including:
    - Database snapshots and PITR logs (WAL/transaction logs).
    - Semantic store backups/exports.
    - Object storage versions and backup buckets.
    - Cross-region backup replicas.
  - Encryption MUST use **cloud-provider or KMS-managed keys**, with:
    - Key rotation policies aligned with security best practices.
    - Tight access controls for key usage (only backup/restore services and authorized ops).
  - Backup processes MUST NOT bypass existing privacy requirements:
    - “No raw PII in logs” still applies; backups MUST NOT introduce new PII in audit/log systems.
    - Any backup exports used for testing/development MUST use sanitized or non-production data where required by policy.

### 18.4 Disaster Scenarios & Recovery Procedures

The platform MUST plan for at least these categories:

#### 18.4.1 Localized Infrastructure Failure

Examples:

- Single node failure.
- Container host issues.

Approach:

- Rely on cloud-native high availability:
  - Multiple instances behind a load balancer.
  - Auto-restart of failed pods/VMs.
- No backup restore required; just redeploy or let orchestration reschedule.

#### 18.4.2 Database Corruption or Critical Migration Failure

Examples:

- Bad migration applied that corrupts metadata.
- Operator error dropping important tables.

Approach:

- Stop write traffic to the affected DB instance (place system in protected mode).
- Identify **last known good snapshot** prior to corruption.
- Restore snapshot to a **new** DB instance.
- Re-point application to the restored instance, update connection configs.
- Replay necessary WAL/point-in-time logs if safe and applicable.
- Validate:
  - Tenants, assets, and recent jobs are consistent.
  - Integrity checks pass (e.g. foreign keys, counts).

#### 18.4.3 Region-Level Outage (Future)

Examples:

- Entire cloud region unavailable.

Approach (future, not strict MVP requirement, but design MUST allow):

- Use multi-region architecture for:
  - Object storage (cross-region replication, or region-pair failover).
  - Databases (read replicas in secondary region, or cold-standby + snapshot restore).
- Maintain warm secondary environment that can be promoted to primary with:
  - DNS/endpoint failover.
  - Configuration to attach to replicated data stores.

For MVP:

- Region-level failover MAY be manual and slower (RTO > 24h), but:
  - Architecture MUST NOT prevent evolution to automated multi-region DR later.

#### 18.4.4 Accidental Deletion of Data Assets

Examples:

- Tenant admin deletes an Asset/Dataset unintentionally.

Approach:

- Application-level protection:
  - Soft-delete mechanics for assets where feasible.
  - Confirmation prompts for destructive actions.
- Backup-level protection:
  - Ability to recover asset metadata from DB backups (point-in-time restore).
  - Ability to restore data files from object versioning:
    - Restore to a safe location or re-link previous object versions.
- Recovery MUST respect retention policies and privacy rules (see 18.5).

### 18.5 Tenant Deletion, Privacy & Backups

Backups MUST be compatible with privacy and regulatory requirements.

- **Logs and audit**:
  - Already constrained by “no raw PII in logs” policy.
  - Longer retention (≥3 years) is acceptable since raw identifiers are not stored.
- **Data files**:
  - May contain personal or sensitive data; deletion requests MUST be honored:
    - Primary copies in object storage are deleted according to **data lifecycle policies**.
    - Backups (snapshots, versioning) may still contain old copies; policy MUST be documented:
      - Either: shorter retention for objects containing personal data, OR
      - Encryption-key-per-tenant model where key destruction effectively renders backup data unreadable (future enhancement).
- **Right to be forgotten**:
  - MVP: focus is on **not storing PII in logs** and proper deletion of primary data copies.
  - Policy for PII in old immutable backups MUST be clearly documented and justified:
    - e.g., retained only for limited time, accessible only to security/ops under strict controls.



### 18.6 Disaster Recovery Runbook

This section defines the minimum contents of the Disaster Recovery (DR) runbook and how it is exercised in practice.

#### 18.6.1 Scope & Triggers

The DR runbook MUST cover, at minimum, the scenarios described in §18.4:

- Localized infrastructure failures.
- Database corruption / critical migration failures.
- Regional or provider-scale incidents.
- Accidental deletion of data assets.

The runbook MUST define **clear triggers** for initiating DR mode, e.g.:

- Control-plane outage exceeding a defined threshold (e.g. 30–60 minutes).
- Detection of unrecoverable DB corruption on the primary.
- Cloud-provider incident affecting a whole region.
- Security incident requiring isolation of primary infrastructure.

Each trigger MUST map to a specific DR flow and responsible roles (on-call engineer, incident commander, communications lead).

#### 18.6.2 RTO/RPO Verification

The DR runbook MUST specify how RTO/RPO targets defined in §18.1 are **verified in practice**:

- **Scheduled DR exercises**
  - At least **once per year**, the team MUST execute a DR exercise in a non-production environment that simulates a major outage (e.g. loss of primary metadata DB or primary region).
  - Each exercise MUST:
    - Measure **actual RTO** (time from incident declaration to restored service).
    - Measure **effective RPO** (latest point-in-time successfully recovered).
    - Compare results against the targets in §18.1 and document any gaps.

- **Acceptance criteria**
  - The runbook MUST define pass/fail criteria, e.g.:
    - “Control plane restored within 24 hours of simulated outage.”
    - “No more than 24 hours of metadata changes lost.”
  - Deviations MUST be recorded and fed into follow-up actions (architecture or process improvements).

- **Post-exercise review**
  - Each DR exercise MUST produce a short report including:
    - Scenario and scope.
    - Measured RTO/RPO.
    - Issues encountered and mitigations.
    - Updates required in the runbook.

#### 18.6.3 Failover Procedures

The DR runbook MUST contain step-by-step **failover procedures** for:

- **Control-plane database failover/restore**
  - Criteria for switching from “attempt to repair” to “restore/replace”.
  - Steps to:
    - Place the system in **protected mode** (minimize or block new writes).
    - Restore from snapshot or PITR to a **new DB instance**.
    - Reconfigure application connections (connection strings, secrets).
    - Validate schema and basic read/write operations.
  - Rollback/abort criteria if validation fails.

- **Region-level failover (when supported)**
  - Preconditions (e.g. cross-region replicas or replicated object storage configured).
  - Steps to:
    - Promote a secondary region or environment.
    - Re-point external endpoints (DNS, load balancer, API gateways).
    - Attach or enable access to replicated object storage and semantic store.
  - Explicit note that for MVP, region failover MAY be manual but MUST be documented.

- **Dependency failover**
  - For critical dependencies (message queues, object storage endpoints, search/semantic store), the runbook MUST:
    - Identify primary and fallback endpoints.
    - Document how to reconfigure the application to use secondary endpoints.
    - Define validation checks for each dependency after failover.

Each failover procedure MUST clearly assign responsibilities (who initiates, who approves, who executes).

#### 18.6.4 Data Consistency Verification After Failover

The DR runbook MUST define **post-failover validation** steps to ensure data consistency:

- **Control-plane vs data-plane checks**
  - Sample a set of tenants/assets and verify:
    - Assets listed in the metadata DB correspond to existing objects in storage.
    - No “orphaned” critical objects (data files without metadata, or vice versa) for a representative sample.
  - Verify semantic store references (if used) align with restored metadata.

- **Job and run integrity**
  - Ensure recent Jobs, DQ runs, and Compliance runs have consistent statuses (no impossible states like “RUNNING” for jobs that were in-flight during failover without logs to support them).
  - Optionally, re-run critical checks for high-value assets after major DR events.

- **Automated health checks**
  - The platform SHOULD provide automated probes that:
    - Validate key read/write paths for the API.
    - Verify connectivity to DB, semantic store, and object storage.
  - The runbook MUST specify which automated checks must be green before declaring DR complete.

The system MUST NOT be declared “fully restored” until the minimal validation steps in this section have passed.

#### 18.6.5 Communication Plan During DR Events

The DR runbook MUST include a **communication plan** covering:

- **Internal communication**
  - Clear incident roles:
    - **Incident Commander** – responsible for overall coordination and decision-making.
    - **Technical Lead(s)** – responsible for diagnosis and execution of failover/restore.
    - **Comms Lead** – responsible for internal and external updates.
  - Standard communication channels:
    - Incident chat channel (e.g. “#incident-dr-<date>”).
    - On-call escalation contacts and rotation.
  - Update frequency (e.g. every 30–60 minutes) during active incidents.

- **External communication (tenants / customers)**
  - Criteria for when to notify tenants (e.g. outages exceeding X minutes or any loss of data within RPO bounds).
  - Mechanisms:
    - Status page and/or email notifications to tenant admins.
    - Post-incident summary with:
      - Impacted time window.
      - Services affected.
      - Whether data loss occurred (and within RPO or not).
      - Mitigations and future prevention steps.

- **Regulatory / contractual obligations**
  - If applicable, the runbook MUST reference any regulatory timelines for incident notification (e.g. security breaches) and how these are met.
  - The runbook MAY delegate detailed legal/compliance procedures to separate policies, but MUST indicate when to involve legal/compliance contacts.

- **Runbook maintenance**
  - After every real DR event or major exercise, the communication plan MUST be reviewed and updated based on lessons learned (what worked, what didn’t).


## 19. Data Migration & HubContract Versioning

This section defines how the platform evolves the **canonical HubContract model** over time, and how existing data and contracts are migrated without breaking clients or losing information.

### 19.1 Goals

- Allow the HubContract schema and related models to evolve safely.
- Preserve:
  - Original source contracts (ODCS v3.0.2+).
  - Canonical HubContract representations for existing assets.
- Avoid breaking changes for:
  - API consumers (v1 endpoints).
  - Stored contracts and semantic mappings.
- Provide:
  - A clear process for migrations.
  - Auditability and rollback options.

### 19.2 Versioning Model

#### 19.2.1 HubContract Version Field

- Every stored contract MUST have:

  - `source_spec` – e.g. `"ODCS"`.
  - `source_spec_version` – e.g. `"3.0.2"`, `"2.2.2"`.
  - `hub_contract_version` – version of the canonical HubContract schema (e.g. `"1.0.0"`).

- `hub_contract_version` MUST follow **semantic versioning**:
  - `MAJOR.MINOR.PATCH`, e.g. `1.0.0`, `1.1.0`, `2.0.0`.
  - `MAJOR` increments indicate **breaking changes** to the canonical schema.
  - `MINOR` increments indicate additive/compatible changes.
  - `PATCH` increments indicate bug fixes or non-structural changes.

#### 19.2.2 Original vs Canonical Storage

For each contract/asset, the platform MUST store:

- `raw_contract`:
  - Original file as uploaded (YAML/JSON) conforming to ODCS v3.0.2+.
  - Preserved as-is for traceability and external interoperability.
- `hub_contract`:
  - Canonical JSON representation used internally and for API responses.
  - Tagged with `hub_contract_version`.

This allows:

- Reconstructing original contracts for export.
- Re-running DataContract CLI operations if needed.
- Changing the canonical model without losing the original shape.

### 19.3 Evolution Strategy

#### 19.3.1 Backward Compatibility First

- The design SHOULD aim to evolve `hub_contract_version` **without breaking v1 API**:
  - Add new fields with defaults where possible.
  - Deprecate old fields gradually, but keep them for at least one MAJOR version.
- v1 API responses MUST remain stable in structure as long as `/api/v1` is supported:
  - New fields may be added.
  - Existing fields MUST NOT change meaning or type without a version bump and clear migration strategy.

#### 19.3.2 Introducing a New HubContract Version

When a new `hub_contract_version` is introduced:

- A **migration specification** MUST be defined, including:
  - Source HubContract versions supported for migration (e.g. `"1.x → 2.0"`).
  - Transformation rules (field mappings, defaults, renames, semantic changes).
- Conversion functions MUST exist:
  - `migrate_hub_contract(v_from, v_to)` – deterministic, idempotent.
  - Capable of:
    - Upgrading stored HubContract objects (e.g. `1.0.0 → 2.0.0`).
    - Mapping older HubContracts to the current version on read if needed.

### 19.4 Migration Types

#### 19.4.1 On-Write Migration (New / Updated Contracts)

- When a new contract is **created** or an existing contract is **edited**:

  - The platform MUST:
    - Normalize from `raw_contract` → latest `hub_contract_version`.
    - Set `hub_contract_version` to the **current** canonical version.
  - DataContract CLI is used to:
    - Validate and possibly convert between ODCS versions.
    - Ensure source contract is valid before building the HubContract.

#### 19.4.2 On-Read “Lazy” Migration (Optional)

- For older stored contracts with `hub_contract_version < current_version`:

  - The platform MAY implement **lazy migration on read** for certain APIs:
    - When fetching via `/assets/{id}` or `/contracts/{id}`, the system:
      - Detects older version.
      - Applies in-memory transformation to present data in the latest logical shape.
  - If used, this behavior MUST be:
    - Transparent to API clients.
    - Documented internally for maintainers.

Lazy migration is useful when a background migration has not yet completed, but API semantics must reflect the latest model.

#### 19.4.3 Background Bulk Migration

- For large-scale changes (e.g. new MAJOR version), the platform SHOULD run **background bulk migrations**:

  - A new job type: `CONTRACT_MIGRATION`.
  - Operates per tenant or per batch of assets.
  - For each contract:
    - Reads current `hub_contract_version`.
    - Applies `migrate_hub_contract(old_version, target_version)`.
    - Writes back updated HubContract and `hub_contract_version`.

- Requirements:

  - `CONTRACT_MIGRATION` jobs MUST be:
    - Idempotent (safe to retry).
    - Logged via `AuditEvent` (`CONTRACT_MIGRATION_STARTED`, `CONTRACT_MIGRATION_COMPLETED`, `CONTRACT_MIGRATION_FAILED`).
  - Failures MUST NOT leave contracts partially migrated:
    - Either whole contract update succeeds, or it stays at previous version.

#### 19.4.4 Migration Transformation Rules

When migrating contracts between HubContract versions, transformation rules define how fields are mapped, renamed, or converted.

**Example: HubContract v1.0 → v2.0 Migration**

**Source (v1.0) Structure:**
```json
{
  "hub_contract_version": 1,
  "id": "contract-123",
  "info": {
    "name": "Customer Orders",
    "version": "1.0.0"
  },
  "schema": {
    "fields": [
      {
        "name": "order_id",
        "type": "string"
      }
    ]
  }
}
```

**Target (v2.0) Structure:**
```json
{
  "hub_contract_version": 2,
  "id": "contract-123",
  "metadata": {
    "name": "Customer Orders",
    "version": "1.0.0",
    "description": null
  },
  "schema": {
    "fields": [
      {
        "name": "order_id",
        "data_type": "string",
        "nullable": true
      }
    ]
  }
}
```

**Transformation Rules:**

1. **Field Renames**:
   - `info` → `metadata`
   - `schema.fields[].type` → `schema.fields[].data_type`

2. **Field Additions**:
   - `metadata.description` → `null` (if not present in v1.0)
   - `schema.fields[].nullable` → `true` (default, if not specified in v1.0)

3. **Field Removals**:
   - No fields removed (backward compatible).

4. **Type Conversions**:
   - `type: "string"` → `data_type: "string"` (direct mapping).

**Migration Function Contract**

```python
def migrate_hub_contract(source_version: str, target_version: str, contract_json: dict) -> dict:
    """
    Migrates a HubContract from source_version to target_version.
    
    Args:
        source_version: Source HubContract version (e.g., "1.0.0").
        target_version: Target HubContract version (e.g., "2.0.0").
        contract_json: Source contract JSON.
    
    Returns:
        Migrated contract JSON with hub_contract_version = target_version.
    
    Raises:
        MigrationError: If migration is not supported or fails.
    """
    # Implementation applies transformation rules
    # Must be deterministic and idempotent
    pass
```

**Backward Compatibility Rules**

- **Additive changes only**: New versions SHOULD only add fields (with defaults) or rename fields (with aliases).
- **Deprecation period**: Removed fields are kept for at least one MAJOR version before removal.
- **Default values**: New required fields MUST have sensible defaults for migrated contracts.

### 19.5 Migration Process & Governance

#### 19.5.1 Migration Planning

Before a breaking HubContract change (new MAJOR version):

- A **migration plan** MUST be produced, including:
  - Motivation and summary of changes.
  - Impacted fields and entities.
  - Compatibility notes (what breaks, what remains compatible).
  - Expected number of contracts to migrate and potential risks.

- The plan MUST define:
  - Whether lazy migration will be enabled.
  - Timeline for bulk migration and cut-over.
  - Rollback strategy if something goes wrong.

#### 19.5.2 Rollout & Rollback

- Rollout steps (typical):

  1. Implement new HubContract version in code, with migration functions.
  2. Deploy with both old and new versions supported:
     - New contracts use latest version.
     - Existing contracts are still readable.
  3. Run `CONTRACT_MIGRATION` jobs in batches.
  4. Monitor logs/metrics for migration errors.
  5. Once migration is complete:
     - Optionally disable old versions (read-only).
     - Update docs to mark old HubContract versions as deprecated.

- Rollback:

  - If serious issues are detected:
    - Stop migrations immediately.
    - Revert to previous application version.
    - For contracts already migrated:
      - If a **reverse migration** function exists (e.g. `2.0.0 → 1.0.0`), run it on affected contracts.
      - Otherwise, treat forward migration as permanent and resolve defects via new fix version (`2.0.1`).

All migrations MUST be tracked in AuditEvents and internal change logs.

### 19.6 Impact on Semantic Mapping & DQ/Compliance

- Semantic mapping (§Semantic_Mapping_Design) MUST be version-aware:

  - Mappings from HubContract to RDF SHOULD be tied to `hub_contract_version`.
  - When HubContract changes:
    - Semantic mapping rules MUST be updated.
    - Existing semantic graphs may need:
      - Full or partial rebuild via `SEMANTIC_MAPPING` jobs (already defined) using the updated HubContracts.

- DQ/Compliance:

  - Historical DQRun/ComplianceRun records maintain their original structure.
  - When HubContract evolves:
    - New runs SHOULD reference the updated contract schema.
    - Old runs remain valid and are not retroactively rewritten, but:
      - APIs MAY present normalized views (with clear “as of version” metadata if needed).

### 19.7 Tenant-Scoped vs Global Migrations

- By default, HubContract schema evolution is **global** (same version for all tenants).
- However, migration execution MAY be orchestrated:

  - Per-tenant (e.g. roll out to internal tenant first, then others).
  - Per-asset type or per domain (for risk management).

- The migration system MUST:

  - Allow scoping `CONTRACT_MIGRATION` jobs using:
    - `tenant_id`
    - `domain` or `tag`
    - asset subsets (e.g. “only published marketplace assets”).

### 19.8 Documentation & API Exposure

- Public API docs MUST:

  - Document the presence of `hub_contract_version` on contract/asset resources.
  - Clarify that `/api/v1` always returns data in a **stable v1 API format**, regardless of internal HubContract version.
  - Explain any client-visible differences when new fields are introduced.

- Internal docs MUST:

  - Maintain a **version history** of HubContract:
    - For each version:
      - Changelog.
      - Migration rules.
      - Mapping rules to/from ODCS versions.

## 20. SDKs (JavaScript & Python)

This section defines the **minimum requirements** and behavior for the official **JavaScript** and **Python** SDKs for the Interoperable Data Hub.

The SDKs are **first-class products**, not thin HTTP wrappers. They MUST:

- Make it easy to integrate:
  - Data asset onboarding (data-first, contract-first, contract-only).
  - DQ and Compliance runs (intake + scan-only).
  - Marketplace and entitlements.
  - Semantic/URI lookups.
- Follow the same:
  - Auth & tenant rules.
  - Error envelope (§13).
  - Job model (§14).
  - Security constraints (no raw PII in logs).

---

### 20.1 Scope & Design Principles

- SDKs MUST be provided for:
  - **JavaScript/TypeScript**:
    - Node.js (backend usage is **required**).
    - Browser support is **nice-to-have** for MVP but MUST be considered in design (especially for uploads).
  - **Python**:
    - Python 3.x (exact minimum version to be defined; e.g. 3.9+).

- Principles:
  - **Typed**:
    - JS SDK SHOULD provide TypeScript types.
    - Python SDK SHOULD provide type hints (PEP 484) for core objects.
  - **Opinionated but low-level**:
    - Provide direct mappings to API endpoints.
    - Provide a few high-level helpers for common flows (intake, scan-only DQ/compliance, job polling).
  - **Stable**:
    - SDK APIs SHOULD remain stable for the lifetime of `/api/v1`.
    - Breaking changes require major version bump of the SDK.

- Naming (placeholder; can be refined):
  - JS: `@datahub/interoperability-sdk` (or similar).
  - Python: `datahub_interoperability` (PyPI package).

---

### 20.2 Configuration & Authentication

Both SDKs MUST expose a consistent configuration model:

#### 20.2.1 Common Configuration

Required configuration options:

- `base_url`  
  - e.g. `https://api.hub.example.com/api/v1`
- `api_token` or equivalent:
  - Bearer token for Authorization header:
    - `Authorization: Bearer <token>`
- Optional:
  - `timeout` (per-request default).
  - `max_retries` and retry/backoff strategy for transient errors.
  - `user_agent` override (for observability).

Environment variable defaults (recommended but not required):

- `DATAHUB_BASE_URL`
- `DATAHUB_API_TOKEN`

#### 20.2.2 JS SDK Initialization Example

- Quick start:

```ts
import { DataHubClient } from "@datahub/interoperability-sdk";

const client = new DataHubClient({
  baseUrl: process.env.DATAHUB_BASE_URL!,
  apiToken: process.env.DATAHUB_API_TOKEN!,
});
```

#### 20.2.3 Python SDK Initialization Example

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(
    base_url=os.environ["DATAHUB_BASE_URL"],
    api_token=os.environ["DATAHUB_API_TOKEN"],
)
```

The client MUST:

- Inject `Authorization: Bearer <token>` for every request.
- Handle `tenant_id` strictly from token context (no manual overriding) unless API supports explicit cross-tenant admin calls.

#### 20.2.4 SDK Authentication Flow and Token Refresh

**Authentication Methods**

SDKs support two authentication methods:

1. **API Key Authentication** (recommended for server-to-server):
   - Use API key directly as bearer token: `Authorization: Bearer <api_key>`
   - API keys do not expire (until revoked)
   - No token refresh required

2. **JWT Token Authentication** (recommended for user-facing applications):
   - Initial login: `POST /auth/login` → returns `access_token` and `refresh_token`
   - Use `access_token` for API requests
   - `access_token` expires after 15 minutes (default)
   - Use `refresh_token` to obtain new `access_token` when expired

**Token Expiration Detection**

SDKs MUST detect token expiration using one or both methods:

1. **Proactive Detection** (recommended):
   - Parse JWT `exp` claim (if token is JWT)
   - Refresh token if `exp < now() + refresh_threshold` (e.g., 1 minute before expiry)
   - Prevents failed requests due to expired tokens

2. **Reactive Detection** (fallback):
   - If API returns `401 Unauthorized` with error code `AUTH_TOKEN_EXPIRED` or `AUTH_TOKEN_INVALID`
   - Attempt automatic token refresh
   - Retry original request with new token

**Automatic Token Refresh Flow**

**Step 1: Detect Expiration**
```typescript
// JavaScript/TypeScript example
class DataHubClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private tokenExpiry: Date | null = null;

  private isTokenExpired(): boolean {
    if (!this.tokenExpiry) return true;
    // Refresh 1 minute before expiry
    return this.tokenExpiry.getTime() < Date.now() + 60000;
  }
}
```

**Step 2: Refresh Token**
```typescript
private async refreshAccessToken(): Promise<void> {
  if (!this.refreshToken) {
    throw new HubAuthenticationError("No refresh token available");
  }

  try {
    const response = await fetch(`${this.baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: this.refreshToken }),
    });

    if (!response.ok) {
      // Refresh token expired or revoked
      throw new HubAuthenticationError("Refresh token invalid");
    }

    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token; // New refresh token (rotation)
    this.tokenExpiry = new Date(Date.now() + data.expires_in * 1000);
  } catch (error) {
    // Refresh failed - user must re-authenticate
    throw new HubAuthenticationError("Token refresh failed", { cause: error });
  }
}
```

**Step 3: Retry Original Request**
```typescript
async request<T>(endpoint: string, options: RequestInit): Promise<T> {
  // Check if token needs refresh
  if (this.isTokenExpired()) {
    await this.refreshAccessToken();
  }

  try {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${this.accessToken}`,
      },
    });

    // Handle 401 - token expired during request
    if (response.status === 401) {
      await this.refreshAccessToken();
      // Retry once with new token
      return this.request(endpoint, options);
    }

    return response.json();
  } catch (error) {
    throw new HubNetworkError("Request failed", { cause: error });
  }
}
```

**Python Example**
```python
class DataHubClient:
    def __init__(self, base_url: str, api_token: str = None, 
                 access_token: str = None, refresh_token: str = None):
        self.base_url = base_url
        self.api_token = api_token
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry: Optional[datetime] = None

    def _is_token_expired(self) -> bool:
        if not self.token_expiry:
            return True
        # Refresh 1 minute before expiry
        return self.token_expiry < datetime.utcnow() + timedelta(minutes=1)

    def _refresh_access_token(self) -> None:
        if not self.refresh_token:
            raise HubAuthenticationError("No refresh token available")

        try:
            response = requests.post(
                f"{self.base_url}/auth/refresh",
                json={"refresh_token": self.refresh_token},
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]  # New refresh token
            expires_in = data["expires_in"]
            self.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        except requests.RequestException as e:
            raise HubAuthenticationError("Token refresh failed") from e

    def request(self, method: str, endpoint: str, **kwargs) -> dict:
        # Check if token needs refresh
        if self._is_token_expired():
            self._refresh_access_token()

        headers = kwargs.get("headers", {})
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            response = requests.request(
                method, f"{self.base_url}{endpoint}", headers=headers, **kwargs
            )

            # Handle 401 - token expired during request
            if response.status_code == 401:
                self._refresh_access_token()
                # Retry once with new token
                return self.request(method, endpoint, **kwargs)

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise HubNetworkError("Request failed") from e
```

**Token Storage Recommendations**

**Browser/JavaScript**:
- **Access Token**: Store in memory (not `localStorage` or `sessionStorage`) to reduce XSS risk
- **Refresh Token**: Store in HTTP-only, Secure, SameSite cookie (server-managed) or in-memory
- **Avoid**: Storing tokens in `localStorage` (vulnerable to XSS)

**Node.js/Server-Side**:
- **Access Token**: In-memory cache (with TTL)
- **Refresh Token**: Secure key-value store (Redis, database) or encrypted file
- **Avoid**: Hardcoding tokens in code or environment variables (use secrets management)

**Python**:
- **Access Token**: In-memory cache (with TTL)
- **Refresh Token**: Secure key-value store or encrypted file
- **Avoid**: Storing tokens in plain text files

**Error Handling**

**Refresh Token Expired** (`REFRESH_TOKEN_EXPIRED`):
- SDK MUST throw `HubAuthenticationError`
- Application MUST prompt user to re-authenticate (login again)
- SDK MUST NOT retry automatically

**Refresh Token Revoked** (`REFRESH_TOKEN_REVOKED`):
- SDK MUST throw `HubAuthenticationError`
- Application MUST prompt user to re-authenticate
- SDK MUST NOT retry automatically

**Network Errors During Refresh**:
- SDK MUST throw `HubNetworkError` or `HubTimeoutError`
- Application MAY retry refresh (with exponential backoff)
- Application MUST NOT retry indefinitely

**Concurrent Refresh Prevention**

SDKs MUST prevent multiple concurrent refresh attempts:

```typescript
class DataHubClient {
  private refreshPromise: Promise<void> | null = null;

  private async refreshAccessToken(): Promise<void> {
    // If refresh already in progress, wait for it
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = this._doRefresh();
    try {
      await this.refreshPromise;
    } finally {
      this.refreshPromise = null;
    }
  }
}
```

**Configuration Options**

SDKs SHOULD support the following configuration options:

- `refresh_threshold_seconds`: Time before expiry to refresh token (default: 60 seconds)
- `max_refresh_retries`: Maximum retry attempts for refresh (default: 1)
- `refresh_backoff_ms`: Backoff delay for refresh retries (default: [1000, 2000])
- `auto_refresh`: Enable/disable automatic token refresh (default: true)

---

### 20.3 Error Handling & Exceptions

The SDKs MUST map the API error envelope (§13.1) into **structured exceptions** in a
consistent way across languages, so that:

- Callers can handle common error categories (auth, validation, rate-limit, not-found,
  server errors) in a predictable manner.
- Retryable errors are distinguishable from non-retryable errors.
- Logging and observability can be implemented without leaking sensitive data.

This section refines the error model for the JS and Python SDKs.

All official SDKs (e.g. TypeScript/JavaScript, Python, Java) MUST implement a consistent error model.


---

#### 20.3.1 SDK error class hierarchy

Each SDK MUST expose:

- A single **base error class**, e.g. `HubError` (or `DataHubError`), from which all SDK-specific errors inherit.
- A set of **standard subclasses**:

  - `HubHttpError` – generic HTTP error (holds `status_code`, raw response).
  - `HubApiError` – well-formed API error with `error.code`, `message`, `details`.
    - `HubAuthenticationError` (401)
    - `HubAuthorizationError` (403)
    - `HubNotFoundError` (404)
    - `HubValidationError` (400 on validation-related codes)
    - `HubConflictError` (409 – e.g. optimistic concurrency, duplicate resources)
    - `HubRateLimitError` (429)
    - `HubServerError` (5xx not covered by more specific types)
  - `HubNetworkError` – network-level issues (DNS failures, connection refused, TLS errors).
  - `HubTimeoutError` – request timed out at transport or SDK level.
  - `HubConfigurationError` – misconfigured SDK/client (missing API key, invalid base URL, etc.).
  - `HubJobFailedError` – when a helper method that waits on a job detects a `FAILED` final job status.

Language-specific naming may vary slightly (e.g. `HubError` vs `HubException`) but the taxonomy MUST be preserved.


**JavaScript / TypeScript**

```ts
class DataHubError extends Error {
  code: string;              // API error code (e.g. "RATE_LIMIT_EXCEEDED") or synthetic
  httpStatus?: number;       // HTTP status, if available
  requestId?: string;        // from response
  details?: unknown;         // structured `details` object, if provided
  cause?: unknown;           // underlying error / transport error

  constructor(
    code: string,
    message: string,
    options?: {
      httpStatus?: number;
      requestId?: string;
      details?: unknown;
      cause?: unknown;
    }
  ) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.httpStatus = options?.httpStatus;
    this.requestId = options?.requestId;
    this.details = options?.details;
    this.cause = options?.cause;
    
    // Maintains proper stack trace for V8 engines
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  toJSON(): Record<string, unknown> {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      httpStatus: this.httpStatus,
      requestId: this.requestId,
      details: this.details,
    };
  }
}

class NetworkError extends DataHubError {
  /** Network-level errors (DNS, connection refused, TLS errors). */
}

class TimeoutError extends NetworkError {
  /** Request timed out at transport or SDK level. */
}

class ApiError extends DataHubError {
  /** Well-formed API error with error.code, message, details. */
}

class AuthError extends ApiError {
  /** Authentication or authorization errors (401/403). */
}

class ValidationError extends ApiError {
  /** Input validation errors (400, VALIDATION_ERROR, CONTRACT_VALIDATION_FAILED, etc.). */
}

class RateLimitError extends ApiError {
  /** Rate limit exceeded (429, RATE_LIMIT_EXCEEDED). */
}

class NotFoundError extends ApiError {
  /** Resource not found (404). */
}

class ConflictError extends ApiError {
  /** Conflict errors (409, IDEMPOTENCY_CONFLICT, COMPLIANCE_BLOCKED, etc.). */
}

class ServerError extends ApiError {
  /** Server errors (5xx). */
}

class RetryAbortedError extends DataHubError {
  /** Retries exhausted in SDK. */
}
```

**JavaScript/TypeScript-Specific Implementation Notes**

- **Standard Error compatibility**: All SDK errors extend `Error` and are compatible with standard JavaScript error handling:
  - Can be caught with `catch (error)` and checked with `error instanceof DataHubError`.
  - `error.stack` is available for debugging (in Node.js and modern browsers).
  - `error.name` is set to the class name (e.g., `"ValidationError"`).
- **Serialization**: Errors are JSON-serializable via `toJSON()` method:
  - Use `JSON.stringify(error)` or `error.toJSON()` for logging/transmission.
  - Stack traces are **not** included in JSON serialization (only in `error.stack` property).
- **Logging**: SDK uses a configurable logger:
  - Default: No-op logger (no logging by default).
  - Can be configured with a logger instance (e.g., `winston`, `pino`, `console`).
  - Error logs include: `error.code`, `error.httpStatus`, `error.requestId`, `error.message`.
  - Stack traces are logged at `error` level; error details (without stack) at `warn` level.
- **Network vs. API timeouts**:
  - **Network timeout**: Raised as `TimeoutError` when the HTTP client times out (e.g., `fetch` timeout, connection timeout).
  - **API timeout**: If the API returns a timeout error (e.g., `DQ_TIMEOUT`, `COMPLIANCE_TIMEOUT`), it is raised as `ServerError` with `code = "DQ_TIMEOUT"` (not `TimeoutError`).
  - SDK distinguishes: `TimeoutError` = transport timeout; `ServerError` with timeout code = API-reported timeout.

**Python**

```python
class DataHubError(Exception):
    def __init__(self, code: str, message: str, http_status: int | None = None,
                 request_id: str | None = None, details: dict | None = None, cause: Exception | None = None):
        self.code = code
        self.http_status = http_status
        self.request_id = request_id
        self.details = details
        self.cause = cause
        super().__init__(message)
    
    def __str__(self) -> str:
        """String representation for logging and display."""
        return f"{self.__class__.__name__}(code={self.code}, message={str(super())})"
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"{self.__class__.__name__}(code={self.code!r}, http_status={self.http_status}, request_id={self.request_id!r})"


class NetworkError(DataHubError):
    """Network-level errors (DNS, connection refused, TLS errors)."""
    pass


class TimeoutError(NetworkError):
    """Request timed out at transport or SDK level."""
    pass


class ApiError(DataHubError):
    """Well-formed API error with error.code, message, details."""
    pass


class AuthError(ApiError):
    """Authentication or authorization errors (401/403)."""
    pass


class ValidationError(ApiError):
    """Input validation errors (400, VALIDATION_ERROR, CONTRACT_VALIDATION_FAILED, etc.)."""
    pass


class RateLimitError(ApiError):
    """Rate limit exceeded (429, RATE_LIMIT_EXCEEDED)."""
    pass


class NotFoundError(ApiError):
    """Resource not found (404)."""
    pass


class ConflictError(ApiError):
    """Conflict errors (409, IDEMPOTENCY_CONFLICT, COMPLIANCE_BLOCKED, etc.)."""
    pass


class ServerError(ApiError):
    """Server errors (5xx)."""
    pass


class RetryAbortedError(DataHubError):
    """Retries exhausted in SDK."""
    pass
```

**Python-Specific Implementation Notes**

- **Serialization**: Python exceptions are **not JSON-serializable by default**. For logging or API responses:
  - Use `str(error)` or `error.__dict__` to extract fields.
  - SDK provides a helper method: `error.to_dict()` that returns a serializable dictionary.
- **Logging**: SDK uses Python's standard `logging` module:
  - Logger name: `datahub_interoperability`
  - Error logs include: `error.code`, `error.http_status`, `error.request_id`, `error.message`.
  - Stack traces are logged at `ERROR` level; error details (without stack) at `WARN` level.
- **Network vs. API timeouts**:
  - **Network timeout**: Raised as `TimeoutError` when the HTTP client times out (e.g., connection establishment, no response within SDK timeout).
  - **API timeout**: If the API returns a timeout error (e.g., `DQ_TIMEOUT`, `COMPLIANCE_TIMEOUT`), it is raised as `ServerError` with `code = "DQ_TIMEOUT"` (not `TimeoutError`).
  - SDK distinguishes: `TimeoutError` = transport timeout; `ServerError` with timeout code = API-reported timeout.

Notes:

- Additional, more specific subclasses MAY be added later (e.g. `FileTooLargeError`,
  `ComplianceBlockedError`) as long as they inherit from the appropriate parent
  (`ValidationError`, `ConflictError`, etc.).
- The base `DataHubError` type MUST be catchable to handle “any SDK error” across all
  languages.

---

#### 20.3.2 Mapping API errors to SDK exceptions

The API returns errors in a standard envelope:

```json
{
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded for this tenant and endpoint category.",
  "http_status": 429,
  "request_id": "req-12345",
  "details": { ... }
}
```

SDKs MUST:

1. **Parse JSON body** for any non-2xx HTTP status.
2. Extract `code`, `message`, `http_status` (or actual HTTP status), `request_id`, `details`.
3. Map them to SDK exceptions as follows:

**By HTTP status**

- 400 → `ValidationError`
- 401 → `AuthError`
- 403 → `AuthError`
- 404 → `NotFoundError`
- 409 → `ConflictError`
- 429 → `RateLimitError`
- 5xx → `ServerError`

**By API `code`** (refining the class)

Within the HTTP-based class, the `code` field MUST be preserved and MAY further refine the class:

- `AUTH_UNAUTHORIZED`, `AUTH_FORBIDDEN` → `AuthError`
- `VALIDATION_ERROR`, `CONTRACT_VALIDATION_FAILED` → `ValidationError`
- `RATE_LIMIT_EXCEEDED` → `RateLimitError`
- `FILE_TOO_LARGE` → subclass of `ValidationError` (e.g. `FileTooLargeError`) if implemented.
- `COMPLIANCE_BLOCKED` → subclass of `ConflictError` (e.g. `ComplianceBlockedError`) if implemented.
- `IDEMPOTENCY_CONFLICT` → `ConflictError`

**Unmapped / unknown codes**

- If the API returns an unknown `code`:
  - SDK selects the appropriate HTTP-derived subclass (e.g. `ValidationError` for 400, `ServerError` for 500).
  - `error.code` is set to the raw API `code` string.
- For responses with no JSON body or malformed JSON:
  - SDK throws a `ServerError` or generic `ApiError` with a synthetic `code` (e.g. `UNPARSEABLE_ERROR_RESPONSE`).

**Network / transport errors**

- DNS, TLS, connection reset, etc. → `NetworkError` (with `cause` set).
- Client-side timeouts → `TimeoutError`.

In all cases:

- `requestId` MUST be populated from the response headers or body when available.
- Callers MUST be able to distinguish:
  - `ApiError` subclasses (server reached, responded with error),
  - `NetworkError` / `TimeoutError` (server may not have been reached).

---

#### 20.3.3 Retry behavior in SDKs

Retry configuration is surfaced via the SDK clients (see §20.2):

- `max_retries` / `retries` configuration options control **automatic retries**.
- Defaults:
  - `max_retries = 0` (i.e. **automatic retries disabled** by default).
  - Callers opt in explicitly.

**Retryable conditions**

When automatic retries are enabled, SDKs MAY retry only when both:

1. The request is **idempotent**:
   - GET, HEAD, OPTIONS.
   - POST/PUT/PATCH when:
     - An idempotency key is used and documented as safe, or
     - The documentation explicitly marks the operation as idempotent.
2. The error is considered **transient**:
   - `NetworkError` or `TimeoutError`.
   - `ServerError` (5xx) excluding 501/505 or explicitly non-retryable statuses.
   - `RateLimitError` (`http_status = 429`, `code = RATE_LIMIT_EXCEEDED`), respecting `Retry-After` when present.

**Non-retryable conditions**

SDKs MUST NOT automatically retry:

- Validation / client-side errors (4xx except 408/429):
  - `ValidationError`, `AuthError`, `NotFoundError`, `ConflictError`, etc.
- Errors with codes indicating logical conflicts, e.g.:
  - `IDEMPOTENCY_CONFLICT`.

**Backoff strategy**

- Exponential backoff with jitter:
  - `delay = min(base * 2^attempt, max_backoff_ms)`
  - Jitter: random within ±50% of computed delay.
- If the response includes a `Retry-After` header:
  - The SDK MUST respect it and delay at least that duration, or the computed backoff, whichever is greater.

**Exhausted retries**

- When all retry attempts are exhausted:
  - SDK throws `RetryAbortedError` with:
    - `lastError` / `cause` set to the final error.
- Callers can:
  - Catch `RetryAbortedError`,
  - Inspect the underlying `lastError`,
  - Decide whether to perform further manual retries or propagate the error.

**Manual retries**

- Callers are always free to implement their own retry loops around SDK calls.
- SDK docs MUST clearly identify:
  - Which errors are usually transient (recommended to retry),
  - Which are permanent (do not retry).

---

#### 20.3.4 SDK logging for errors

Error-related logging in SDKs MUST be:

- **Opt-in and configurable**, not noisy by default.
- **Safe by default**, with no secrets or PII in logs.

**Log contents**

When logging is enabled (see §20.7 for full logging/instrumentation):

- At `DEBUG` level, SDK MAY log:
  - Request method and path (without secret query params).
  - HTTP status code.
  - Retry attempts:
    - `attempt number`, `error type`, `next backoff ms`.

- At `INFO` level, SDK MAY log:
  - High-level lifecycle events (client initialization, configuration warnings).

- At `WARN`/`ERROR` level, SDK MAY log:
  - Final errors after retries exhausted.
  - Deserialization / parsing issues.

**Redaction rules**

SDK MUST NOT log:

- Authorization headers, API tokens, refresh tokens, cookies.
- Raw request/response bodies containing:
  - Contract content.
  - Dataset content.
  - Any user data, unless the user has explicitly enabled a debug mode clearly marked as unsafe.

**Logger integration**

- JS SDK:
  - Accepts a `logger` and `logLevel` in configuration (see §20.2 & §20.7).
- Python SDK:
  - Uses a named logger (e.g. `datahub_interoperability`) with standard `logging` handlers.

In all cases, error logs SHOULD include:

- `requestId` (if available).
- SDK client name and version.
- Optionally `tenant_id` (if derived from token claims and non-sensitive).

This ensures that SDK users can:

- Reliably catch and classify errors.
- Implement robust retry strategies.
- Integrate with their existing logging and observability stacks without leaking sensitive information.


---

### 20.4 Core SDK Domains & Methods

The SDKs MUST provide **organized, domain-based clients** rather than a flat list of methods.

A suggested structure:

- `client.files`
- `client.contracts`
- `client.assets`
- `client.dq`
- `client.compliance`
- `client.jobs`
- `client.marketplace`
- `client.semantic`

#### 20.4.1 Files

Wraps `/files/init`, `/files/{id}/complete`, and related metadata endpoints.

Core capabilities:

- `init_upload(...)`:
  - Parameters: file name, size, content type, intended use (intake vs external scan).
  - Returns:
    - `file_id`
    - Pre-signed URLs and chunk size info.
- `upload_file(...)` (**high-level helper**):
  - Given a local file path (Node/Python) or Blob (browser), the SDK:
    - Calls `init_upload`.
    - Performs chunked/multi-part upload with retries.
    - Calls `complete` when finished.
    - Returns final file descriptor.
- `get_file_metadata(file_id)`:
  - Read-only metadata (no raw content).
- Optional: `delete_file(file_id)` (if supported by API).

#### 20.4.2 Contracts & Assets

Wraps `/contracts`, `/assets` and related APIs.

Core methods:

- `create_contract_from_file(raw_contract_path_or_content, options)`:
  - Uploads raw contract content.
  - Calls contract validation endpoint (DataContract CLI integration).
  - Returns contract object (HubContract + metadata).
- `update_contract(contract_id, updates)`:
  - PATCH-like behavior; re-validates contract as required.
- `get_contract(contract_id)` / `list_contracts(filters)`.

- `create_asset(...)`:
  - Associate contract + dataset (file or external reference).
- `get_asset(asset_id)` / `list_assets(filters)`:
  - Should expose:
    - Contract.
    - DQ & compliance latest status.
    - Marketplace flags.
- `publish_asset(asset_id)` / `unpublish_asset(asset_id)` (or via marketplace domain).

#### 20.4.3 DQ (Data Quality)

Wraps `/dq-runs` and DQ-related endpoints.

Core methods:

- `run_dq(asset_id_or_file_id, profile="intake_basic", *, external=False)`:
  - For in-platform assets:
    - Triggers DQ run on associated dataset.
  - For external scan-only:
    - Takes `file_id` from `files` helper and runs DQ without storing dataset.
  - Returns:
    - `dq_run_id`
    - Underlying `job_id`.

- `get_dq_run(dq_run_id)`:
  - Returns:
    - Status.
    - Summary metrics.
    - Link to job.

- `wait_for_dq_run(dq_run_id, poll_interval=..., timeout=...)` (**high-level helper**):
  - Polls `Job` status using recommended backoff.
  - Returns final DQRun object or raises on timeout.

#### 20.4.4 Compliance

Wraps `/compliance-runs`.

Core methods:

- `run_compliance(asset_id_or_file_id, regulations=None, *, external=False)`:
  - Similar to `run_dq`.
  - `regulations` can specify GDPR/LGPD/CCPA profiles, etc.
- `get_compliance_run(run_id)` and `wait_for_compliance_run(...)` with same pattern.

#### 20.4.5 Jobs

Wraps `/jobs`.

Core methods:

- `get_job(job_id)`:
  - Returns Job (status, details).
- `wait_for_job(job_id, poll_interval=..., timeout=...)`:
  - Implements the **polling with backoff** rules from §14.4:
    - Start 1–2 seconds, backoff to max 10–15 seconds.
- `list_jobs(filters)` (optional for MVP).

#### 20.4.6 Marketplace & Entitlements

Wraps `/listings`, `/orders`, `/entitlements` (names per API spec).

Core methods:

- `list_public_listings(filters)`.
- `get_listing(listing_id)`.
- `request_access(listing_id)`:
  - For `FREE_AUTO_APPROVE`:
    - Immediately returns active entitlement.
  - For `REQUEST_APPROVAL`:
    - Creates order with `status=REQUESTED`.
- `get_entitlements(filters)` and `get_entitlement(entitlement_id)`:
  - For “My Data” view.
- `revoke_entitlement(entitlement_id)` (if allowed for providers).

#### 20.4.7 Semantic

Wraps semantic endpoints (JSON-LD, RDF, SPARQL).

Core methods (MVP):

- `resolve_uri(uri_or_iri)`:
  - Returns semantic representation (JSON-LD) for that resource.
- `get_contract_semantic_view(asset_or_contract_id)`:
  - Convenience to fetch ontology view for an asset/contract.
- Optional/future:
  - SPARQL query helper:
    - `semantic.query_sparql(query_string)`.

---

### 20.5 High-Level Flow Helpers

In addition to low-level methods, SDKs SHOULD provide helpers that implement **key user journeys** end-to-end, especially for developers/automations.

Examples:

#### 20.5.1 Data-First Intake Helper

`client.intake.data_first(...)`:

- Inputs:
  - Local file path (Py/Node) or stream.
  - Optional:
    - Pre-existing contract template.
    - DQ/compliance options.
- Behavior:
  1. Upload file via `files.upload_file`.
  2. Trigger `schema inference`, `DQ`, `Compliance` jobs as required (API).
  3. Wait for jobs (with `wait_for_job`).
  4. Construct initial `HubContract` draft (from API results) and return:
     - Contract draft (for UI or further editing).
     - DQ/compliance summaries.
     - Asset ID if created.
- This helper MUST NOT hide errors:
  - Raises on `COMPLIANCE_BLOCKED`, DQ engine errors, etc.

#### 20.5.2 Contract-First Intake Helper

`client.intake.contract_first(...)`:

- Inputs:
  - Raw contract file or object.
  - Data file path or reference.
- Pattern similar to data-first, but:
  - Validates contract first.
  - Then uploads data and reconciles schema.

#### 20.5.3 External Scan-Only Check

`client.scan_only.run_checks(...)`:

- Inputs:
  - File path or stream.
  - DQ profile, compliance profile.
- Workflow:
  - Upload file (to ephemeral/scan bucket).
  - Run DQ + Compliance with external mode.
  - Wait for jobs.
  - Delete file (or rely on ephemeral lifetime).
  - Return combined report object (no asset created).

---

### 20.6 Async model & concurrency

The SDKs MUST follow a clear, modern async model so that:

- All network operations are non-blocking where appropriate.
- Long-running flows (uploads, job polling) support **progress reporting**.
- Callers can **cancel** operations when they are no longer needed.
- Concurrency behavior is predictable and configurable.

This section refines the async behavior for JavaScript/TypeScript and Python SDKs.

---

#### 20.6.1 JavaScript / TypeScript async model

**Primary pattern: Promises + async/await**

- All SDK methods that perform network I/O MUST return a `Promise<T>`.
- Typical usage:

```ts
const asset = await client.assets.getAsset(assetId);
```

- High-level helpers (e.g. `waitForJob`, `uploadFile`) also return `Promise<T>`.

**Callbacks**

- The SDK SHOULD NOT rely on old-style Node callbacks `(err, result)` as the primary API.
- Where callbacks are useful (e.g. progress notifications), they are provided as **optional arguments**, not as the core async mechanism.

Example:

```ts
await client.files.uploadFile({
  file,
  purpose: "INTAKE",
  onProgress: (p) => {
    console.log(`Uploaded ${p.bytesUploaded} / ${p.bytesTotal} (${p.percent}%)`);
  },
});
```

**Concurrency**

- The SDK itself does not create background worker pools or threads.
- Concurrency is driven by the caller (e.g. `Promise.all`):

```ts
await Promise.all(assetIds.map(id => client.assets.getAsset(id)));
```

- Bulk helpers (if provided) MUST document any internal concurrency limits (e.g. max 5 parallel requests) and allow overriding via options.

---

#### 20.6.2 Python async model

**Primary pattern: synchronous client (MVP)**

- MVP Python SDK provides a synchronous client (`DataHubClient`) using standard blocking I/O (e.g. `requests` or `httpx` in sync mode).
- All methods block the calling thread until the HTTP request completes:

```python
asset = client.assets.get_asset(asset_id)
```

**Optional future pattern: async client**

- A separate `AsyncDataHubClient` MAY be introduced later using `asyncio` (`async def`, `await`) and an async HTTP library (`httpx.AsyncClient`).
- If/when introduced:
  - Async client API SHOULD mirror the synchronous client’s method names and signatures, returning `await`-able coroutines instead of plain values.

**Concurrency & cancellation in Python (MVP)**

- Concurrency is achieved by the caller using:
  - Threads or processes (e.g. `concurrent.futures`), or
  - An async client (if/when available).
- Cancellation is handled via:
  - Timeouts (per-request or global).
  - User-implemented thread/task cancellation, not built into the sync methods.

---

#### 20.6.3 Progress reporting for long operations

Long-running operations include:

- File uploads (possibly multi-GB, chunked).
- Job polling (`waitForJob`, `waitForDqRun`, `waitForComplianceRun`).
- Bulk operations (e.g. migrating many assets).

**JavaScript / TypeScript**

For operations that can be meaningfully tracked, the SDK MUST support an optional `onProgress` callback.

**File uploads**

Method variant (example):

```ts
await client.files.uploadFile({
  file,
  purpose: "INTAKE",
  onProgress: (progress) => {
    // progress: { bytesUploaded, bytesTotal, percent, chunkIndex?, totalChunks? }
  },
  signal, // optional AbortSignal (see below)
});
```

- `onProgress` is called periodically as chunks are sent.
- The SDK SHOULD:
  - Emit at least one progress event per chunk.
  - Emit a final event with `percent = 100` on success.

**Job polling**

For helpers that wrap polling (e.g. `waitForJob`):

```ts
await client.jobs.waitForJob(jobId, {
  pollIntervalMs: 2000,
  onProgress: (status) => {
    // status: { jobId, state, attempts?, startedAt?, updatedAt? }
  },
  signal,
});
```

- `onProgress` is called after each poll with the latest job status.
- Callers can use this to update UI or logs.

**Python**

For MVP synchronous client, progress is provided via optional callbacks:

**File uploads**

```python
def on_progress(progress):
    print(f"Uploaded {progress.bytes_uploaded} / {progress.bytes_total} ({progress.percent}%)")

client.files.upload_file(
    path="/tmp/data.csv",
    purpose="INTAKE",
    progress_callback=on_progress,
)
```

**Job polling**

```python
client.jobs.wait_for_job(
    job_id,
    poll_interval=2.0,
    progress_callback=lambda status: print(status.state),
)
```

- Progress callbacks are called synchronously within the upload/polling loop.

---

#### 20.6.4 Cancellation support

SDKs MUST provide a way for callers to **cancel** long-running operations, especially uploads and polling.

**JavaScript / TypeScript**

- All networked SDK methods MUST accept an optional `AbortSignal`:

```ts
const controller = new AbortController();

const promise = client.files.uploadFile({
  file,
  purpose: "INTAKE",
  signal: controller.signal,
});

setTimeout(() => controller.abort(), 5000); // cancel after 5s

await promise; // will reject with a cancellation error
```

Requirements:

- Methods must:
  - Wire `signal` through to the underlying HTTP client (`fetch`, `axios`, or similar) where supported.
  - Check `signal.aborted` in multi-step flows (chunked uploads, polling) between steps and abort cleanly.
- On cancellation:
  - Promise MUST reject with a `DataHubError` subclass, typically:
    - `TimeoutError` (if due to timeout), or
    - A dedicated `CancelledError` if introduced, or
    - A `NetworkError` with a specific `code = "REQUEST_CANCELLED"`.
  - The type and `code` MUST be documented and stable.

**Python**

For the synchronous MVP client:

- Per-request **timeouts** are the primary mechanism for limiting how long calls can block:

```python
client = DataHubClient(
    base_url=...,
    api_token=...,
    timeout=30.0,  # seconds
)
```

- Methods MAY accept an optional `timeout` override per call.
- Cancellation is managed by caller, typically by:
  - Running SDK calls in threads/tasks and cancelling those tasks.
  - Using an async client in the future (`AsyncDataHubClient`) with `asyncio` cancellation:

    ```python
    task = asyncio.create_task(async_client.files.upload_file(...))
    task.cancel()
    ```

If an operation is cancelled:

- SDK SHOULD raise a `TimeoutError` or `DataHubError` with `code = "REQUEST_CANCELLED"` where applicable.
- This behavior MUST be documented.

---

With this async model:

- JS/TS SDK uses idiomatic `Promise` / `async` / `await` with optional `onProgress` and `AbortSignal`.
- Python SDK provides a clear synchronous story for MVP, with room for an async variant.
- Long operations expose progress hooks and do not trap callers in uninterruptible loops.
- Cancellation and timeouts are explicit, documented, and consistent with the overall error model (§20.3).


---

### 20.7 Logging & Instrumentation in SDKs

- SDKs SHOULD provide **optional** logging hooks:

  - Users can pass a logger object or callback:
    - JS: e.g. `logger.debug/info/warn/error`.
    - Python: standard `logging.Logger`.
  - SDK logs MAY include:
    - Request method, route, status code, latency.
    - `request_id` from responses.
  - SDK logs MUST NOT include:
    - Raw data payloads.
    - Raw contract content in production settings (only if user explicitly enables debug).

- SDKs MAY expose hooks for:
  - Metrics integration (e.g. counters/timers using Prometheus client libraries).
  - Request/response middleware for advanced users.

---

### 20.8 Versioning & Compatibility

- SDK versions MUST follow semantic versioning:
  - `MAJOR.MINOR.PATCH`.
- `MAJOR` bumps:
  - Correspond to breaking changes in SDK API.
  - MAY align with new `/api/v2` endpoints, but v1 support should remain for a defined period.
- `MINOR` bumps:
  - Add new methods or optional parameters in backward-compatible ways.
- `PATCH`:
  - Bug fixes and minor improvements with no API changes.

Compatibility expectations:

- A given SDK major version (e.g. `1.x`) MUST fully support `/api/v1`.
- When `/api/v2` is introduced:
  - Either:
    - Same SDK major version supports v1+v2 with configuration, or
    - SDK v2 targets API v2, with explicit migration guidance.

Release & documentation:

- Each release MUST:
  - Document changes in a changelog.
  - Update examples and reference docs.
  - Clearly state supported API versions and minimum language/runtime versions.

---

### 20.9 Distribution & Packaging

- JavaScript SDK:
  - Published to npm under an appropriate scoped package.
  - MUST provide:
    - TypeScript declarations.
    - ES module and CommonJS builds (or ESM-only if clearly documented).
- Python SDK:
  - Published to PyPI.
  - Standard install via:
    - `pip install datahub_interoperability` (or chosen name).

- Both SDKs MUST:
  - Include license and basic metadata.
  - Be tested via CI against:
    - At least one staging/test instance of the API.
  - Provide clear “Getting Started” examples and code snippets for:
    - Authenticating.
    - Uploading a file.
    - Creating a contract.
    - Running DQ & compliance.
    - Using the marketplace APIs.


---

_End of System Requirements._
