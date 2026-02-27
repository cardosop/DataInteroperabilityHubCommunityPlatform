# Features Documentation

**Last Updated**: 2026-02-07
**Version**: 2.3.0

Complete documentation of all features and capabilities in the Data Interoperability Hub.

## Table of Contents

1. [Auth](#auth)
2. [Contracts](#contracts)
3. [ODPS (Open Data Product Standard)](#odps-open-data-product-standard)
4. [Assets](#assets)
5. [Datasets](#datasets)
6. [Data Quality](#data-quality)
7. [Compliance](#compliance)
8. [Marketplace](#marketplace)
9. [Governance](#governance)
10. [Search](#search)
11. [Observability](#observability)
12. [Workflows](#workflows)
13. [Lineage](#lineage)
14. [Versioning](#versioning)
15. [BaaS](#baas)
16. [Integrations](#integrations)
17. [Jobs](#jobs)
18. [Files](#files)
19. [Semantic](#semantic)
20. [AI](#ai)
21. [ML](#ml)
22. [Social](#social)
23. [Data Mesh](#data-mesh)
24. [Virtualization](#virtualization)
25. [Scheduled Ingestion](#scheduled-ingestion)
26. [Scheduled Export](#scheduled-export)
27. [Webhooks](#webhooks)
28. [Audit](#audit)
29. [Health](#health)
30. [Supporting capabilities](#supporting-capabilities)
31. [Capabilities ↔ Features ↔ Use Cases](#capabilities--features--use-cases)
32. [Future roadmap](#future-roadmap)
33. [Related Documentation](#related-documentation)

---

## Auth

Authentication, registration, API keys, sessions, and optional SSO for unauthenticated and registered users.

### Key Features

- **Login**: Email/password authentication; JWT access and refresh tokens
- **Registration**: Self-service sign-up (when enabled); default tenant assignment
- **Password Reset**: Request and confirm password reset (optional/MVP)
- **API Keys**: Create and manage API keys for programmatic access
- **Sessions**: List active sessions; revoke sessions
- **Invitations**: Accept tenant/user invitations
- **SSO**: Optional single sign-on integration (SAML/OIDC)

### API Endpoints

- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/auth/register/` - User registration
- `POST /api/v1/auth/refresh/` - Refresh token
- `POST /api/v1/auth/logout/` - Logout
- `GET /api/v1/auth/me/` - Current user
- `POST /api/v1/auth/password-reset/` - Request password reset
- `POST /api/v1/auth/password-reset/confirm/` - Confirm password reset
- `POST /api/v1/auth/accept-invitation/` - Accept invitation
- `GET /api/v1/auth/sessions/` - List active sessions
- `POST /api/v1/auth/sessions/{id}/revoke/` - Revoke session
- `GET /api/v1/auth/api-keys/` - List API keys
- `POST /api/v1/auth/api-keys/` - Create API key
- `DELETE /api/v1/auth/api-keys/{id}/` - Delete API key

### Documentation

- [Use Cases – Authentication & Access](USE_CASES.md#authentication--access-use-cases) (UC-AUTH-001–004)
- [User Journeys – Visitor / Authentication](USER_JOURNEYS.md#visitor--authentication-journeys) (JOURNEY-AUTH-001–004)
- [User Personas – Visitor / Prospect](USER_PERSONAS.md#persona-0-visitor--prospect)
- [Test Traceability – Auth](TEST_TRACEABILITY.md#auth)

---

## Contracts

Data contract management, validation, normalization, and conversion.

### Key Features

- **Contract Creation**: Create contracts from various formats (ODCS, DataContract, HubContract)
- **Contract Validation**: Validate contracts against schemas
- **Contract Normalization**: Normalize contracts to HubContract format
- **Contract Conversion**: Convert between contract formats
- **Contract Linting**: Lint contracts for best practices
- **Contract Lineage**: Track contract dependencies and relationships
- **Contract Versioning**: Version contracts and track changes

### API Endpoints

- `GET /api/v1/contracts/` - List contracts
- `POST /api/v1/contracts/` - Create contract
- `GET /api/v1/contracts/{id}/` - Get contract
- `PUT /api/v1/contracts/{id}/` - Update contract
- `DELETE /api/v1/contracts/{id}/` - Delete contract
- `POST /api/v1/contracts/{id}/validate/` - Validate contract
- `POST /api/v1/contracts/{id}/lint/` - Lint contract
- `POST /api/v1/contracts/{id}/convert/` - Convert contract format

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#contracts)
- [Contract Normalization](NORMALIZATION_FOUNDATION.md)
- [Contract Lineage](MULTI_LEVEL_LINEAGE.md)

---

## ODPS (Open Data Product Standard)

ODPS (Open Data Product Standard) integration for marketplace-focused data product management, pricing, and access control.

### Key Features

- **ODPS Product Creation**: Create ODPS products with embedded ODCS contracts (Product-First flow)
  - Upload ODPS documents (JSON or YAML format)
  - Automatic ODCS extraction from `product.contract.spec`
  - Bidirectional linking between ODPS and ODCS contracts
  - Support for ODPS 4.1 and 4.0 versions
- **ODPS Linking**: Link ODPS products to existing ODCS contracts (Technical-First flow)
  - Link existing ODCS contracts to ODPS products
  - Validate linking compatibility
  - Establish bidirectional links
- **ODPS Export**: Export ODPS contracts in ODPS format
  - Export as JSON or YAML
  - Include linked ODCS contracts in `product.contract.spec`
  - Version-specific exports (4.1, 4.0)
- **ODPS Pricing Management**: Configure pricing plans, access methods, and payment gateways
  - Define multiple pricing plans (free, basic, premium, enterprise)
  - Configure access methods (API, download, streaming)
  - Set up payment gateways (Stripe, PayPal, bank transfer)
  - Support for usage-based and subscription pricing
- **ODPS Semantic Mapping**: Map ODPS products to semantic layer (RDF)
  - Automatic RDF mapping for discovery
  - Support for multilingual product descriptions
  - Product-contract linking in semantic layer
- **ODPS Reference Resolution**: Resolve `$ref` references in ODPS documents
  - Internal references (within document)
  - Local references (relative paths)
  - External references (HTTP/HTTPS URLs)
  - Configurable external reference handling
- **ODPS Validation**: Comprehensive ODPS document validation
  - Schema validation against ODPS specification
  - Version detection and validation
  - Field-level validation with detailed error messages
- **ODPS Workflow Orchestration**: Automated workflow for ODPS product creation
  - ProductCreationWorkflow for Product-First flow
  - Error handling and compensation logic
  - Workflow state tracking and monitoring

### Creation Flows

- **Product-First Flow**: Start with ODPS document, extract ODCS automatically
- **Technical-First Flow**: Start with ODCS contract, link/generate ODPS
- **Data-First Flow**: Start with data asset, attach ODPS and ODCS contracts

### API Endpoints

- `POST /api/v1/contracts/products/` - Create ODPS product (Product-First flow)
- `POST /api/v1/contracts/{id}/link-odps/` - Link ODPS to ODCS contract
- `POST /api/v1/contracts/{id}/unlink-odps/` - Unlink ODPS from ODCS contract
- `GET /api/v1/contracts/{id}/export/` - Export contract (ODPS format)
- `GET /api/v1/contracts/{id}/download/` - Download contract as file (ODPS format)
- `GET /api/v1/contracts/{id}/links/` - List contract links (ODPS ↔ ODCS)

### GraphQL Mutations

- `createODPS(input: CreateODPSInput!)` - Create ODPS product
- `linkODPS(input: LinkODPSInput!)` - Link ODPS to ODCS
- `exportODPS(input: ExportODPSInput!)` - Export ODPS product

### SDK Support

- **Python SDK**: `ContractsAPI.create_odps()`, `ContractsAPI.export_odps()`, `ContractsAPI.link_odps_to_odcs()`
- **JavaScript SDK**: `ContractsAPI.createODPS()`, `ContractsAPI.exportODPS()`, `ContractsAPI.linkODPSToODCS()`
- **CLI**: `datahub contracts create-odps`, `datahub contracts export`, `datahub contracts link-odps`

### Documentation

- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md) - Complete ODPS integration guide
- [ODPS Creation Flows](ODPS_CREATION_FLOWS.md) - Detailed creation flow documentation
- [ODPS Migration Guide](ODPS_MIGRATION_GUIDE.md) - ODPS and ODCS version migration guide
- [ODPS Examples](ODPS_EXAMPLES.md) - Complete ODPS examples and use cases
- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#odps) - ODPS API endpoints

---

## Assets

Asset catalog management, health scores, recommendations, and dependencies.

### Key Features

- **Asset Catalog**: Manage data assets in a centralized catalog
- **Asset Health Scores**: Calculate and track asset health
- **Asset Recommendations**: Get recommendations for asset usage
- **Asset Dependencies**: Track asset dependencies and relationships
- **Asset Activation**: Activate assets for use
- **Asset Popularity**: Track asset usage and popularity metrics

### API Endpoints

- `GET /api/v1/assets/` - List assets
- `POST /api/v1/assets/` - Create asset
- `GET /api/v1/assets/{id}/` - Get asset
- `PUT /api/v1/assets/{id}/` - Update asset
- `DELETE /api/v1/assets/{id}/` - Delete asset
- `POST /api/v1/assets/{id}/datasets/` - Attach dataset
- `POST /api/v1/assets/{id}/contracts/` - Attach contract
- `POST /api/v1/assets/{id}/activate/` - Activate asset

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#assets)
- [Asset Health Score](ASSET_HEALTH_SCORE.md) (deprecated - see deprecated-doc)
- [Asset Recommendations](ASSET_RECOMMENDATIONS.md) (deprecated - see deprecated-doc)

---

## Datasets

Dataset management, versioning, schema evolution, and time travel.

### Key Features

- **Dataset Management**: Create, update, and delete datasets
- **Dataset Versioning**: Version datasets and track changes
- **Schema Evolution**: Track schema changes over time
- **Time Travel**: Query historical dataset versions
- **Version Comparison**: Compare dataset versions
- **Version Impact Analysis**: Analyze impact of version changes

### API Endpoints

- `GET /api/v1/datasets/` - List datasets
- `POST /api/v1/datasets/` - Create dataset
- `GET /api/v1/datasets/{id}/` - Get dataset
- `PUT /api/v1/datasets/{id}/` - Update dataset
- `DELETE /api/v1/datasets/{id}/` - Delete dataset

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#datasets)
- [Schema Evolution](SCHEMA_EVOLUTION_AND_COMPARISON.md)
- [Dataset Version History](DATASET_VERSION_HISTORY.md)

---

## Data Quality

Data quality checks, monitoring, alerting, and scorecards.

### Key Features

- **Quality Checks**: Run data quality checks using Great Expectations and Soda
- **Quality Runs**: Execute and track quality runs
- **Anomaly Detection**: Detect data quality anomalies
- **Trend Analysis**: Analyze quality trends over time
- **Root Cause Analysis**: Analyze root causes of quality issues
- **Scorecards**: Generate quality scorecards
- **Alerting**: Alert on quality issues

### API Endpoints

- `GET /api/v1/dq/runs/` - List DQ runs
- `POST /api/v1/dq/runs/` - Create DQ run
- `GET /api/v1/dq/runs/{id}/` - Get DQ run
- `GET /api/v1/dq/runs/{id}/results/` - Get DQ results

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#data-quality)
- DQ feature docs (deprecated - see deprecated-doc/feature-docs/)

---

## Compliance

Compliance scanning, PII detection, risk assessment, and reporting.

### Key Features

- **Compliance Scanning**: Scan data for compliance issues
- **PII Detection**: Detect personally identifiable information
- **Risk Assessment**: Assess compliance risks
- **Compliance Reports**: Generate compliance reports
- **ABAC Integration**: Attribute-based access control integration

### API Endpoints

- `GET /api/v1/compliance/runs/` - List compliance runs
- `POST /api/v1/compliance/runs/` - Create compliance run
- `GET /api/v1/compliance/runs/{id}/` - Get compliance run
- `GET /api/v1/compliance/runs/{id}/results/` - Get compliance run results

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#compliance)
- [Compliance Guide](COMPLIANCE.md)

---

## Marketplace

Data marketplace for listing, ordering, and purchasing data assets.

### Key Features

- **Marketplace Listings**: List assets in the marketplace
- **Orders**: Create and manage orders
- **Entitlements**: Manage data entitlements
- **Purchases**: Purchase data assets
- **Data preview** (Phase 4 Gap Remediation): Preview data and quality before purchase
- **Trust signals**: Quality metrics and optional badges/SLAs in listings and preview

### Data preview

Data preview allows consumers to inspect sample data, schema, and quality metrics for a **published** listing before requesting access.

- **Endpoint**: `GET /api/v1/marketplace/listings/{id}/preview/` (published listings only)
- **Response**: `listing_id`, `asset_id`, `sample_data` (rows, total_rows, sample_size), `schema` (fields), `quality_metrics` (from latest DQ run: completeness, accuracy, freshness, overall_score), optional `trust_signals` (from listing metadata), `preview_expires_at` (e.g. 1 hour)
- **Behaviour**: Sample data comes from the asset’s current dataset (`sample_data_json` or extracted from file). Quality metrics come from the latest successful DQ run for the asset. Requires authentication; 403 for draft/unlisted, 404 if no dataset.

### Trust signals

Trust signals help consumers assess listing quality and reliability.

- **Current implementation**: (1) **Quality metrics** in Data preview are derived from the latest DQ run (overall score, completeness, accuracy, freshness). (2) **Listing-level trust signals** (e.g. badges, SLA labels) can be stored in `Listing.metadata_json.trust_signals` and are included in the Data preview response when present. (3) A **Trust signals configuration API** provides tenant-scoped CRUD for trust signal definitions (badges, quality SLAs); see below.
- **Use cases**: [UC-MKT-ADV-003 Manage Trust Signals](USE_CASES.md#uc-mkt-adv-003-manage-trust-signals), [UC-MKT-ADV-005 Configure Data Quality SLAs](USE_CASES.md#uc-mkt-adv-005-configure-data-quality-slas).

#### Trust signals (config API)

The **Trust signals configuration API** provides CRUD for tenant-scoped trust signal definitions (badges, quality SLAs). It supports [UC-MKT-ADV-003](USE_CASES.md#uc-mkt-adv-003-manage-trust-signals) and [UC-MKT-ADV-005](USE_CASES.md#uc-mkt-adv-005-configure-data-quality-slas). Listing-level trust signals can still be set via `Listing.metadata_json.trust_signals` and are exposed in [Data preview](#data-preview). Endpoints: [API Endpoints Reference – Trust signals configuration API](API_ENDPOINTS_REFERENCE.md#trust-signals-configuration-api).

### API Endpoints

- `GET /api/v1/marketplace/listings/` - List marketplace listings
- `POST /api/v1/marketplace/listings/` - Create listing
- `GET /api/v1/marketplace/listings/{id}/` - Get listing
- `GET /api/v1/marketplace/listings/{id}/preview/` - Data preview (sample data, schema, quality metrics, trust signals)
- `GET /api/v1/marketplace/config/trust-signals/` - List trust signal configs (tenant-scoped)
- `POST /api/v1/marketplace/config/trust-signals/` - Create trust signal config
- `GET /api/v1/marketplace/config/trust-signals/{id}/` - Get trust signal config
- `PUT /api/v1/marketplace/config/trust-signals/{id}/` - Update trust signal config
- `PATCH /api/v1/marketplace/config/trust-signals/{id}/` - Partial update
- `DELETE /api/v1/marketplace/config/trust-signals/{id}/` - Delete trust signal config
- `POST /api/v1/marketplace/orders/` - Create order
- `GET /api/v1/marketplace/orders/{id}/` - Get order

### Documentation

- [API Endpoints Reference – Marketplace (listings and data preview)](API_ENDPOINTS_REFERENCE.md#marketplace-listings-and-data-preview)

---

## Governance

Access control, access requests, classifications, and compliance reporting.

### Key Features

- **Access Requests**: Request access to data assets
- **Access Control**: Role-based and attribute-based access control
- **Classifications**: Classify data assets
- **Compliance Reporting**: Generate compliance reports
- **Access Analytics**: Analyze access patterns
- **Access Certification**: Certify access rights

### API Endpoints

- `GET /api/v1/governance/access-requests/` - List access requests
- `POST /api/v1/governance/access-requests/` - Create access request
- `GET /api/v1/governance/access-requests/{id}/` - Get access request
- `POST /api/v1/governance/access-requests/{id}/approve/` - Approve request
- `POST /api/v1/governance/access-requests/{id}/reject/` - Reject request

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#governance)
- [ABAC System](ABAC_SYSTEM.md)
- [Access Analytics](ACCESS_ANALYTICS.md)
- [Access Certification](ACCESS_CERTIFICATION.md)
- [Data Governance](DATA_GOVERNANCE.md)

---

## Search

Full-text search across contracts, assets, and datasets.

### Key Features

- **Full-Text Search**: Search across all resources
- **Resource-Specific Search**: Search within specific resource types
- **Search Ranking**: Ranked search results
- **Search Indexing**: Automatic search index updates

### API Endpoints

- `GET /api/v1/search/` - Search across resources
- `GET /api/v1/search/contracts/` - Search contracts
- `GET /api/v1/search/assets/` - Search assets

### Documentation

- [Search Guide](SEARCH.md)

---

## Observability

Data observability, freshness monitoring, and lineage tracking.

**Note**: A first-class **observability lineage endpoint** (aggregate lineage, optional filters) is planned for **Phase 1** (Gap Remediation). Until then, contract-level lineage is available as below; full hierarchical lineage and visualization remain under Contracts. See [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md).

**Lineage (current)**: Contract-level lineage is available at `GET /api/v1/observability/lineage/?contract_id={uuid}` (delegates to contract lineage service; tenant isolation enforced). Full hierarchical lineage and visualization remain under Contracts: `GET /api/v1/contracts/{id}/lineage/`, `lineage/full`, `lineage/visualization/`.

### Key Features

- **Data Observability**: Monitor data health and freshness
- **Freshness Monitoring**: Track data update frequency
- **Lineage Tracking**: Track data lineage (observability lineage endpoint and contract-level lineage under Contracts)
- **SLA Monitoring**: Monitor data SLAs

### API Endpoints

- `GET /api/v1/observability/metrics/` - Get observability metrics
- `GET /api/v1/observability/freshness/` - Get freshness metrics
- `GET /api/v1/observability/lineage/` - Get contract-level lineage (query: `contract_id`, required)

### Documentation

- [Data Observability](DATA_OBSERVABILITY.md)

---

## Workflows

Workflow orchestration for complex business processes.

### Workflows API (Phase 3 — Implemented)

- **List workflows**: `GET /api/v1/workflows/` — Paginated list of workflow definitions; query params: `name`, `is_active`, `page`, `page_size`. Tenant required.
- **Get workflow**: `GET /api/v1/workflows/{name}/` — Workflow definition by name; optional query `version`. Tenant required.
- **Trigger workflow**: `POST /api/v1/workflows/{name}/trigger/` — Create (and optionally start) a workflow instance; body: `input_data`, `start_immediately`. Tenant isolation enforced (instance created for user's tenant).

Workflows are also used internally (e.g. ODPS product creation, scheduled ingestion/export). See [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md).

### Key Features

- **Workflow Engine**: Execute workflows
- **Workflow Registry**: Register and discover workflows
- **Workflow State Management**: Manage workflow state
- **Workflow Versioning**: Version workflows

### Documentation

- [Workflow State Schema](WORKFLOW_STATE_SCHEMA.md)
- [Orchestration Documentation](../hub/apps/orchestration/README.md)
- [API Endpoints Reference – Workflows](API_ENDPOINTS_REFERENCE.md#workflows)

---

## Lineage

Data lineage tracking and visualization.

### Key Features

- **Multi-Level Lineage**: Track lineage across multiple levels
- **Impact Analysis**: Analyze impact of changes
- **Source Path Tracing**: Trace source paths

### Documentation

- [Multi-Level Lineage](MULTI_LEVEL_LINEAGE.md)
- [Impact Analysis](IMPACT_ANALYSIS.md)
- [Source Path Tracing](SOURCE_PATH_TRACING.md)
- [Developer Guide: Lineage](DEVELOPER_GUIDE_LINEAGE.md) (deprecated - see deprecated-doc)

---

## Versioning

Version management for contracts and datasets. A minimal **Versioning API** (Phase 2 Gap Remediation) exposes list versions, get version, and compare using existing contract and dataset version data.

### Key Features

- **List Versions**: List versions for a resource (contract or dataset) by asset id; tenant-scoped
- **Get Version**: Retrieve a single version by id (contract or dataset)
- **Compare**: Compare two versions (same resource type); returns version numbers and timestamps
- **Version Management**: Version data lives in Contracts (per-asset version counter) and Datasets (version, semantic_version, is_current)

### API Endpoints

- `GET /api/v1/versioning/versions/` - List versions (query: `resource_type=contract|dataset`, `resource_id=<asset_uuid>`)
- `GET /api/v1/versioning/versions/{id}/` - Get version by id
- `GET /api/v1/versioning/compare/` - Compare two versions (query: `resource_type`, `id_a`, `id_b`)

### Documentation

- [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md) - Phase 2 Versioning API
- [Semantic Versioning](SEMANTIC_VERSIONING.md) (deprecated - see deprecated-doc)
- [Version Impact Analysis](VERSION_IMPACT_ANALYSIS.md) (deprecated - see deprecated-doc)

---

## BaaS

Backend-as-a-Service platform APIs, usage tracking, and developer documentation for external integrators.

### Key Features

- **Platform APIs**: BaaS platform endpoints for tenants, users, and platform operations
- **Usage Tracking**: Track API usage and quotas
- **Developer Documentation**: SDK and CLI usage guides for BaaS workflows

### Documentation

- [BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md)
- [BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md)

---

## Integrations

External marketplace connectors, sync jobs, and mapping management for publishing and syncing assets to external platforms.

### Key Features

- **Marketplace Connections**: Create and manage connections to external marketplaces (Snowflake, AWS, Azure, GCP, Databricks, CKAN, etc.)
- **Sync Jobs**: PUSH sync of assets to external marketplaces; monitor and cancel jobs
- **Mappings**: Track mappings between Hub assets and external marketplace listings
- **Connectors**: Connector framework for marketplace-specific adapters

### API Endpoints

- `GET /api/v1/integrations/` - List integrations/connections
- `POST /api/v1/integrations/` - Create connection
- `GET /api/v1/integrations/{id}/` - Get connection
- Sync and mapping endpoints as defined in integrations app

### Documentation

- [Marketplace Integration User Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)
- [Marketplace User Journeys](MARKETPLACE_USER_JOURNEYS.md)

---

## Jobs

Job management, status, and cancellation for long-running and scheduled operations.

### Key Features

- **Job Listing**: List jobs with filters (status, type, tenant)
- **Job Status**: Get job status and progress
- **Job Cancellation**: Cancel running jobs
- **Job Types**: Ingestion, sync, workflow, and other job types

### API Endpoints

- `GET /api/v1/jobs/` - List jobs
- `GET /api/v1/jobs/{id}/` - Get job
- `POST /api/v1/jobs/{id}/cancel/` - Cancel job (where supported)

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#jobs) (if present)

---

## Files

Multipart file upload (init, upload, complete), listing, and storage for data assets.

### Key Features

- **Init Upload**: Start multipart upload; obtain upload URL/credentials
- **Complete Upload**: Finalize multipart upload
- **List Files**: List uploaded files or parts
- **Storage**: Configurable storage backends (local, S3, etc.)

### API Endpoints

- `POST /api/v1/files/init/` - Initiate multipart upload
- `POST /api/v1/files/complete/` - Complete multipart upload
- `GET /api/v1/files/` - List files (or equivalent)

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#files) (if present)

---

## Semantic

Semantic layer, RDF mapping, SPARQL, and ODPS/semantic mapping for discovery and ontology alignment.

### Key Features

- **Semantic Layer**: Map assets and contracts to RDF; semantic search
- **URI/Ontology Endpoints**: Resolve URIs and ontology terms
- **ODPS Semantic Mapping**: Map ODPS products to semantic layer for discovery
- **SPARQL**: Query semantic store (where enabled)

### API Endpoints

- `GET /api/v1/semantic/` - Semantic endpoints as defined in semantic app
- URI and ontology resolution endpoints

### Documentation

- [ODPS Integration Guide](ODPS_INTEGRATION_GUIDE.md)
- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#semantic) (if present)

---

## AI

Natural language search and AI-assisted schema matching for assets and contracts.

### Key Features

- **Natural Language Search**: Query assets using natural language; LLM-backed search
- **Schema Matching**: AI-assisted schema matching for field mappings (e.g. data-first flow)

### API Endpoints

- `POST /api/v1/ai/natural-language-search/` - Natural language search
- `POST /api/v1/ai/schema-matching/` - AI schema matching

### Documentation

- [Use Cases](USE_CASES.md) – AI/ML use cases
- [User Journeys](USER_JOURNEYS.md) – Natural language search and schema matching journeys

---

## ML

ML models, training, inference, and model serving for anomaly detection, recommendations, and classification.

### Key Features

- **Models**: Register and manage ML models
- **Training**: Trigger or track training runs
- **Inference**: Run inference for anomaly detection, recommendations, auto-classification
- **Model Serving**: Serve models for platform features (e.g. recommendations, DQ)

### API Endpoints

- `GET /api/v1/ml/` - ML endpoints as defined in ml app

### Documentation

- [Model Serving Usage](../cli/docs/MODEL_SERVING_USAGE.md) (if present)
- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#ml) (if present)

---

## Social

Ratings, reviews, comments, and communities for assets and data products.

### Key Features

- **Ratings**: Rate assets
- **Reviews**: Write and manage reviews
- **Comments**: Comment on assets or reviews
- **Communities**: Create and join data communities

### API Endpoints

- `POST /api/v1/social/ratings/` - Create rating
- `POST /api/v1/social/reviews/` - Create review
- `POST /api/v1/social/comments/` - Create comment
- `POST /api/v1/social/communities/` - Create community
- List/update/delete endpoints as defined in social app

### Documentation

- [Use Cases](USE_CASES.md) – Social use cases
- [User Journeys](USER_JOURNEYS.md) – Social journeys (e.g. JOURNEY-DPO-009, JOURNEY-DC-008)

---

## Data Mesh

Domains, topology, federated governance, and domain-scoped asset management.

### Key Features

- **Domains**: Create and manage data mesh domains; domain boundaries
- **Topology**: Mesh topology visualization and management
- **Federated Governance**: Domain-specific policies and governance
- **Domain Ownership**: Assign domain ownership; transfer assets between domains

### API Endpoints

- `GET /api/v1/mesh/` - Mesh endpoints as defined in mesh app
- Domains, topology, and governance endpoints

### Documentation

- [User Journeys](USER_JOURNEYS.md) – Data Mesh Domain Owner journeys (JOURNEY-DMO-001–005)
- [User Personas](USER_PERSONAS.md) – Data Mesh Domain Owner

---

## Virtualization

Virtual datasets, query execution, and federated query for logical data access.

### Key Features

- **Virtual Datasets**: Define virtual datasets over one or more sources
- **Query Execution**: Execute queries against virtual datasets
- **Federated Query**: Query across federated sources

### API Endpoints

- `GET /api/v1/virtualization/` - Virtualization endpoints
- Virtual dataset and query execution endpoints

### Documentation

- [User Journeys](USER_JOURNEYS.md) – Virtualization journeys (e.g. JOURNEY-DE-009, JOURNEY-DC-010, JOURNEY-DA-003)

---

## Scheduled Ingestion

Scheduled ingestion jobs, runs, and configuration for recurring data ingestion.

### Key Features

- **Schedules**: Define ingestion schedules (cron or interval)
- **Runs**: Trigger and monitor ingestion runs
- **Configuration**: Configure sources and targets for scheduled ingestion

### API Endpoints

- `GET /api/v1/scheduled-ingestions/` - List schedules/runs
- Create, update, trigger endpoints as defined in scheduled_ingestion app

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#scheduled-ingestion) (if present)

---

## Scheduled Export

Scheduled export jobs, runs, and configuration for recurring data export (e.g. to external destinations or formats).

### Key Features

- **Schedules**: Define export schedules (cron or interval)
- **Runs**: Trigger and monitor export runs; status and history
- **Destination and format**: Configure export destination and output format per schedule
- **Internal worker API**: Worker-only endpoints for run lifecycle (create run, complete, fail) under `internal/`

### API Endpoints

- `GET /api/v1/scheduled-exports/` - List scheduled exports (tenant-scoped; optional `?status=` filter: ACTIVE, PAUSED, ERROR)
- CRUD and run management as defined in `hub.apps.scheduled_export` (ViewSet and runs); all endpoints are tenant-scoped
- Internal worker API: `POST /api/v1/scheduled-exports/internal/...` (worker authentication required)

### Documentation

- [API Endpoints Reference – Scheduled Export](API_ENDPOINTS_REFERENCE.md#scheduled-export) and [Scheduled Export Internal Worker API](API_ENDPOINTS_REFERENCE.md#scheduled-export-internal-worker-api)
- [Scheduled Export API Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_EXPORT.md) – full public and internal worker API
- [Use Cases – Scheduled Export](USE_CASES.md#category-scheduled-export--data-operations) (UC-EXPORT-001–004)
- [User Journeys – Scheduled Export](USER_JOURNEYS.md#scheduled-export-journeys) (JOURNEY-EXPORT-001–002)
- [api-audit/current-api-inventory.md](api-audit/current-api-inventory.md) – full endpoint list

---

## Webhooks

Webhook registration and delivery for event-driven integrations.

### Key Features

- **Webhook Registration**: Register webhooks for events
- **Delivery**: Event delivery to registered URLs
- **Retries**: Configurable retries and delivery status

### API Endpoints

- `GET /api/v1/webhooks/` - List webhooks
- `POST /api/v1/webhooks/` - Create webhook
- Update, delete, delivery history as defined in webhooks app

### Documentation

- [Event Types Reference](EVENT_TYPES_REFERENCE.md)
- [Event Bus](EVENT_BUS.md)

---

## Audit

Audit event recording, querying, and export for compliance and debugging.

### Key Features

- **Audit Events**: Record actor, action, resource, and metadata
- **Query**: Filter by resource type, action, actor, date range
- **Export**: Export audit events (JSON, CSV)

### API Endpoints

- `GET /api/v1/audit/audit-events/` - List/filter audit events
- `GET /api/v1/audit/audit-events/export/` - Export audit events
- `GET /api/v1/audit/audit-events/{id}/` - Get audit event

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#audit) (if present)
- [User Personas](USER_PERSONAS.md) – Auditor persona

---

## Health

Health checks for services, dependencies, and readiness/liveness for orchestration and load balancers.

### Key Features

- **Liveness**: Simple liveness probe
- **Readiness**: Readiness (e.g. DB, cache) checks
- **Detailed Health**: Per-service or per-dependency health (optional)

### Endpoints

- `GET /health/` (or `/health/live/`, `/health/ready/`) - Health check endpoints as configured

### Documentation

- [Use Cases](USE_CASES.md) – UC-AUTH-004 (Unauthenticated User Accesses Public Resources)
- [User Journeys](USER_JOURNEYS.md) – JOURNEY-AUTH-004

---

## Supporting capabilities

The following are **supporting capabilities** used across the 29 product features above. They are not standalone features in the main list; traceability is via the features that use them (see [Capabilities ↔ Features ↔ Use Cases](#capabilities--features--use-cases) and [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md#supporting-capabilities)).

| Capability | Description | Used by (examples) |
|------------|-------------|-------------------|
| **Notifications** | Alerts, email, in-app notifications | Compliance, Governance, Jobs, Contract impact |
| **Billing** | Usage, metering, billing integration | Marketplace, ODPS pricing, Phase 25 |
| **Platform** | Tenant lifecycle, config, deployment | BaaS, Auth, tenant isolation |
| **Tenants** | Multi-tenancy, tenant-scoped data | Auth, BaaS, all scoped APIs |
| **Users** | User and role management | Auth, BaaS, invitations |
| **Analytics** | Access analytics, usage metrics | Governance, Observability, Marketplace |
| **Events** | Event bus, event-driven flows | Audit, Webhooks, lineage, contract events |

---

## Capabilities ↔ Features ↔ Use Cases

This section maps **frontend/API capability names** (e.g. feature flags or permission keys) to **features** and to **use cases / user journeys** for role and tenant gating.

| Capability / Area | Feature(s) | Use Cases / Journeys |
|-------------------|------------|----------------------|
| `auth.login`, `auth.register` | Auth | UC-AUTH-001, UC-AUTH-002; JOURNEY-AUTH-001, JOURNEY-AUTH-002 |
| `auth.password_reset` | Auth | UC-AUTH-003; JOURNEY-AUTH-003 |
| Public health, docs | Auth, Health | UC-AUTH-004; JOURNEY-AUTH-004 |
| `ai.natural-language-search` | AI | AI/ML use cases; JOURNEY-DC-006, JOURNEY-DS-001 |
| `ai.schema-matching` | AI | Data-first flow; JOURNEY-DPO-007, JOURNEY-DE-008, JOURNEY-DS-002 |
| `social.ratings`, `social.reviews` | Social | Social use cases; JOURNEY-DPO-009, JOURNEY-DC-008, JOURNEY-CM-002 |
| `social.communities` | Social | JOURNEY-DPO-012, JOURNEY-DC-009, JOURNEY-CM-001 |
| `mesh.domains`, `mesh.topology` | Data Mesh | JOURNEY-DMO-001–005, JOURNEY-DPO-013, JOURNEY-DE-013 |
| `virtualization.query` | Virtualization | JOURNEY-DE-009, JOURNEY-DC-010, JOURNEY-DA-003, JOURNEY-DA-004 |
| Marketplace listing, pricing | Marketplace, ODPS | Marketplace use cases; JOURNEY-DPO-002, JOURNEY-DC-011, JOURNEY-DC-012 |
| Integrations, sync jobs | Integrations | Marketplace integration; JOURNEY-DE-010, JOURNEY-DE-011 |
| Audit query, export | Audit | Auditor persona; audit use cases |
| Notifications, Billing, Platform, Tenants, Users, Analytics, Events | Supporting capabilities | See [Supporting Capabilities](#supporting-capabilities); used across features |

Deployments may restrict UI to authenticated users only; public capabilities (health, docs, optional landing) remain available to the Visitor persona. The landing page is frontend-only at `/` (auth-based switch: unauthenticated → landing, authenticated → dashboard). See [Landing Page](LANDING_PAGE.md), [User Personas](USER_PERSONAS.md#access-control-summary), and [Use Cases – Authentication & Access](USE_CASES.md#authentication--access-use-cases).

---

## Future roadmap

The following capabilities are **planned** or **deferred** (not yet implemented). They are documented here for traceability and planning; no implementation exists unless stated.

| Item | Status | Notes |
|------|--------|--------|
| **Central schema registry** | Planned | Single registry for schema definitions and versioning across assets and contracts. |
| **Transformation pipeline** | Deferred (Phase 5) | Public API for create/validate/execute pipelines; see [GAP_REMEDIATION_PLAN, Section 8 (Phase 5)](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md#8-phase-5--transformation-pipeline-option-a-defer). Use cases and journeys in [USER_JOURNEYS.md](USER_JOURNEYS.md) and [USE_CASES.md](USE_CASES.md) are marked **Deferred**. |
| **Inter-hub / federation** | Planned | Multi-hub discovery, federation topology, and cross-hub queries; complements the existing [Virtualization](#virtualization) feature. |

---

## Related Documentation

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Architecture](ARCHITECTURE.md) - System architecture
- [Use Cases](USE_CASES.md) - Use cases including Authentication & Access (UC-AUTH-001–004)
- [User Journeys](USER_JOURNEYS.md) - User journeys including Visitor/Authentication (JOURNEY-AUTH-001–004)
- [User Personas](USER_PERSONAS.md) - Personas including Visitor/Prospect
- [Test Traceability](TEST_TRACEABILITY.md) - Comprehensive test traceability matrix mapping features, use cases, and journeys to tests
- [Test Coverage Matrix](TEST_COVERAGE_MATRIX.md) - Feature/use case/journey coverage and gap remediation mapping
- [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md) - Phased gap remediation (observability, versioning, workflows, data preview, traceability)
- [User Journey Mapping](USER_JOURNEY_MAPPING.md) - User journeys and personas
- [Marketplace Use Cases](MARKETPLACE_USE_CASES.md) - Marketplace use cases
- [Marketplace User Journeys](MARKETPLACE_USER_JOURNEYS.md) - Marketplace user journeys

---

**Last Updated**: 2026-02-07
**Version**: 2.3.0 (Phase 0 Gap Remediation: Versioning/Workflows/Observability lineage notes; Supporting capabilities section; Capabilities table update)
