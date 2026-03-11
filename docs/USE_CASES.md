# Use Cases

**Last Updated**: 2026-03-06
**Version**: 2.3.0

---

## Overview

This document provides a comprehensive catalog of use cases for the Data Interoperability Hub platform. The platform supports **~109 total use cases** including authentication and access for unauthenticated and non-registered users, plus all features and strategic differentiators.

**Note on Scheduled Ingestion Execution Model**: Scheduled ingestion runs are executed by **Prefect workers** via the **Internal Worker API** (`/api/v1/scheduled-ingestions/internal/*`). The execution model is **Prefect worker → Hub API**, where Prefect workers execute `scheduled_ingestion_full_flow` (HTTP-only, no Django) and communicate with the Hub API via internal endpoints. Authentication uses worker API keys (`HUB_WORKER_API_KEY` or API key with scope `scheduled_ingestion:internal`), and internal worker endpoints have **no rate limit**. See [Scheduled Ingestion Worker API](SCHEDULED_INGESTION_WORKER_API.md) and [Services Architecture](SERVICES_ARCHITECTURE.md#prefect-integration-service-prefect-integration-service) for details.

**Note on Scheduled Export Execution Model**: Scheduled export runs are executed by **Prefect workers** via the **Internal Worker API** (`/api/v1/scheduled-exports/internal/*`). The execution model is **Prefect worker → Hub API**, where Prefect workers execute `scheduled_export_full_flow` (HTTP-only, no Django) and communicate with the Hub API via internal endpoints. Authentication uses worker API keys (`HUB_WORKER_API_KEY` or API key with scope `scheduled_export:internal`), and internal worker endpoints have **no rate limit**. Destination connectors (S3, GCS, Azure Blob) are implemented in the Prefect worker. Hub serves as the source of truth for configuration and state. See [Scheduled Export API Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_EXPORT.md) and [Services Architecture](SERVICES_ARCHITECTURE.md#scheduled-export-execution-model) for details.

**Use Case Statistics**:
- **Total Use Cases**: ~109
- **High Priority**: ~64
- **Medium Priority**: ~32
- **Low Priority**: ~13
- **MVP Status**: ~74
- **Post-MVP Status**: ~35

**Cross-References**:
- **[Marketplace Use Cases](MARKETPLACE_USE_CASES.md)** - External marketplace integration use cases (publish to external marketplace, discover and import, sync, federated assets, semantic discovery).
- **[Resource Pickers (Component Docs)](UI/RESOURCE_PICKERS.md)** - Searchable pickers (AssetPicker, ContractPicker, DatasetPicker, FilePicker) used in ODPS upload, asset attach, DQ/Compliance/Access Request, Scheduled Export, Retention, Dataset edit, ODPS Link flows.

---

## Table of Contents

1. [Use Case Categories](#use-case-categories)
2. [Authentication & Access Use Cases](#authentication--access-use-cases)
3. [Asset Management Use Cases](#asset-management-use-cases)
4. [Contract Management Use Cases](#contract-management-use-cases)
5. [Data Quality Use Cases](#data-quality-use-cases)
6. [Compliance Use Cases](#compliance-use-cases)
7. [Marketplace Use Cases](#marketplace-use-cases)
8. [AI/ML Use Cases](#aiml-use-cases)
9. [Social Feature Use Cases](#social-feature-use-cases)
10. [Data Mesh Use Cases](#data-mesh-use-cases)
11. [Virtualization Use Cases](#virtualization-use-cases)
12. [Advanced Marketplace Use Cases](#advanced-marketplace-use-cases)
13. [Advanced Governance Use Cases](#advanced-governance-use-cases)
14. [Advanced Observability Use Cases](#advanced-observability-use-cases)
15. [Integration Ecosystem Use Cases](#integration-ecosystem-use-cases)
16. [Developer Experience Use Cases](#developer-experience-use-cases)
17. [Use Cases Previously Referenced Only (Documentation Completeness)](#use-cases-previously-referenced-only-documentation-completeness)
18. [Use Case Matrix](#use-case-matrix)

---

## Use Case Categories

### Category 1: Asset Management
Use cases related to creating, managing, and organizing data assets.

### Category 2: Contract Management
Use cases related to creating, validating, and managing data contracts.

### Category 3: Data Quality
Use cases related to data quality checks, monitoring, and remediation.

### Category 4: Compliance
Use cases related to compliance scanning, reporting, and governance.

### Category 5: Marketplace
Use cases related to publishing, discovering, and purchasing data assets.

### Category 6: AI/ML **NEW**
Use cases related to AI/ML-powered features (natural language search, schema matching, recommendations, auto-classification).

### Category 7: Social Features **NEW**
Use cases related to ratings, reviews, communities, and collaboration.

### Category 9: Data Mesh **NEW**
Use cases related to data mesh domains, federated governance, and topology.

### Category 10: Virtualization **NEW**
Use cases related to virtual datasets, federated queries, and data federation.

### Category 11: Advanced Marketplace **NEW**
Use cases related to usage-based pricing, data previews, and trust signals.

### Category 12: Advanced Governance **NEW**
Use cases related to automated compliance, GDPR workflows, and consent management.

### Category 13: Advanced Observability **NEW**
Use cases related to reliability scores, cost tracking, and predictive alerts.

### Category 14: Integration Ecosystem **NEW**
Use cases related to connectors, BI integration, and reverse ETL.

### Category 15: Developer Experience **NEW**
Use cases related to plugins, SDKs, CLI, and developer portal.

### Category 0: Authentication & Access
Use cases related to unauthenticated visitors, registration, login, session management, and public access. These flows apply to **non-registered** and **unauthenticated** users before they assume a role-based persona.

---

## Authentication & Access Use Cases

### UC-AUTH-001: User Registers (Self-Service Sign-Up)

**ID**: UC-AUTH-001
**Title**: User Registers (Self-Service Sign-Up)
**Persona**: Visitor, Prospect
**Priority**: High
**Status**: MVP

**Description**:
A first-time visitor creates an account via the registration endpoint. Registration may be enabled or disabled per deployment; when disabled, users are created by Tenant Admin or Platform Admin only.

**Preconditions**:
- User **not authenticated**
- Registration feature enabled (if deployment supports self-signup)
- Valid email and password meeting policy (e.g. complexity, length)

**Main Flow**:
1. User navigates to registration page or invokes `POST /api/v1/auth/register/`
2. User provides email, password, and optional display name
3. System validates email format and password policy
4. System checks email is not already registered
5. If no tenant_id provided: system creates personal tenant and assigns DATA_PROVIDER and DATA_CONSUMER; if tenant_id provided: user associated with that tenant
6. System sets user status (e.g. ACTIVE or PENDING_VERIFICATION per configuration)
7. User receives confirmation (e.g. email or success response)
8. User can log in (UC-AUTH-002)

**Alternate Flows**:
- **A1**: Registration disabled → system returns 403 or UI shows "Contact administrator"
- **A2**: Email already exists → system returns 400 with clear message
- **A3**: Password policy not met → system returns 400 with policy description
- **A4**: Invalid tenant or invitation required → system returns 400

**Postconditions**:
- User account created
- User has tenant (personal or provided)
- User can authenticate (UC-AUTH-002)

**Related Use Cases**: UC-AUTH-002, JOURNEY-TA-001 (admin invite flow)

**Test Traceability**: [TEST_TRACEABILITY.md#uc-auth-001-user-registers-self-service-sign-up](TEST_TRACEABILITY.md#uc-auth-001-user-registers-self-service-sign-up)

---

### UC-AUTH-002: User Logs In

**ID**: UC-AUTH-002
**Title**: User Logs In
**Persona**: Visitor (becomes authenticated user), any registered persona
**Priority**: High
**Status**: MVP

**Description**:
User authenticates with email and password and receives a session or token to access protected resources.

**Preconditions**:
- User **not authenticated** (or re-authenticating)
- User has an existing account (created via UC-AUTH-001 or admin invite)
- Account is active (not disabled or pending verification, per policy)

**Main Flow**:
1. User navigates to login page or invokes `POST /api/v1/auth/login/`
2. User provides email and password
3. System validates credentials
4. System returns access token (and optionally refresh token)
5. Client stores token and uses it for subsequent API requests
6. User is redirected to application home or requested resource
7. User assumes role-based persona (Data Consumer, Data Product Owner, etc.) for further use cases

**Alternate Flows**:
- **A1**: Invalid credentials → system returns 401, user can retry or use "Forgot password" (UC-AUTH-003)
- **A2**: Account disabled or locked → system returns 403 with reason
- **A3**: Multi-factor required → system challenges for MFA then completes login

**Postconditions**:
- User authenticated
- Session/token valid for configured period
- User can perform role-scoped use cases

**Related Use Cases**: UC-AUTH-001, UC-AUTH-003, all persona-specific use cases

**Test Traceability**: [TEST_TRACEABILITY.md#uc-auth-002-user-logs-in](TEST_TRACEABILITY.md#uc-auth-002-user-logs-in)

---

### UC-AUTH-003: User Resets Password

**ID**: UC-AUTH-003
**Title**: User Resets Password
**Persona**: Visitor, any registered user
**Priority**: Medium
**Status**: MVP (if implemented)

**Description**:
User requests a password reset (e.g. via "Forgot password" link), receives a secure link or code, and sets a new password.

**Preconditions**:
- User **not authenticated** (or authenticated and changing password)
- User account exists and is identifiable (e.g. by email)
- Password reset feature enabled (e.g. email delivery configured)

**Main Flow**:
1. User navigates to "Forgot password" or equivalent
2. User submits email (or username) for account
3. System validates that account exists (no disclosure of existence if not)
4. System generates time-limited reset token and sends link/code to registered email
5. User opens link or enters code and is presented with new password form
6. User submits new password meeting policy
7. System invalidates reset token and updates password
8. User can log in with new password (UC-AUTH-002)

**Alternate Flows**:
- **A1**: Reset not enabled → system returns 501 or UI shows "Contact administrator"
- **A2**: Token expired or invalid → user must request reset again
- **A3**: New password does not meet policy → system returns 400

**Postconditions**:
- Password updated
- Previous sessions/tokens optionally invalidated (per policy)

**Related Use Cases**: UC-AUTH-002

**Test Traceability**: [TEST_TRACEABILITY.md#uc-auth-003-user-resets-password](TEST_TRACEABILITY.md#uc-auth-003-user-resets-password)

---

### UC-AUTH-004: Unauthenticated User Accesses Public Resources

**ID**: UC-AUTH-004
**Title**: Unauthenticated User Accesses Public Resources
**Persona**: Visitor
**Priority**: Medium
**Status**: MVP

**Description**:
A user who is not logged in accesses resources that do not require authentication, such as health checks, public API documentation, or (if configured) a public landing or catalog view.

**Preconditions**:
- User **not authenticated**
- Resource is designated as public (no auth required)

**Main Flow**:
1. User opens public URL (e.g. health endpoint, developer docs, or landing page)
2. System serves resource without requiring authentication
3. User may browse public information and optionally navigate to login (UC-AUTH-002) or register (UC-AUTH-001)

**Alternate Flows**:
- **A1**: Resource requires auth → system returns 401 and may redirect to login
- **A2**: When a public landing is configured, root `/` shows the landing (unauthenticated) or dashboard (authenticated). See [Landing Page](LANDING_PAGE.md). Deployments without a public landing may redirect root to login; documented as intentional.

**Postconditions**:
- User has accessed public content only
- No session or token issued unless user completes login or registration

**Related Use Cases**: UC-AUTH-001, UC-AUTH-002

**Test Traceability**: [TEST_TRACEABILITY.md#uc-auth-004-unauthenticated-user-accesses-public-resources](TEST_TRACEABILITY.md#uc-auth-004-unauthenticated-user-accesses-public-resources)

**Note**: Many deployments restrict all application UI to authenticated users; public access is typically limited to health checks and API docs. See [API Reference](API_REFERENCE.md) for public endpoints.

---

### UC-AUTH-005: User Switches Active Tenant

**ID**: UC-AUTH-005
**Title**: User Switches Active Tenant
**Persona**: Any authenticated user with multiple tenants (e.g. personal + org via invitation)
**Priority**: High
**Status**: MVP

**Description**:
User with membership in multiple tenants can switch active tenant context without re-login. Subsequent requests are scoped to the switched tenant via X-Tenant-Id header.

**Preconditions**:
- User authenticated (JWT or session)
- User has membership in at least two tenants (UserTenantMembership)
- `FEATURE_TENANT_SWITCH_ENABLED` is true (default)

**Main Flow**:
1. User opens tenant switcher in header (or calls GET /auth/me/tenants/)
2. System returns list of tenants user has membership in
3. User selects target tenant
4. User invokes switch (or POST /auth/switch-tenant/ with tenant_id)
5. System validates membership
6. System returns updated me summary with tenant_id overridden
7. Client sends X-Tenant-Id on subsequent requests
8. User sees assets/listings scoped to switched tenant

**Alternate Flows**:
- **A1**: Feature disabled → GET /auth/me/tenants/ and POST /auth/switch-tenant/ return 403; tenant switcher hidden in UI
- **A2**: User has no membership in target tenant → 403 Forbidden
- **A3**: Invalid tenant_id (not UUID) → 400 Bad Request

**Postconditions**:
- Active tenant context updated
- TENANT_SWITCH audit event recorded
- Subsequent API requests scoped to switched tenant

**Related Use Cases**: UC-AUTH-002, UC-AM-001 (assets scoped to tenant)

**Test Traceability**: [TEST_TRACEABILITY.md#uc-auth-005-user-switches-active-tenant](TEST_TRACEABILITY.md#uc-auth-005-user-switches-active-tenant)

---

## Asset Management Use Cases

### UC-AM-001: Create Asset via Data-First Flow

**ID**: UC-AM-001
**Title**: Create Asset via Data-First Flow
**Persona**: Data Product Owner, Data Engineer
**Priority**: High
**Status**: MVP

**Description**:
User uploads a data file first, system infers schema and runs quality/compliance checks, then user creates and validates a contract.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` role
- Tenant is active
- Data file available (CSV, JSON, Parquet, etc.)

**Main Flow**:
1. User navigates to "Create Asset" → selects "Data-First"
2. User provides basic metadata (name, description, domain)
3. User uploads data file
4. System validates file format
5. System infers schema and extracts sample
6. **NEW**: System runs AI schema matching (if enabled)
7. **NEW**: System runs auto-classification (PII detection, categorization)
8. System runs compliance check (mandatory gate)
9. System runs DQ check (`intake_basic` profile)
10. **NEW**: System runs ML-based anomaly detection
11. If checks pass, system creates draft asset and contract
12. User edits contract in contract editor
13. User triggers DataContract CLI validation
14. If validation passes, asset is activated

**Alternate Flows**:
- **A1**: Compliance check fails → data not stored, user receives report
- **A2**: DQ check fails → data not stored, user receives report
- **A3**: **NEW**: AI schema matching fails → user can proceed manually
- **A4**: **NEW**: Auto-classification fails → user can proceed manually
- **A5**: Contract validation fails → user fixes contract and re-validates

**Postconditions**:
- Asset created and activated
- Contract validated and stored
- Data stored (if checks passed)
- Semantic mapping triggered
- **NEW**: AI schema matching results stored
- **NEW**: Auto-classification results stored

**API Endpoints**: `POST /api/v1/assets/data-first/` (file_id, key, name; optional description, domain, visibility). Creates asset, dataset, and contract in one call. Runbook: [DATA_FIRST_ASSET_CREATION.md](runbooks/DATA_FIRST_ASSET_CREATION.md).

**UI Paths**: (1) Datasets → Create Dataset → Flow selector "Create new asset and link" → upload file, enter key/name. (2) Assets → Create Asset → "I have data to upload" → redirects to Dataset Create with create_new mode.

**Related Use Cases**: UC-AM-002, UC-CM-001, UC-DQ-001, UC-COMP-001, **UC-AI-002**, **UC-AI-005**
**Related Journeys**: JOURNEY-DPO-001

---

### UC-DS-EDIT: Edit Dataset and Link to Asset

**ID**: UC-DS-EDIT
**Title**: Edit Dataset and Link to Asset
**Persona**: Data Product Owner, Data Engineer
**Priority**: High
**Status**: MVP

**Description**:
User edits a dataset (e.g. format) and links or unlinks it to/from an asset. Supports the data-first flow where a dataset may be created without an asset and later linked.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` role
- Dataset exists (created via Files → Create Dataset or asset upload)
- Asset exists (when linking)

**Main Flow**:
1. User navigates to Datasets → selects a dataset
2. User clicks "Edit" or "Link to Asset"
3. User selects asset via **AssetPicker** (searchable dropdown; or clear to unlink)
4. User optionally updates format
5. User saves
6. System validates asset UUID (same tenant)
7. System updates dataset via `PATCH /api/v1/datasets/{id}/` with `asset` (UUID or null)
8. Dataset detail shows linked asset (asset_id, asset_name)

**Alternate Flows**:
- **A1**: AssetPicker returns tenant-scoped IDs only; invalid UUID not applicable
- **A2**: Asset not in tenant → 400
- **A3**: Unlink → clear AssetPicker, send `asset: null`

**Postconditions**:
- Dataset linked to asset (or unlinked)
- Audit event DATASET_UPDATED

**API Endpoints**: `PATCH /api/v1/datasets/{id}/` (asset, format)

**Related Use Cases**: UC-AM-001, UC-DQ-001
**Related Journeys**: JOURNEY-DPO-001, JOURNEY-DPO-018

---

### UC-FILE-UPLOAD: Upload File

**ID**: UC-FILE-UPLOAD
**Title**: Upload File
**Persona**: Data Product Owner, Data Engineer
**Priority**: High
**Status**: MVP

**Description**:
User uploads a data file (CSV, JSON, Parquet) via the Files page. File can later be used to create a dataset.

**Preconditions**:
- User authenticated
- File format supported (CSV, JSON, Parquet)

**Main Flow**:
1. User navigates to Files
2. User clicks "Upload File"
3. User selects file or drops into dropzone
4. System validates format and size
5. System uploads file via Files API
6. File appears in list; user can create dataset from it

**Alternate Flows**:
- **A1**: Invalid format → validation error
- **A2**: File too large → error

**Postconditions**:
- File stored; available for dataset creation

**API Endpoints**: `POST /api/v1/files/init/` (initiate), `POST /api/v1/files/{id}/complete/` (complete multipart upload)

**Related Use Cases**: UC-AM-001, UC-DS-EDIT
**Related Journeys**: JOURNEY-DPO-001, JOURNEY-DE-015

---

## AI/ML Use Cases **NEW**

### UC-AI-001: Natural Language Search

**ID**: UC-AI-001
**Title**: Natural Language Search
**Persona**: Data Consumer, Data Scientist
**Priority**: High
**Status**: New

**Description**:
User searches for data using natural language queries instead of SQL or keyword search.

**Preconditions**:
- User authenticated
- LLM service available
- Natural language search enabled

**Main Flow**:
1. User navigates to search
2. User enters natural language query ("show me customer data from last quarter")
3. System sends query to LLM service
4. LLM translates query to SQL/SPARQL
5. System displays query interpretation
6. User reviews interpretation
7. System executes translated query
8. System returns results
9. User reviews results
10. User can refine query if needed

**Alternate Flows**:
- **A1**: LLM service unavailable → fallback to keyword search
- **A2**: Query translation fails → system suggests alternative queries
- **A3**: Query results empty → system suggests query refinement

**Postconditions**:
- Query translated
- Results returned
- Query cached for performance
- Query saved to history (optional)

**Related Use Cases**: UC-DC-001, UC-AI-008

---

### UC-AI-002: AI Schema Matching

**ID**: UC-AI-002
**Title**: AI Schema Matching
**Persona**: Data Product Owner, Data Engineer, Data Scientist
**Priority**: High
**Status**: New

**Description**:
System uses AI to automatically suggest field mappings between different schemas.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` role
- Source and target schemas available
- AI schema matching service available

**Main Flow**:
1. User selects source and target schemas
2. System triggers AI schema matching
3. AI analyzes schema similarity
4. System generates mapping suggestions with confidence scores
5. User reviews suggestions
6. User accepts/rejects/modifies mappings
7. System saves accepted mappings
8. System uses mappings for contract creation or data integration

**Alternate Flows**:
- **A1**: Low confidence mappings → flagged for manual review
- **A2**: No mappings found → user creates mappings manually
- **A3**: AI service unavailable → user creates mappings manually

**Postconditions**:
- Mappings suggested
- Mappings accepted/rejected
- Mappings saved
- Mappings used for integration

**Related Use Cases**: UC-AM-001, UC-CM-001, UC-AI-003

---

### UC-AI-003: ML-Based Anomaly Detection

**ID**: UC-AI-003
**Title**: ML-Based Anomaly Detection
**Persona**: Data Product Owner, Data Scientist
**Priority**: High
**Status**: New

**Description**:
System uses ML models to detect data quality anomalies beyond rule-based checks.

**Preconditions**:
- User authenticated
- Data quality metrics available
- ML models trained and deployed

**Main Flow**:
1. System collects data quality metrics
2. ML models analyze metrics for anomalies
3. System generates anomaly scores
4. System flags high-confidence anomalies
5. System generates alerts for anomalies
6. User reviews anomalies
7. User provides feedback on anomalies
8. System updates ML models based on feedback

**Alternate Flows**:
- **A1**: ML model unavailable → fallback to rule-based checks
- **A2**: False positive → user marks as false positive, model learns
- **A3**: False negative → user reports missed anomaly, model learns

**Postconditions**:
- Anomalies detected
- Alerts generated
- Models updated
- Anomaly detection accuracy improves

**Related Use Cases**: UC-DQ-001, UC-AI-004

---

### UC-AI-004: Smart Recommendations

**ID**: UC-AI-004
**Title**: Smart Recommendations
**Persona**: Data Consumer, Data Product Owner
**Priority**: Medium
**Status**: New

**Description**:
System provides intelligent recommendations for data assets based on user behavior and patterns.

**Preconditions**:
- User authenticated
- User activity data available
- Recommendation engine available

**Main Flow**:
1. User views asset or searches
2. System generates recommendations using:
   - Collaborative filtering ("Users like you also used...")
   - Content-based filtering (similar assets)
   - Knowledge-based filtering (lineage, domain)
3. System displays recommendations
4. User explores recommended assets
5. User provides feedback (like/dislike)
6. System updates recommendations based on feedback

**Alternate Flows**:
- **A1**: No recommendations available → system suggests popular assets
- **A2**: Recommendations irrelevant → user provides negative feedback

**Postconditions**:
- Recommendations displayed
- Recommendations updated
- Recommendation relevance improves over time

**Related Use Cases**: UC-DC-001, UC-DC-013

---

### UC-AI-005: Auto-Classification

**ID**: UC-AI-005
**Title**: Auto-Classification
**Persona**: Data Product Owner, Compliance Officer, Data Scientist
**Priority**: High
**Status**: New

**Description**:
System automatically classifies data using ML models (PII detection, data categorization).

**Preconditions**:
- User authenticated
- Data available
- Classification models available

**Main Flow**:
1. System analyzes data
2. ML models detect PII and categorize data
3. System generates classification results with confidence scores
4. System flags low-confidence classifications for review
5. User reviews classifications
6. User approves/rejects classifications
7. System updates models based on feedback
8. System applies classifications to asset metadata

**Alternate Flows**:
- **A1**: Low confidence → flagged for manual review
- **A2**: Misclassification → user corrects, model learns
- **A3**: Classification service unavailable → manual classification

**Postconditions**:
- Data classified
- Classifications applied to metadata
- Models updated
- Classification accuracy improves

**Related Use Cases**: UC-AM-001, UC-COMP-001, UC-CPO-010

---

### UC-AI-006: Predictive Quality Forecasting

**ID**: UC-AI-006
**Title**: Predictive Quality Forecasting
**Persona**: Data Product Owner, Data Scientist
**Priority**: Medium
**Status**: New

**Description**:
System predicts future data quality trends using ML models.

**Preconditions**:
- User authenticated
- Historical quality data available
- Forecasting models available

**Main Flow**:
1. System analyzes historical quality trends
2. ML models generate quality forecasts
3. System displays forecasts
4. System generates alerts for predicted issues
5. User reviews forecasts
6. User addresses predicted issues proactively
7. System validates forecast accuracy
8. System updates models based on accuracy

**Alternate Flows**:
- **A1**: Insufficient historical data → forecasts unavailable
- **A2**: Forecast inaccurate → user provides feedback, model updates

**Postconditions**:
- Forecasts generated
- Alerts triggered
- Issues addressed proactively
- Forecast accuracy improves

**Related Use Cases**: UC-DQ-001, UC-AI-003

---

### UC-AI-007: Auto-Generated Quality Rules

**ID**: UC-AI-007
**Title**: Auto-Generated Quality Rules
**Persona**: Data Product Owner, Data Scientist
**Priority**: Medium
**Status**: New

**Description**:
System automatically generates data quality rules from patterns in data.

**Preconditions**:
- User authenticated
- Data quality patterns available
- Rule generation service available

**Main Flow**:
1. System analyzes data quality patterns
2. ML models identify patterns
3. System generates quality rule suggestions
4. User reviews suggestions
5. User accepts/rejects suggestions
6. System applies accepted rules
7. System monitors rule effectiveness
8. System updates rules based on effectiveness

**Alternate Flows**:
- **A1**: No patterns found → no rules suggested
- **A2**: Rule ineffective → user removes rule, system learns

**Postconditions**:
- Rules suggested
- Rules accepted/rejected
- Rules applied
- Rule effectiveness monitored

**Related Use Cases**: UC-DQ-001, UC-AI-003

---

### UC-AI-008: Query-to-SQL Translation

**ID**: UC-AI-008
**Title**: Query-to-SQL Translation
**Persona**: Data Consumer, Data Scientist
**Priority**: High
**Status**: New

**Description**:
System translates natural language queries to SQL for execution.

**Preconditions**:
- User authenticated
- LLM service available
- Database schema available

**Main Flow**:
1. User enters natural language query
2. System sends query to LLM with schema context
3. LLM generates SQL query
4. System validates SQL query
5. System displays SQL translation
6. User reviews translation
7. System executes SQL query
8. System returns results

**Alternate Flows**:
- **A1**: SQL validation fails → system suggests alternative queries
- **A2**: Query execution fails → system provides error explanation

**Postconditions**:
- Query translated to SQL
- SQL validated
- Query executed
- Results returned

**Related Use Cases**: UC-AI-001, UC-DC-006

---

### UC-AI-009: ML Model Training

**ID**: UC-AI-009
**Title**: ML Model Training
**Persona**: Data Scientist
**Priority**: Medium
**Status**: New

**Description**:
User trains ML models for anomaly detection, classification, or recommendations.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` role
- Training data available
- ML infrastructure available

**Main Flow**:
1. User selects model type (anomaly detection, classification, recommendation)
2. User provides training data
3. User configures model parameters
4. System trains model
5. System validates model
6. User reviews model performance
7. User deploys model
8. System monitors model performance

**Alternate Flows**:
- **A1**: Training fails → user adjusts parameters
- **A2**: Model performance poor → user retrains with different parameters

**Postconditions**:
- Model trained
- Model validated
- Model deployed
- Model performance monitored

**Related Use Cases**: UC-AI-003, UC-AI-004, UC-AI-005

---

### UC-AI-010: Recommendation Feedback Loop

**ID**: UC-AI-010
**Title**: Recommendation Feedback Loop
**Persona**: Data Consumer, Data Scientist
**Priority**: Medium
**Status**: New

**Description**:
System improves recommendations based on user feedback.

**Preconditions**:
- User authenticated
- Recommendations displayed
- Feedback mechanism available

**Main Flow**:
1. System displays recommendations
2. User provides feedback (like/dislike, click, purchase)
3. System records feedback
4. System updates recommendation models
5. System generates improved recommendations
6. System displays updated recommendations
7. Recommendation relevance improves over time

**Alternate Flows**:
- **A1**: No feedback → recommendations unchanged
- **A2**: Negative feedback → recommendations adjusted

**Postconditions**:
- Feedback recorded
- Models updated
- Recommendations improved
- Relevance increases

**Related Use Cases**: UC-AI-004, UC-DC-013

---

## Social Feature Use Cases **NEW**

**Route reference (Phase 27)**: Communities are accessed at `/communities`; legacy `/social` redirects to `/communities`. Asset ratings, reviews, and Community section are embedded on the asset detail page (`/assets/:id`). See [E2E_FULL_COVERAGE_PLAN.md](../frontend/e2e/E2E_FULL_COVERAGE_PLAN.md) and [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md#social).

### UC-SOCIAL-001: Rate Asset

**ID**: UC-SOCIAL-001
**Title**: Rate Asset
**Persona**: Data Consumer, Data Product Owner
**Priority**: Medium
**Status**: New

**Description**:
User rates a data asset (1-5 stars).

**Preconditions**:
- User authenticated
- Asset accessible
- Rating feature enabled

**Main Flow**:
1. User navigates to asset details
2. User views ratings section
3. User selects rating (1-5 stars)
4. User submits rating
5. System updates asset rating
6. System recalculates asset quality score
7. System publishes rating_updated event
8. Asset quality score updated

**Alternate Flows**:
- **A1**: Rating submission fails → user retries
- **A2**: User already rated → user can update rating

**Postconditions**:
- Rating submitted
- Asset rating updated
- Quality score updated
- Event published

**Related Use Cases**: UC-SOCIAL-002, UC-DC-008

---

### UC-SOCIAL-002: Review Asset

**ID**: UC-SOCIAL-002
**Title**: Review Asset
**Persona**: Data Consumer, Data Product Owner
**Priority**: Medium
**Status**: New

**Description**:
User writes a review for a data asset.

**Preconditions**:
- User authenticated
- Asset accessible
- Review feature enabled

**Main Flow**:
1. User navigates to asset details
2. User navigates to reviews section
3. User writes review
4. User submits review
5. System validates review
6. System sends review for moderation
7. Moderator approves/rejects review
8. System publishes review (if approved)
9. System publishes review_created event
10. Asset quality score updated

**Alternate Flows**:
- **A1**: Review validation fails → user fixes review
- **A2**: Review rejected → user can resubmit
- **A3**: Review contains inappropriate content → review flagged

**Postconditions**:
- Review submitted
- Review moderated
- Review published (if approved)
- Event published
- Quality score updated

**Related Use Cases**: UC-SOCIAL-001, UC-SOCIAL-003, UC-CM-002

---

### UC-SOCIAL-003: Comment on Asset

**ID**: UC-SOCIAL-003
**Title**: Comment on Asset
**Persona**: Data Consumer, Data Product Owner
**Priority**: Low
**Status**: New

**Description**:
User adds a comment to an asset discussion.

**Preconditions**:
- User authenticated
- Asset accessible
- Comments feature enabled

**Main Flow**:
1. User navigates to asset details
2. User navigates to comments section
3. User writes comment
4. User can @mention other users
5. User submits comment
6. System validates comment
7. System publishes comment
8. System sends notifications to @mentioned users
9. System publishes comment_created event

**Alternate Flows**:
- **A1**: Comment validation fails → user fixes comment
- **A2**: Comment contains inappropriate content → comment flagged

**Postconditions**:
- Comment published
- Notifications sent
- Event published

**Related Use Cases**: UC-SOCIAL-002

---

### UC-SOCIAL-004: Join Data Community

**ID**: UC-SOCIAL-004
**Title**: Join Data Community
**Persona**: Data Consumer, Data Product Owner, Community Manager
**Priority**: Low
**Status**: New

**Description**:
User joins a data community for collaboration.

**Preconditions**:
- User authenticated
- Community exists
- Community membership open (or user invited)

**Main Flow**:
1. User browses data communities
2. User views community details
3. User joins community
4. System adds user to community
5. System grants community access
6. User can participate in discussions
7. User can access community assets
8. User can contribute to knowledge base

**Alternate Flows**:
- **A1**: Community membership closed → user requests invitation
- **A2**: Join fails → user retries

**Postconditions**:
- User joined community
- Community access granted
- User can participate

**Related Use Cases**: UC-SOCIAL-005, UC-CM-001

---

### UC-SOCIAL-005: Manage Activity Feed

**ID**: UC-SOCIAL-005
**Title**: Manage Activity Feed
**Persona**: Data Consumer, Data Product Owner, Community Manager
**Priority**: Low
**Status**: New
**Backend status**: **Not implemented.** No activity feed API or model in `hub/apps/social`; UI SHALL NOT implement until backend exists. See `artifacts/SOCIAL_ENDPOINTS_VERIFICATION.md` in frontdev1.

**Description**:
User views and manages activity feed.

**Preconditions**:
- User authenticated
- Activity feed enabled

**Main Flow**:
1. User navigates to activity feed
2. System displays activities chronologically
3. User filters activities
4. User searches activities
5. User views activity details
6. User receives notifications for relevant activities
7. User can configure notification preferences

**Alternate Flows**:
- **A1**: Feed loading fails → user refreshes
- **A2**: Too many activities → user applies filters

**Postconditions**:
- Activities displayed
- Activities filtered/searched
- Notifications configured

**Related Use Cases**: UC-SOCIAL-004, UC-CM-004

---

### UC-SOCIAL-006: Assign Data Steward

**ID**: UC-SOCIAL-006
**Title**: Assign Data Steward
**Persona**: Data Product Owner, Community Manager
**Priority**: Medium
**Status**: New

**Description**:
User assigns data stewards to manage assets.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `TENANT_ADMIN` role
- Asset exists
- Steward users available

**Main Flow**:
1. User navigates to asset details
2. User navigates to stewardship section
3. User assigns stewards
4. User configures steward permissions
5. System notifies stewards
6. System tracks steward activity
7. User monitors steward activity

**Alternate Flows**:
- **A1**: Steward assignment fails → user retries
- **A2**: Steward unavailable → user selects alternative

**Postconditions**:
- Stewards assigned
- Permissions configured
- Stewards notified
- Activity tracked

**Related Use Cases**: UC-SOCIAL-002, UC-CM-003

---

## Data Mesh Use Cases **NEW**

### UC-MESH-001: Create Data Mesh Domain

**ID**: UC-MESH-001
**Title**: Create Data Mesh Domain
**Persona**: Data Mesh Domain Owner, Tenant Admin
**Priority**: High
**Status**: New

**Description**:
User creates a data mesh domain with boundaries and ownership.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `TENANT_ADMIN` role
- Data mesh feature enabled

**Main Flow**:
1. User navigates to data mesh section
2. User creates new domain
3. User defines domain boundaries
4. User assigns domain ownership
5. User configures domain infrastructure
6. User sets up self-serve capabilities
7. User configures resource quotas
8. System validates domain configuration
9. System deploys domain
10. System publishes domain_created event

**Alternate Flows**:
- **A1**: Domain validation fails → user fixes configuration
- **A2**: Domain deployment fails → user retries

**Postconditions**:
- Domain created
- Boundaries defined
- Ownership assigned
- Domain deployed
- Event published

**Related Use Cases**: UC-MESH-002, UC-MESH-003, UC-DMO-001

---

### UC-MESH-002: Configure Federated Governance

**ID**: UC-MESH-002
**Title**: Configure Federated Governance
**Persona**: Data Mesh Domain Owner, Compliance Officer
**Priority**: High
**Status**: New

**Description**:
User configures federated governance policies for domains.

**Preconditions**:
- User authenticated with domain ownership
- Domain exists
- Governance feature enabled

**Main Flow**:
1. User navigates to domain governance
2. User defines domain-specific policies
3. User configures policy enforcement
4. User sets up compliance checking
5. User configures policy violation alerts
6. System validates policies
7. System applies policies to domain
8. System monitors policy compliance
9. System publishes policy_applied event

**Alternate Flows**:
- **A1**: Policy validation fails → user fixes policies
- **A2**: Policy conflicts → system flags conflicts

**Postconditions**:
- Policies defined
- Policies applied
- Compliance monitored
- Event published

**Related Use Cases**: UC-MESH-001, UC-MESH-003, UC-DMO-002

---

### UC-MESH-003: Manage Domain Topology

**ID**: UC-MESH-003
**Title**: Manage Domain Topology
**Persona**: Data Mesh Domain Owner, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User manages data mesh topology and domain relationships.

**Preconditions**:
- User authenticated
- Multiple domains exist
- Topology feature enabled

**Main Flow**:
1. User navigates to topology visualization
2. System displays mesh topology graph
3. User views domain relationships
4. User manages domain relationships
5. User monitors topology health
6. User updates topology as needed
7. System publishes topology_updated event

**Alternate Flows**:
- **A1**: Topology visualization fails → user uses list view
- **A2**: Topology update fails → user retries

**Postconditions**:
- Topology visualized
- Relationships managed
- Health monitored
- Event published

**Related Use Cases**: UC-MESH-001, UC-MESH-002, UC-DMO-003

---

### UC-MESH-004: Assign Domain Ownership

**ID**: UC-MESH-004
**Title**: Assign Domain Ownership
**Persona**: Data Mesh Domain Owner, Tenant Admin
**Priority**: Medium
**Status**: New

**Description**:
User assigns ownership of domains to users or teams.

**Preconditions**:
- User authenticated with `TENANT_ADMIN` or domain management permissions
- Domain exists
- Users/teams available

**Main Flow**:
1. User navigates to domain management
2. User selects domain
3. User assigns owners
4. User configures owner permissions
5. System notifies owners
6. System tracks ownership changes
7. System publishes domain_created or ownership_updated event

**Alternate Flows**:
- **A1**: Ownership assignment fails → user retries
- **A2**: Owner unavailable → user selects alternative

**Postconditions**:
- Ownership assigned
- Permissions configured
- Owners notified
- Event published

**Related Use Cases**: UC-MESH-001, UC-DMO-001

---

### UC-MESH-005: Monitor Mesh Health

**ID**: UC-MESH-005
**Title**: Monitor Mesh Health
**Persona**: Data Mesh Domain Owner, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User monitors data mesh health and performance.

**Preconditions**:
- User authenticated
- Mesh exists
- Health monitoring enabled

**Main Flow**:
1. User navigates to mesh health dashboard
2. System displays domain health metrics
3. User views topology health
4. User monitors domain performance
5. User reviews domain compliance
6. User identifies issues
7. User addresses issues
8. System generates health reports

**Alternate Flows**:
- **A1**: Health data unavailable → user contacts support
- **A2**: Issues identified → user takes corrective action

**Postconditions**:
- Health monitored
- Issues identified
- Issues addressed
- Reports generated

**Related Use Cases**: UC-MESH-003, UC-DMO-005

---

## Virtualization Use Cases **NEW**

### UC-VIRT-001: Create Virtual Dataset

**ID**: UC-VIRT-001
**Title**: Create Virtual Dataset
**Persona**: Data Engineer, Data Analyst
**Priority**: High
**Status**: New

**Description**:
User creates a virtual dataset that queries across multiple sources.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `DATA_CONSUMER` role
- Source systems available
- Virtualization service available

**Main Flow**:
1. User navigates to virtualization section
2. User creates new virtual dataset
3. User configures source systems
4. User defines query mapping
5. User configures caching strategy
6. System validates virtual dataset
7. System creates virtual dataset
8. User can query virtual dataset

**Alternate Flows**:
- **A1**: Validation fails → user fixes configuration
- **A2**: Source unavailable → user removes source or retries

**Postconditions**:
- Virtual dataset created
- Sources configured
- Query mapping defined
- Caching configured

**Related Use Cases**: UC-VIRT-002, UC-DE-009, UC-DA-003

---

### UC-VIRT-002: Execute Federated Query

**ID**: UC-VIRT-002
**Title**: Execute Federated Query
**Persona**: Data Analyst, Data Engineer
**Priority**: High
**Status**: New

**Description**:
User executes a query across multiple data sources.

**Preconditions**:
- User authenticated
- Virtual dataset or multiple sources available
- Query federation service available

**Main Flow**:
1. User selects virtual dataset or multiple sources
2. User builds federated query (SQL or visual builder)
3. System optimizes query across sources
4. System executes query in parallel where possible
5. System aggregates results
6. System returns results
7. User reviews results
8. User can export results

**Alternate Flows**:
- **A1**: Query optimization fails → system executes sequentially
- **A2**: Source unavailable → system returns partial results or error
- **A3**: Query timeout → user simplifies query

**Postconditions**:
- Query executed
- Results aggregated
- Results returned
- Results exported (if needed)

**Related Use Cases**: UC-VIRT-001, UC-DA-004

---

### UC-VIRT-003: Manage Federation Topology

**ID**: UC-VIRT-003
**Title**: Manage Federation Topology
**Persona**: Data Engineer, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User manages federation topology and source relationships.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `PLATFORM_ADMIN` role
- Multiple sources available
- Federation feature enabled

**Main Flow**:
1. User navigates to federation topology
2. System displays federation graph
3. User views source relationships
4. User manages source relationships
5. User monitors federation health
6. User updates topology as needed
7. System publishes topology_updated event

**Alternate Flows**:
- **A1**: Topology visualization fails → user uses list view
- **A2**: Topology update fails → user retries

**Postconditions**:
- Topology visualized
- Relationships managed
- Health monitored
- Event published

**Related Use Cases**: UC-VIRT-001, UC-VIRT-002

---

### UC-VIRT-004: Monitor Virtualization Performance

**ID**: UC-VIRT-004
**Title**: Monitor Virtualization Performance
**Persona**: Data Engineer, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User monitors virtualization query performance.

**Preconditions**:
- User authenticated
- Virtual datasets exist
- Performance monitoring enabled

**Main Flow**:
1. User navigates to virtualization performance dashboard
2. System displays query performance metrics
3. User views query latency
4. User views cache hit rates
5. User identifies slow queries
6. User optimizes queries or caching
7. System generates performance reports

**Alternate Flows**:
- **A1**: Performance data unavailable → user contacts support
- **A2**: Performance poor → user optimizes

**Postconditions**:
- Performance monitored
- Issues identified
- Optimizations applied
- Reports generated

**Related Use Cases**: UC-VIRT-001, UC-VIRT-002

---

## Advanced Marketplace Use Cases **NEW**

### UC-MKT-ADV-001: Configure Usage-Based Pricing

**ID**: UC-MKT-ADV-001
**Title**: Configure Usage-Based Pricing
**Persona**: Data Product Owner, Platform Admin
**Priority**: High
**Status**: New

**Description**:
User configures usage-based pricing for marketplace assets.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `PLATFORM_ADMIN` role
- Asset exists
- Usage-based pricing enabled

**Main Flow**:
1. User navigates to marketplace pricing configuration
2. User selects usage-based pricing model
3. User configures pricing tiers (per-query, per-GB)
4. User sets pricing rates
5. User configures billing settings
6. System validates pricing configuration
7. System applies pricing to asset
8. System tracks usage for billing

**Alternate Flows**:
- **A1**: Pricing validation fails → user fixes configuration
- **A2**: Billing configuration fails → user retries

**Postconditions**:
- Usage-based pricing configured
- Pricing applied
- Usage tracking enabled
- Billing configured

**Related Use Cases**: UC-MKT-ADV-002, UC-DPO-010, UC-DC-011

---

### UC-MKT-ADV-002: Preview Data Before Purchase

**ID**: UC-MKT-ADV-002
**Title**: Preview Data Before Purchase
**Persona**: Data Consumer
**Priority**: High
**Status**: New

**Description**:
User previews data before purchasing from marketplace.

**Preconditions**:
- User authenticated
- Marketplace listing available
- Preview feature enabled

**Main Flow**:
1. User navigates to marketplace listing
2. User requests data preview
3. System generates sample data
4. System displays sample data
5. System displays data quality metrics
6. System displays schema information
7. User reviews preview
8. User makes purchase decision

**Alternate Flows**:
- **A1**: Preview generation fails → user contacts support
- **A2**: Preview unavailable → user proceeds without preview

**Postconditions**:
- Preview generated
- Sample data displayed
- Quality metrics visible
- Decision made

**Related Use Cases**: UC-DC-012, UC-MKT-ADV-003

---

### UC-MKT-ADV-003: Manage Trust Signals

**ID**: UC-MKT-ADV-003
**Title**: Manage Trust Signals
**Persona**: Data Product Owner, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User configures trust signals for marketplace listings (quality SLAs, badges).

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `PLATFORM_ADMIN` role
- Asset exists
- Trust signals feature enabled

**Main Flow**:
1. User navigates to trust signals configuration
2. User configures quality SLAs
3. User configures data freshness guarantees
4. User applies certification badges
5. System validates trust signals
6. System displays trust signals in listing
7. System monitors trust signal compliance

**Alternate Flows**:
- **A1**: Trust signal validation fails → user fixes configuration
- **A2**: Compliance fails → system alerts user

**Postconditions**:
- Trust signals configured
- Signals displayed
- Compliance monitored

**Related Use Cases**: UC-MKT-ADV-002, UC-DPO-002

---

### UC-MKT-ADV-004: Track Revenue Analytics

**ID**: UC-MKT-ADV-004
**Title**: Track Revenue Analytics
**Persona**: Data Product Owner, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User tracks revenue and analytics for marketplace assets.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `PLATFORM_ADMIN` role
- Assets published to marketplace
- Revenue tracking enabled

**Main Flow**:
1. User navigates to revenue analytics dashboard
2. System displays revenue metrics
3. User views revenue by asset
4. User views revenue trends
5. User views usage analytics
6. User generates revenue reports
7. User optimizes pricing based on analytics

**Alternate Flows**:
- **A1**: Revenue data unavailable → user contacts support
- **A2**: Analytics incomplete → user waits for data collection

**Postconditions**:
- Revenue tracked
- Analytics displayed
- Reports generated
- Pricing optimized

**Related Use Cases**: UC-MKT-ADV-001, UC-DPO-002

---

### UC-MKT-ADV-005: Configure Data Quality SLAs

**ID**: UC-MKT-ADV-005
**Title**: Configure Data Quality SLAs
**Persona**: Data Product Owner, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User configures data quality SLAs for marketplace assets.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `PLATFORM_ADMIN` role
- Asset exists
- Quality SLA feature enabled

**Main Flow**:
1. User navigates to quality SLA configuration
2. User defines quality thresholds
3. User configures SLA monitoring
4. User sets up SLA violation alerts
5. System monitors quality against SLAs
6. System displays SLA compliance
7. System alerts on violations

**Alternate Flows**:
- **A1**: SLA configuration fails → user fixes
- **A2**: SLA violations → system alerts, user addresses

**Postconditions**:
- SLAs configured
- Monitoring active
- Compliance displayed
- Alerts configured

**Related Use Cases**: UC-MKT-ADV-003, UC-DQ-001

---

## Advanced Governance Use Cases **NEW**

### UC-GOV-ADV-001: Configure Automated Compliance

**ID**: UC-GOV-ADV-001
**Title**: Configure Automated Compliance
**Persona**: Compliance Officer, Tenant Admin
**Priority**: High
**Status**: New

**Description**:
User configures automated compliance detection and enforcement.

**Preconditions**:
- User authenticated with `AUDITOR` or `TENANT_ADMIN` role
- Compliance feature enabled

**Main Flow**:
1. User navigates to compliance configuration
2. User defines compliance rules
3. User configures auto-detection
4. User sets up enforcement actions
5. User configures alerts
6. System validates configuration
7. System tests automated compliance
8. System deploys automated compliance
9. System monitors compliance

**Alternate Flows**:
- **A1**: Configuration validation fails → user fixes
- **A2**: Test fails → user adjusts configuration

**Postconditions**:
- Rules defined
- Auto-detection configured
- Enforcement active
- Compliance monitored

**Related Use Cases**: UC-GOV-ADV-002, UC-CPO-006

---

### UC-GOV-ADV-002: GDPR Right to be Forgotten (Phase 25.5)

**ID**: UC-GOV-ADV-002
**Title**: GDPR Right to be Forgotten (Data Erasure)
**Persona**: User, Compliance Officer, Platform Admin
**Priority**: High
**Status**: **Implemented (Phase 25.5.2)**

**Description**:
Users can request deletion or anonymization of their personal data (GDPR Article 17). The platform provides an erasure workflow that handles PII deletion/anonymization while respecting legal and compliance retention requirements.

**Preconditions**:
- User is authenticated (for self-service)
- Platform admin authentication (for admin-initiated erasure)

**Main Flow**:
1. User requests erasure via **POST** `/api/v1/users/me/request-erasure/`
2. System creates erasure request with status `PENDING`
3. System executes erasure:
   - Anonymizes user profile (email, display name)
   - Revokes all user sessions
   - Deactivates all API keys
   - Anonymizes actor references in audit events
4. System sets request status to `COMPLETED`
5. System logs audit event: `ERASURE_COMPLETED`

**API Endpoints**:
- **POST** `/api/v1/users/me/request-erasure/` - User self-service erasure request
- **GET** `/api/v1/users/me/erasure-requests/{id}/` - Check erasure request status
- **POST** `/api/v1/platform/users/{id}/request-erasure/` - Platform admin erasure request
- **POST** `/api/v1/platform/users/{id}/erasure-requests/{request_id}/execute/` - Execute erasure (admin)

**What is Deleted vs Anonymized**:
- **Deleted**: Sessions, API keys (deactivated)
- **Anonymized**: User profile (email, display name), audit event actor references
- **Retained**: Audit events (with anonymized references), compliance records, legal holds

**Related Documentation**:
- `docs/GDPR_ERASURE.md` - Complete erasure workflow documentation
- `docs/DATA_PORTABILITY.md` - Right to data portability (Article 20)

**Postconditions**:
- Workflow configured
- Deletion service set up
- Verification configured
- Workflow operational

**Related Use Cases**: UC-GOV-ADV-001, UC-CPO-007

---

### UC-GOV-ADV-002A: GDPR Data Portability (Phase 25.5)

**ID**: UC-GOV-ADV-002A
**Title**: GDPR Data Portability (Right to Data Portability)
**Persona**: User
**Priority**: High
**Status**: **Implemented (Phase 25.5.1)**

**Description**:
Users can request a copy of their personal data in a machine-readable format (GDPR Article 20). The platform provides a data export feature that collects user data and provides it as a downloadable archive.

**Preconditions**:
- User is authenticated

**Main Flow**:
1. User requests data export via **POST** `/api/v1/users/me/export-data/`
2. System creates data export job with status `PENDING`
3. System processes export job:
   - Collects user profile data
   - Collects audit events (last 1000)
   - Collects asset metadata (created by user)
   - Collects dataset metadata (created by user)
   - Collects contract metadata (created by user)
4. System builds ZIP archive with JSON data
5. System uploads archive to storage (S3/MinIO)
6. System generates signed download URL (24 hour expiry)
7. System sets job status to `COMPLETED`
8. User downloads export archive

**API Endpoints**:
- **POST** `/api/v1/users/me/export-data/` - Request data export
- **GET** `/api/v1/users/me/export-jobs/{job_id}/` - Check export job status

**Export Contents**:
- **user_data.json**: Complete user profile and metadata
- **README.txt**: Export information and format description

**Data Included**:
- User profile (email, display name, status, timestamps)
- Audit events (recent 1000 events)
- Asset metadata (name, description, status)
- Dataset metadata (name, description, status)
- Contract metadata (name, status)

**Note**: Actual file contents are not included for privacy and storage reasons.

**Related Documentation**:
- `docs/DATA_PORTABILITY.md` - Complete data portability documentation
- `docs/GDPR_ERASURE.md` - Right to be Forgotten (Article 17)

**Postconditions**:
- Export job created
- Export archive available for download
- Download URL provided (24 hour expiry)

---

### UC-GOV-ADV-003: Manage Consent Tracking

**ID**: UC-GOV-ADV-003
**Title**: Manage Consent Tracking
**Persona**: Compliance Officer
**Priority**: High
**Status**: New

**Description**:
User tracks and manages data consent.

**Preconditions**:
- User authenticated with `AUDITOR` or `TENANT_ADMIN` role
- Consent tracking enabled

**Main Flow**:
1. User navigates to consent management
2. User configures consent rules
3. User sets up consent tracking
4. System tracks consent status
5. User monitors consent status
6. User handles consent changes
7. User generates consent reports

**Alternate Flows**:
- **A1**: Consent tracking fails → user contacts support
- **A2**: Consent changes → user updates tracking

**Postconditions**:
- Rules configured
- Tracking active
- Status monitored
- Reports generated

**Related Use Cases**: UC-GOV-ADV-001, UC-CPO-008

---

### UC-GOV-ADV-004: Configure Automated Retention

**ID**: UC-GOV-ADV-004
**Title**: Configure Automated Retention
**Persona**: Compliance Officer
**Priority**: Medium
**Status**: New

**Description**:
User configures automated data retention policies.

**Preconditions**:
- User authenticated with `AUDITOR` or `TENANT_ADMIN` role
- Retention feature enabled

**Main Flow**:
1. User navigates to retention configuration
2. User defines retention rules
3. User configures automation
4. User sets up scheduling
5. User configures deletion workflows
6. System validates configuration
7. System tests retention policies
8. System deploys retention
9. System monitors retention execution

**Alternate Flows**:
- **A1**: Configuration validation fails → user fixes
- **A2**: Test fails → user adjusts policies

**Postconditions**:
- Rules defined
- Automation configured
- Scheduling set up
- Retention operational

**Related Use Cases**: UC-GOV-ADV-001, UC-CPO-009

---

## Advanced Observability Use Cases **NEW**

### UC-OBS-ADV-001: Monitor Reliability Scores

**ID**: UC-OBS-ADV-001
**Title**: Monitor Reliability Scores
**Persona**: Data Product Owner, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User monitors data reliability scores for assets.

**Preconditions**:
- User authenticated
- Assets exist
- Reliability scoring enabled

**Main Flow**:
1. User navigates to reliability dashboard
2. System displays reliability scores
3. User views score breakdown (quality, freshness, compliance)
4. User identifies issues affecting scores
5. User addresses issues
6. User monitors score trends
7. System generates reliability reports

**Alternate Flows**:
- **A1**: Score calculation fails → user contacts support
- **A2**: Issues identified → user takes corrective action

**Postconditions**:
- Scores displayed
- Issues identified
- Issues addressed
- Trends monitored

**Related Use Cases**: UC-DPO-014, UC-OBS-ADV-002

---

### UC-OBS-ADV-002: Track Data Costs

**ID**: UC-OBS-ADV-002
**Title**: Track Data Costs
**Persona**: Tenant Admin, Platform Admin
**Priority**: Medium
**Status**: New

**Description**:
User tracks data storage and compute costs.

**Preconditions**:
- User authenticated with `TENANT_ADMIN` or `PLATFORM_ADMIN` role
- Cost tracking enabled
- Cloud cost APIs integrated

**Main Flow**:
1. User navigates to cost dashboard
2. System displays cost breakdown
3. User views costs by asset/domain
4. User analyzes cost trends
5. User reviews cost optimization recommendations
6. User implements optimizations
7. User monitors cost trends
8. System generates cost reports

**Alternate Flows**:
- **A1**: Cost data unavailable → user contacts support
- **A2**: Costs high → user implements optimizations

**Postconditions**:
- Costs tracked
- Breakdown visible
- Recommendations provided
- Optimizations implemented

**Related Use Cases**: UC-OBS-ADV-001, UC-TA-007

---

### UC-OBS-ADV-003: Set Up Predictive Alerts

**ID**: UC-OBS-ADV-003
**Title**: Set Up Predictive Alerts
**Persona**: Platform Admin, Data Product Owner
**Priority**: Medium
**Status**: New

**Description**:
User configures ML-based predictive alerts.

**Preconditions**:
- User authenticated
- ML forecasting service available
- Alerting system available

**Main Flow**:
1. User navigates to alert configuration
2. User selects metrics for forecasting
3. User configures alert thresholds
4. User sets up alert channels
5. System trains forecasting models
6. System generates forecasts
7. System triggers alerts for predicted issues
8. User receives alerts
9. User addresses predicted issues

**Alternate Flows**:
- **A1**: Model training fails → user adjusts parameters
- **A2**: Forecast inaccurate → user provides feedback

**Postconditions**:
- Alerts configured
- Forecasts generated
- Alerts triggered
- Issues addressed

**Related Use Cases**: UC-OBS-ADV-001, UC-AI-006

---

### UC-OBS-ADV-004: Monitor Performance Regressions

**ID**: UC-OBS-ADV-004
**Title**: Monitor Performance Regressions
**Persona**: Platform Admin, Data Engineer
**Priority**: Medium
**Status**: New

**Description**:
User monitors API and query performance for regressions.

**Preconditions**:
- User authenticated
- Performance monitoring enabled
- Historical performance data available

**Main Flow**:
1. User navigates to performance dashboard
2. System displays performance metrics
3. User views API latency trends
4. User views query performance trends
5. System detects performance regressions
6. System alerts on regressions
7. User investigates regressions
8. User addresses performance issues

**Alternate Flows**:
- **A1**: Performance data unavailable → user contacts support
- **A2**: Regression detected → user takes corrective action

**Postconditions**:
- Performance monitored
- Regressions detected
- Issues addressed

**Related Use Cases**: UC-OBS-ADV-001, UC-OBS-ADV-003

---

## Integration Ecosystem Use Cases **NEW**

### UC-INT-001: Install Pre-built Connector

**ID**: UC-INT-001
**Title**: Install Pre-built Connector
**Persona**: Data Engineer, Tenant Admin
**Priority**: High
**Status**: New

**Description**:
User installs a pre-built connector from marketplace.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `TENANT_ADMIN` role
- Connector marketplace available
- Connector exists

**Main Flow**:
1. User navigates to connector marketplace
2. User browses connectors
3. User selects connector
4. User installs connector
5. System validates connector
6. System installs connector
7. User configures connector
8. User tests connector
9. User deploys connector

**Alternate Flows**:
- **A1**: Connector validation fails → user contacts support
- **A2**: Installation fails → user retries
- **A3**: Test fails → user adjusts configuration

**Postconditions**:
- Connector installed
- Connector configured
- Connector tested
- Connector deployed

**Related Use Cases**: UC-INT-002, UC-DE-010

---

### UC-INT-002: Create Custom Connector

**ID**: UC-INT-002
**Title**: Create Custom Connector
**Persona**: Data Engineer, External Developer
**Priority**: Medium
**Status**: New

**Description**:
User creates a custom connector for a data source.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` role
- Connector framework available
- Data source available

**Main Flow**:
1. User navigates to connector builder
2. User designs connector
3. User implements connector interface
4. User tests connector
5. User validates connector
6. User saves connector
7. User can publish to marketplace (optional)

**Alternate Flows**:
- **A1**: Connector test fails → user fixes implementation
- **A2**: Validation fails → user adjusts connector

**Postconditions**:
- Connector created
- Connector tested
- Connector validated
- Connector available for use

**Related Use Cases**: UC-INT-001, UC-DEV-007

---

### UC-INT-003: Integrate BI Tool

**ID**: UC-INT-003
**Title**: Integrate BI Tool
**Persona**: Data Engineer, Tenant Admin
**Priority**: High
**Status**: New

**Description**:
User integrates BI tool (Tableau, Power BI, Looker) with hub.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` or `TENANT_ADMIN` role
- BI tool available
- BI connector available

**Main Flow**:
1. User navigates to BI integration
2. User selects BI tool
3. User installs BI connector
4. User configures connection
5. User maps data sources
6. User tests connection
7. User deploys integration
8. User can query hub data from BI tool

**Alternate Flows**:
- **A1**: Connection test fails → user fixes configuration
- **A2**: Mapping fails → user adjusts mappings

**Postconditions**:
- BI tool integrated
- Connection configured
- Data accessible from BI tool

**Related Use Cases**: UC-INT-001, UC-TA-008

---

### UC-INT-004: Set Up Reverse ETL

**ID**: UC-INT-004
**Title**: Set Up Reverse ETL
**Persona**: Data Engineer
**Priority**: Medium
**Status**: New

**Description**:
User sets up reverse ETL to push data to operational systems.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` role
- Data source available
- Destination system available (CRM, marketing platform)
- Reverse ETL feature enabled

**Main Flow**:
1. User navigates to reverse ETL configuration
2. User selects data source
3. User configures destination (CRM, marketing platform)
4. User maps data fields
5. User configures transformation (if needed)
6. User sets up schedule
7. User tests reverse ETL
8. User deploys reverse ETL
9. System monitors reverse ETL execution

**Alternate Flows**:
- **A1**: Test fails → user fixes configuration
- **A2**: Destination unavailable → user retries

**Postconditions**:
- Reverse ETL configured
- Schedule set
- Reverse ETL operational
- Execution monitored

**Related Use Cases**: UC-INT-001, UC-DE-011

---

### UC-INT-005: Integrate CI/CD Pipeline

**ID**: UC-INT-005
**Title**: Integrate CI/CD Pipeline
**Persona**: Data Engineer, External Developer
**Priority**: Medium
**Status**: New

**Description**:
User integrates contract validation into CI/CD pipeline.

**Preconditions**:
- User authenticated
- CI/CD system available (GitHub Actions, GitLab CI)
- CI/CD integration feature enabled

**Main Flow**:
1. User navigates to CI/CD integration
2. User selects CI/CD system
3. User configures integration
4. User adds contract validation step
5. User configures workflow
6. User tests integration
7. User deploys integration
8. System validates contracts in CI/CD
9. System blocks merge on validation failure

**Alternate Flows**:
- **A1**: Integration test fails → user fixes configuration
- **A2**: Validation fails → user fixes contracts

**Postconditions**:
- CI/CD integrated
- Validation step added
- Workflow operational
- Contracts validated in CI/CD

**Related Use Cases**: UC-DE-005, UC-DEV-009

---

## Developer Experience Use Cases **NEW**

### UC-DEV-001: Install Plugin

**ID**: UC-DEV-001
**Title**: Install Plugin
**Persona**: External Developer, Data Engineer
**Priority**: Medium
**Status**: New

**Description**:
User installs a plugin from marketplace.

**Preconditions**:
- User authenticated
- Plugin marketplace available
- Plugin exists

**Main Flow**:
1. User navigates to plugin marketplace
2. User browses plugins
3. User selects plugin
4. User installs plugin
5. System validates plugin
6. System installs plugin
7. User configures plugin
8. User uses plugin functionality

**Alternate Flows**:
- **A1**: Plugin validation fails → user contacts support
- **A2**: Installation fails → user retries

**Postconditions**:
- Plugin installed
- Plugin configured
- Plugin functional

**Related Use Cases**: UC-DEV-002, UC-DEV-008

---

### UC-DEV-002: Create Custom Plugin

**ID**: UC-DEV-002
**Title**: Create Custom Plugin
**Persona**: External Developer, Data Engineer
**Priority**: Medium
**Status**: New

**Description**:
User creates a custom plugin for platform extension.

**Preconditions**:
- User authenticated with `DATA_PROVIDER` role
- Plugin framework available
- Plugin type selected (connector, transformation, quality check)

**Main Flow**:
1. User navigates to plugin development
2. User designs plugin
3. User implements plugin interface
4. User tests plugin
5. User validates plugin
6. User saves plugin
7. User can publish to marketplace (optional)

**Alternate Flows**:
- **A1**: Plugin test fails → user fixes implementation
- **A2**: Validation fails → user adjusts plugin

**Postconditions**:
- Plugin created
- Plugin tested
- Plugin validated
- Plugin available for use

**Related Use Cases**: UC-DEV-001, UC-DE-012

---

### UC-DEV-003: Use CLI Tool

**ID**: UC-DEV-003
**Title**: Use CLI Tool
**Persona**: External Developer, Data Engineer
**Priority**: Medium
**Status**: New

**Description**:
User uses CLI tool for platform operations.

**Preconditions**:
- User authenticated
- CLI tool installed
- CLI credentials configured

**Main Flow**:
1. User installs CLI tool
2. User configures CLI (authentication, endpoints)
3. User uses CLI commands:
   - Asset management commands
   - Contract management commands
   - Pipeline commands
   - Marketplace commands
4. User executes workflows via CLI
5. User views CLI output

**Alternate Flows**:
- **A1**: CLI installation fails → user checks requirements
- **A2**: Authentication fails → user reconfigures

**Postconditions**:
- CLI installed
- CLI configured
- CLI commands work
- Workflows executed

**Related Use Cases**: UC-DEV-004, UC-DEV-009

---

### UC-DEV-004: Access Developer Portal

**ID**: UC-DEV-004
**Title**: Access Developer Portal
**Persona**: External Developer
**Priority**: Medium
**Status**: New

**Description**:
User accesses developer portal for documentation and resources.

**Preconditions**:
- User authenticated
- Developer portal available

**Main Flow**:
1. User navigates to developer portal
2. User reviews API documentation
3. User reviews code examples
4. User uses sandbox environment
5. User follows tutorials
6. User builds integration
7. User deploys integration

**Alternate Flows**:
- **A1**: Portal unavailable → user uses alternative documentation
- **A2**: Sandbox unavailable → user uses production (with caution)

**Postconditions**:
- Portal accessed
- Documentation reviewed
- Examples used
- Integration built

**Related Use Cases**: UC-DEV-001, UC-DEV-002, UC-DEV-003

---

## Use Cases Previously Referenced Only (Documentation Completeness)

This section closes documentation gaps for use case IDs that were referenced in "Related Use Cases" but did not have a dedicated `### UC-XXX:` block. Each is classified as **implemented (backend)** or **not implemented (backend)** so that frontend and E2E planning can rely on a single source of truth.

### Deferred — Transformation Pipeline (Phase 5)

The following **transformation pipeline** use cases and user journeys are **Deferred** (Phase 5 Option A). No public transformation-pipeline API is implemented; they are documented for future scope. See [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md), [USER_JOURNEYS.md — Deferred Journeys](USER_JOURNEYS.md#deferred-journeys-transformation-pipeline), and [Transformation Pipeline Backlog](BACKLOG_TRANSFORMATION_PIPELINE.md).

**Related user journeys** (all **Deferred**): JOURNEY-DPO-008 (Create Transformation Pipeline for Asset), JOURNEY-DE-007 (Create Transformation Pipeline), JOURNEY-DC-007 (Create Transformation Pipeline for Data), JOURNEY-DEV-006 (Integrate Transformation Pipeline API), JOURNEY-AUD-005 (Audit Transformation Pipelines), JOURNEY-DA-001 (Create Transformation Pipeline). Any use case that would map to a dedicated "Create/Execute/Validate Transformation Pipeline" API is deferred with these journeys.

### Implemented (Backend)

The following use cases have backend support (OpenAPI/runtime). Frontend and E2E SHALL provide or extend UI and tests per `openspec/changes/frontdev1` (ROUTE_MAP, JOURNEY_COVERAGE_MATRIX, USE_CASE_COVERAGE_MATRIX).

#### UC-AM-002: Publish Asset to Marketplace

**ID**: UC-AM-002
**Title**: Publish Asset to Marketplace
**Persona**: Data Product Owner
**Priority**: High
**Status**: MVP
**Backend status**: Implemented. `hub/apps/marketplace` — listings create/update/retrieve.

**Description**: User publishes an asset as a marketplace listing with metadata, pricing (if supported), and eligibility.

**Preconditions**: User authenticated with DATA_PROVIDER role; asset exists and is activated; tenant/marketplace enabled.

**Main Flow**: 1. User navigates to marketplace publish flow (e.g. `/marketplace/publish`). 2. User selects asset and configures listing (title, description, pricing). 3. System creates or updates listing via API. 4. Listing is visible in marketplace.

**Postconditions**: Listing created/updated; entitlement and purchase flows available per UC-DC-001.

**API Endpoints**: `marketplace_listings_create`, `marketplace_listings_update`, `marketplace_listings_retrieve`

**Related Use Cases**: UC-AM-001, UC-DC-001, UC-DPO-002

---

#### UC-CM-001: Manage Data Community

**ID**: UC-CM-001
**Title**: Manage Data Community
**Persona**: Community Manager, Data Product Owner, Data Consumer
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/social` — CommunityViewSet, `create_or_join_community`.

**Description**: User creates or joins a data community; community membership and metadata are managed.

**Preconditions**: User authenticated; social/communities feature enabled.

**Main Flow**: 1. User navigates to communities (`/communities`; `/social` redirects to `/communities`). 2. User creates a new community or joins existing via API. 3. System creates/updates community and membership.

**Postconditions**: Community exists; user is member; community discoverable per UC-SOCIAL-004.

**API Endpoints**: `create_or_join_community` (POST); community list/detail per OpenAPI.

**Related Use Cases**: UC-SOCIAL-004, UC-CM-002, UC-CM-003

---

#### UC-CM-002: Moderate Reviews and Ratings

**ID**: UC-CM-002
**Title**: Moderate Reviews and Ratings
**Persona**: Community Manager
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/social` — Review model with status (PENDING, APPROVED, REJECTED); review list/update per OpenAPI.

**Description**: User moderates asset reviews and ratings (approve/reject; optional edit).

**Preconditions**: User with moderation permission; reviews exist.

**Main Flow**: 1. User navigates to reviews or asset detail. 2. User views pending reviews. 3. User approves or rejects; system updates status.

**Postconditions**: Review status updated; approved reviews visible to consumers.

**API Endpoints**: Review list/retrieve/update per `hub/apps/social/urls.py`.

**Related Use Cases**: UC-SOCIAL-002, UC-DC-008, UC-CM-001

---

#### UC-CM-003: Assign Data Steward

**ID**: UC-CM-003
**Title**: Assign Data Steward
**Persona**: Community Manager, Data Product Owner
**Priority**: Medium
**Status**: New
**Backend status**: Partially implemented. `users_list`, `users_roles_list`; asset steward assignment may be limited — gate UI by endpoint availability.

**Description**: User assigns data stewards to assets; stewardship is visible and auditable.

**Preconditions**: User with steward-assignment permission; users and roles available.

**Main Flow**: 1. User opens asset detail (stewardship panel). 2. User selects user(s) and role(s). 3. System assigns steward where endpoint exists.

**Postconditions**: Steward assignment recorded or limitation clearly shown in UI.

**API Endpoints**: `users_list`, `users_roles_list`; asset steward endpoint if present (see JOURNEY-DPO-011, JOURNEY-CM-003).

**Related Use Cases**: UC-SOCIAL-006, UC-AM-001, UC-CM-001

---

#### UC-COMP-001: Run Compliance Scan / Review Compliance for Asset

**ID**: UC-COMP-001
**Title**: Run Compliance Scan / Review Compliance for Asset
**Persona**: Compliance Officer, Data Product Owner
**Priority**: High
**Status**: MVP
**Backend status**: Implemented. `hub/apps/compliance` — ComplianceRun, compliance runs list/detail/results; scan execution via job.

**Description**: User triggers a compliance run for an asset/file or reviews existing compliance run results.

**Preconditions**: User authenticated; compliance feature enabled; asset or file available.

**Main Flow**: 1. User navigates to compliance runs (e.g. `/compliance/runs`). 2. User creates a run via **AssetPicker**, **DatasetPicker**, **FilePicker** (searchable dropdowns; cascading when selecting asset). 3. System executes scan; user views results and remediation guidance.

**Postconditions**: Compliance run recorded; results and risk level visible; fail-closed guidance when applicable.

**API Endpoints**: `compliance_runs_list`, `compliance_runs_create`, `get_compliance_run_results`

**Related Use Cases**: UC-AM-001, UC-CPO-001, UC-DQ-001, UC-AI-005

---

#### UC-CPO-009: Configure Automated Retention Policies

**ID**: UC-CPO-009
**Title**: Configure Automated Retention Policies
**Persona**: Compliance Officer
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/governance` — RetentionPolicy, RetentionPolicyEnforcer, retention_views; CRUD via OpenAPI.

**Description**: User creates or updates retention policies (time-based or event-based); system enforces retention.

**Preconditions**: User with governance/admin permission; governance feature enabled.

**Main Flow**: 1. User navigates to governance (e.g. `/governance`). 2. User lists retention policies; creates or updates policy via **AssetPicker**, **DatasetPicker**, **FilePicker** (searchable dropdowns; cascading). 3. System validates and stores; enforcer runs per schedule.

**Postconditions**: Policy active; retention actions (soft delete, archive, etc.) applied per policy.

**API Endpoints**: `governance_retention_policies_list`, `governance_retention_policies_create`, `governance_retention_policies_update`

**Related Use Cases**: UC-GOV-ADV-004, UC-CPO-003, JOURNEY-CPO-003

---

#### UC-DA-003: Query Virtual Dataset

**ID**: UC-DA-003
**Title**: Query Virtual Dataset
**Persona**: Data Analyst
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/virtualization` — query create, progress, result.

**Description**: User runs a query against a virtual dataset and views results.

**Preconditions**: User authenticated; virtual dataset exists; virtualization enabled.

**Main Flow**: 1. User navigates to virtualization query (e.g. `/virtualization/query`). 2. User selects dataset and enters/submits query. 3. System executes; user sees progress and results.

**Postconditions**: Query executed; results displayed and optionally exported.

**API Endpoints**: `virtualization_datasets_queries_create`, `virtualization_queries_result_retrieve`, `virtualization_queries_progress_retrieve`

**Related Use Cases**: UC-VIRT-002, UC-DA-004, JOURNEY-DA-003

---

#### UC-DA-004: Execute Federated Query

**ID**: UC-DA-004
**Title**: Execute Federated Query
**Persona**: Data Analyst, Data Engineer
**Priority**: High
**Status**: New
**Backend status**: Implemented. Same as UC-DA-003; virtualization backend supports federated execution.

**Description**: User executes a federated query across sources; system runs and returns combined results.

**Preconditions**: As UC-DA-003; federated topology configured.

**Main Flow**: 1. User composes federated query. 2. System executes across sources. 3. User sees results or partial results and errors.

**Postconditions**: Federated query completed or failure clearly reported.

**API Endpoints**: As UC-DA-003; topology endpoints if exposed.

**Related Use Cases**: UC-VIRT-002, UC-DA-003, JOURNEY-DA-004

---

#### UC-DC-001: Discover and Purchase Marketplace Asset

**ID**: UC-DC-001
**Title**: Discover and Purchase Marketplace Asset
**Persona**: Data Consumer
**Priority**: High
**Status**: MVP
**Backend status**: Implemented. `hub/apps/marketplace` — listings list, purchase, entitlements.

**Description**: User discovers a listing, purchases (or requests access), and sees entitlement.

**Preconditions**: User authenticated; marketplace enabled; listing available.

**Main Flow**: 1. User browses/search listings. 2. User opens listing detail; optionally preview (UC-DC-012). 3. User purchases or requests access. 4. Entitlement visible in entitlements list.

**Postconditions**: Order placed; entitlement active; user can access per contract.

**API Endpoints**: `marketplace_listings_list`, `marketplace_listings_retrieve`, `marketplace_orders_purchase_create`, `marketplace_entitlements_list`

**Related Use Cases**: UC-AI-001, UC-DC-012, UC-DC-013, UC-AM-002

---

#### UC-DC-006: Use Natural Language Search

**ID**: UC-DC-006
**Title**: Use Natural Language Search
**Persona**: Data Consumer, Data Scientist
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/ai` — `natural_language_search`; `hub/apps/search` — `search_search_retrieve`.

**Description**: User searches for data using natural language; system returns results (and optionally query interpretation).

**Preconditions**: User authenticated; NL search enabled; LLM/service available when required.

**Main Flow**: 1. User navigates to search (e.g. `/search`, `/ai/search`). 2. User enters natural language query. 3. System returns results or interpretation.

**Postconditions**: Results displayed; user can navigate to assets/listings.

**API Endpoints**: `natural_language_search`, `search_search_retrieve`

**Related Use Cases**: UC-AI-001, UC-AI-008, JOURNEY-DC-006, JOURNEY-DS-001

---

#### UC-DC-008: Rate and Review Asset

**ID**: UC-DC-008
**Title**: Rate and Review Asset
**Persona**: Data Consumer, Data Product Owner
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/social` — submit_rating, submit_review; Rating, Review models.

**Description**: User submits a rating and/or review for an asset; moderation may apply.

**Preconditions**: User authenticated; asset exists; social feature enabled.

**Main Flow**: 1. User opens asset detail (Community section on asset page, Phase 27.1). 2. User submits rating (1–5) and/or review text. 3. System stores; status PENDING or APPROVED per config.

**Postconditions**: Rating/review stored; visible to others after moderation if applicable.

**API Endpoints**: `submit_rating`, `submit_review`

**Related Use Cases**: UC-SOCIAL-001, UC-SOCIAL-002, UC-CM-002

---

#### UC-DC-011: Purchase Asset with Usage-Based Pricing

**ID**: UC-DC-011
**Title**: Purchase Asset with Usage-Based Pricing
**Persona**: Data Consumer
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. Marketplace listing/order schema supports usage-based pricing; UI gated by schema.

**Description**: User selects usage-based pricing option when purchasing and completes order.

**Preconditions**: Listing supports usage-based pricing; user eligible.

**Main Flow**: 1. User selects listing with usage-based plan. 2. User confirms pricing and purchases. 3. Entitlement reflects usage-based terms.

**Postconditions**: Order completed; entitlement active; metering/usage per contract.

**API Endpoints**: `marketplace_orders_purchase_create`, listing schema for pricing

**Related Use Cases**: UC-DC-001, UC-MKT-ADV-001, UC-DPO-010

---

#### UC-DC-012: Preview Data Before Purchase

**ID**: UC-DC-012
**Title**: Preview Data Before Purchase
**Persona**: Data Consumer
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/marketplace` — preview_marketplace_listing (or equivalent per OpenAPI).

**Description**: User previews data or sample before purchasing a listing.

**Preconditions**: Listing supports preview; user authenticated.

**Main Flow**: 1. User opens listing detail. 2. User triggers preview. 3. System returns sample or preview payload; user reviews.

**Postconditions**: Preview displayed; user can proceed to purchase (UC-DC-001).

**API Endpoints**: `preview_marketplace_listing` (or per OpenAPI)

**Related Use Cases**: UC-DC-001, UC-MKT-ADV-002

---

#### UC-DC-013: Use Asset Recommendations

**ID**: UC-DC-013
**Title**: Use Asset Recommendations
**Persona**: Data Consumer, Data Product Owner
**Priority**: Medium
**Status**: New
**Backend status**: Implemented or fallback. `assets_recommendations_retrieve` where available; otherwise UI shows empty or non-ML recommendations.

**Description**: User sees recommended assets (e.g. on home or catalog); recommendations may be ML-based or rule-based.

**Preconditions**: User authenticated; recommendation endpoint or fallback available.

**Main Flow**: 1. User navigates to catalog/home. 2. System fetches recommendations. 3. User sees list; can open asset detail.

**Postconditions**: Recommendations displayed; safe empty state when none.

**API Endpoints**: `assets_recommendations_retrieve` (or per OpenAPI)

**Related Use Cases**: UC-AI-004, UC-DC-001, UC-AM-001

---

#### UC-DE-005: CI/CD Integration

**ID**: UC-DE-005
**Title**: CI/CD Integration
**Persona**: Data Engineer, External Developer
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/developer` — SDK docs; `hub/apps/baas` — API keys. UI provides runnable snippets.

**Description**: User integrates platform with CI/CD using SDK docs and API keys; runs automated flows.

**Preconditions**: User authenticated; developer/BaaS access.

**Main Flow**: 1. User opens developer portal and SDK docs. 2. User creates/manages API keys (BaaS). 3. User copies snippets and configures pipeline.

**Postconditions**: CI/CD pipeline can call APIs; docs and keys current.

**API Endpoints**: `get_sdk_documentation`, `baas_api_keys_list`, `baas_api_keys_create`

**Related Use Cases**: UC-DEV-009, UC-INT-005, JOURNEY-DE-005

---

#### UC-DE-009: Set Up Data Virtualization

**ID**: UC-DE-009
**Title**: Set Up Data Virtualization
**Persona**: Data Engineer
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/virtualization` — datasets create/validate, queries create/progress/result.

**Description**: User creates and configures virtual datasets; runs queries and views results.

**Preconditions**: User authenticated; virtualization enabled.

**Main Flow**: 1. User creates virtual dataset (sources, schema). 2. User validates and saves. 3. User runs queries; views progress and results.

**Postconditions**: Virtual dataset available; query execution reliable (cancel/progress/result).

**API Endpoints**: `virtualization_datasets_create`, `virtualization_datasets_validate_create`, `virtualization_datasets_queries_create`, `virtualization_queries_result_retrieve`, `virtualization_queries_progress_retrieve`

**Related Use Cases**: UC-VIRT-001, UC-VIRT-002, UC-DA-003, JOURNEY-DE-009

---

#### UC-DE-010: Configure Connector for Data Source

**ID**: UC-DE-010
**Title**: Configure Connector for Data Source
**Persona**: Data Engineer, Tenant Admin
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/integrations` — connections create/list/test; connectors retrieve.

**Description**: User configures a connector to an external data source; tests connection.

**Preconditions**: User authenticated; integrations enabled; connector type available.

**Main Flow**: 1. User navigates to integrations connections. 2. User creates connection (credentials, config). 3. User runs connection test; fixes failures if any.

**Postconditions**: Connection created and tested; sync/jobs can use it (JOURNEY-MP-001–007).

**API Endpoints**: `integrations_marketplace_connections_create`, `integrations_marketplace_connections_test_create`, `integrations_marketplace_connectors_retrieve`

**Related Use Cases**: UC-INT-001, JOURNEY-DE-010, JOURNEY-MP-001

---

#### UC-DE-012: Create or Browse Custom Plugin

**ID**: UC-DE-012
**Title**: Create or Browse Custom Plugin
**Persona**: Data Engineer, External Developer
**Priority**: Medium
**Status**: New
**Backend status**: Partially implemented. `hub/apps/developer` — plugins list/retrieve; create not in OpenAPI — UI gate "create" or document external process.

**Description**: User browses available plugins; optionally creates custom plugin where backend supports.

**Preconditions**: User authenticated; developer portal enabled.

**Main Flow**: 1. User navigates to developer plugins. 2. User lists/inspects plugins. 3. Create flow only if endpoint exists; otherwise docs/external.

**Postconditions**: Plugins discoverable; creation path clear or explicitly limited.

**API Endpoints**: `developer_plugins_list`, `developer_plugins_retrieve`

**Related Use Cases**: UC-DEV-001, UC-DEV-002, JOURNEY-DE-012

---

#### UC-DEV-007: Build Custom Connector

**ID**: UC-DEV-007
**Title**: Build Custom Connector
**Persona**: External Developer, Data Engineer
**Priority**: Medium
**Status**: New
**Backend status**: Implemented (framework/docs). `hub/apps/integrations` — connectors retrieve; framework docs and examples; custom build may be external.

**Description**: User builds a custom connector using platform framework and docs; registers or deploys per capability.

**Preconditions**: User has developer/integration access; connector framework documented.

**Main Flow**: 1. User reads connector framework docs (integrations/developer). 2. User implements connector; tests against API if available. 3. User deploys or registers per process.

**Postconditions**: Custom connector available or process clearly documented.

**API Endpoints**: `integrations_marketplace_connectors_retrieve`; docs per developer portal.

**Related Use Cases**: UC-INT-002, UC-DE-010, JOURNEY-DEV-007

---

#### UC-DEV-008: Use Plugin System

**ID**: UC-DEV-008
**Title**: Use Plugin System
**Persona**: External Developer, Data Engineer
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/developer` — plugins list/retrieve; plugin usage per runtime.

**Description**: User discovers and uses plugins from the developer portal; installs or configures per platform.

**Preconditions**: User authenticated; plugins available.

**Main Flow**: 1. User navigates to developer plugins. 2. User lists and selects plugin. 3. User follows install/configure steps.

**Postconditions**: Plugin available for use; docs and limits clear.

**API Endpoints**: `developer_plugins_list`, `developer_plugins_retrieve`

**Related Use Cases**: UC-DEV-001, UC-DEV-009, JOURNEY-DEV-008

---

#### UC-DEV-009: Integrate with Developer Portal

**ID**: UC-DEV-009
**Title**: Integrate with Developer Portal
**Persona**: External Developer
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/developer` — SDK docs, plugins; portal UI at `/developer`.

**Description**: User accesses developer portal for SDK docs, plugins, and examples; builds integration.

**Preconditions**: User authenticated; developer portal enabled.

**Main Flow**: 1. User navigates to `/developer`. 2. User browses SDK docs and plugins. 3. User uses examples and API keys (BaaS) to integrate.

**Postconditions**: Portal navigable; docs and runnable examples available.

**API Endpoints**: `get_sdk_documentation`, `developer_plugins_list`

**Related Use Cases**: UC-DEV-001, UC-DEV-003, UC-DEV-004, UC-DE-005, JOURNEY-DEV-009

---

#### UC-DMO-001: Create Data Mesh Domain

**ID**: UC-DMO-001
**Title**: Create Data Mesh Domain
**Persona**: Data Mesh Domain Owner, Tenant Admin
**Priority**: High
**Status**: New
**Backend status**: Implemented. Same as UC-MESH-001. `hub/apps/mesh` — mesh_domains_create, mesh_domains_list.

**Description**: User creates a data mesh domain; domain is available for assignment and topology.

**Preconditions**: User with mesh/admin permission; mesh feature enabled.

**Main Flow**: 1. User navigates to mesh domains. 2. User creates domain (name, scope). 3. System creates domain; visible in list and topology.

**Postconditions**: Domain created; can be used in UC-MESH-002, UC-MESH-003.

**API Endpoints**: `mesh_domains_create`, `mesh_domains_list`, `mesh_domains_retrieve`

**Related Use Cases**: UC-MESH-001, UC-MESH-002, UC-MESH-003

---

#### UC-DMO-002: Configure Federated Governance

**ID**: UC-DMO-002
**Title**: Configure Federated Governance
**Persona**: Data Mesh Domain Owner, Compliance Officer
**Priority**: High
**Status**: New
**Backend status**: Implemented. Same as UC-MESH-002. `hub/apps/mesh` — domain policies list/apply.

**Description**: User configures federated governance policies for a mesh domain.

**Preconditions**: Domain exists; user with governance permission.

**Main Flow**: 1. User opens domain detail/policies. 2. User defines or applies policies. 3. System stores and applies per mesh engine.

**Postconditions**: Policies active; governance auditable.

**API Endpoints**: `mesh_domains_policies_list`, `mesh_domains_policies_apply_create`

**Related Use Cases**: UC-MESH-002, UC-DMO-001, UC-DMO-003

---

#### UC-DMO-003: Manage Domain Topology

**ID**: UC-DMO-003
**Title**: Manage Domain Topology
**Persona**: Data Mesh Domain Owner, Platform Admin
**Priority**: High
**Status**: New
**Backend status**: Implemented. Same as UC-MESH-003. `hub/apps/mesh` — topology list, relationships.

**Description**: User views and manages domain topology (graph of domains, assets, relationships).

**Preconditions**: Mesh enabled; topology data available.

**Main Flow**: 1. User navigates to topology view. 2. System displays graph. 3. User explores and optionally updates where supported.

**Postconditions**: Topology visible and performant; relationships clear.

**API Endpoints**: `mesh_topology_list`, `mesh_topology_relationships_retrieve`

**Related Use Cases**: UC-MESH-003, UC-DMO-001, UC-DMO-005, JOURNEY-MPA-007

---

#### UC-DMO-005: Monitor Domain Health

**ID**: UC-DMO-005
**Title**: Monitor Domain Health
**Persona**: Data Mesh Domain Owner, Platform Admin
**Priority**: Medium
**Status**: New
**Backend status**: Partially implemented. `mesh_topology_health_retrieve` where available; observability metrics may be limited — gate UI by endpoint.

**Description**: User monitors health of mesh domains and related resources.

**Preconditions**: Mesh and optionally observability enabled.

**Main Flow**: 1. User opens topology or observability. 2. User views health metrics per domain. 3. Alerts or degradation visible when supported.

**Postconditions**: Health view usable; limits documented when advanced metrics absent.

**API Endpoints**: `mesh_topology_health_retrieve`; `observability_metrics_create` if exposed.

**Related Use Cases**: UC-MESH-005, UC-DMO-003, JOURNEY-DPO-014

---

#### UC-DPO-002: Publish Asset to Marketplace

**ID**: UC-DPO-002
**Title**: Publish Asset to Marketplace
**Persona**: Data Product Owner
**Priority**: High
**Status**: MVP
**Backend status**: Implemented. Same capability as UC-AM-002; marketplace listings create/update.

**Description**: User publishes an asset as a marketplace listing.

**Preconditions**: Asset activated; user DATA_PROVIDER; marketplace enabled.

**Main Flow**: 1. User selects asset and navigates to publish. 2. User configures listing. 3. Listing created/updated; visible in marketplace.

**Postconditions**: Listing live; consumers can discover and purchase (UC-DC-001).

**API Endpoints**: `marketplace_listings_create`, `marketplace_listings_update`, `marketplace_listings_retrieve`

**Related Use Cases**: UC-AM-002, UC-DC-001, JOURNEY-DPO-002

---

#### UC-DPO-010: Publish Asset with Usage-Based Pricing

**ID**: UC-DPO-010
**Title**: Publish Asset with Usage-Based Pricing
**Persona**: Data Product Owner
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. Marketplace listing schema supports usage-based pricing; UI derives knobs from schema.

**Description**: User configures usage-based pricing when publishing a listing.

**Preconditions**: Marketplace supports pricing schema; user publishing listing.

**Main Flow**: 1. User in publish flow selects usage-based pricing. 2. User configures tiers/limits. 3. Listing saved with pricing; consumers see it (UC-DC-011).

**Postconditions**: Listing has usage-based terms; purchase flow supports it.

**API Endpoints**: `marketplace_listings_update` (schema-driven pricing fields)

**Related Use Cases**: UC-DPO-002, UC-DC-011, UC-MKT-ADV-001

---

#### UC-DPO-014: Create ODPS Product (Product-First Flow)

**ID**: UC-DPO-014
**Title**: Create ODPS Product (Product-First Flow)
**Persona**: Data Product Owner
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/contracts` — contracts_products_create, contracts_products_status_retrieve; ODPS upload/workflow.

**Description**: User creates an ODPS product via product-first flow (upload, workflow, link to ODCS).

**Preconditions**: User authenticated; contracts/ODPS enabled.

**Main Flow**: 1. User uploads ODPS product (e.g. `/odps/upload`). User selects target asset via **AssetPicker** (searchable dropdown). 2. System runs workflow; user sees status. 3. User links to ODCS contract where required; exports if supported.

**Postconditions**: ODPS product created; workflow traceable; link/export available per JOURNEY-DPO-015–017.

**API Endpoints**: `contracts_products_create`, `contracts_products_status_retrieve`, `contracts_retrieve`

**Related Use Cases**: UC-DMO-005, JOURNEY-DPO-015, JOURNEY-DPO-016, JOURNEY-DPO-017

---

#### UC-DQ-001: Run Data Quality Check / Monitor Asset Quality

**ID**: UC-DQ-001
**Title**: Run Data Quality Check / Monitor Asset Quality
**Persona**: Data Product Owner, Data Engineer, Compliance Officer
**Priority**: High
**Status**: MVP
**Backend status**: Implemented. `hub/apps/dq` — DQ runs create/list/results; assets health score where available.

**Description**: User runs a data quality check (e.g. on intake or ad hoc) or monitors asset quality results.

**Preconditions**: User authenticated; DQ feature enabled; asset or dataset available.

**Main Flow**: 1. User navigates to DQ runs (e.g. `/dq/runs`). 2. User creates run via **AssetPicker**, **DatasetPicker**, **FilePicker** (searchable dropdowns; cascading when selecting asset). 3. User views results and remediation guidance.

**Postconditions**: DQ run recorded; results and pass/fail visible; asset health usable when endpoint exists.

**API Endpoints**: `dq_runs_list`, `dq_runs_create`, `get_dq_run_results`; `assets_health_score_retrieve` for health

**Related Use Cases**: UC-AM-001, UC-COMP-001, UC-AI-006, UC-AI-007, JOURNEY-DPO-004

---

### Category: Scheduled Export / Data Operations

#### UC-EXPORT-001: Schedule Recurring Export

**ID**: UC-EXPORT-001
**Title**: Schedule Recurring Export
**Persona**: Data Engineer, Data Product Owner
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/scheduled_export` — scheduled_exports_create, scheduled_exports_list, scheduled_exports_retrieve; Prefect integration.

**Description**: Tenant configures a scheduled export (source scope, destination, schedule) and runs are executed by Prefect workers.

**Preconditions**: User authenticated; assets/datasets/files exist for export scope.

**Main Flow**:
1. User navigates to scheduled exports page
2. User creates scheduled export with source scope via **AssetMultiPicker**, **DatasetMultiPicker**, **FileMultiPicker**, **ContractPicker** (searchable dropdowns)
3. User configures destination (S3/GCS/Azure Blob) and credentials
4. User sets schedule (cron expression)
5. System syncs export to Prefect deployment
6. Prefect worker executes exports according to schedule

**Postconditions**: Scheduled export created; Prefect deployment synced; exports run automatically.

**API Endpoints**: `scheduled_exports_create`, `scheduled_exports_list`, `scheduled_exports_retrieve`

**Related Use Cases**: UC-EXPORT-002, UC-EXPORT-003, UC-EXPORT-004, JOURNEY-EXPORT-001

---

#### UC-EXPORT-002: Configure Export Destination

**ID**: UC-EXPORT-002
**Title**: Configure Export Destination
**Persona**: Data Engineer, Data Product Owner
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/scheduled_export` — scheduled_exports_update; destination configuration stored in hub.

**Description**: Tenant sets destination type (S3/GCS/Azure Blob) and path/prefix. Credentials configured via Prefect Blocks or environment variables.

**Preconditions**: Scheduled export exists or being created.

**Main Flow**:
1. User selects destination type (S3, GCS, Azure Blob)
2. User configures bucket/container name and prefix/path
3. User configures credentials (via Prefect Blocks or environment variables)
4. System validates destination configuration
5. Configuration stored in hub (credentials masked in API responses)

**Postconditions**: Export destination configured; credentials stored securely.

**API Endpoints**: `scheduled_exports_create`, `scheduled_exports_update`

**Related Use Cases**: UC-EXPORT-001, UC-EXPORT-003, JOURNEY-EXPORT-001

---

#### UC-EXPORT-003: Monitor Export Runs

**ID**: UC-EXPORT-003
**Title**: Monitor Export Runs
**Persona**: Data Engineer, Data Product Owner
**Priority**: High
**Status**: New
**Backend status**: Implemented. `hub/apps/scheduled_export` — scheduled_export_runs_list, scheduled_export_runs_retrieve; run status tracking.

**Description**: Tenant views run history, status, counts (items_exported, items_failed), and optional Prefect link.

**Preconditions**: Scheduled export exists; at least one run has been executed.

**Main Flow**:
1. User navigates to scheduled export detail page
2. User views run list with status, timestamps, counts
3. User opens run detail to see full information
4. User optionally clicks "View in Prefect" to see Prefect flow run details
5. User interprets status (RUNNING, COMPLETED, FAILED, CANCELLED)

**Postconditions**: User understands export run status and history.

**API Endpoints**: `scheduled_export_runs_list`, `scheduled_export_runs_retrieve`

**Related Use Cases**: UC-EXPORT-001, UC-EXPORT-004, JOURNEY-EXPORT-001, JOURNEY-EXPORT-002

---

#### UC-EXPORT-004: Manual Trigger of Scheduled Export

**ID**: UC-EXPORT-004
**Title**: Manual Trigger of Scheduled Export
**Persona**: Data Engineer, Data Product Owner
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/scheduled_export` — scheduled_exports_trigger; triggers Prefect flow run.

**Description**: Tenant triggers a one-off run of a scheduled export.

**Preconditions**: Scheduled export exists and is ACTIVE.

**Main Flow**:
1. User navigates to scheduled export detail page
2. User clicks "Trigger Export" button
3. System creates Prefect flow run
4. System creates hub run record (status RUNNING)
5. Prefect worker executes export
6. User can monitor run status

**Postconditions**: Export run triggered; run visible in run history.

**API Endpoints**: `scheduled_exports_trigger`

**Related Use Cases**: UC-EXPORT-001, UC-EXPORT-003, JOURNEY-EXPORT-001

---

#### UC-TA-008: Configure Integration Ecosystem

**ID**: UC-TA-008
**Title**: Configure Integration Ecosystem
**Persona**: Tenant Admin
**Priority**: Medium
**Status**: New
**Backend status**: Implemented. `hub/apps/integrations` — connections, sync jobs, mappings; tenant-scoped.

**Description**: Tenant admin configures integrations (connections, sync jobs, mappings) for the tenant.

**Preconditions**: User TENANT_ADMIN; integrations enabled.

**Main Flow**: 1. User navigates to integrations. 2. User manages connections, sync jobs, mappings. 3. System applies config; jobs run per schedule or trigger.

**Postconditions**: Integrations configured; failures actionable; JOURNEY-MP-001–007 supported.

**API Endpoints**: `integrations_marketplace_connections_create/list`, `integrations_marketplace_sync_create/list`, `integrations_marketplace_mappings_list`

**Related Use Cases**: UC-DE-010, UC-INT-001, JOURNEY-TA-008, JOURNEY-MP-007

---

### Not Implemented (Backend)

The following use case IDs are referenced in the doc but **have no backend implementation** (no OpenAPI endpoints or runtime support). UI SHALL NOT implement these flows until backend exists; show `/unavailable` or clear "not available" message. See `openspec/changes/frontdev1/artifacts/JOURNEY_COVERAGE_MATRIX.md` (Red journeys) and `USE_CASE_COVERAGE_MATRIX.md`.

#### UC-CM-004: Manage Activity Feed

**ID**: UC-CM-004
**Title**: Manage Activity Feed
**Persona**: Community Manager
**Backend status**: **Not implemented.** Same as UC-SOCIAL-005; no activity feed API in `hub/apps/social`. UI: N/A or `/unavailable`.

**Related Use Cases**: UC-SOCIAL-005, UC-SOCIAL-004

---

#### UC-CPO-006: Configure Automated Compliance

**ID**: UC-CPO-006
**Title**: Configure Automated Compliance
**Persona**: Compliance Officer
**Backend status**: **Not implemented.** No dedicated automated-compliance configuration API in OpenAPI. (UC-GOV-ADV-001 describes the capability; backend not evidenced.) UI: `/unavailable`.

**Related Use Cases**: UC-GOV-ADV-001, UC-CPO-007

---

#### UC-CPO-007: Set Up GDPR Right to be Forgotten

**ID**: UC-CPO-007
**Title**: Set Up GDPR Right to be Forgotten
**Persona**: Compliance Officer
**Backend status**: ✅ **Implemented (Phase 25.5.2)**. GDPR erasure workflow API available. See UC-GOV-ADV-002 for details.

**Related Use Cases**: UC-GOV-ADV-002, UC-CPO-006

---

#### UC-CPO-008: Manage Consent Tracking

**ID**: UC-CPO-008
**Title**: Manage Consent Tracking
**Persona**: Compliance Officer
**Backend status**: **Not implemented.** No consent model or consent-tracking API; only legal_basis (e.g. CONSENT) in contracts. UI: `/unavailable`.

**Related Use Cases**: UC-GOV-ADV-003, UC-CPO-007

---

#### UC-CPO-010: Review AI Auto-Classification Results

**ID**: UC-CPO-010
**Title**: Review AI Auto-Classification Results
**Persona**: Compliance Officer
**Backend status**: **Not implemented.** AI classification endpoints not evidenced in OpenAPI. See `artifacts/AI_ENDPOINTS_VERIFICATION.md`. UI: `/unavailable`; DPO flow unblocked via manual classification where supported.

**Related Use Cases**: UC-AI-005, UC-AM-001

---

#### UC-DE-011: Set Up Reverse ETL

**ID**: UC-DE-011
**Title**: Set Up Reverse ETL
**Persona**: Data Engineer
**Backend status**: **Not implemented.** No reverse ETL endpoints in OpenAPI. UI: `/unavailable`.

**Related Use Cases**: UC-INT-004, JOURNEY-DE-011

---

#### UC-DEV-002: Create Custom Plugin

**ID**: UC-DEV-002
**Title**: Create Custom Plugin
**Persona**: External Developer, Data Engineer
**Backend status**: **Not implemented.** Only plugin list/retrieve exist; no plugin creation API. UI: browse only; create path external or `/unavailable`.

**Related Use Cases**: UC-DEV-001, UC-DEV-008, JOURNEY-DE-012

---

#### UC-TA-007: Monitor Cost Tracking

**ID**: UC-TA-007
**Title**: Monitor Cost Tracking
**Persona**: Tenant Admin
**Backend status**: **Implemented.** GET /api/v1/analytics/costs/ (summary, breakdown, by-asset, recommendations, trends). Usage → cost via CostTrackingService (storage, API, ingestion from IngestionCost). UI: `/settings/cost` (CostPage).

**Related Use Cases**: UC-OBS-ADV-002, JOURNEY-TA-007

---

## Use Case Matrix

| Use Case ID | Title | Persona | Priority | Status | Category | New Feature |
|-------------|-------|---------|----------|--------|----------|-------------|
| UC-AI-001 | Natural Language Search | Data Consumer, Data Scientist | High | New | AI/ML | **NEW** |
| UC-AI-002 | AI Schema Matching | Data Product Owner, Data Engineer, Data Scientist | High | New | AI/ML | **NEW** |
| UC-AI-003 | ML-Based Anomaly Detection | Data Product Owner, Data Scientist | High | New | AI/ML | **NEW** |
| UC-AI-004 | Smart Recommendations | Data Consumer, Data Product Owner | Medium | New | AI/ML | **NEW** |
| UC-AI-005 | Auto-Classification | Data Product Owner, Compliance Officer, Data Scientist | High | New | AI/ML | **NEW** |
| UC-AI-006 | Predictive Quality Forecasting | Data Product Owner, Data Scientist | Medium | New | AI/ML | **NEW** |
| UC-AI-007 | Auto-Generated Quality Rules | Data Product Owner, Data Scientist | Medium | New | AI/ML | **NEW** |
| UC-AI-008 | Query-to-SQL Translation | Data Consumer, Data Scientist | High | New | AI/ML | **NEW** |
| UC-AI-009 | ML Model Training | Data Scientist | Medium | New | AI/ML | **NEW** |
| UC-AI-010 | Recommendation Feedback Loop | Data Consumer, Data Scientist | Medium | New | AI/ML | **NEW** |
| UC-SOCIAL-001 | Rate Asset | Data Consumer, Data Product Owner | Medium | New | Social | **NEW** |
| UC-SOCIAL-002 | Review Asset | Data Consumer, Data Product Owner | Medium | New | Social | **NEW** |
| UC-SOCIAL-003 | Comment on Asset | Data Consumer, Data Product Owner | Low | New | Social | **NEW** |
| UC-SOCIAL-004 | Join Data Community | Data Consumer, Data Product Owner, Community Manager | Low | New | Social | **NEW** |
| UC-SOCIAL-005 | Manage Activity Feed | Data Consumer, Data Product Owner, Community Manager | Low | New | Social | **NEW** |
| UC-SOCIAL-006 | Assign Data Steward | Data Product Owner, Community Manager | Medium | New | Social | **NEW** |
| UC-MESH-001 | Create Data Mesh Domain | Data Mesh Domain Owner, Tenant Admin | High | New | Data Mesh | **NEW** |
| UC-MESH-002 | Configure Federated Governance | Data Mesh Domain Owner, Compliance Officer | High | New | Data Mesh | **NEW** |
| UC-MESH-003 | Manage Domain Topology | Data Mesh Domain Owner, Platform Admin | Medium | New | Data Mesh | **NEW** |
| UC-MESH-004 | Assign Domain Ownership | Data Mesh Domain Owner, Tenant Admin | Medium | New | Data Mesh | **NEW** |
| UC-MESH-005 | Monitor Mesh Health | Data Mesh Domain Owner, Platform Admin | Medium | New | Data Mesh | **NEW** |
| UC-VIRT-001 | Create Virtual Dataset | Data Engineer, Data Analyst | High | New | Virtualization | **NEW** |
| UC-VIRT-002 | Execute Federated Query | Data Analyst, Data Engineer | High | New | Virtualization | **NEW** |
| UC-VIRT-003 | Manage Federation Topology | Data Engineer, Platform Admin | Medium | New | Virtualization | **NEW** |
| UC-VIRT-004 | Monitor Virtualization Performance | Data Engineer, Platform Admin | Medium | New | Virtualization | **NEW** |
| UC-MKT-ADV-001 | Configure Usage-Based Pricing | Data Product Owner, Platform Admin | High | New | Advanced Marketplace | **NEW** |
| UC-MKT-ADV-002 | Preview Data Before Purchase | Data Consumer | High | New | Advanced Marketplace | **NEW** |
| UC-MKT-ADV-003 | Manage Trust Signals | Data Product Owner, Platform Admin | Medium | New | Advanced Marketplace | **NEW** |
| UC-MKT-ADV-004 | Track Revenue Analytics | Data Product Owner, Platform Admin | Medium | New | Advanced Marketplace | **NEW** |
| UC-MKT-ADV-005 | Configure Data Quality SLAs | Data Product Owner, Platform Admin | Medium | New | Advanced Marketplace | **NEW** |
| UC-GOV-ADV-001 | Configure Automated Compliance | Compliance Officer, Tenant Admin | High | New | Advanced Governance | **NEW** |
| UC-GOV-ADV-002 | Set Up GDPR Right to be Forgotten | Compliance Officer | High | New | Advanced Governance | **NEW** |
| UC-GOV-ADV-003 | Manage Consent Tracking | Compliance Officer | High | New | Advanced Governance | **NEW** |
| UC-GOV-ADV-004 | Configure Automated Retention | Compliance Officer | Medium | New | Advanced Governance | **NEW** |
| UC-OBS-ADV-001 | Monitor Reliability Scores | Data Product Owner, Platform Admin | Medium | New | Advanced Observability | **NEW** |
| UC-OBS-ADV-002 | Track Data Costs | Tenant Admin, Platform Admin | Medium | New | Advanced Observability | **NEW** |
| UC-OBS-ADV-003 | Set Up Predictive Alerts | Platform Admin, Data Product Owner | Medium | New | Advanced Observability | **NEW** |
| UC-OBS-ADV-004 | Monitor Performance Regressions | Platform Admin, Data Engineer | Medium | New | Advanced Observability | **NEW** |
| UC-INT-001 | Install Pre-built Connector | Data Engineer, Tenant Admin | High | New | Integration Ecosystem | **NEW** |
| UC-INT-002 | Create Custom Connector | Data Engineer, External Developer | Medium | New | Integration Ecosystem | **NEW** |
| UC-INT-003 | Integrate BI Tool | Data Engineer, Tenant Admin | High | New | Integration Ecosystem | **NEW** |
| UC-INT-004 | Set Up Reverse ETL | Data Engineer | Medium | New | Integration Ecosystem | **NEW** |
| UC-INT-005 | Integrate CI/CD Pipeline | Data Engineer, External Developer | Medium | New | Integration Ecosystem | **NEW** |
| UC-DEV-001 | Install Plugin | External Developer, Data Engineer | Medium | New | Developer Experience | **NEW** |
| UC-DEV-002 | Create Custom Plugin | External Developer, Data Engineer | Medium | New | Developer Experience | **NEW** |
| UC-DEV-003 | Use CLI Tool | External Developer, Data Engineer | Medium | New | Developer Experience | **NEW** |
| UC-DEV-004 | Access Developer Portal | External Developer | Medium | New | Developer Experience | **NEW** |
| UC-EXPORT-001 | Schedule Recurring Export | Data Engineer, Data Product Owner | High | New | Scheduled Export | **NEW** |
| UC-EXPORT-002 | Configure Export Destination | Data Engineer, Data Product Owner | High | New | Scheduled Export | **NEW** |
| UC-EXPORT-003 | Monitor Export Runs | Data Engineer, Data Product Owner | High | New | Scheduled Export | **NEW** |
| UC-EXPORT-004 | Manual Trigger of Scheduled Export | Data Engineer, Data Product Owner | Medium | New | Scheduled Export | **NEW** |
| UC-AUTH-001 | User Registers (Self-Service Sign-Up) | Visitor, Prospect | High | MVP | Authentication & Access | **NEW** |
| UC-AUTH-002 | User Logs In | Visitor, any persona | High | MVP | Authentication & Access | **NEW** |
| UC-AUTH-003 | User Resets Password | Visitor, any persona | Medium | MVP | Authentication & Access | **NEW** |
| UC-AUTH-004 | Unauthenticated User Accesses Public Resources | Visitor | Medium | MVP | Authentication & Access | **NEW** |
| UC-AUTH-005 | User Switches Active Tenant | Any with multiple tenants | High | MVP | Authentication & Access | **NEW** |

**Total**: ~114 use cases (~50 original + ~59 new + 5 authentication & access)

---

**Last Updated**: 2026-02-03
**Version**: 2.3.0 (Added Scheduled Export use cases UC-EXPORT-001–004; ~113 total use cases)

## Related Documentation

- **[User Journeys](USER_JOURNEYS.md)** - Detailed user journey maps including Visitor/Authentication (JOURNEY-AUTH-001–004) and marketplace flows
- **[User Personas](USER_PERSONAS.md)** - Personas including Visitor/Prospect and role-based personas
- **[Features](FEATURES.md)** - Feature documentation including Auth and Capabilities ↔ Use Cases matrix
- **[Test Traceability](TEST_TRACEABILITY.md)** - Comprehensive test traceability matrix mapping features, use cases, and journeys to tests
- **[Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)** - Versioning API (Phase 2), Observability lineage (Phase 1), Workflows API (Phase 3), Transformation pipeline (Deferred, Phase 5); traceability aligned with this plan
- **[Marketplace Use Cases](MARKETPLACE_USE_CASES.md)** - External marketplace integration use cases
- **[Marketplace User Journeys](MARKETPLACE_USER_JOURNEYS.md)** - Marketplace user journeys
- **[Architecture](ARCHITECTURE.md)** - BaaS Platform and ODH Integration architecture
- **[API Reference](API_REFERENCE.md)** - BaaS Platform and ODH Integration APIs
- **[BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md)** - BaaS Platform CLI commands
- **[BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md)** - BaaS Platform SDK APIs
- **[ODH Integration CLI Usage Guide](../cli/docs/ODH_USAGE.md)** - ODH Integration CLI commands
- **[ODH Integration SDK Usage Guide](../sdk/python/docs/ODH_USAGE.md)** - ODH Integration SDK APIs
