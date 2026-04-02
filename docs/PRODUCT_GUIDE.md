# Product Guide

> Features, use cases, user journeys, personas, billing, and virtualization
>
> **Source**: Merged during Phase 120F documentation consolidation.

---


---

# Features Documentation

**Last Updated**: 2026-03-22
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

**Last Updated**: 2026-03-22
**Version**: 2.3.0 (Phase 0 Gap Remediation: Versioning/Workflows/Observability lineage notes; Supporting capabilities section; Capabilities table update)

---

# Use Cases

**Last Updated**: 2026-03-22
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

**Last Updated**: 2026-03-22
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

---

# User Journeys

**Last Updated**: 2026-03-22
**Version**: 2.4.2

---

## Overview

This document provides detailed user journey maps for **Visitor** (unauthenticated / non-registered) and all **12 role-based personas**. The platform supports **97 total journeys** (5 authentication + 37 original + 55 new) covering authentication and access, all features, the 10 strategic differentiators, and ODPS integration.

**Journey Statistics**:
- **Total Journeys**: 97
- **Total Steps**: ~730+
- **Average Steps per Journey**: ~8
- **Target Completion Rate**: 100%
- **Target Success Rate**: 95%+

**Cross-References**:
- **[Marketplace User Journeys](MARKETPLACE_USER_JOURNEYS.md)** - Marketplace integration journeys (publish to external marketplace, discover and import, sync, federated assets).
- **[Resource Pickers (Component Docs)](UI/RESOURCE_PICKERS.md)** - Searchable pickers (AssetPicker, ContractPicker, DatasetPicker, FilePicker) used in ODPS upload, asset attach, DQ/Compliance/Access Request, Scheduled Export, Retention, Dataset edit, ODPS Link flows.

---

## Deferred Journeys (Transformation Pipeline)

The following **6 journeys** are **deferred until the transformation pipeline exists**. No public transformation-pipeline API is implemented; these journeys are documented for future scope.

| Journey ID | Title | Persona |
|------------|-------|---------|
| JOURNEY-DPO-008 | Create Transformation Pipeline for Asset | Data Product Owner |
| JOURNEY-DE-007 | Create Transformation Pipeline | Data Engineer |
| JOURNEY-DC-007 | Create Transformation Pipeline for Data | Data Consumer |
| JOURNEY-AUD-005 | Audit Transformation Pipelines | Auditor |
| JOURNEY-DA-001 | Create Transformation Pipeline | Data Analyst |
| JOURNEY-DEV-006 | Integrate Transformation Pipeline API | External Developer |

**Rationale**: A dedicated transformation-pipeline API (create/validate/execute pipelines, visual builder, asset-linked pipelines) is not yet implemented. See [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md) Phase 5 and [Transformation Pipeline Backlog](BACKLOG_TRANSFORMATION_PIPELINE.md).

**When implemented**: Each journey will be un-deferred; tests and traceability will be updated.

---

## Table of Contents

1. [Deferred Journeys (Transformation Pipeline)](#deferred-journeys-transformation-pipeline) — 6 journeys (deferred until transformation pipeline exists)
2. [Visitor / Authentication Journeys](#visitor--authentication-journeys) - 5 journeys (NEW)
3. [Data Product Owner Journeys](#data-product-owner-journeys) - 17 journeys (6 original + 11 new)
4. [Data Engineer Journeys](#data-engineer-journeys) - 14 journeys (6 original + 8 new)
5. [Compliance Officer Journeys](#compliance-officer-journeys) - 10 journeys (5 original + 5 new)
6. [Data Consumer Journeys](#data-consumer-journeys) - 15 journeys (5 original + 10 new)
7. [Tenant Admin Journeys](#tenant-admin-journeys) - 10 journeys (4 original + 4 new + 2 gap coverage)
8. [Platform Admin Journeys](#platform-admin-journeys) - 10 journeys (4 original + 6 new)
9. [External Developer Journeys](#external-developer-journeys) - 9 journeys (4 original + 5 new)
10. [Auditor Journeys](#auditor-journeys) - 6 journeys (3 original + 3 new)
11. [Data Scientist Journeys](#data-scientist-journeys) - 5 journeys (NEW)
12. [Data Analyst Journeys](#data-analyst-journeys) - 4 journeys (NEW)
13. [Community Manager Journeys](#community-manager-journeys) - 4 journeys (NEW)
14. [Data Mesh Domain Owner Journeys](#data-mesh-domain-owner-journeys) - 5 journeys (NEW)
15. [Journey Map Matrix](#journey-map-matrix)

---

## Visitor / Authentication Journeys

These journeys apply to **unauthenticated** and **non-registered** users (Visitor / Prospect persona). After completing login or registration, the user assumes a role-based persona for subsequent journeys.

### JOURNEY-AUTH-001: First-Time Visitor Registers

**Journey ID**: JOURNEY-AUTH-001
**Title**: First-Time Visitor Registers
**Persona**: Visitor, Prospect
**Goal**: Create an account via self-service registration (when enabled)

**Steps**:
1. User lands on application (or is redirected to login)
2. User navigates to registration page (or invokes `POST /api/v1/auth/register/`)
3. User enters email, password, and optional display name
4. System validates email format and password policy
5. System checks email is not already registered
6. If no tenant_id provided: system creates personal tenant, assigns user to tenant, creates DATA_PROVIDER and DATA_CONSUMER roles, assigns user roles; if tenant_id provided: user associated with that tenant
7. System sets user status (e.g. ACTIVE or PENDING_VERIFICATION)
8. User receives confirmation (success message or email)
9. User can log in (JOURNEY-AUTH-002)

**Success Criteria**:
- Registration endpoint/page available (when feature enabled)
- User account created
- User has tenant (personal or provided)
- User can authenticate

**Performance Targets**:
- Total duration: < 1 minute
- API response: < 2 seconds

**API Endpoints**:
- `POST /api/v1/auth/register/` - User registration

**Error Scenarios**:
- Registration disabled → 403 or UI shows "Contact administrator"
- Email already exists → 400 Bad Request
- Password policy not met → 400 Bad Request

**Related Use Cases**: UC-AUTH-001, UC-AUTH-002

**Test Traceability**: [TEST_TRACEABILITY.md#journey-auth-001-first-time-visitor-registers](TEST_TRACEABILITY.md#journey-auth-001-first-time-visitor-registers)

---

### JOURNEY-AUTH-002: User Logs In

**Journey ID**: JOURNEY-AUTH-002
**Title**: User Logs In
**Persona**: Visitor (becomes authenticated), any registered persona
**Goal**: Authenticate and obtain session/token to access protected resources

**Steps**:
1. User navigates to login page (or invokes `POST /api/v1/auth/login/`)
2. User enters email and password
3. System validates credentials
4. System returns access token (and optionally refresh token)
5. Client stores token and uses it for subsequent requests
6. User is redirected to application home or requested resource
7. User assumes role-based persona for further journeys (e.g. Data Consumer, Data Product Owner)

**Success Criteria**:
- Credentials validated
- Token/session issued
- User can access protected resources

**Performance Targets**:
- Total duration: < 10 seconds
- API response: < 1 second

**API Endpoints**:
- `POST /api/v1/auth/login/` - User login

**Error Scenarios**:
- Invalid credentials → 401 Unauthorized
- Account disabled/locked → 403 Forbidden

**Related Use Cases**: UC-AUTH-002, all persona-specific use cases

---

### JOURNEY-AUTH-003: User Resets Password

**Journey ID**: JOURNEY-AUTH-003
**Title**: User Resets Password
**Persona**: Visitor, any registered user
**Goal**: Request password reset and set new password (when feature enabled)

**Steps**:
1. User navigates to "Forgot password" or equivalent
2. User submits email (or username) for account
3. System validates account exists (no disclosure if not)
4. System generates time-limited reset token and sends link/code to registered email
5. User opens link or enters code
6. User submits new password meeting policy
7. System invalidates reset token and updates password
8. User can log in with new password (JOURNEY-AUTH-002)

**Success Criteria**:
- Reset request accepted
- Reset link/code sent (if account exists)
- Password updated
- User can log in with new password

**Performance Targets**:
- Reset request: < 2 seconds
- Password update: < 2 seconds

**Related Use Cases**: UC-AUTH-003, UC-AUTH-002

**Note**: If password reset is not implemented, this journey is N/A; users contact administrator or use invite flow (JOURNEY-TA-001).

**Test Traceability**: [TEST_TRACEABILITY.md#journey-auth-003-user-resets-password](TEST_TRACEABILITY.md#journey-auth-003-user-resets-password)

---

### JOURNEY-AUTH-004: Unauthenticated User Accesses Public Resources

**Journey ID**: JOURNEY-AUTH-004
**Title**: Unauthenticated User Accesses Public Resources
**Persona**: Visitor
**Goal**: Access resources that do not require authentication (health, public docs, optional landing)

**Steps**:
1. User opens public URL (e.g. health endpoint, API docs, or landing page if configured)
2. System serves resource without requiring authentication
3. User may browse public information
4. User may navigate to login (JOURNEY-AUTH-002) or register (JOURNEY-AUTH-001)

**Success Criteria**:
- Public resources accessible without auth
- No session/token issued unless user completes login or registration

**Performance Targets**:
- Response: < 1 second for health/docs

**Related Use Cases**: UC-AUTH-004

**Test Traceability**: [TEST_TRACEABILITY.md#journey-auth-004-unauthenticated-user-accesses-public-resources](TEST_TRACEABILITY.md#journey-auth-004-unauthenticated-user-accesses-public-resources)

**Note**: Many deployments restrict all application UI to authenticated users; public access is typically limited to health checks and API documentation. See [API Reference](API_REFERENCE.md) for public endpoints.

---

### JOURNEY-AUTH-005: User Switches Active Tenant

**Journey ID**: JOURNEY-AUTH-005
**Title**: User Switches Active Tenant
**Persona**: Any authenticated user with multiple tenants
**Goal**: Switch active tenant context without re-login; subsequent operations scoped to switched tenant

**Steps**:
1. User is logged in and has membership in at least two tenants (e.g. personal + org via invitation)
2. User opens tenant switcher in header (dropdown)
3. System fetches GET /auth/me/tenants/ and displays list
4. User selects target tenant
5. Client calls POST /auth/switch-tenant/ with tenant_id
6. System validates membership and returns updated me summary
7. Client updates auth store (active_tenant_id) and sends X-Tenant-Id on subsequent requests
8. User sees assets, listings, and data scoped to switched tenant

**Success Criteria**:
- Tenant list displayed
- Switch completes without error
- Subsequent API requests use X-Tenant-Id
- Assets/listings reflect switched tenant

**Performance Targets**:
- GET /auth/me/tenants/: < 200ms
- POST /auth/switch-tenant/: < 200ms

**API Endpoints**:
- `GET /api/v1/auth/me/tenants/` - List tenants
- `POST /api/v1/auth/switch-tenant/` - Switch tenant

**Error Scenarios**:
- Feature disabled → 403; tenant switcher hidden
- No membership in target tenant → 403 Forbidden
- Invalid tenant_id → 400 Bad Request

**Related Use Cases**: UC-AUTH-005, UC-AUTH-002

**Test Traceability**: [TEST_TRACEABILITY.md#journey-auth-005-user-switches-active-tenant](TEST_TRACEABILITY.md#journey-auth-005-user-switches-active-tenant)

---

## Data Product Owner Journeys

**Journey List**:
- JOURNEY-DPO-001: Onboard New Asset via Data-First Flow
- JOURNEY-DPO-002: Publish Asset to Marketplace
- JOURNEY-DPO-003: Manage Asset Lifecycle
- JOURNEY-DPO-004: Monitor Asset Quality
- JOURNEY-DPO-005: Configure Data Contracts
- JOURNEY-DPO-006: Manage Marketplace Listings
- JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation **NEW**
- JOURNEY-DPO-008: Create Transformation Pipeline for Asset **Deferred** (Phase 5 — see [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md))
- JOURNEY-DPO-009: Manage Asset Ratings and Reviews **NEW**
- JOURNEY-DPO-010: Publish Asset with Usage-Based Pricing **NEW**
- JOURNEY-DPO-011: Assign Data Stewards **NEW**
- JOURNEY-DPO-012: Join Data Community **NEW**
- JOURNEY-DPO-013: Configure Data Mesh Domain **NEW**
- JOURNEY-DPO-014: Monitor Asset Reliability Score **NEW**
- JOURNEY-DPO-015: Create ODPS Product (Product-First Flow) **NEW**
- JOURNEY-DPO-016: Link ODPS to ODCS Contract (Technical-First Flow) **NEW**
- JOURNEY-DPO-017: Export ODPS Product **NEW**
- JOURNEY-DPO-018: Edit Dataset and Link to Asset **NEW**
- JOURNEY-EXPORT-001: Create and Run Scheduled Export **NEW** (see [Scheduled Export Journeys](#scheduled-export-journeys))
- JOURNEY-EXPORT-002: Monitor and Troubleshoot Export Runs **NEW** (see [Scheduled Export Journeys](#scheduled-export-journeys))

### JOURNEY-DPO-001: Onboard New Asset via Data-First Flow

**Journey ID**: JOURNEY-DPO-001
**Title**: Onboard New Asset via Data-First Flow
**Persona**: Data Product Owner
**Goal**: Turn a data file into a validated, quality-checked, compliant data product

**Steps**:
1. Create asset (draft)
2. Upload file
3. Create dataset (triggers schema inference)
4. **NEW**: AI schema matching suggests field mappings
5. **NEW**: Auto-classification detects PII and categorizes data
6. Run compliance check
7. Run DQ check
8. **NEW**: ML-based anomaly detection identifies quality issues
9. Create contract
10. Activate asset

**Success Criteria**:
- Asset created in DRAFT status
- File uploaded successfully
- Schema inferred from file
- **NEW**: AI schema matching suggestions provided
- **NEW**: Auto-classification completed
- Compliance check passes
- DQ check passes
- **NEW**: ML anomaly detection completed
- Contract created and linked
- Asset activated (status = ACTIVE)

**Performance Targets**:
- Total duration: < 5 minutes
- File upload: < 30 seconds
- Schema inference: < 10 seconds
- **NEW**: AI schema matching: < 15 seconds
- **NEW**: Auto-classification: < 20 seconds
- Compliance check: < 60 seconds
- DQ check: < 60 seconds
- **NEW**: ML anomaly detection: < 30 seconds

---

### JOURNEY-DPO-002: Publish Asset to Marketplace

**Journey ID**: JOURNEY-DPO-002
**Title**: Publish Asset to Marketplace
**Persona**: Data Product Owner
**Goal**: Publish an active asset to the marketplace

**Steps**:
1. Verify asset is active
2. Check marketplace eligibility
3. **NEW**: Validate transformation pipelines (if applicable)
4. Create marketplace listing
5. **NEW**: Configure pricing model (static, usage-based, subscription)
6. **NEW**: Set up data preview
7. **NEW**: Configure trust signals (quality SLAs, badges)
8. **ODPS**: Configure ODPS pricing plans (if ODPS contract exists):
   - Define pricing plans (free, basic, premium, enterprise)
   - Set prices and billing periods
   - Configure plan features
9. **ODPS**: Configure ODPS access methods (if ODPS contract exists):
   - API access (REST, GraphQL)
   - Download access (file formats)
   - Streaming access (if applicable)
10. **ODPS**: Configure ODPS payment gateways (if ODPS contract exists):
    - Stripe integration
    - PayPal integration
    - Other payment gateways
11. Publish listing

**Success Criteria**:
- Asset is in ACTIVE status
- Asset passes eligibility checks
- **NEW**: Transformation pipelines validated (if applicable)
- Listing created successfully
- **NEW**: Pricing model configured
- **NEW**: Data preview configured
- **NEW**: Trust signals configured
- **ODPS**: ODPS pricing plans configured (if applicable)
- **ODPS**: ODPS access methods configured (if applicable)
- **ODPS**: ODPS payment gateways configured (if applicable)
- Listing published (status = PUBLISHED)

**Performance Targets**:
- Total duration: < 10 minutes
- ODPS configuration: < 2 minutes

---

### JOURNEY-DPO-007: Use AI Schema Matching for Asset Creation **NEW**

**Journey ID**: JOURNEY-DPO-007
**Title**: Use AI Schema Matching for Asset Creation
**Persona**: Data Product Owner
**Goal**: Use AI-powered schema matching to create contracts faster

**Steps**:
1. Upload data file
2. System infers schema
3. **NEW**: AI schema matching analyzes schema
4. **NEW**: Review suggested field mappings with confidence scores
5. **NEW**: Accept/reject/modify mappings
6. **NEW**: System generates contract draft with mappings
7. Review and refine contract
8. Validate contract
9. Activate asset

**Success Criteria**:
- AI schema matching completed
- Mappings suggested with confidence scores
- User accepts/rejects mappings
- Contract draft generated
- Contract validated
- Asset activated

**Performance Targets**:
- Total duration: < 3 minutes
- AI schema matching: < 15 seconds
- Mapping review: < 1 minute
- Contract generation: < 10 seconds

---

### JOURNEY-DPO-008: Create Transformation Pipeline for Asset **Deferred**

**Status**: **Deferred** (Phase 5 — transformation pipeline; see [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)).

**Journey ID**: JOURNEY-DPO-008
**Title**: Create Transformation Pipeline for Asset
**Persona**: Data Product Owner
**Goal**: Create a transformation pipeline to transform asset data

**Steps**:
1. Select asset
2. Navigate to transformation section
3. Create new pipeline
4. **NEW**: Design pipeline using visual builder (drag-and-drop nodes)
5. **NEW**: Configure transformation nodes (filter, join, aggregate, transform)
6. **NEW**: Validate pipeline
7. **NEW**: Preview transformation results
8. **NEW**: Save pipeline
9. **NEW**: Execute pipeline
10. **NEW**: Review transformation results
11. **NEW**: Sync results with asset

**Success Criteria**:
- Pipeline created
- Pipeline validated
- Preview generated
- Pipeline executed successfully
- Results synced with asset

**Performance Targets**:
- Total duration: < 10 minutes
- Pipeline design: < 5 minutes
- Validation: < 10 seconds
- Preview: < 30 seconds
- Execution: < 5 minutes (depends on data size)

---

### JOURNEY-DPO-009: Manage Asset Ratings and Reviews **NEW**

**Journey ID**: JOURNEY-DPO-009
**Title**: Manage Asset Ratings and Reviews
**Persona**: Data Product Owner
**Goal**: Manage ratings and reviews for owned assets

**Steps**:
1. Navigate to asset details
2. **NEW**: View Community section (ratings/reviews on asset page, Phase 27.1)
3. **NEW**: Review ratings (1-5 stars)
4. **NEW**: Read reviews
5. **NEW**: Respond to reviews (if needed)
6. **NEW**: View asset quality score impact
7. **NEW**: Moderate reviews (if has permissions)

**Success Criteria**:
- Ratings and reviews displayed
- Quality score updated based on ratings
- Reviews can be responded to
- Moderation works (if applicable)

---

### JOURNEY-DPO-010: Publish Asset with Usage-Based Pricing **NEW**

**Journey ID**: JOURNEY-DPO-010
**Title**: Publish Asset with Usage-Based Pricing
**Persona**: Data Product Owner
**Goal**: Publish asset with usage-based pricing model

**Steps**:
1. Select asset to publish
2. Navigate to marketplace publishing
3. **NEW**: Select pricing model (usage-based)
4. **NEW**: Configure usage tiers (per-query, per-GB)
5. **NEW**: Set pricing rates
6. **NEW**: Configure billing settings
7. Create listing
8. Publish listing

**Success Criteria**:
- Usage-based pricing configured
- Pricing tiers set
- Billing settings configured
- Listing published

---

### JOURNEY-DPO-011: Assign Data Stewards **NEW**

**Journey ID**: JOURNEY-DPO-011
**Title**: Assign Data Stewards
**Persona**: Data Product Owner
**Goal**: Assign data stewards to manage assets

**Steps**:
1. Navigate to asset details
2. **NEW**: Navigate to stewardship section
3. **NEW**: Assign stewards
4. **NEW**: Configure steward permissions
5. **NEW**: Notify stewards
6. **NEW**: Monitor steward activity

**Success Criteria**:
- Stewards assigned
- Permissions configured
- Stewards notified
- Activity tracked

---

### JOURNEY-DPO-012: Join Data Community **NEW**

**Journey ID**: JOURNEY-DPO-012
**Title**: Join Data Community
**Persona**: Data Product Owner
**Goal**: Join a data community for collaboration

**Steps**:
1. **NEW**: Browse data communities
2. **NEW**: View community details
3. **NEW**: Join community
4. **NEW**: Participate in discussions
5. **NEW**: Share assets in community
6. **NEW**: Access community knowledge base

**Success Criteria**:
- Community joined
- Discussions accessible
- Assets can be shared
- Knowledge base accessible

---

### JOURNEY-DPO-013: Configure Data Mesh Domain **NEW**

**Journey ID**: JOURNEY-DPO-013
**Title**: Configure Data Mesh Domain
**Persona**: Data Product Owner
**Goal**: Configure data mesh domain for assets

**Steps**:
1. **NEW**: Navigate to data mesh section
2. **NEW**: Create domain (or select existing)
3. **NEW**: Define domain boundaries
4. **NEW**: Assign domain ownership
5. **NEW**: Configure domain-scoped assets
6. **NEW**: Set up domain analytics

**Success Criteria**:
- Domain created/selected
- Boundaries defined
- Ownership assigned
- Assets scoped to domain
- Analytics configured

---

### JOURNEY-DPO-014: Monitor Asset Reliability Score **NEW**

**Journey ID**: JOURNEY-DPO-014
**Title**: Monitor Asset Reliability Score
**Persona**: Data Product Owner
**Goal**: Monitor and improve asset reliability score

**Steps**:
1. Navigate to asset details
2. **NEW**: View reliability score dashboard
3. **NEW**: Review score breakdown (quality, freshness, compliance)
4. **NEW**: Identify issues affecting score
5. **NEW**: Address issues
6. **NEW**: Monitor score trends

**Success Criteria**:
- Reliability score displayed
- Score breakdown visible
- Issues identified
- Score improves over time

---

### JOURNEY-DPO-015: Create ODPS Product (Product-First Flow) **NEW**

**Journey ID**: JOURNEY-DPO-015
**Title**: Create ODPS Product (Product-First Flow)
**Persona**: Data Product Owner
**Goal**: Create an ODPS product with embedded ODCS contract using the product-first flow

**Steps**:
1. Navigate to contract creation (e.g. `/odps/upload`)
2. Select "Create ODPS Product" option
3. Select target asset via **AssetPicker** (searchable dropdown)
4. Upload ODPS document (JSON or YAML format)
5. System parses and validates ODPS document
6. System detects ODPS version (e.g., 4.1, 4.0)
7. System validates ODPS schema
8. System extracts ODCS from `product.contract.spec`
9. System validates extracted ODCS contract
10. System creates ODCS contract (technical contract)
11. System creates ODPS contract (marketplace contract)
12. System links ODPS ↔ ODCS bidirectionally
13. System maps to semantic layer (RDF)
14. Asset activated (if asset attached)

**Success Criteria**:
- ODPS document uploaded successfully
- ODPS document parsed and validated
- ODPS version detected correctly
- ODCS contract extracted from `product.contract`
- ODCS contract validated
- ODCS contract created successfully
- ODPS contract created successfully
- ODPS and ODCS contracts linked bidirectionally
- Semantic mapping completed
- Asset activated (if applicable)

**Performance Targets**:
- Total duration: < 5 minutes
- ODPS parsing: < 2 seconds
- ODPS validation: < 3 seconds
- ODCS extraction: < 1 second
- ODCS validation: < 2 seconds
- Contract creation: < 2 seconds per contract
- Contract linking: < 1 second
- Semantic mapping: < 30 seconds (async)

**API Endpoints**:
- `POST /api/v1/contracts/products/` - Create ODPS product (Product-First flow)
- `GET /api/v1/contracts/{id}/` - Get contract details
- `GET /api/v1/workflows/{id}/` - Get workflow instance status

**Error Scenarios**:
- Invalid ODPS format → 400 Bad Request (format not supported)
- ODPS validation fails → 400 Bad Request (validation errors)
- ODCS extraction fails → 400 Bad Request (no contract in product.contract)
- ODCS validation fails → 400 Bad Request (ODCS validation errors)
- Contract creation fails → 500 Internal Server Error (with error details)

---

### JOURNEY-DPO-016: Link ODPS to ODCS Contract (Technical-First Flow) **NEW**

**Journey ID**: JOURNEY-DPO-016
**Title**: Link ODPS to ODCS Contract (Technical-First Flow)
**Persona**: Data Product Owner
**Goal**: Link an existing ODCS contract to an ODPS contract (or create new ODPS and link)

**Steps**:
1. Navigate to existing ODCS contract
2. Click "Link ODPS Contract" option
3. Choose linking method:
   - **Link to existing ODPS**: Select existing ODPS contract via **ContractPicker** (searchable dropdown; specType=ODPS)
   - **Create new ODPS**: Upload new ODPS document
4. If creating new ODPS:
   - Upload ODPS document
   - System parses and validates ODPS
   - System creates ODPS contract
5. System validates linking compatibility:
   - ODCS and ODPS contracts exist
   - Contracts belong to same tenant
   - No circular references
   - Schema compatibility (if applicable)
6. System establishes bidirectional link:
   - ODPS → ODCS: Store ODCS contract ID in ODPS `hub_contract_json.extensions.x_odps.odcs_link`
   - ODCS → ODPS: Store ODPS contract ID in ODCS `hub_contract_json.extensions.x_odps.odps_link`
7. System updates semantic layer with linking information
8. Link verification completed

**Success Criteria**:
- ODCS contract identified
- ODPS contract selected or created
- Linking compatibility validated
- Bidirectional link established
- Link stored in both contracts
- Semantic layer updated
- Link verification successful

**Performance Targets**:
- Total duration: < 2 minutes
- ODPS creation (if new): < 3 seconds
- Linking validation: < 1 second
- Link establishment: < 1 second
- Semantic update: < 5 seconds (async)

**API Endpoints**:
- `POST /api/v1/contracts/{odcs_contract_id}/link-odps/` - Link ODPS to ODCS contract
- `GET /api/v1/contracts/{id}/` - Get contract with linking information

**Error Scenarios**:
- ODCS contract not found → 404 Not Found
- ODPS contract not found → 404 Not Found
- Linking validation fails → 400 Bad Request (incompatible contracts)
- Circular reference detected → 400 Bad Request (circular reference)
- Contracts belong to different tenants → 403 Forbidden

---

### JOURNEY-DPO-017: Export ODPS Product **NEW**

**Journey ID**: JOURNEY-DPO-017
**Title**: Export ODPS Product
**Persona**: Data Product Owner
**Goal**: Export an ODPS contract in ODPS format (JSON or YAML)

**Steps**:
1. Navigate to ODPS contract details
2. Click "Export" button
3. Select export format:
   - **JSON**: Machine-readable format
   - **YAML**: Human-readable format
4. Optionally specify ODPS version (defaults to contract version)
5. System generates ODPS document from `hub_contract_json`
6. System includes linked ODCS contract in `product.contract.spec` (if linked)
7. System validates exported ODPS document
8. Export completed:
   - **API**: Returns ODPS document in response
   - **UI**: Downloads file with `.odps.json` or `.odps.yaml` extension

**Success Criteria**:
- ODPS contract identified
- Export format selected
- ODPS document generated from hub_contract_json
- Linked ODCS included in export (if linked)
- Exported ODPS document validated
- Export file downloaded or returned

**Performance Targets**:
- Total duration: < 10 seconds
- ODPS generation: < 2 seconds
- ODPS validation: < 1 second
- File download: < 1 second

**API Endpoints**:
- `GET /api/v1/contracts/{id}/export/?format=odps&output_format=json` - Export as JSON
- `GET /api/v1/contracts/{id}/export/?format=odps&output_format=yaml` - Export as YAML
- `GET /api/v1/contracts/{id}/download/?format=odps&output_format=json` - Download as JSON file
- `GET /api/v1/contracts/{id}/download/?format=odps&output_format=yaml` - Download as YAML file

**Error Scenarios**:
- Contract not found → 404 Not Found
- Contract is not ODPS type → 400 Bad Request (not an ODPS contract)
- Export generation fails → 500 Internal Server Error (with error details)
- Export validation fails → 500 Internal Server Error (generated ODPS invalid)

---

### JOURNEY-DPO-018: Edit Dataset and Link to Asset **NEW**

**Journey ID**: JOURNEY-DPO-018
**Title**: Edit Dataset and Link to Asset
**Persona**: Data Product Owner, Data Engineer
**Goal**: Link an existing dataset to an asset (or unlink) via dataset edit

**Steps**:
1. Navigate to Datasets
2. Select a dataset (or create one from Files → Create Dataset)
3. Click "Edit" or "Link to Asset"
4. Select asset via **AssetPicker** (searchable dropdown; or clear to unlink)
5. Optionally update format
6. Save
7. Dataset detail shows linked asset (asset_id, asset_name)

**Success Criteria**:
- Dataset linked to asset (or unlinked)
- AssetPicker returns valid tenant-scoped IDs only

**API Endpoints**: `PATCH /api/v1/datasets/{id}/` (asset, format)

**Related Use Cases**: UC-DS-EDIT
**Test Traceability**: [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) — `frontend/e2e/use-cases/ux/dataset-edit.spec.ts`

---

## Data Engineer Journeys

**Journey List**:
- JOURNEY-DE-001: Programmatic Contract-First Onboarding
- JOURNEY-DE-002: Set Up Scheduled Ingestion (if applicable)
- JOURNEY-DE-003: Configure Data Quality Checks
- JOURNEY-DE-004: Set Up Compliance Scanning
- JOURNEY-DE-005: Integrate External Data Source
- JOURNEY-DE-006: Monitor Data Pipeline Health
- JOURNEY-DE-007: Create Transformation Pipeline **NEW**
- JOURNEY-DE-008: Integrate AI Schema Matching into Workflow **NEW**
- JOURNEY-DE-009: Set Up Data Virtualization **NEW**
- JOURNEY-DE-010: Configure Connector for Data Source **NEW**
- JOURNEY-DE-011: Set Up Reverse ETL **NEW**
- JOURNEY-DE-012: Create Custom Plugin **NEW**
- JOURNEY-DE-013: Configure Data Mesh Domain **NEW**
- JOURNEY-DE-014: Create ODPS via API **NEW**
- JOURNEY-DE-015: Upload File via Files Page **NEW**
- JOURNEY-EXPORT-001: Create and Run Scheduled Export **NEW** (see [Scheduled Export Journeys](#scheduled-export-journeys))
- JOURNEY-EXPORT-002: Monitor and Troubleshoot Export Runs **NEW** (see [Scheduled Export Journeys](#scheduled-export-journeys))

### JOURNEY-DE-001: Programmatic Contract-First Onboarding

**Journey ID**: JOURNEY-DE-001
**Title**: Programmatic Contract-First Onboarding
**Persona**: Data Engineer
**Goal**: Onboard asset via contract-first flow using API/SDK/CLI

**Steps**:
1. Create contract via API/SDK/CLI
2. Validate contract
3. Normalize contract
4. Attach dataset
5. Create asset
6. Activate asset

---

### JOURNEY-DE-007: Create Transformation Pipeline **Deferred**

**Status**: **Deferred** (Phase 5 — transformation pipeline; see [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)).

**Journey ID**: JOURNEY-DE-007
**Title**: Create Transformation Pipeline
**Persona**: Data Engineer
**Goal**: Create transformation pipeline programmatically or via UI

**Steps**:
1. **NEW**: Design pipeline (UI or code)
2. **NEW**: Configure transformation nodes
3. **NEW**: Validate pipeline
4. **NEW**: Test pipeline with sample data
5. **NEW**: Save pipeline
6. **NEW**: Execute pipeline
7. **NEW**: Monitor execution
8. **NEW**: Review results

**Success Criteria**:
- Pipeline designed
- Pipeline validated
- Test successful
- Execution successful
- Results reviewed

---

### JOURNEY-DE-008: Integrate AI Schema Matching into Workflow **NEW**

**Journey ID**: JOURNEY-DE-008
**Title**: Integrate AI Schema Matching into Workflow
**Persona**: Data Engineer
**Goal**: Integrate AI schema matching into automated workflows

**Steps**:
1. **NEW**: Configure AI service connection
2. **NEW**: Integrate schema matching API into workflow
3. **NEW**: Test schema matching
4. **NEW**: Configure mapping acceptance rules
5. **NEW**: Deploy workflow
6. **NEW**: Monitor schema matching performance

**Success Criteria**:
- AI service connected
- Schema matching integrated
- Tests pass
- Workflow deployed
- Performance monitored

---

### JOURNEY-DE-009: Set Up Data Virtualization **NEW**

**Journey ID**: JOURNEY-DE-009
**Title**: Set Up Data Virtualization
**Persona**: Data Engineer
**Goal**: Set up data virtualization for querying across sources

**Steps**:
1. **NEW**: Define virtual dataset
2. **NEW**: Configure source systems
3. **NEW**: Set up query mapping
4. **NEW**: Configure caching strategy
5. **NEW**: Test virtual dataset queries
6. **NEW**: Deploy virtual dataset
7. **NEW**: Monitor query performance

**Success Criteria**:
- Virtual dataset defined
- Sources configured
- Queries work
- Caching configured
- Performance acceptable

---

### JOURNEY-DE-010: Configure Connector for Data Source **NEW**

**Journey ID**: JOURNEY-DE-010
**Title**: Configure Connector for Data Source
**Persona**: Data Engineer
**Goal**: Configure connector for external data source

**Steps**:
1. **NEW**: Browse connector marketplace
2. **NEW**: Select connector (or create custom)
3. **NEW**: Install connector
4. **NEW**: Configure connection (credentials, settings)
5. **NEW**: Test connection
6. **NEW**: Deploy connector
7. **NEW**: Monitor connector health

**Success Criteria**:
- Connector selected/created
- Connection configured
- Test successful
- Connector deployed
- Health monitored

---

### JOURNEY-DE-011: Set Up Reverse ETL **NEW**

**Journey ID**: JOURNEY-DE-011
**Title**: Set Up Reverse ETL
**Persona**: Data Engineer
**Goal**: Set up reverse ETL to push data to operational systems

**Steps**:
1. **NEW**: Select data source
2. **NEW**: Configure destination (CRM, marketing platform)
3. **NEW**: Map data fields
4. **NEW**: Configure transformation (if needed)
5. **NEW**: Set up schedule
6. **NEW**: Test reverse ETL
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Destination configured
- Mapping complete
- Schedule set
- Test successful
- Reverse ETL operational

---

### JOURNEY-DE-012: Create Custom Plugin **NEW**

**Journey ID**: JOURNEY-DE-012
**Title**: Create Custom Plugin
**Persona**: Data Engineer
**Goal**: Create custom plugin for platform extension

**Steps**:
1. **NEW**: Design plugin (connector, transformation, quality check)
2. **NEW**: Implement plugin interface
3. **NEW**: Test plugin
4. **NEW**: Validate plugin
5. **NEW**: Publish to plugin marketplace (optional)
6. **NEW**: Deploy plugin

**Success Criteria**:
- Plugin designed
- Interface implemented
- Tests pass
- Plugin validated
- Plugin deployed

---

### JOURNEY-DE-013: Configure Data Mesh Domain **NEW**

**Journey ID**: JOURNEY-DE-013
**Title**: Configure Data Mesh Domain
**Persona**: Data Engineer
**Goal**: Configure data mesh domain infrastructure

**Steps**:
1. **NEW**: Create domain
2. **NEW**: Configure domain infrastructure
3. **NEW**: Set up self-serve capabilities
4. **NEW**: Configure resource quotas
5. **NEW**: Set up governance
6. **NEW**: Deploy domain
7. **NEW**: Monitor domain

**Success Criteria**:
- Domain created
- Infrastructure configured
- Capabilities set up
- Governance configured
- Domain operational

---

### JOURNEY-DE-014: Create ODPS via API **NEW**

**Journey ID**: JOURNEY-DE-014
**Title**: Create ODPS via API
**Persona**: Data Engineer
**Goal**: Create an ODPS product programmatically via REST API, GraphQL, or SDK

**Steps**:
1. Authenticate with API (obtain access token)
2. Prepare ODPS document (JSON or YAML):
   - Include product details
   - Include marketplace information (pricing, access methods, payment gateways)
   - Optionally include ODCS contract in `product.contract.spec` (Product-First flow)
3. Choose creation method:
   - **REST API**: `POST /api/v1/contracts/products/`
   - **GraphQL**: `mutation { createODPS(input: {...}) }`
   - **Python SDK**: `client.contracts.create_odps(...)`
   - **JavaScript SDK**: `client.contracts.createODPS(...)`
   - **CLI**: `datahub contracts create-odps ...`
4. Send request with ODPS document:
   - Include `original_raw` (ODPS document as string)
   - Include `original_format` (JSON or YAML)
   - Include `extract_odcs` (true for Product-First flow)
   - Include `resolve_external_refs` (optional, for $ref resolution)
5. System processes request:
   - Parses ODPS document
   - Validates ODPS schema
   - Detects ODPS version
   - If Product-First flow: Extracts ODCS from `product.contract`
   - Creates ODCS contract (if extracted)
   - Creates ODPS contract
   - Links contracts bidirectionally (if both created)
   - Triggers semantic mapping (async)
6. Receive response:
   - ODPS contract ID
   - ODCS contract ID (if Product-First flow)
   - Workflow instance ID (for tracking)
7. Monitor workflow status (optional):
   - Query workflow instance status
   - Check contract creation progress
8. Verify contracts created:
   - Query ODPS contract details
   - Query ODCS contract details (if applicable)
   - Verify linking (if applicable)

**Success Criteria**:
- API authenticated
- ODPS document prepared
- Request sent successfully
- ODPS contract created
- ODCS contract created (if Product-First flow)
- Contracts linked bidirectionally (if both created)
- Workflow completed successfully
- Contracts accessible via API

**Performance Targets**:
- Total duration: < 5 minutes
- API request: < 1 second
- ODPS parsing: < 2 seconds
- ODPS validation: < 3 seconds
- Contract creation: < 2 seconds per contract
- Workflow completion: < 5 minutes (includes async semantic mapping)

**API Endpoints**:
- `POST /api/v1/contracts/products/` - Create ODPS product (REST)
- `POST /graphql/` - Create ODPS product (GraphQL mutation)
- `GET /api/v1/contracts/{id}/` - Get contract details
- `GET /api/v1/workflows/{id}/` - Get workflow instance status

**SDK Methods**:
- Python: `ContractsAPI.create_odps()`
- JavaScript: `ContractsAPI.createODPS()`
- CLI: `datahub contracts create-odps`

**Error Scenarios**:
- Authentication fails → 401 Unauthorized
- Invalid ODPS format → 400 Bad Request (format not supported)
- ODPS validation fails → 400 Bad Request (validation errors)
- ODCS extraction fails → 400 Bad Request (no contract in product.contract)
- Contract creation fails → 500 Internal Server Error (with error details)
- Workflow execution fails → 500 Internal Server Error (workflow error)

---

### JOURNEY-DE-015: Upload File via Files Page **NEW**

**Journey ID**: JOURNEY-DE-015
**Title**: Upload File via Files Page
**Persona**: Data Engineer, Data Product Owner
**Goal**: Upload a data file (CSV, JSON, Parquet) via the Files page for later dataset creation

**Steps**:
1. Navigate to Files
2. Click "Upload File"
3. Select file or drop into dropzone
4. System validates format and size
5. File uploads; appears in list
6. User can create dataset from file (Datasets → Create Dataset → Select File)

**Success Criteria**:
- File uploaded successfully
- File appears in Files list
- File available for dataset creation

**API Endpoints**: `POST /api/v1/files/init/`, `POST /api/v1/files/{id}/complete/` (multipart upload flow)

**Related Use Cases**: UC-FILE-UPLOAD
**Test Traceability**: [TEST_TRACEABILITY.md](TEST_TRACEABILITY.md) — `frontend/e2e/use-cases/ux/files-upload.spec.ts`

---

## Compliance Officer Journeys

### JOURNEY-CPO-001: Review Compliance for Asset

**Journey ID**: JOURNEY-CPO-001
**Title**: Review Compliance for Asset
**Persona**: Compliance Officer
**Goal**: Review compliance status and details for an asset

**Steps**:
1. Navigate to asset
2. View compliance section
3. Review compliance status
4. Review compliance details
5. **NEW**: Review AI auto-classification results
6. Generate compliance report (if needed)

---

### JOURNEY-CPO-006: Configure Automated Compliance **NEW**

**Journey ID**: JOURNEY-CPO-006
**Title**: Configure Automated Compliance
**Persona**: Compliance Officer
**Goal**: Configure automated compliance detection and enforcement

**Steps**:
1. **NEW**: Navigate to compliance configuration
2. **NEW**: Define compliance rules
3. **NEW**: Configure auto-detection
4. **NEW**: Set up enforcement actions
5. **NEW**: Configure alerts
6. **NEW**: Test automated compliance
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Rules defined
- Auto-detection configured
- Enforcement set up
- Tests pass
- Automated compliance operational

---

### JOURNEY-CPO-007: Set Up GDPR Right to be Forgotten **NEW**

**Journey ID**: JOURNEY-CPO-007
**Title**: Set Up GDPR Right to be Forgotten
**Persona**: Compliance Officer
**Goal**: Configure GDPR deletion workflows

**Steps**:
1. **NEW**: Navigate to GDPR configuration
2. **NEW**: Configure deletion request workflow
3. **NEW**: Set up data deletion service
4. **NEW**: Configure deletion verification
5. **NEW**: Test deletion workflow
6. **NEW**: Deploy workflow
7. **NEW**: Monitor deletion requests

**Success Criteria**:
- Workflow configured
- Deletion service set up
- Verification configured
- Tests pass
- Workflow operational

---

### JOURNEY-CPO-008: Manage Consent Tracking **NEW**

**Journey ID**: JOURNEY-CPO-008
**Title**: Manage Consent Tracking
**Persona**: Compliance Officer
**Goal**: Track and manage data consent

**Steps**:
1. **NEW**: Navigate to consent management
2. **NEW**: Configure consent rules
3. **NEW**: Set up consent tracking
4. **NEW**: Monitor consent status
5. **NEW**: Generate consent reports
6. **NEW**: Handle consent changes

**Success Criteria**:
- Rules configured
- Tracking set up
- Status monitored
- Reports generated
- Changes handled

---

### JOURNEY-CPO-009: Configure Automated Retention Policies **NEW**

**Journey ID**: JOURNEY-CPO-009
**Title**: Configure Automated Retention Policies
**Persona**: Compliance Officer
**Goal**: Configure automated data retention

**Steps**:
1. **NEW**: Navigate to retention configuration
2. **NEW**: Define retention rules
3. **NEW**: Configure automation
4. **NEW**: Set up scheduling
5. **NEW**: Configure deletion workflows
6. **NEW**: Test retention policies
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Rules defined
- Automation configured
- Scheduling set up
- Tests pass
- Retention operational

---

### JOURNEY-CPO-010: Review AI Auto-Classification Results **NEW**

**Journey ID**: JOURNEY-CPO-010
**Title**: Review AI Auto-Classification Results
**Persona**: Compliance Officer
**Goal**: Review and validate AI auto-classification results

**Steps**:
1. **NEW**: Navigate to classification dashboard
2. **NEW**: View classification results
3. **NEW**: Review confidence scores
4. **NEW**: Approve/reject classifications
5. **NEW**: Update classification rules (if needed)
6. **NEW**: Generate classification reports

**Success Criteria**:
- Results reviewed
- Classifications validated
- Rules updated (if needed)
- Reports generated

---

## Data Consumer Journeys

### JOURNEY-DC-001: Discover and Purchase Marketplace Asset

**Journey ID**: JOURNEY-DC-001
**Title**: Discover and Purchase Marketplace Asset
**Persona**: Data Consumer
**Goal**: Discover and purchase data asset from marketplace

**Steps**:
1. Navigate to marketplace
2. **NEW**: Use natural language search OR keyword search
3. **NEW**: View asset recommendations
4. View asset details
5. **NEW**: Preview data before purchase
6. **NEW**: Review ratings and reviews
7. **NEW**: View trust signals (quality SLAs, badges)
8. Review pricing
9. **NEW**: Select pricing model (if multiple options)
10. Purchase asset
11. Download or access data

**Success Criteria**:
- Asset discovered
- **NEW**: Natural language search works
- **NEW**: Recommendations displayed
- **NEW**: Preview accessible
- **NEW**: Ratings/reviews visible
- Purchase completed
- Data accessible

---

### JOURNEY-DC-006: Use Natural Language Search **NEW**

**Journey ID**: JOURNEY-DC-006
**Title**: Use Natural Language Search
**Persona**: Data Consumer
**Goal**: Discover data using natural language queries

**Steps**:
1. **NEW**: Navigate to search
2. **NEW**: Enter natural language query ("show me customer data from last quarter")
3. **NEW**: Review query interpretation
4. **NEW**: Execute query
5. **NEW**: Review results
6. **NEW**: Refine query if needed
7. **NEW**: Save query (optional)

**Success Criteria**:
- Query understood
- Interpretation displayed
- Results returned
- Query can be refined
- Query can be saved

**Performance Targets**:
- Query understanding: < 3 seconds
- Results returned: < 5 seconds

---

### JOURNEY-DC-007: Create Transformation Pipeline for Data **Deferred**

**Status**: **Deferred** (Phase 5 — transformation pipeline; see [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)).

**Journey ID**: JOURNEY-DC-007
**Title**: Create Transformation Pipeline for Data
**Persona**: Data Consumer
**Goal**: Create transformation pipeline to transform purchased data

**Steps**:
1. **NEW**: Select data asset
2. **NEW**: Navigate to transformation section
3. **NEW**: Create pipeline
4. **NEW**: Design pipeline (visual builder)
5. **NEW**: Configure transformations
6. **NEW**: Preview results
7. **NEW**: Execute pipeline
8. **NEW**: Download transformed data

**Success Criteria**:
- Pipeline created
- Transformations configured
- Preview generated
- Pipeline executed
- Data downloaded

---

### JOURNEY-DC-008: Rate and Review Asset **NEW**

**Journey ID**: JOURNEY-DC-008
**Title**: Rate and Review Asset
**Persona**: Data Consumer
**Goal**: Rate and review data asset

**Steps**:
1. **NEW**: Navigate to asset details
2. **NEW**: Open Community section (ratings/reviews on asset page, Phase 27.1)
3. **NEW**: Rate asset (1-5 stars)
4. **NEW**: Write review
5. **NEW**: Submit review
6. **NEW**: View review status (pending moderation)

**Success Criteria**:
- Rating submitted
- Review submitted
- Review pending moderation
- Review published (after moderation)

---

### JOURNEY-DC-009: Join Data Community **NEW**

**Journey ID**: JOURNEY-DC-009
**Title**: Join Data Community
**Persona**: Data Consumer
**Goal**: Join data community for collaboration

**Steps**:
1. **NEW**: Browse data communities
2. **NEW**: View community details
3. **NEW**: Join community
4. **NEW**: Participate in discussions
5. **NEW**: Access community assets
6. **NEW**: Contribute to knowledge base

**Success Criteria**:
- Community joined
- Discussions accessible
- Assets accessible
- Knowledge base accessible

---

### JOURNEY-DC-010: Query Virtual Dataset **NEW**

**Journey ID**: JOURNEY-DC-010
**Title**: Query Virtual Dataset
**Persona**: Data Consumer
**Goal**: Query virtual dataset across multiple sources

**Steps**:
1. **NEW**: Navigate to virtualization section
2. **NEW**: Select virtual dataset
3. **NEW**: Build query (SQL or visual builder)
4. **NEW**: Execute query
5. **NEW**: Review results
6. **NEW**: Export results (if needed)

**Success Criteria**:
- Virtual dataset selected
- Query built
- Query executed
- Results returned
- Results exported (if needed)

**Performance Targets**:
- Query execution: < 10 seconds
- Results returned: < 5 seconds

---

### JOURNEY-DC-011: Purchase Asset with Usage-Based Pricing **NEW**

**Journey ID**: JOURNEY-DC-011
**Title**: Purchase Asset with Usage-Based Pricing
**Persona**: Data Consumer
**Goal**: Purchase asset with usage-based pricing

**Steps**:
1. **NEW**: Select asset with usage-based pricing
2. **NEW**: Review pricing model (per-query, per-GB)
3. **NEW**: Purchase asset
4. **NEW**: Use asset (queries, downloads)
5. **NEW**: Monitor usage
6. **NEW**: Review billing

**Success Criteria**:
- Asset purchased
- Usage tracked
- Billing accurate
- Usage monitored

---

### JOURNEY-DC-012: Preview Data Before Purchase **NEW**

**Journey ID**: JOURNEY-DC-012
**Title**: Preview Data Before Purchase
**Persona**: Data Consumer
**Goal**: Preview data before purchasing

**Steps**:
1. **NEW**: Navigate to marketplace listing
2. **NEW**: Request data preview
3. **NEW**: Review sample data
4. **NEW**: Review data quality metrics
5. **NEW**: Review schema
6. **NEW**: Make purchase decision

**Success Criteria**:
- Preview requested
- Sample data displayed
- Quality metrics visible
- Schema visible
- Decision made

---

### JOURNEY-DC-013: Use Asset Recommendations **NEW**

**Journey ID**: JOURNEY-DC-013
**Title**: Use Asset Recommendations
**Persona**: Data Consumer
**Goal**: Discover assets using AI recommendations

**Steps**:
1. **NEW**: Navigate to recommendations section
2. **NEW**: View "Recommended for you"
3. **NEW**: View "Similar assets"
4. **NEW**: View "Users who viewed this also used..."
5. **NEW**: Explore recommended assets
6. **NEW**: Provide feedback (like/dislike)

**Success Criteria**:
- Recommendations displayed
- Recommendations relevant
- Assets can be explored
- Feedback can be provided
- Recommendations improve over time

---

### JOURNEY-DC-014: Discover ODPS Products (Semantic Search) **NEW**

**Journey ID**: JOURNEY-DC-014
**Title**: Discover ODPS Products (Semantic Search)
**Persona**: Data Consumer
**Goal**: Discover ODPS products using semantic search queries

**Steps**:
1. Navigate to semantic search interface
2. Enter search query (natural language or SPARQL)
3. System executes semantic search query:
   - Search by product name/description (multilingual support)
   - Search by pricing plan
   - Search by access method
   - Search by product strategy
   - Search by product-contract linking (ODPS ↔ ODCS)
4. System queries semantic layer (RDF/SPARQL)
5. System returns matching ODPS products
6. Review search results:
   - Product details
   - Pricing information
   - Access methods
   - Linked ODCS contract information
7. Filter results (if needed):
   - By pricing range
   - By access method type
   - By product category
8. Select product for detailed view

**Success Criteria**:
- Semantic search query executed
- ODPS products discovered
- Results include product metadata
- Results include pricing information
- Results include access methods
- Results include linked ODCS information (if linked)
- Filtering works correctly
- Product details accessible

**Performance Targets**:
- Total duration: < 10 seconds
- Query execution: < 3 seconds
- Results returned: < 2 seconds

**API Endpoints**:
- `POST /api/v1/semantic/search/` - Execute semantic search query
- `GET /api/v1/semantic/products/` - List ODPS products
- `GET /api/v1/contracts/{id}/` - Get ODPS product details

**Error Scenarios**:
- Invalid query syntax → 400 Bad Request (query syntax error)
- Semantic service unavailable → 503 Service Unavailable
- No results found → 200 OK (empty results)

---

### JOURNEY-DC-015: Purchase ODPS Product (Marketplace) **NEW**

**Journey ID**: JOURNEY-DC-015
**Title**: Purchase ODPS Product (Marketplace)
**Persona**: Data Consumer
**Goal**: Purchase an ODPS product from the marketplace with pricing, access, and payment processing

**Steps**:
1. Navigate to marketplace
2. Discover ODPS product (via search, browse, or recommendations)
3. View ODPS product details:
   - Product information (name, description, category)
   - Pricing plans (free, basic, premium, enterprise)
   - Access methods (API, download, streaming)
   - Payment gateways (Stripe, PayPal, etc.)
   - Linked ODCS contract information (technical details)
4. Select pricing plan
5. Review pricing details:
   - Price amount
   - Currency
   - Billing period
   - Plan features
6. Select access method (if multiple available)
7. Review payment gateway options
8. Click "Purchase" button
9. System creates order
10. System processes payment via selected payment gateway:
    - Stripe: Process payment with Stripe API
    - PayPal: Process payment with PayPal API
    - Other: Process via configured gateway
11. Payment processed successfully
12. System creates entitlement:
    - Grant access to selected access method
    - Configure API keys (if API access)
    - Set up download permissions (if download access)
13. Order approved
14. Access granted to ODPS product

**Success Criteria**:
- ODPS product discovered
- Product details displayed correctly
- Pricing plans visible
- Access methods visible
- Payment gateways visible
- Pricing plan selected
- Payment processed successfully
- Order created
- Entitlement created
- Access granted

**Performance Targets**:
- Total duration: < 5 minutes
- Product discovery: < 10 seconds
- Order creation: < 2 seconds
- Payment processing: < 30 seconds
- Entitlement creation: < 2 seconds

**API Endpoints**:
- `GET /api/v1/marketplace/listings/{id}/` - Get marketplace listing with ODPS details
- `POST /api/v1/marketplace/orders/purchase/` - Create order and process payment
- `GET /api/v1/marketplace/orders/{id}/` - Get order status
- `GET /api/v1/entitlements/` - List user entitlements

**Error Scenarios**:
- Product not found → 404 Not Found
- Pricing plan not available → 400 Bad Request (plan unavailable)
- Payment gateway error → 500 Internal Server Error (payment failed)
- Insufficient funds → 400 Bad Request (payment declined)
- Entitlement creation fails → 500 Internal Server Error (with compensation)

---

## Tenant Admin Journeys

### JOURNEY-TA-001: Onboard New User

**Journey ID**: JOURNEY-TA-001
**Title**: Onboard New User
**Persona**: Tenant Admin
**Goal**: Invite and onboard a new user to the tenant

**Steps**:
1. Navigate to User Management
2. Click "Invite User"
3. Enter user email
4. Select role
5. Send invitation
6. User receives email
7. User accepts invitation
8. Verify user activated

---

### JOURNEY-TA-005: Configure Data Mesh Domains **NEW**

**Journey ID**: JOURNEY-TA-005
**Title**: Configure Data Mesh Domains
**Persona**: Tenant Admin
**Goal**: Configure data mesh domains for tenant

**Steps**:
1. **NEW**: Navigate to data mesh configuration
2. **NEW**: Create domains
3. **NEW**: Assign domain owners
4. **NEW**: Configure domain policies
5. **NEW**: Monitor domains

**Success Criteria**:
- Domains created
- Owners assigned
- Policies configured
- Domains monitored

---

### JOURNEY-TA-006: Set Up Advanced Governance **NEW**

**Journey ID**: JOURNEY-TA-006
**Title**: Set Up Advanced Governance
**Persona**: Tenant Admin
**Goal**: Configure advanced governance features

**Steps**:
1. **NEW**: Navigate to governance configuration
2. **NEW**: Configure automated compliance
3. **NEW**: Set up retention automation
4. **NEW**: Configure consent management
5. **NEW**: Test governance features
6. **NEW**: Deploy and monitor

**Success Criteria**:
- Automated compliance configured
- Retention automation set up
- Consent management configured
- Tests pass
- Governance operational

---

### JOURNEY-TA-007: Monitor Cost Tracking **NEW**

**Journey ID**: JOURNEY-TA-007
**Title**: Monitor Cost Tracking
**Persona**: Tenant Admin
**Goal**: Monitor and optimize tenant costs

**Steps**:
1. **NEW**: Navigate to cost dashboard
2. **NEW**: View cost breakdown
3. **NEW**: Analyze costs by asset/domain
4. **NEW**: Review cost optimization recommendations
5. **NEW**: Implement optimizations
6. **NEW**: Monitor cost trends

**Success Criteria**:
- Costs displayed
- Breakdown visible
- Recommendations provided
- Optimizations implemented
- Trends monitored

---

### JOURNEY-TA-008: Configure Integration Ecosystem **NEW**

**Journey ID**: JOURNEY-TA-008
**Title**: Configure Integration Ecosystem
**Persona**: Tenant Admin
**Goal**: Configure integrations for tenant

**Steps**:
1. **NEW**: Navigate to integrations
2. **NEW**: Install connectors
3. **NEW**: Configure connections
4. **NEW**: Test integrations
5. **NEW**: Deploy integrations
6. **NEW**: Monitor integration health

**Success Criteria**:
- Connectors installed
- Connections configured
- Tests pass
- Integrations deployed
- Health monitored

---

### JOURNEY-TA-SUBSCRIPTION: Manage Subscription and Invoices **NEW** (useronboardfix Phase 17)

**Journey ID**: JOURNEY-TA-SUBSCRIPTION
**Title**: Manage Subscription and Invoices
**Persona**: Tenant Admin
**Goal**: View subscription plan, change plan, and access invoice history

**Steps**:
1. **NEW**: Navigate to Settings → Subscription (`/settings/subscription`)
2. **NEW**: View current plan (e.g. FREE, PRO)
3. **NEW**: View invoice history (table or empty state)
4. **NEW**: Change plan (if other plans exist) via dropdown
5. **NEW**: Download invoice (if invoices exist)

**Success Criteria**:
- Subscription page accessible
- Current plan visible
- Invoice history visible
- Plan change UI visible when other plans exist
- Invoice download works when invoices exist

**API Endpoints**: `GET /api/v1/billing/subscription/current/`, `POST .../change-plan/`, `GET /api/v1/billing/plans/`, `GET /api/v1/billing/invoices/`, `GET .../invoices/{id}/download/`

---

### JOURNEY-TA-TENANT-SETTINGS: View Usage and Configure Tenant **NEW** (useronboardfix Phase 8)

**Journey ID**: JOURNEY-TA-TENANT-SETTINGS
**Title**: View Usage and Configure Tenant
**Persona**: Tenant Admin
**Goal**: View tenant usage and configure tenant settings (DQ profile, versioning, workflows)

**Steps**:
1. **NEW**: Navigate to Settings → Tenant (`/settings/tenant`)
2. **NEW**: View usage tab (storage, API calls, limits)
3. **NEW**: Switch to Configuration tab
4. **NEW**: Edit default DQ profile, save
5. **NEW**: Toggle versioning enabled, save
6. **NEW**: Toggle workflows enabled, save

**Success Criteria**:
- Usage tab shows metrics
- Config tab allows edits
- Changes persist after save

**API Endpoints**: `GET /api/v1/tenants/me/usage/`, `GET /api/v1/tenants/me/config/`, `PATCH /api/v1/tenants/me/config/`

---

## Platform Admin Journeys

### JOURNEY-PA-001: Onboard New Tenant

**Journey ID**: JOURNEY-PA-001
**Title**: Onboard New Tenant
**Persona**: Platform Admin
**Goal**: Create a new tenant organization

**Steps**:
1. Navigate to tenant management
2. Create new tenant
3. Configure tenant settings
4. Set up KYC
5. Verify tenant
6. Activate tenant

---

### JOURNEY-MPA-005: Manage Connector Marketplace **NEW**

**Journey ID**: JOURNEY-MPA-005
**Title**: Manage Connector Marketplace
**Persona**: Platform Admin
**Goal**: Manage connector marketplace

**Steps**:
1. **NEW**: Navigate to connector marketplace admin
2. **NEW**: Review connector submissions
3. **NEW**: Validate connectors
4. **NEW**: Approve/reject connectors
5. **NEW**: Publish connectors
6. **NEW**: Monitor connector usage

**Success Criteria**:
- Submissions reviewed
- Connectors validated
- Connectors published
- Usage monitored

---

### JOURNEY-MPA-006: Configure Advanced Marketplace Features **NEW**

**Journey ID**: JOURNEY-MPA-006
**Title**: Configure Advanced Marketplace Features
**Persona**: Platform Admin
**Goal**: Configure advanced marketplace features

**Steps**:
1. **NEW**: Navigate to marketplace configuration
2. **NEW**: Set up usage-based pricing
3. **NEW**: Configure trust signals
4. **NEW**: Set up data previews
5. **NEW**: Configure marketplace recommendations
6. **NEW**: Test features
7. **NEW**: Deploy features

**Success Criteria**:
- Usage-based pricing configured
- Trust signals set up
- Previews configured
- Recommendations configured
- Features operational

---

### JOURNEY-MPA-007: Monitor Data Mesh Topology **NEW**

**Journey ID**: JOURNEY-MPA-007
**Title**: Monitor Data Mesh Topology
**Persona**: Platform Admin
**Goal**: Monitor data mesh topology across platform

**Steps**:
1. **NEW**: Navigate to mesh topology dashboard
2. **NEW**: View mesh topology visualization
3. **NEW**: Monitor domain health
4. **NEW**: Review domain relationships
5. **NEW**: Identify topology issues
6. **NEW**: Generate topology reports

**Success Criteria**:
- Topology visualized
- Health monitored
- Relationships visible
- Issues identified
- Reports generated

---

### JOURNEY-MPA-008: Configure Advanced Observability **NEW**

**Journey ID**: JOURNEY-MPA-008
**Title**: Configure Advanced Observability
**Persona**: Platform Admin
**Goal**: Configure advanced observability features

**Steps**:
1. **NEW**: Navigate to observability configuration
2. **NEW**: Set up reliability scores
3. **NEW**: Configure cost tracking
4. **NEW**: Set up predictive alerts
5. **NEW**: Configure performance monitoring
6. **NEW**: Test observability
7. **NEW**: Deploy and monitor

**Success Criteria**:
- Reliability scores configured
- Cost tracking set up
- Predictive alerts configured
- Performance monitoring set up
- Observability operational

---

### JOURNEY-MPA-009: Manage Plugin Marketplace **NEW**

**Journey ID**: JOURNEY-MPA-009
**Title**: Manage Plugin Marketplace
**Persona**: Platform Admin
**Goal**: Manage plugin marketplace

**Steps**:
1. **NEW**: Navigate to plugin marketplace admin
2. **NEW**: Review plugin submissions
3. **NEW**: Validate plugins
4. **NEW**: Approve/reject plugins
5. **NEW**: Publish plugins
6. **NEW**: Monitor plugin usage

**Success Criteria**:
- Submissions reviewed
- Plugins validated
- Plugins published
- Usage monitored

---

### JOURNEY-PA-010: Manage ODPS Products **NEW**

**Journey ID**: JOURNEY-PA-010
**Title**: Manage ODPS Products
**Persona**: Platform Admin
**Goal**: Manage ODPS products across the platform (monitor, validate, troubleshoot)

**Steps**:
1. Navigate to ODPS products management dashboard
2. View ODPS products overview:
   - Total ODPS products count
   - Products by version (4.1, 4.0, etc.)
   - Products by status (DRAFT, ACTIVE, ARCHIVED)
   - Products with linked ODCS contracts
   - Products without linked ODCS contracts
3. Filter and search ODPS products:
   - By tenant
   - By status
   - By version
   - By linking status (linked/unlinked)
4. Review ODPS product details:
   - Product metadata
   - Contract information
   - Linking status (ODPS ↔ ODCS)
   - Semantic mapping status
   - Marketplace listing status
5. Monitor ODPS product health:
   - Validation status
   - Normalization status
   - Semantic mapping status
   - Marketplace sync status
6. Validate ODPS products:
   - Re-validate ODPS schema
   - Check linking integrity
   - Verify semantic mapping
7. Troubleshoot issues:
   - Review validation errors
   - Check linking errors
   - Review semantic mapping errors
   - Fix data inconsistencies
8. Manage ODPS product lifecycle:
   - Archive inactive products
   - Update product versions
   - Migrate products to new ODPS versions
9. Generate ODPS product reports:
   - Product statistics
   - Linking statistics
   - Usage statistics
   - Error reports

**Success Criteria**:
- ODPS products dashboard accessible
- Products overview displayed correctly
- Filtering and search work
- Product details accessible
- Health monitoring functional
- Validation works correctly
- Issues can be identified and resolved
- Lifecycle management functional
- Reports generated successfully

**Performance Targets**:
- Total duration: < 5 minutes
- Dashboard load: < 2 seconds
- Product list: < 1 second
- Product details: < 500ms
- Validation: < 5 seconds per product
- Report generation: < 10 seconds

**API Endpoints**:
- `GET /api/v1/admin/odps/products/` - List all ODPS products
- `GET /api/v1/admin/odps/products/{id}/` - Get ODPS product details
- `POST /api/v1/admin/odps/products/{id}/validate/` - Re-validate ODPS product
- `GET /api/v1/admin/odps/products/stats/` - Get ODPS product statistics
- `GET /api/v1/admin/odps/products/reports/` - Generate ODPS product reports

**Error Scenarios**:
- Insufficient permissions → 403 Forbidden
- Product not found → 404 Not Found
- Validation fails → 400 Bad Request (validation errors)
- Report generation fails → 500 Internal Server Error

---

## External Developer Journeys

### JOURNEY-DEV-001: Build Custom Integration

**Journey ID**: JOURNEY-DEV-001
**Title**: Build Custom Integration
**Persona**: External Developer
**Goal**: Build integration between hub and external system

**Steps**:
1. Review API documentation
2. Obtain API credentials
3. Initialize SDK/client
4. Test authentication
5. Implement integration
6. Handle errors
7. Test integration
8. Deploy application

---

### JOURNEY-DEV-005: Use Natural Language Search API **NEW**

**Journey ID**: JOURNEY-DEV-005
**Title**: Use Natural Language Search API
**Persona**: External Developer
**Goal**: Integrate natural language search into application

**Steps**:
1. **NEW**: Review natural language search API documentation
2. **NEW**: Authenticate with API
3. **NEW**: Send natural language query
4. **NEW**: Receive query interpretation
5. **NEW**: Receive search results
6. **NEW**: Process results in application

**Success Criteria**:
- API authenticated
- Query sent
- Interpretation received
- Results received
- Results processed

---

### JOURNEY-DEV-006: Integrate Transformation Pipeline API **Deferred**

**Status**: **Deferred** (Phase 5 — transformation pipeline; see [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)).

**Journey ID**: JOURNEY-DEV-006
**Title**: Integrate Transformation Pipeline API
**Persona**: External Developer
**Goal**: Integrate transformation pipelines into application

**Steps**:
1. **NEW**: Review transformation API documentation
2. **NEW**: Create pipeline via API
3. **NEW**: Execute pipeline via API
4. **NEW**: Monitor pipeline execution
5. **NEW**: Retrieve transformation results
6. **NEW**: Process results in application

**Success Criteria**:
- Pipeline created
- Pipeline executed
- Execution monitored
- Results retrieved
- Results processed

---

### JOURNEY-DEV-007: Build Custom Connector **NEW**

**Journey ID**: JOURNEY-DEV-007
**Title**: Build Custom Connector
**Persona**: External Developer
**Goal**: Build custom connector for data source

**Steps**:
1. **NEW**: Review connector framework documentation
2. **NEW**: Design connector
3. **NEW**: Implement connector interface
4. **NEW**: Test connector
5. **NEW**: Validate connector
6. **NEW**: Publish connector to marketplace (optional)

**Success Criteria**:
- Connector designed
- Interface implemented
- Tests pass
- Connector validated
- Connector published (if applicable)

---

### JOURNEY-DEV-008: Use Plugin System **NEW**

**Journey ID**: JOURNEY-DEV-008
**Title**: Use Plugin System
**Persona**: External Developer
**Goal**: Use or create plugins for platform extension

**Steps**:
1. **NEW**: Browse plugin marketplace
2. **NEW**: Install plugin
3. **NEW**: Configure plugin
4. **NEW**: Use plugin functionality
5. **NEW**: Create custom plugin (if needed)
6. **NEW**: Publish plugin (if applicable)

**Success Criteria**:
- Plugin installed
- Plugin configured
- Plugin functional
- Custom plugin created (if applicable)
- Plugin published (if applicable)

---

### JOURNEY-DEV-009: Integrate with Developer Portal **NEW**

**Journey ID**: JOURNEY-DEV-009
**Title**: Integrate with Developer Portal
**Persona**: External Developer
**Goal**: Use developer portal for integration development

**Steps**:
1. **NEW**: Access developer portal
2. **NEW**: Review API documentation
3. **NEW**: Review code examples
4. **NEW**: Use sandbox environment
5. **NEW**: Follow tutorials
6. **NEW**: Deploy integration

**Success Criteria**:
- Portal accessed
- Documentation reviewed
- Examples used
- Sandbox used
- Integration deployed

---

## Auditor Journeys

### JOURNEY-AUD-001: Review Audit Logs

**Journey ID**: JOURNEY-AUD-001
**Title**: Review Audit Logs
**Persona**: Auditor
**Goal**: Review system audit logs

**Steps**:
1. Navigate to audit dashboard
2. Filter logs
3. Review log details
4. Export logs (if needed)

---

### JOURNEY-AUD-004: Review Data Mesh Governance **NEW**

**Journey ID**: JOURNEY-AUD-004
**Title**: Review Data Mesh Governance
**Persona**: Auditor
**Goal**: Audit data mesh governance

**Steps**:
1. **NEW**: Navigate to data mesh governance dashboard
2. **NEW**: View mesh topology
3. **NEW**: Review domain policies
4. **NEW**: Audit policy compliance
5. **NEW**: Generate governance audit report

**Success Criteria**:
- Topology viewed
- Policies reviewed
- Compliance audited
- Report generated

---

### JOURNEY-AUD-005: Audit Transformation Pipelines **Deferred**

**Status**: **Deferred** (Phase 5 — transformation pipeline; see [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)).

**Journey ID**: JOURNEY-AUD-005
**Title**: Audit Transformation Pipelines
**Persona**: Auditor
**Goal**: Audit transformation pipeline executions

**Steps**:
1. **NEW**: Navigate to transformation audit dashboard
2. **NEW**: List pipelines
3. **NEW**: Review pipeline executions
4. **NEW**: Audit transformations
5. **NEW**: Generate audit report

**Success Criteria**:
- Pipelines listed
- Executions reviewed
- Transformations audited
- Report generated

---

### JOURNEY-AUD-006: Review Social Feature Activity **NEW**

**Journey ID**: JOURNEY-AUD-006
**Title**: Review Social Feature Activity
**Persona**: Auditor
**Goal**: Audit social feature activity

**Steps**:
1. **NEW**: Navigate to social activity audit dashboard
2. **NEW**: View activity feeds
3. **NEW**: Review ratings and reviews
4. **NEW**: Audit moderation decisions
5. **NEW**: Generate audit report

**Success Criteria**:
- Activities viewed
- Ratings/reviews reviewed
- Moderation audited
- Report generated

---

## Data Scientist Journeys **NEW**

### JOURNEY-DS-001: Use Natural Language Search

**Journey ID**: JOURNEY-DS-001
**Title**: Use Natural Language Search
**Persona**: Data Scientist / ML Engineer
**Goal**: Discover data using natural language queries

**Steps**:
1. Navigate to search
2. Enter natural language query
3. Review query interpretation
4. Execute query
5. Review results
6. Refine query
7. Save query for reuse

**Success Criteria**:
- Query understood
- Results returned
- Query can be refined
- Query saved

---

### JOURNEY-DS-002: Use AI Schema Matching

**Journey ID**: JOURNEY-DS-002
**Title**: Use AI Schema Matching
**Persona**: Data Scientist / ML Engineer
**Goal**: Use AI to match schemas for data integration

**Steps**:
1. Select source and target schemas
2. Trigger AI schema matching
3. Review matching suggestions with confidence scores
4. Accept/reject/modify mappings
5. Save mappings
6. Use mappings for integration

**Success Criteria**:
- Matching completed
- Suggestions provided
- Mappings accepted
- Mappings saved
- Integration uses mappings

---

### JOURNEY-DS-003: Configure ML-Based Anomaly Detection

**Journey ID**: JOURNEY-DS-003
**Title**: Configure ML-Based Anomaly Detection
**Persona**: Data Scientist / ML Engineer
**Goal**: Configure ML models for anomaly detection

**Steps**:
1. Navigate to ML configuration
2. Select anomaly detection model
3. Configure model parameters
4. Train model with historical data
5. Deploy model
6. Monitor model performance
7. Update model based on feedback

**Success Criteria**:
- Model selected
- Parameters configured
- Model trained
- Model deployed
- Performance monitored
- Model updated

---

### JOURNEY-DS-004: Tune Recommendation Engine

**Journey ID**: JOURNEY-DS-004
**Title**: Tune Recommendation Engine
**Persona**: Data Scientist / ML Engineer
**Goal**: Tune recommendation algorithms

**Steps**:
1. Navigate to recommendation configuration
2. Select recommendation algorithms
3. Configure algorithm parameters
4. Test recommendations
5. Monitor recommendation performance
6. Tune parameters based on feedback
7. Deploy tuned recommendations

**Success Criteria**:
- Algorithms selected
- Parameters configured
- Tests pass
- Performance monitored
- Recommendations tuned
- Recommendations deployed

---

### JOURNEY-DS-005: Review Auto-Classification Results

**Journey ID**: JOURNEY-DS-005
**Title**: Review Auto-Classification Results
**Persona**: Data Scientist / ML Engineer
**Goal**: Review and improve auto-classification models

**Steps**:
1. Navigate to classification dashboard
2. Review classification results
3. Analyze confidence scores
4. Identify misclassifications
5. Provide feedback
6. Update classification models
7. Deploy updated models

**Success Criteria**:
- Results reviewed
- Misclassifications identified
- Feedback provided
- Models updated
- Models deployed

---

## Data Analyst Journeys **NEW**

### JOURNEY-DA-001: Create Transformation Pipeline **Deferred**

**Status**: **Deferred** (Phase 5 — transformation pipeline; see [Gap Remediation Plan](../openspec/changes/testreview1/GAP_REMEDIATION_PLAN.md)).

**Journey ID**: JOURNEY-DA-001
**Title**: Create Transformation Pipeline
**Persona**: Data Analyst
**Goal**: Create transformation pipeline for data analysis

**Steps**:
1. Navigate to transformation section
2. Create new pipeline
3. Design pipeline using visual builder
4. Configure transformation nodes
5. Preview transformation results
6. Execute pipeline
7. Review results
8. Export transformed data

**Success Criteria**:
- Pipeline created
- Transformations configured
- Preview generated
- Pipeline executed
- Results reviewed
- Data exported

---

### JOURNEY-DA-002: Wrangle Data Interactively

**Journey ID**: JOURNEY-DA-002
**Title**: Wrangle Data Interactively
**Persona**: Data Analyst
**Goal**: Clean and transform data interactively

**Steps**:
1. Select data asset
2. Navigate to data wrangling
3. Perform column operations (split, merge, rename, type conversion)
4. Perform row operations (filter, sort, deduplicate)
5. Preview wrangling results
6. Save wrangling history
7. Apply wrangling to data

**Success Criteria**:
- Operations performed
- Results previewed
- History saved
- Wrangling applied

---

### JOURNEY-DA-003: Query Virtual Dataset

**Journey ID**: JOURNEY-DA-003
**Title**: Query Virtual Dataset
**Persona**: Data Analyst
**Goal**: Query data across multiple sources

**Steps**:
1. Navigate to virtualization section
2. Select virtual dataset
3. Build query (SQL or visual builder)
4. Execute query
5. Review results
6. Refine query if needed
7. Export results

**Success Criteria**:
- Virtual dataset selected
- Query built
- Query executed
- Results returned
- Results exported

---

### JOURNEY-DA-004: Execute Federated Query

**Journey ID**: JOURNEY-DA-004
**Title**: Execute Federated Query
**Persona**: Data Analyst
**Goal**: Query multiple data sources in one query

**Steps**:
1. Navigate to federation section
2. Select multiple data sources
3. Build federated query
4. Execute query
5. Review aggregated results
6. Export results

**Success Criteria**:
- Sources selected
- Query built
- Query executed
- Results aggregated
- Results exported

---

## Community Manager Journeys **NEW**

**Route reference (Phase 27)**: Communities are at `/communities`; `/social` redirects to `/communities`. Asset ratings, reviews, and Community section are on the asset detail page (`/assets/:id`). See [E2E_FULL_COVERAGE_PLAN.md](../frontend/e2e/E2E_FULL_COVERAGE_PLAN.md).

### JOURNEY-CM-001: Manage Data Community

**Journey ID**: JOURNEY-CM-001
**Title**: Manage Data Community
**Persona**: Community Manager
**Goal**: Create and manage data community

**Steps**:
1. Navigate to communities section
2. Create new community
3. Configure community settings
4. Manage community membership
5. Moderate community discussions
6. Manage community knowledge base
7. Monitor community activity

**Success Criteria**:
- Community created
- Settings configured
- Membership managed
- Discussions moderated
- Knowledge base managed
- Activity monitored

---

### JOURNEY-CM-002: Moderate Reviews and Ratings

**Journey ID**: JOURNEY-CM-002
**Title**: Moderate Reviews and Ratings
**Persona**: Community Manager
**Goal**: Moderate asset reviews and ratings

**Steps**:
1. Navigate to moderation dashboard
2. Review pending reviews
3. Approve/reject reviews
4. Manage review helpfulness voting
5. Handle review disputes
6. Generate moderation reports

**Success Criteria**:
- Reviews reviewed
- Reviews approved/rejected
- Voting managed
- Disputes handled
- Reports generated

---

### JOURNEY-CM-003: Assign Data Stewards

**Journey ID**: JOURNEY-CM-003
**Title**: Assign Data Stewards
**Persona**: Community Manager
**Goal**: Assign data stewards to assets

**Steps**:
1. Navigate to stewardship section
2. Select assets
3. Assign stewards
4. Configure steward permissions
5. Notify stewards
6. Monitor steward activity
7. Generate stewardship reports

**Success Criteria**:
- Stewards assigned
- Permissions configured
- Stewards notified
- Activity monitored
- Reports generated

---

### JOURNEY-CM-004: Manage Activity Feeds

**Journey ID**: JOURNEY-CM-004
**Title**: Manage Activity Feeds
**Persona**: Community Manager
**Goal**: Manage and monitor activity feeds

**Steps**:
1. Navigate to activity feeds
2. Filter activities
3. Search activities
4. Monitor activity trends
5. Configure activity notifications
6. Generate activity reports

**Success Criteria**:
- Activities filtered
- Activities searched
- Trends monitored
- Notifications configured
- Reports generated

---

## Data Mesh Domain Owner Journeys **NEW**

### JOURNEY-DMO-001: Create Data Mesh Domain

**Journey ID**: JOURNEY-DMO-001
**Title**: Create Data Mesh Domain
**Persona**: Data Mesh Domain Owner
**Goal**: Create and configure data mesh domain

**Steps**:
1. Navigate to data mesh section
2. Create new domain
3. Define domain boundaries
4. Assign domain ownership
5. Configure domain infrastructure
6. Set up self-serve capabilities
7. Configure resource quotas
8. Deploy domain

**Success Criteria**:
- Domain created
- Boundaries defined
- Ownership assigned
- Infrastructure configured
- Capabilities set up
- Domain deployed

---

### JOURNEY-DMO-002: Configure Federated Governance

**Journey ID**: JOURNEY-DMO-002
**Title**: Configure Federated Governance
**Persona**: Data Mesh Domain Owner
**Goal**: Configure federated governance for domain

**Steps**:
1. Navigate to governance configuration
2. Define domain-specific policies
3. Configure policy enforcement
4. Set up compliance checking
5. Configure policy violation alerts
6. Test governance
7. Deploy governance

**Success Criteria**:
- Policies defined
- Enforcement configured
- Compliance checking set up
- Alerts configured
- Tests pass
- Governance deployed

---

### JOURNEY-DMO-003: Manage Domain Topology

**Journey ID**: JOURNEY-DMO-003
**Title**: Manage Domain Topology
**Persona**: Data Mesh Domain Owner
**Goal**: Manage data mesh topology

**Steps**:
1. Navigate to topology visualization
2. View domain relationships
3. Manage domain relationships
4. Monitor topology health
5. Update topology as needed
6. Generate topology reports

**Success Criteria**:
- Topology visualized
- Relationships managed
- Health monitored
- Topology updated
- Reports generated

---

### JOURNEY-DMO-004: Transfer Asset Ownership

**Journey ID**: JOURNEY-DMO-004
**Title**: Transfer Asset Ownership
**Persona**: Data Mesh Domain Owner
**Goal**: Transfer asset ownership between domains

**Steps**:
1. Navigate to asset management
2. Select assets to transfer
3. Select target domain
4. Initiate ownership transfer
5. Verify transfer
6. Update domain topology
7. Notify stakeholders

**Success Criteria**:
- Assets selected
- Transfer initiated
- Transfer verified
- Topology updated
- Stakeholders notified

---

### JOURNEY-DMO-005: Monitor Domain Health

**Journey ID**: JOURNEY-DMO-005
**Title**: Monitor Domain Health
**Persona**: Data Mesh Domain Owner
**Goal**: Monitor domain health and performance

**Steps**:
1. Navigate to domain health dashboard
2. View domain metrics
3. Monitor domain performance
4. Review domain compliance
5. Identify issues
6. Address issues
7. Generate health reports

**Success Criteria**:
- Metrics displayed
- Performance monitored
- Compliance reviewed
- Issues identified
- Issues addressed
- Reports generated

---

## Journey Map Matrix

| Journey ID | Title | Persona | Priority | Status | Category | New Feature |
|------------|-------|---------|----------|--------|----------|-------------|
| JOURNEY-AUTH-001 | First-Time Visitor Registers | Visitor, Prospect | High | New | Authentication & Access | **NEW** |
| JOURNEY-AUTH-002 | User Logs In | Visitor (becomes authenticated) | High | MVP | Authentication & Access | **NEW** |
| JOURNEY-AUTH-003 | User Resets Password | Visitor, any registered | Medium | Optional | Authentication & Access | **NEW** |
| JOURNEY-AUTH-004 | Unauthenticated User Accesses Public Resources | Visitor | Medium | MVP | Authentication & Access | **NEW** |
| JOURNEY-AUTH-005 | User Switches Active Tenant | Any with multiple tenants | High | MVP | Authentication & Access | **NEW** |
| JOURNEY-DPO-001 | Onboard New Asset via Data-First Flow | Data Product Owner | High | MVP | Asset Management | Enhanced with AI |
| JOURNEY-DPO-002 | Publish Asset to Marketplace | Data Product Owner | High | MVP | Marketplace | Enhanced with transformation |
| JOURNEY-DPO-007 | Use AI Schema Matching | Data Product Owner | High | New | AI/ML | **NEW** |
| JOURNEY-DPO-008 | Create Transformation Pipeline | Data Product Owner | High | Deferred | Transformation | **Deferred** |
| JOURNEY-DPO-009 | Manage Asset Ratings and Reviews | Data Product Owner | Medium | New | Social | **NEW** |
| JOURNEY-DPO-010 | Publish with Usage-Based Pricing | Data Product Owner | Medium | New | Marketplace | **NEW** |
| JOURNEY-DPO-011 | Assign Data Stewards | Data Product Owner | Medium | New | Social | **NEW** |
| JOURNEY-DPO-012 | Join Data Community | Data Product Owner | Low | New | Social | **NEW** |
| JOURNEY-DPO-013 | Configure Data Mesh Domain | Data Product Owner | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DPO-014 | Monitor Asset Reliability Score | Data Product Owner | Medium | New | Observability | **NEW** |
| JOURNEY-DE-007 | Create Transformation Pipeline | Data Engineer | High | Deferred | Transformation | **Deferred** |
| JOURNEY-DE-008 | Integrate AI Schema Matching | Data Engineer | High | New | AI/ML | **NEW** |
| JOURNEY-DE-009 | Set Up Data Virtualization | Data Engineer | High | New | Virtualization | **NEW** |
| JOURNEY-DE-010 | Configure Connector | Data Engineer | High | New | Integration | **NEW** |
| JOURNEY-DE-011 | Set Up Reverse ETL | Data Engineer | Medium | New | Integration | **NEW** |
| JOURNEY-DE-012 | Create Custom Plugin | Data Engineer | Medium | New | Developer Experience | **NEW** |
| JOURNEY-DE-013 | Configure Data Mesh Domain | Data Engineer | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DC-006 | Use Natural Language Search | Data Consumer | High | New | AI/ML | **NEW** |
| JOURNEY-DC-007 | Create Transformation Pipeline | Data Consumer | High | Deferred | Transformation | **Deferred** |
| JOURNEY-DC-008 | Rate and Review Asset | Data Consumer | Medium | New | Social | **NEW** |
| JOURNEY-DC-009 | Join Data Community | Data Consumer | Low | New | Social | **NEW** |
| JOURNEY-DC-010 | Query Virtual Dataset | Data Consumer | High | New | Virtualization | **NEW** |
| JOURNEY-DC-011 | Purchase with Usage-Based Pricing | Data Consumer | Medium | New | Marketplace | **NEW** |
| JOURNEY-DC-012 | Preview Data Before Purchase | Data Consumer | High | New | Marketplace | **NEW** |
| JOURNEY-DC-013 | Use Asset Recommendations | Data Consumer | Medium | New | AI/ML | **NEW** |
| JOURNEY-DS-001 | Use Natural Language Search | Data Scientist | High | New | AI/ML | **NEW** |
| JOURNEY-DS-002 | Use AI Schema Matching | Data Scientist | High | New | AI/ML | **NEW** |
| JOURNEY-DS-003 | Configure ML Anomaly Detection | Data Scientist | High | New | AI/ML | **NEW** |
| JOURNEY-DS-004 | Tune Recommendation Engine | Data Scientist | Medium | New | AI/ML | **NEW** |
| JOURNEY-DS-005 | Review Auto-Classification | Data Scientist | Medium | New | AI/ML | **NEW** |
| JOURNEY-DA-001 | Create Transformation Pipeline | Data Analyst | High | Deferred | Transformation | **Deferred** |
| JOURNEY-DA-002 | Wrangle Data Interactively | Data Analyst | High | New | Transformation | **NEW** |
| JOURNEY-DA-003 | Query Virtual Dataset | Data Analyst | High | New | Virtualization | **NEW** |
| JOURNEY-DA-004 | Execute Federated Query | Data Analyst | High | New | Virtualization | **NEW** |
| JOURNEY-CM-001 | Manage Data Community | Community Manager | High | New | Social | **NEW** |
| JOURNEY-CM-002 | Moderate Reviews and Ratings | Community Manager | High | New | Social | **NEW** |
| JOURNEY-CM-003 | Assign Data Stewards | Community Manager | Medium | New | Social | **NEW** |
| JOURNEY-CM-004 | Manage Activity Feeds | Community Manager | Medium | New | Social | **NEW** |
| JOURNEY-DMO-001 | Create Data Mesh Domain | Data Mesh Domain Owner | High | New | Data Mesh | **NEW** |
| JOURNEY-DMO-002 | Configure Federated Governance | Data Mesh Domain Owner | High | New | Data Mesh | **NEW** |
| JOURNEY-DMO-003 | Manage Domain Topology | Data Mesh Domain Owner | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DMO-004 | Transfer Asset Ownership | Data Mesh Domain Owner | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DMO-005 | Monitor Domain Health | Data Mesh Domain Owner | Medium | New | Data Mesh | **NEW** |
| JOURNEY-DPO-015 | Create ODPS Product (Product-First Flow) | Data Product Owner | High | New | ODPS | **NEW** |
| JOURNEY-DPO-016 | Link ODPS to ODCS Contract (Technical-First Flow) | Data Product Owner | High | New | ODPS | **NEW** |
| JOURNEY-DPO-017 | Export ODPS Product | Data Product Owner | Medium | New | ODPS | **NEW** |
| JOURNEY-DPO-018 | Edit Dataset and Link to Asset | Data Product Owner, Data Engineer | High | MVP | Datasets | **NEW** |
| JOURNEY-DC-014 | Discover ODPS Products (Semantic Search) | Data Consumer | High | New | ODPS | **NEW** |
| JOURNEY-DC-015 | Purchase ODPS Product (Marketplace) | Data Consumer | High | New | ODPS | **NEW** |
| JOURNEY-DE-014 | Create ODPS via API | Data Engineer | High | New | ODPS | **NEW** |
| JOURNEY-DE-015 | Upload File via Files Page | Data Engineer, Data Product Owner | High | MVP | Files | **NEW** |
| JOURNEY-PA-010 | Manage ODPS Products | Platform Admin | Medium | New | ODPS | **NEW** |
| JOURNEY-EXPORT-001 | Create and Run Scheduled Export | Data Engineer, Data Product Owner | High | New | Scheduled Export | **NEW** |
| JOURNEY-EXPORT-002 | Monitor and Troubleshoot Export Runs | Data Engineer, Data Product Owner | High | New | Scheduled Export | **NEW** |

**Total**: 98 journeys (4 authentication + 37 original + 57 new)

---

**Last Updated**: 2026-03-22
**Version**: 2.4.2 (Task 6.4: Deferred journeys consolidated in [Deferred Journeys (Transformation Pipeline)](#deferred-journeys-transformation-pipeline); backlog item [BACKLOG_TRANSFORMATION_PIPELINE.md](BACKLOG_TRANSFORMATION_PIPELINE.md); Task 28.6.4: Social route reference /communities, asset Community section)

---

## Related Documentation

- **[Transformation Pipeline Backlog](BACKLOG_TRANSFORMATION_PIPELINE.md)** - Backlog item for transformation pipeline; links to deferred journeys (JOURNEY-DPO-008, DE-007, DC-007, AUD-005, DA-001, DEV-006)
- **[Use Cases](USE_CASES.md)** - Use cases including Authentication & Access (UC-AUTH-001–005)
- **[User Personas](USER_PERSONAS.md)** - Personas including Visitor/Prospect
- **[Features](FEATURES.md)** - Feature documentation and Capabilities ↔ Use Cases matrix
- **[Test Traceability](TEST_TRACEABILITY.md)** - Comprehensive test traceability matrix mapping features, use cases, and journeys to tests
- **[Marketplace User Journeys](MARKETPLACE_USER_JOURNEYS.md)** - Detailed user journey maps for marketplace integration operations (7 journeys)
- **[Marketplace Use Cases](MARKETPLACE_USE_CASES.md)** - Complete use cases documentation for marketplace integration
- **[Marketplace Integration User Guide](MARKETPLACE_INTEGRATION_USER_GUIDE.md)** - User guide for marketplace integrations
- **[BaaS Platform CLI Usage Guide](../cli/docs/BAAS_USAGE.md)** - BaaS Platform CLI commands and workflows
- **[BaaS Platform SDK Usage Guide](../sdk/python/docs/BAAS_USAGE.md)** - BaaS Platform SDK APIs and examples
- **[ODH Integration CLI Usage Guide](../cli/docs/ODH_USAGE.md)** - ODH Integration CLI commands and workflows
- **[ODH Integration SDK Usage Guide](../sdk/python/docs/ODH_USAGE.md)** - ODH Integration SDK APIs and examples
- **[Architecture](ARCHITECTURE.md)** - BaaS Platform and ODH Integration architecture documentation


---

# User Personas

**Last Updated**: 2026-03-22
**Version**: 2.2.0

---

## Overview

The Data Interoperability Hub serves **13 personas**: **Visitor / Prospect** (unauthenticated, non-registered) and **12 role-based personas** (8 original + 4 new), each with distinct goals, responsibilities, and technical capabilities. This document provides comprehensive profiles for all personas, their role mappings, and how they interact with the platform. **Authentication & Access** use cases (UC-AUTH-001–004) and journeys (JOURNEY-AUTH-001–004) apply to the Visitor persona before a user has a role.

**Key Principles:**
- **Multi-tenant isolation**: Each persona operates within tenant boundaries (except Platform Admin)
- **Role-based access control**: Permissions are granted through roles, not direct user attributes
- **Audit trails**: All actions are logged for compliance and debugging
- **API-first**: All personas can access functionality via APIs, with UI as a convenience layer

---

## Table of Contents

0. [Persona 0: Visitor / Prospect](#persona-0-visitor--prospect) **NEW**
1. [Persona 1: Data Product Owner](#persona-1-data-product-owner)
2. [Persona 2: Data Engineer / Contract Author](#persona-2-data-engineer--contract-author)
3. [Persona 3: Compliance & Privacy Officer](#persona-3-compliance--privacy-officer)
4. [Persona 4: Data Consumer / Buyer](#persona-4-data-consumer--buyer)
5. [Persona 5: Tenant Admin](#persona-5-tenant-admin)
6. [Persona 6: Platform Admin / Marketplace Operator](#persona-6-platform-admin--marketplace-operator)
7. [Persona 7: External Developer / Integrator](#persona-7-external-developer--integrator)
8. [Persona 8: Auditor](#persona-8-auditor)
9. [Persona 9: Data Scientist / ML Engineer](#persona-9-data-scientist--ml-engineer) **NEW**
10. [Persona 10: Data Analyst](#persona-10-data-analyst) **NEW**
11. [Persona 11: Community Manager / Data Steward](#persona-11-community-manager--data-steward) **NEW**
12. [Persona 12: Data Mesh Domain Owner](#persona-12-data-mesh-domain-owner) **NEW**
13. [Role Mapping Matrix](#role-mapping-matrix)
14. [Access Control Summary](#access-control-summary)

---

## Persona 0: Visitor / Prospect

**Aliases**: Unauthenticated user, prospect, anonymous visitor
**Typical Role Mapping**: None (no role until authenticated and assigned)
**Seniority**: N/A
**Technical Level**: Any – may use browser or API

### Summary

A **Visitor** is someone who has not yet authenticated or registered. They may land on a public landing page, documentation, or health endpoint, or be redirected to the login page. Once they register (when self-service is enabled) or log in, they assume a role-based persona (e.g. Data Consumer, Data Product Owner). Use cases **UC-AUTH-001** (User Registers), **UC-AUTH-002** (User Logs In), **UC-AUTH-003** (User Resets Password), and **UC-AUTH-004** (Unauthenticated User Accesses Public Resources) and journeys **JOURNEY-AUTH-001** through **JOURNEY-AUTH-004** apply to this persona.

### Goals

- Access public resources (health, API docs, optional landing)
- Register an account (when self-service registration is enabled)
- Log in to access protected resources
- Reset password (when feature is available)

### Key Responsibilities / Tasks

- Navigate to login or registration page (or call auth APIs)
- Enter credentials or registration data
- Access only public/unauthenticated endpoints (e.g. health, docs)

### Technical Capabilities

- **UI Access**: Login page, optional registration and landing; no protected UI until authenticated
- **API Access**: Auth endpoints (login, register, password reset); public health/docs endpoints only
- **SDK/CLI Access**: Same as API – auth and public endpoints only

### Pain Points

- Registration may be disabled (admin-only onboarding)
- No access to catalog or marketplace until authenticated

### Success Metrics

- Successful login or registration
- Access to protected resources after authentication

### Related Documentation

- [Use Cases – Authentication & Access](USE_CASES.md#authentication--access-use-cases) (UC-AUTH-001–004)
- [User Journeys – Visitor / Authentication](USER_JOURNEYS.md#visitor--authentication-journeys) (JOURNEY-AUTH-001–004)

---

## Persona 1: Data Product Owner

**Aliases**: Data Steward, Domain Data Owner, Data Product Manager
**Typical Role Mapping**: `DATA_PROVIDER` (sometimes `TENANT_ADMIN`)
**Seniority**: Mid to senior
**Technical Level**: Medium – understands data and schemas; not deeply into infrastructure/CLI

### Summary

Owns one or more datasets inside an organization and wants to publish them as **data products** in the hub, either for internal reuse (within the tenant) or for sale in the **marketplace**. Responsible for the meaning, quality, and lifecycle of the asset, but usually collaborates with data engineers for technical implementation.

They work primarily through the **web UI**, relying on the platform to enforce data contract standards, data quality, and compliance gates.

### Goals

- Turn internal datasets into **well-described, trustworthy and compliant data products**
- Publish assets to the **tenant catalog** and optionally to the **cross-tenant marketplace** ("on the shelf")
- **Publish assets to external data marketplaces** (Snowflake, AWS Data Exchange, Azure, GCP, etc.) via marketplace integration
- **Manage marketplace connections** to external platforms for asset distribution
- Keep contracts, documentation, and metadata **up to date across versions** (while the platform guarantees they stay `VALID`)
- Be confident that mandatory **data-quality** and **compliance** checks ran, and that everything is backed by audit logs

### Key Responsibilities / Tasks

#### Onboarding Flows

1. **Data First Flow**
   - Upload data file via browser (up to size limits) or via SDK/CLI (for larger files)
   - System infers schema and extracts sample
   - **NEW**: AI schema matching suggests field mappings
   - **NEW**: Auto-classification detects PII and categorizes data
   - System runs compliance validation (mandatory gate)
   - System runs basic data quality checks (`intake_basic`)
   - **NEW**: ML-based anomaly detection identifies quality issues
   - If checks fail: receive reports, correct/remediate data externally, retry
   - If checks pass: edit and refine contract in UI
   - Trigger DataContract CLI validation (lint + validate)
   - After successful validation: contract + dataset registered in catalog
   - Contract and asset mapped into semantic layer

2. **Contract First Flow**
   - Upload data contract file (ODCS or DataContract.com format)
   - System runs DataContract CLI validation
   - If errors: fix and re-run validation
   - After validation: upload data file
   - System validates data matches contract schema
   - System runs compliance and DQ checks
   - If checks pass: asset registered in catalog

3. **Contract Only Flow**
   - Upload contract without data (for external data sources)
   - System validates contract
   - Contract registered in catalog
   - Asset can reference external data source

#### Asset Management

- **Update Assets**: Update metadata, contracts, documentation
- **Version Management**: Create new versions, track version history
- **Quality Monitoring**: Monitor data quality scores, receive alerts
- **Compliance Monitoring**: Monitor compliance status, address violations
- **Marketplace Publishing**: Publish assets to marketplace with pricing models
- **NEW**: **Transformation Pipelines**: Create and manage transformation pipelines for assets
- **NEW**: **Social Features**: Respond to ratings and reviews, manage asset reputation
- **NEW**: **Data Mesh**: Configure domain ownership, manage domain-scoped assets

#### ODPS (Open Data Product Standard) Management

- **Create ODPS Products**: Create ODPS products using Product-First flow (with embedded ODCS)
  - Upload ODPS documents (JSON or YAML)
  - System automatically extracts ODCS from `product.contract.spec`
  - System creates both ODPS and ODCS contracts with bidirectional linking
- **Link ODPS to ODCS**: Link existing ODCS contracts to ODPS products (Technical-First flow)
  - Select existing ODCS contract
  - Create or select ODPS contract
  - System validates linking compatibility
  - System establishes bidirectional links
- **Export ODPS Products**: Export ODPS contracts in ODPS format (JSON or YAML)
  - Export includes linked ODCS contract in `product.contract.spec`
  - Support for multiple ODPS versions (4.1, 4.0)
- **Manage ODPS Pricing**: Configure pricing plans, access methods, and payment gateways
  - Define pricing plans (free, basic, premium, enterprise)
  - Configure access methods (API, download, streaming)
  - Set up payment gateways (Stripe, PayPal, etc.)
- **ODPS Marketplace Integration**: Publish ODPS products to marketplace
  - Configure marketplace listing with ODPS metadata
  - Set up pricing and access controls
  - Monitor marketplace performance

#### Marketplace Integration (External Marketplaces)

- **Create Marketplace Connections**: Set up connections to external marketplaces (Snowflake, AWS, Azure, GCP, Databricks, CKAN, etc.)
- **Test Connections**: Verify marketplace connection credentials and connectivity
- **PUSH Sync Operations**: Sync assets to external marketplaces for broader distribution
  - Select assets to publish
  - Configure sync options (metadata only, full sync, etc.)
  - Monitor sync job progress
  - Review sync results and errors
- **Manage Sync Jobs**: View, monitor, and cancel marketplace sync jobs
- **View Mappings**: Track mappings between Hub assets and external marketplace listings
- **Update Marketplace Listings**: Keep marketplace listings synchronized with Hub assets
- **Marketplace-Specific Configuration**: Configure marketplace-specific settings per platform

### Technical Capabilities

- **UI Access**: Full access to asset management UI
- **API Access**: Full access to asset APIs
- **SDK Access**: Can use SDKs for automation
- **CLI Access**: Limited (prefers UI)

### Pain Points

- Understanding technical contract details
- Waiting for quality/compliance checks
- Keeping contracts in sync with data changes
- Managing asset versions

### Success Metrics

- Asset onboarding time
- Contract validation success rate
- Quality score improvements
- Marketplace sales (if applicable)
- **External marketplace sync success rate**
- **Number of external marketplace connections**
- **Assets published to external marketplaces**
- **Scheduled exports configured and running successfully**

### Related Journeys

- [JOURNEY-DPO-001](USER_JOURNEYS.md#journey-dpo-001-onboard-new-asset-via-data-first-flow): Onboard New Asset via Data-First Flow
- [JOURNEY-DPO-002](USER_JOURNEYS.md#journey-dpo-002-publish-asset-to-marketplace): Publish Asset to Marketplace
- [JOURNEY-EXPORT-001](USER_JOURNEYS.md#journey-export-001-create-and-run-scheduled-export): Create and Run Scheduled Export **NEW**
- [JOURNEY-EXPORT-002](USER_JOURNEYS.md#journey-export-002-monitor-and-troubleshoot-export-runs): Monitor and Troubleshoot Export Runs **NEW**

### Related Use Cases

- [UC-AM-001](USE_CASES.md#uc-am-001-create-asset-via-data-first-flow): Create Asset via Data-First Flow
- [UC-DPO-002](USE_CASES.md#uc-dpo-002-publish-asset-to-marketplace): Publish Asset to Marketplace
- [UC-EXPORT-001](USE_CASES.md#uc-export-001-schedule-recurring-export): Schedule Recurring Export **NEW**
- [UC-EXPORT-002](USE_CASES.md#uc-export-002-configure-export-destination): Configure Export Destination **NEW**
- [UC-EXPORT-003](USE_CASES.md#uc-export-003-monitor-export-runs): Monitor Export Runs **NEW**
- [UC-EXPORT-004](USE_CASES.md#uc-export-004-manual-trigger-of-scheduled-export): Manual Trigger of Scheduled Export **NEW**

---

## Persona 2: Data Engineer / Contract Author

**Aliases**: Data Engineer, Contract Developer, Technical Data Owner
**Typical Role Mapping**: `DATA_PROVIDER`
**Seniority**: Mid to senior
**Technical Level**: High – comfortable with APIs, SDKs, CLI, infrastructure

### Summary

Technical implementer who creates contracts, sets up data pipelines, integrates external systems, and automates data operations. Works primarily through **APIs, SDKs, and CLI**, but also uses UI for complex operations.

### Goals

- Automate asset onboarding and management
- Integrate hub with external systems (CI/CD, data sources, BI tools)
- Create and validate contracts programmatically
- Set up scheduled ingestions
- Set up scheduled exports
- **NEW**: Create and manage transformation pipelines
- **NEW**: Integrate AI/ML features into workflows
- **NEW**: Set up data virtualization and federation
- Set up scheduled exports

### Key Responsibilities / Tasks

#### Contract Management

- Create contracts programmatically (API/SDK/CLI)
- Validate contracts in CI/CD pipelines
- Manage contract versions
- **NEW**: Use AI schema matching to generate contracts
- **NEW**: Integrate auto-classification into contract creation

#### ODPS (Open Data Product Standard) Management

- **Create ODPS via API**: Programmatically create ODPS products using REST API, GraphQL, or SDKs
  - REST API: `POST /api/v1/contracts/products/`
  - GraphQL: `mutation { createODPS(input: {...}) }`
  - Python SDK: `client.contracts.create_odps(...)`
  - JavaScript SDK: `client.contracts.createODPS(...)`
  - CLI: `datahub contracts create-odps ...`
- **ODPS Workflow Integration**: Integrate ODPS creation into CI/CD pipelines
  - Automate ODPS product creation from templates
  - Validate ODPS documents in build pipelines
  - Monitor workflow execution status
- **ODPS Linking Automation**: Automate linking of ODPS to ODCS contracts
  - Link ODPS products to existing ODCS contracts
  - Validate linking compatibility programmatically
  - Manage bidirectional links via API
- **ODPS Export Automation**: Export ODPS products programmatically
  - Export ODPS contracts in JSON or YAML format
  - Include linked ODCS contracts in exports
  - Version-specific exports (4.1, 4.0)

#### Integration

- Set up scheduled ingestions
- Set up scheduled exports
- Integrate with external data sources
- Set up CI/CD integration
- **NEW**: Create custom connectors
- **NEW**: Set up reverse ETL
- **NEW**: Integrate BI tools

#### Pipeline Management

- **NEW**: Create transformation pipelines
- **NEW**: Execute and monitor pipelines
- **NEW**: Integrate pipelines with asset lifecycle
- **NEW**: Set up data virtualization

### Technical Capabilities

- **UI Access**: Full access (for complex operations)
- **API Access**: Full access to all APIs
- **SDK Access**: Full access to all SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- API documentation completeness
- Integration complexity
- Error handling
- Performance optimization

### Success Metrics

- Integration success rate
- Automation coverage
- Pipeline execution success rate
- Integration time

---

## Persona 3: Compliance & Privacy Officer

**Aliases**: Compliance Officer, Privacy Officer, Governance Officer
**Typical Role Mapping**: `AUDITOR` (read-only) or `TENANT_ADMIN` (with compliance permissions)
**Seniority**: Mid to senior
**Technical Level**: Low to medium – understands compliance requirements, not deeply technical

### Summary

Ensures data assets comply with regulations (GDPR, HIPAA, SOX, LGPD, CCPA) and organizational policies. Monitors compliance status, reviews reports, and manages access requests. Works primarily through **web UI dashboards and reports**.

### Goals

- Ensure all data assets comply with regulations
- Monitor compliance status across all assets
- Review and approve access requests
- Generate compliance reports for audits
- Identify and remediate compliance violations
- **NEW**: Configure automated compliance enforcement
- **NEW**: Manage GDPR right to be forgotten workflows
- **NEW**: Track and manage consent

### Key Responsibilities / Tasks

#### Compliance Monitoring

- View compliance status dashboard
- Generate compliance reports (GDPR, HIPAA, SOX, etc.)
- Receive alerts for compliance violations
- Monitor compliance trends over time
- **NEW**: Review AI auto-classification results for compliance
- **NEW**: Configure automated compliance rules

#### Access Management

- Review and approve/deny access requests
- Conduct periodic access certifications
- Review access logs for audit purposes
- Configure data masking rules based on classification
- **NEW**: Manage consent tracking and workflows

#### Policy Management

- Configure automatic data classification rules
- Configure data retention policies
- Configure fine-grained access control policies
- Configure compliance scanning rules
- **NEW**: Configure automated retention policies
- **NEW**: Set up GDPR deletion workflows

#### Audit & Reporting

- Review audit logs for all data operations
- Generate scheduled compliance reports
- Review and track compliance violations
- Track remediation of compliance issues
- **NEW**: Generate GDPR compliance reports
- **NEW**: Generate consent tracking reports

### Technical Capabilities

- **UI Access**: Full access to compliance dashboards and reports
- **API Access**: Limited (read-only for reports and logs)
- **SDK Access**: Limited (for report generation automation)
- **CLI Access**: None (prefers UI)

### Pain Points

- Understanding technical implementation details
- Navigating complex compliance reports
- Keeping up with changing regulations
- Proving compliance during audits

### Success Metrics

- Compliance pass rate
- Time to identify violations
- Access request processing time
- Audit report generation time

---

## Persona 4: Data Consumer / Buyer

**Aliases**: Data Consumer, Data Buyer, Data Analyst, Business User
**Typical Role Mapping**: `DATA_CONSUMER`
**Seniority**: Junior to senior
**Technical Level**: Low to medium – understands data needs, not deeply technical

### Summary

Discovers, evaluates, and accesses data assets for analysis, reporting, or integration. May purchase assets from marketplace or request access to internal assets. Works primarily through **web UI catalog and marketplace**.

### Goals

- Discover relevant data assets quickly
- Evaluate data quality and compliance before use
- Access data assets easily (download, API, or direct connection)
- Understand data lineage and dependencies
- Purchase data assets from marketplace (if applicable)
- **Discover and import assets from external data marketplaces** (Snowflake, AWS, Azure, GCP, etc.)
- **Access federated assets** imported from external marketplaces
- **NEW**: Use natural language search to find data
- **NEW**: Create transformation pipelines for data
- **NEW**: Rate and review assets
- **NEW**: Join data communities
- **NEW**: Query virtual datasets

### Key Responsibilities / Tasks

#### Discovery

- Browse tenant catalog for internal assets
- Browse marketplace for external assets
- **Browse external data marketplaces** via marketplace integration (Snowflake, AWS, Azure, GCP, etc.)
- Search assets by name, description, tags, domain
- **NEW**: Use natural language search ("show me customer data from last quarter")
- Filter assets by type, quality, compliance, domain
- Use semantic search for concept-based discovery
- **NEW**: Use asset recommendations
- **ODPS Product Discovery**: Discover ODPS products using semantic search
  - Search by product name/description (multilingual support)
  - Search by pricing plan
  - Search by access method
  - Search by product strategy
  - Filter by product-contract linking (ODPS ↔ ODCS)

#### Evaluation

- Review asset metadata and documentation
- Review data quality scores and reports
- Review compliance status
- **NEW**: Preview data before purchase
- **NEW**: Review ratings and reviews
- **NEW**: View trust signals (quality SLAs, badges)

#### Access

- Request access to internal assets
- Purchase assets from marketplace
- Download purchased data
- Access data via API
- **NEW**: Execute transformation pipelines
- **NEW**: Query virtual datasets
- **ODPS Product Purchase**: Purchase ODPS products from marketplace
  - View ODPS product details (pricing plans, access methods, payment gateways)
  - Select pricing plan (free, basic, premium, enterprise)
  - Select access method (API, download, streaming)
  - Process payment via configured payment gateway (Stripe, PayPal, etc.)
  - Receive entitlement with access credentials
  - Access ODPS product data via selected access method

#### Marketplace Integration (External Marketplaces)

- **PULL Sync Operations**: Discover and import assets from external marketplaces
  - Browse available listings in external marketplaces
  - Filter and search marketplace listings
  - Select listings to import
  - Configure import options (metadata only, full data, selective resources)
  - Monitor sync job progress
  - Review imported federated assets
- **Access Federated Assets**: Use assets imported from external marketplaces
  - Query federated assets with dual contracts (ODPS + ODCS)
  - Access marketplace resources
  - View marketplace metadata
- **View Mappings**: Track relationships between Hub assets and external marketplace listings

#### Collaboration

- **NEW**: Rate and review assets
- **NEW**: Comment on assets
- **NEW**: Join data communities
- **NEW**: Participate in discussions

### Technical Capabilities

- **UI Access**: Full access to catalog and marketplace
- **API Access**: Limited (for accessing purchased data)
- **SDK Access**: Limited (for data access)
- **CLI Access**: None (prefers UI)

### Pain Points

- Finding relevant assets
- Understanding data quality
- Approval delays
- **NEW**: Understanding transformation pipelines
- **NEW**: Using natural language search effectively

### Success Metrics

- Discovery time
- Purchase completion rate
- User satisfaction
- **NEW**: Transformation pipeline usage
- **NEW**: Social engagement (ratings, reviews)
- **External marketplace discovery success rate**
- **Federated assets imported from external marketplaces**
- **Usage of federated assets**

---

## Persona 5: Tenant Admin

**Aliases**: Organization Admin, Tenant Administrator
**Typical Role Mapping**: `TENANT_ADMIN`
**Seniority**: Mid to senior
**Technical Level**: Medium – understands administration, not deeply technical

### Summary

Manages tenant-level configuration, users, and settings. Ensures tenant compliance with platform policies. Works primarily through **web UI administration panels**.

### Goals

- Manage tenant users and roles
- Configure tenant settings
- Monitor tenant usage and costs
- Ensure tenant compliance
- **NEW**: Configure data mesh domains
- **NEW**: Set up advanced governance
- **NEW**: Monitor cost tracking
- **NEW**: Configure integration ecosystem

### Key Responsibilities / Tasks

#### User Management

- Onboard new users
- Assign roles and permissions
- Manage user access
- Deactivate users

#### Tenant Configuration

- Configure tenant settings
- Set up tenant policies
- Configure tenant branding
- **NEW**: Configure data mesh domains
- **NEW**: Set up federated governance

#### Monitoring

- Monitor tenant usage
- Monitor tenant costs
- **NEW**: Monitor cost tracking and optimization
- Generate tenant reports

#### Integration

- **NEW**: Install and configure connectors
- **NEW**: Set up BI tool integrations
- **NEW**: Configure reverse ETL

### Technical Capabilities

- **UI Access**: Full access to admin panels
- **API Access**: Full access to admin APIs
- **SDK Access**: Limited (for automation)
- **CLI Access**: Limited (for automation)

### Pain Points

- Managing large numbers of users
- Understanding platform policies
- Cost management
- **NEW**: Data mesh configuration complexity

### Success Metrics

- User onboarding time
- Tenant compliance rate
- Cost optimization
- **NEW**: Data mesh adoption

---

## Persona 6: Platform Admin / Marketplace Operator

**Aliases**: Platform Administrator, Marketplace Operator
**Typical Role Mapping**: `PLATFORM_ADMIN`
**Seniority**: Senior
**Technical Level**: High – understands platform infrastructure and operations

### Summary

Manages platform-wide configuration, monitors platform health, and operates the marketplace. Works through **web UI administration panels and APIs**.

### Goals

- Onboard new tenants
- Monitor platform health
- Manage marketplace operations (internal marketplace)
- **Manage external marketplace integrations** across all tenants
- **Monitor marketplace connection health** and sync job performance
- Configure platform settings
- **NEW**: Manage connector marketplace
- **NEW**: Configure advanced marketplace features
- **NEW**: Monitor data mesh topology
- **NEW**: Configure advanced observability

### Key Responsibilities / Tasks

#### Tenant Management

- Onboard new tenants
- Configure tenant settings
- Monitor tenant health
- Manage tenant billing

#### Marketplace Operations

- Manage marketplace listings (internal marketplace)
- Process marketplace orders (internal marketplace)
- Monitor marketplace health (internal marketplace)
- **NEW**: Manage connector marketplace
- **NEW**: Configure usage-based pricing
- **NEW**: Set up trust signals
- **NEW**: Configure data previews

#### External Marketplace Integration Management

- **Monitor Marketplace Connections**: Oversee all tenant marketplace connections
  - View connection status across all tenants
  - Monitor connection health and test results
  - Identify and resolve connection issues
  - Review connection usage statistics
- **Monitor Sync Jobs**: Track marketplace sync operations across platform
  - View all sync jobs (PUSH and PULL) across tenants
  - Monitor sync job success rates and performance
  - Identify and resolve sync job failures
  - Generate sync job reports and analytics
- **Marketplace Platform Management**: Manage supported marketplace platforms
  - Configure marketplace platform settings
  - Manage marketplace connector availability
  - Monitor marketplace API rate limits and quotas
  - Coordinate with marketplace platform providers
- **Troubleshooting and Support**: Provide support for marketplace integration issues
  - Investigate connection failures
  - Resolve sync job errors
  - Provide guidance on marketplace-specific requirements
  - Coordinate with marketplace platform support teams

#### Platform Monitoring

- Monitor platform health
- Monitor platform performance
- **NEW**: Monitor data mesh topology
- **NEW**: Monitor reliability scores
- **NEW**: Track platform costs
- **NEW**: Set up predictive alerts

#### Platform Configuration

- Configure platform settings
- Manage platform policies
- **NEW**: Configure advanced observability
- **NEW**: Manage plugin marketplace

### Technical Capabilities

- **UI Access**: Full access to all admin panels
- **API Access**: Full access to all APIs
- **SDK Access**: Full access to all SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- Managing platform scale
- Monitoring complexity
- Marketplace operations
- **NEW**: Data mesh topology management

### Success Metrics

- Platform uptime
- Marketplace transaction volume (internal marketplace)
- Tenant satisfaction
- **NEW**: Data mesh adoption
- **NEW**: Connector marketplace usage
- **External marketplace connection success rate**
- **Marketplace sync job success rate**
- **Number of active marketplace connections**
- **Assets synced to/from external marketplaces**

---

## Persona 7: External Developer / Integrator

**Aliases**: Developer, Integrator, API User
**Typical Role Mapping**: `DATA_CONSUMER` or `DATA_PROVIDER` (depending on use case)
**Seniority**: Junior to senior
**Technical Level**: High – comfortable with APIs, SDKs, CLI, programming

### Summary

Builds integrations between the hub and external systems. Uses APIs, SDKs, and CLI to automate operations. Works primarily through **APIs, SDKs, and CLI**.

### Goals

- Integrate hub with external systems
- Automate data operations
- Build custom applications
- **Integrate with external data marketplaces** via marketplace integration APIs
- **Automate marketplace sync operations** (PUSH and PULL)
- **Build custom marketplace connectors** for unsupported platforms
- **NEW**: Use natural language search API
- **NEW**: Integrate transformation pipeline API
- **NEW**: Build custom connectors
- **NEW**: Use plugin system
- **NEW**: Access developer portal

### Key Responsibilities / Tasks

#### Integration Development

- Review API documentation
- Obtain API credentials
- Initialize SDK/client
- Implement integrations
- **NEW**: Use natural language search API
- **NEW**: Integrate transformation pipeline API
- **NEW**: Build custom connectors

#### Marketplace Integration Development

- **Marketplace Connection Management**: Create, update, test, and delete marketplace connections via API
  - Use `/api/v1/integrations/marketplace/connections/` endpoints
  - Configure marketplace-specific connection parameters
  - Test connection credentials programmatically
- **Sync Job Automation**: Automate marketplace sync operations
  - Create PUSH sync jobs to publish assets to external marketplaces
  - Create PULL sync jobs to import assets from external marketplaces
  - Monitor sync job progress via API
  - Handle sync job errors and retries
  - Cancel sync jobs programmatically
- **Mapping Management**: Track and manage asset-to-marketplace mappings
  - Query mappings between Hub assets and marketplace listings
  - Monitor sync status via mappings
- **Custom Connector Development**: Build connectors for unsupported marketplaces
  - Implement `MarketplaceConnector` interface
  - Register custom connectors via factory pattern
  - Test and validate custom connectors

#### Plugin Development

- **NEW**: Browse plugin marketplace
- **NEW**: Install plugins
- **NEW**: Create custom plugins
- **NEW**: Publish plugins to marketplace

#### Developer Resources

- **NEW**: Access developer portal
- **NEW**: Use sandbox environment
- **NEW**: Review code examples
- **NEW**: Follow tutorials

### Technical Capabilities

- **UI Access**: Limited (for testing)
- **API Access**: Full access to all APIs
- **SDK Access**: Full access to all SDKs (Python, JavaScript, R, Go)
- **CLI Access**: Full access to CLI tool

### Pain Points

- API documentation completeness
- Authentication complexity
- Error handling
- **NEW**: Plugin development complexity

### Success Metrics

- Integration success rate
- Integration time
- Developer satisfaction
- **NEW**: Plugin adoption
- **Marketplace integration API usage**
- **Custom connector development success**
- **Marketplace sync automation coverage**

---

## Persona 8: Auditor

**Aliases**: Internal Auditor, External Auditor, Compliance Auditor
**Typical Role Mapping**: `AUDITOR` (read-only)
**Seniority**: Mid to senior
**Technical Level**: Low to medium – understands audit requirements, not deeply technical

### Summary

Reviews system audit logs, generates audit reports, and verifies compliance. Works primarily through **web UI audit dashboards and reports**.

### Goals

- Review audit logs for compliance
- Generate audit reports
- Verify compliance with regulations
- Export audit data for external analysis
- **NEW**: Review data mesh governance
- **NEW**: Audit transformation pipelines
- **NEW**: Review social feature activity

### Key Responsibilities / Tasks

#### Audit Review

- Review audit logs
- Generate audit reports
- Export audit data
- **NEW**: Review data mesh governance
- **NEW**: Audit transformation pipelines
- **NEW**: Review social feature activity

#### Compliance Verification

- Verify compliance with regulations
- Review access logs
- Review policy compliance
- **NEW**: Verify data mesh domain compliance

### Technical Capabilities

- **UI Access**: Full access to audit dashboards
- **API Access**: Read-only access to audit APIs
- **SDK Access**: None (prefers UI)
- **CLI Access**: None (prefers UI)

### Pain Points

- Navigating audit logs
- Generating comprehensive reports
- Understanding technical details
- **NEW**: Understanding data mesh governance

### Success Metrics

- Audit report generation time
- Compliance verification rate
- Audit coverage

---

## Persona 9: Data Scientist / ML Engineer **NEW**

**Aliases**: ML Engineer, Data Scientist, AI Engineer
**Typical Role Mapping**: `DATA_PROVIDER` or `DATA_CONSUMER` (depending on use case)
**Seniority**: Mid to senior
**Technical Level**: High – expert in ML/AI, data science, programming

### Summary

Uses AI/ML features to build models, analyze data patterns, and leverage intelligent features. Works through **APIs, SDKs, and UI** for different tasks.

### Goals

- Use natural language search to discover data
- Leverage AI schema matching for data integration
- Use ML-based anomaly detection for data quality
- Configure recommendation engines
- Train and deploy ML models
- Analyze data patterns using AI/ML

### Key Responsibilities / Tasks

#### Natural Language Search

- Use natural language queries to discover data
- Review query interpretations
- Refine queries based on results
- Save and reuse queries

#### Schema Matching

- Use AI schema matching for data integration
- Review matching suggestions with confidence scores
- Accept/reject/modify mappings
- Integrate schema matching into workflows

#### ML Model Management

- Train ML models for anomaly detection
- Deploy ML models for quality checks
- Monitor model performance
- Update models based on feedback

#### Recommendation Engine

- Configure recommendation algorithms
- Tune recommendation parameters
- Monitor recommendation performance
- Analyze recommendation feedback

#### Auto-Classification

- Review auto-classification results
- Validate PII detection
- Improve classification models
- Configure classification rules

### Technical Capabilities

- **UI Access**: Full access to AI/ML features
- **API Access**: Full access to AI/ML APIs
- **SDK Access**: Full access to all SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- ML model training time
- Model accuracy
- Integration complexity
- Cost management (LLM API costs)

### Success Metrics

- Model accuracy
- Query success rate
- Schema matching accuracy
- Recommendation relevance

---

## Persona 10: Data Analyst **NEW**

**Aliases**: Business Analyst, Data Analyst, Analytics User
**Typical Role Mapping**: `DATA_CONSUMER`
**Seniority**: Junior to senior
**Technical Level**: Medium – understands data analysis, SQL, not deeply technical

### Summary

Uses transformation pipelines, data wrangling, and virtualization to analyze data. Works primarily through **web UI** for visual tools, **APIs** for programmatic access.

### Goals

- Create transformation pipelines for data analysis
- Wrangle data interactively
- Query virtual datasets
- Execute federated queries
- Analyze data across sources

### Key Responsibilities / Tasks

#### Transformation Pipelines

- Create transformation pipelines using visual builder
- Configure transformation nodes
- Execute pipelines
- Monitor pipeline execution
- Review transformation results

#### Data Wrangling

- Clean data interactively
- Perform column operations (split, merge, rename, type conversion)
- Perform row operations (filter, sort, deduplicate)
- Preview wrangling results
- Save wrangling history

#### Virtualization

- Create virtual datasets
- Query virtual datasets
- Execute federated queries
- Monitor query performance
- Cache query results

#### Analysis

- Analyze transformed data
- Export analysis results
- Share analysis with team
- **NEW**: Use natural language search for data discovery

### Technical Capabilities

- **UI Access**: Full access to transformation and virtualization UI
- **API Access**: Full access to transformation and virtualization APIs
- **SDK Access**: Limited (for automation)
- **CLI Access**: Limited (for automation)

### Pain Points

- Pipeline complexity
- Query performance
- Data quality issues
- Understanding virtualization

### Success Metrics

- Pipeline execution success rate
- Query performance
- Analysis completion time
- User satisfaction

---

## Persona 11: Community Manager / Data Steward **NEW**

**Aliases**: Community Manager, Data Steward, Social Manager
**Typical Role Mapping**: `DATA_PROVIDER` or `TENANT_ADMIN`
**Seniority**: Mid to senior
**Technical Level**: Low to medium – understands community management, not deeply technical

### Summary

Manages social features, communities, data stewardship, and collaboration. Works primarily through **web UI** for community management.

### Goals

- Manage data communities
- Moderate reviews and ratings
- Assign data stewards
- Manage activity feeds
- Foster collaboration

### Key Responsibilities / Tasks

#### Community Management

- Create and manage data communities
- Manage community membership
- Moderate community discussions
- Manage community knowledge base

#### Review Moderation

- Moderate asset reviews
- Approve/reject reviews
- Manage review helpfulness voting
- Handle review disputes

#### Data Stewardship

- Assign data stewards to assets
- Manage steward responsibilities
- Monitor steward activity
- Generate stewardship reports

#### Activity Management

- Monitor activity feeds
- Filter and search activities
- Manage activity notifications
- Generate activity reports

### Technical Capabilities

- **UI Access**: Full access to social and community features
- **API Access**: Limited (for automation)
- **SDK Access**: None (prefers UI)
- **CLI Access**: None (prefers UI)

### Pain Points

- Managing large communities
- Review moderation workload
- Activity feed management
- Steward assignment

### Success Metrics

- Community engagement
- Review moderation time
- Steward assignment coverage
- Activity feed usage

---

## Persona 12: Data Mesh Domain Owner **NEW**

**Aliases**: Domain Owner, Mesh Domain Manager
**Typical Role Mapping**: `DATA_PROVIDER` or `TENANT_ADMIN`
**Seniority**: Senior
**Technical Level**: Medium to high – understands data mesh architecture, governance

### Summary

Manages data mesh domains, federated governance, and domain topology. Works through **web UI** for domain management and **APIs** for automation.

### Goals

- Create and manage data mesh domains
- Configure federated governance
- Manage domain topology
- Assign domain ownership
- Monitor domain health

### Key Responsibilities / Tasks

#### Domain Management

- Create data mesh domains
- Define domain boundaries
- Assign domain ownership
- Manage domain-scoped assets
- Monitor domain health

#### Federated Governance

- Configure domain-specific policies
- Apply federated governance rules
- Monitor policy compliance
- Generate governance reports

#### Topology Management

- Visualize mesh topology
- Manage domain relationships
- Monitor topology health
- Update topology as needed

#### Domain Operations

- Transfer asset ownership between domains
- Migrate assets to domains
- Configure domain infrastructure
- Monitor domain costs

### Technical Capabilities

- **UI Access**: Full access to data mesh UI
- **API Access**: Full access to data mesh APIs
- **SDK Access**: Full access to SDKs
- **CLI Access**: Full access to CLI tool

### Pain Points

- Domain boundary definition
- Federated governance complexity
- Topology management
- Asset ownership transfer

### Success Metrics

- Domain creation time
- Governance compliance rate
- Topology health
- Asset ownership accuracy

---

## Role Mapping Matrix

| Persona | Primary Role | Secondary Roles | Access Level |
|---------|-------------|-----------------|--------------|
| Visitor / Prospect | None | - | Public only (auth, health, docs); no role until authenticated |
| Data Product Owner | `DATA_PROVIDER` | `TENANT_ADMIN` | Full (tenant-scoped) |
| Data Engineer | `DATA_PROVIDER` | - | Full (tenant-scoped) |
| Compliance Officer | `AUDITOR` | `TENANT_ADMIN` | Read-only or Full (tenant-scoped) |
| Data Consumer | `DATA_CONSUMER` | - | Limited (consumer access) |
| Tenant Admin | `TENANT_ADMIN` | - | Full (tenant-scoped) |
| Platform Admin | `PLATFORM_ADMIN` | - | Full (platform-wide) |
| External Developer | `DATA_CONSUMER` or `DATA_PROVIDER` | - | Varies by use case |
| Auditor | `AUDITOR` | - | Read-only |
| Data Scientist / ML Engineer | `DATA_PROVIDER` or `DATA_CONSUMER` | - | Varies by use case |
| Data Analyst | `DATA_CONSUMER` | - | Limited (consumer access) |
| Community Manager | `DATA_PROVIDER` or `TENANT_ADMIN` | - | Full (tenant-scoped) |
| Data Mesh Domain Owner | `DATA_PROVIDER` or `TENANT_ADMIN` | - | Full (domain-scoped) |

---

## Access Control Summary

**Visitor / Prospect** (unauthenticated): Access is limited to authentication flows (login, register, password reset) and public resources (health, API docs, optional landing). No role is assigned until the user is authenticated; thereafter they are covered by one of the 12 role-based personas below. See [Use Cases – Authentication & Access](USE_CASES.md#authentication--access-use-cases) and [User Journeys – Visitor / Authentication](USER_JOURNEYS.md#visitor--authentication-journeys).

### UI Access

- **Full Access**: Data Product Owner, Data Engineer, Tenant Admin, Platform Admin, Data Scientist, Data Analyst, Community Manager, Data Mesh Domain Owner
- **Limited Access**: Data Consumer, External Developer
- **Read-Only Access**: Compliance Officer, Auditor
- **Public / Unauthenticated Only**: Visitor (login, register, password reset, health, docs)

### API Access

- **Full Access**: Data Engineer, Platform Admin, External Developer, Data Scientist, Data Analyst, Data Mesh Domain Owner
- **Limited Access**: Data Product Owner, Tenant Admin, Community Manager
- **Read-Only Access**: Compliance Officer, Auditor, Data Consumer

### SDK Access

- **Full Access**: Data Engineer, Platform Admin, External Developer, Data Scientist, Data Analyst, Data Mesh Domain Owner
- **Limited Access**: Data Product Owner, Tenant Admin
- **No Access**: Compliance Officer, Auditor, Data Consumer, Community Manager

### CLI Access

- **Full Access**: Data Engineer, Platform Admin, External Developer, Data Scientist, Data Analyst, Data Mesh Domain Owner
- **Limited Access**: Data Product Owner, Tenant Admin
- **No Access**: Compliance Officer, Auditor, Data Consumer, Community Manager

---

**Last Updated**: 2026-03-22
**Version**: 2.3.0 (Added Scheduled Export capabilities to Data Engineer and Data Product Owner personas; linked to JOURNEY-EXPORT-001–002 and UC-EXPORT-001–004)


---

# Billing and Subscription Management

**Last Updated**: 2026-03-22

This document describes the billing and subscription system, including plans, limits, Stripe integration, webhooks, and usage metering.

---

## Overview

The platform uses Stripe for subscription management and billing. Each tenant can subscribe to a plan (FREE, PRO, or ENTERPRISE) with specific resource limits.

### Key Components

- **TenantPlan**: Defines subscription plans with limits
- **Subscription**: Tracks tenant subscriptions to plans (Stripe integration)
- **UsageRecord**: Records usage metrics for billing
- **Invoice**: Tracks invoices from Stripe

---

## Plans and Limits

### Default Plans

Three default plans are seeded via `python manage.py seed_default_plans`:

#### FREE Plan
- **max_assets**: 10
- **max_datasets**: 20
- **max_api_calls_per_month**: 10,000
- **max_scheduled_ingestions**: 5
- **max_scheduled_runs_per_month**: 50
- **max_scheduled_exports**: 5
- **max_export_runs_per_month**: 20
- **max_storage_gb**: 1

#### PRO Plan
- **max_assets**: 100
- **max_datasets**: 500
- **max_api_calls_per_month**: 100,000
- **max_scheduled_ingestions**: 50
- **max_scheduled_runs_per_month**: 1,000
- **max_scheduled_exports**: 50
- **max_export_runs_per_month**: 500
- **max_storage_gb**: 100

#### ENTERPRISE Plan
- All limits: **Unlimited** (None in limits_json)

### Plan Limits Enforcement

Plan limits are enforced via `PlanLimitService.check_limit()`:

- **Asset creation**: Checks `max_assets` limit
- **Dataset creation**: Checks `max_datasets` limit
- **Scheduled ingestion creation**: Checks `max_scheduled_ingestions` limit
- **Scheduled export creation**: Checks `max_scheduled_exports` limit

When a limit is exceeded, a `403 Forbidden` response is returned with:
```json
{
  "error": "Plan limit exceeded for max_assets",
  "code": "plan_limit_exceeded",
  "details": {
    "limit_key": "max_assets",
    "current": 10,
    "max": 10,
    "requested_delta": 1,
    "new_usage": 11,
    "plan_slug": "free",
    "plan_tier": "FREE"
  }
}
```

---

## Stripe Integration

### Configuration

Set the following environment variables:

```bash
STRIPE_SECRET_KEY=sk_test_...  # Stripe secret key (use test key for development)
STRIPE_WEBHOOK_SECRET=whsec_...  # Webhook signing secret
```

### Creating Subscriptions

#### 1. Create Stripe Customer

```python
from hub.apps.billing.services import SubscriptionService
from hub.apps.tenants.models import Tenant

service = SubscriptionService()
result = service.create_customer(tenant=tenant, email="user@example.com")
stripe_customer_id = result['stripe_customer_id']
```

#### 2. Create Subscription

```python
from hub.apps.tenants.models import TenantPlan

plan = TenantPlan.objects.get(slug='pro')
subscription = service.create_subscription(
    tenant=tenant,
    plan=plan,
    payment_method_id='pm_...',  # Optional: Stripe payment method ID
    trial_days=14  # Optional: Trial period in days
)
```

### Subscription Status

Subscriptions can have the following statuses:

- **ACTIVE**: Subscription is active and paid
- **TRIAL**: Subscription is in trial period
- **PAST_DUE**: Payment failed, subscription is past due
- **CANCELED**: Subscription has been canceled
- **UNPAID**: Subscription is unpaid
- **INCOMPLETE**: Subscription setup incomplete
- **INCOMPLETE_EXPIRED**: Subscription setup expired

### Subscription Lifecycle

1. **Trial**: New subscriptions start with TRIAL status (if trial_days > 0)
2. **Active**: After trial or payment, status becomes ACTIVE
3. **Past Due**: If payment fails, status becomes PAST_DUE
4. **Suspended**: After 3 failed payments, tenant is SUSPENDED (read-only)
5. **Canceled**: User cancels subscription (can be immediate or at period end)

---

## Stripe Webhooks

### Webhook Endpoint

**POST** `/api/v1/billing/webhooks/stripe/`

### Supported Events

#### customer.subscription.updated
- Updates subscription status and period dates
- Suspends tenant if status is PAST_DUE

#### customer.subscription.deleted
- Marks subscription as CANCELED
- Sets canceled_at timestamp

#### invoice.payment_failed
- Creates or updates invoice record
- After 3 failed payments, suspends tenant

#### invoice.paid
- Marks invoice as paid
- Reactivates tenant if was suspended

### Webhook Signature Verification

All webhooks are verified using Stripe's signature verification:

```python
event = stripe.Webhook.construct_event(
    payload, sig_header, STRIPE_WEBHOOK_SECRET
)
```

Invalid signatures return `400 Bad Request`.

### Idempotency

Webhook handlers are idempotent:
- Subscription updates: Updates existing subscription (no duplicates)
- Invoice creation: Creates invoice if doesn't exist, updates if exists

---

## Usage Metering

### Recording Usage

Usage is recorded via `BillingService.record_usage()`:

```python
from hub.apps.billing.services import BillingService
from decimal import Decimal

service = BillingService()
usage_record = service.record_usage(
    tenant_id=tenant_id,
    metric_key='api_calls',
    quantity=Decimal('100'),
    period_start=month_start,
    period_end=month_end
)
```

### Syncing to Stripe

Usage records can be synced to Stripe metering:

```python
service.sync_usage_to_stripe(usage_record_id=str(usage_record.id))
```

**Note**: Stripe metering requires subscription items with metered pricing. This is typically configured in Stripe Dashboard.

### Usage Metrics

Common metric keys:
- `api_calls`: API call count
- `storage_gb`: Storage usage in GB
- `compute_hours`: Compute hours used
- `scheduled_runs`: Scheduled ingestion/export runs

---

## API Endpoints

### Get Current Subscription

**GET** `/api/v1/billing/subscription/current/`

Returns current subscription for tenant (latest by created_at).

**Response**:
```json
{
  "id": "uuid",
  "tenant": "tenant-uuid",
  "plan": "plan-uuid",
  "plan_name": "Pro Plan",
  "plan_slug": "pro",
  "plan_tier": "PRO",
  "status": "ACTIVE",
  "stripe_subscription_id": "sub_...",
  "stripe_customer_id": "cus_...",
  "current_period_start": "2026-02-01T00:00:00Z",
  "current_period_end": "2026-03-01T00:00:00Z",
  "trial_end": null,
  "canceled_at": null,
  "cancel_at_period_end": false
}
```

### Change Subscription Plan (Phase 17)

**POST** `/api/v1/billing/subscription/current/change-plan/`

Change the tenant's subscription plan. Requires TENANT_ADMIN or PLATFORM_ADMIN.

**Request**:
```json
{
  "plan_slug": "pro"
}
```

**Response**: Updated subscription (same as Get Current Subscription).

**Errors**:
- 400: Plan not found, already on this plan, or tenant context required
- 403: User lacks TENANT_ADMIN or Platform Admin
- 404: No subscription found

### List Available Plans (Phase 17)

**GET** `/api/v1/billing/plans/`

Returns list of active plans available for subscription change. Used by tenant admins when changing plan.

### List Invoices

**GET** `/api/v1/billing/invoices/`

Returns list of invoices for tenant.

**Response**:
```json
{
  "count": 5,
  "results": [
    {
      "id": "uuid",
      "tenant": "tenant-uuid",
      "subscription": "subscription-uuid",
      "stripe_invoice_id": "in_...",
      "amount_due": "99.00",
      "amount_paid": "99.00",
      "currency": "usd",
      "status": "paid",
      "invoice_pdf_url": "https://...",
      "hosted_invoice_url": "https://...",
      "period_start": "2026-02-01T00:00:00Z",
      "period_end": "2026-03-01T00:00:00Z",
      "due_date": "2026-03-01T00:00:00Z",
      "paid_at": "2026-02-15T10:30:00Z"
    }
  ]
}
```

### Get Invoice Detail

**GET** `/api/v1/billing/invoices/{id}/`

Returns invoice detail.

### Download Invoice (Phase 17)

**GET** `/api/v1/billing/invoices/{id}/download/`

Redirects (302) to invoice PDF URL or hosted invoice page when available. Returns 404 when neither URL is present.

---

## Subscription Status Enforcement

### Middleware

`TenantSuspensionMiddleware` (enhanced in Phase 25.2.4) blocks write operations when:

1. **Tenant is SUSPENDED**: All write operations blocked
2. **Subscription is PAST_DUE or UNPAID**: Write operations blocked

**Response** (403 Forbidden):
```json
{
  "error": "Subscription is inactive. Write operations are not allowed.",
  "code": "subscription_inactive",
  "details": {
    "subscription_id": "uuid",
    "status": "PAST_DUE"
  }
}
```

### Grace Period

- **Read operations**: Always allowed (GET, HEAD, OPTIONS)
- **Write operations**: Blocked when subscription inactive or tenant suspended
- **Grace period**: Not currently implemented (all writes blocked immediately)

---

## Failed Payments and Manual Override

### Automatic Suspension

After **3 failed payment attempts**, tenant is automatically suspended:
- Tenant status set to `SUSPENDED`
- All write operations blocked
- Read operations still allowed

### Manual Override

Platform admins can manually override subscription status:

```python
from hub.apps.billing.models import Subscription, SubscriptionStatus

subscription = Subscription.objects.get(id=subscription_id)
subscription.status = SubscriptionStatus.ACTIVE
subscription.save()

# Reactivate tenant
tenant = subscription.tenant
tenant.status = TenantStatus.ACTIVE
tenant.save()
```

### Runbook

See `runbooks/RB-BILLING-001.md` (to be created) for:
- Handling failed payments
- Manual subscription reactivation
- Tenant suspension override
- Stripe webhook troubleshooting

---

## Testing

### Stripe Test Mode

All tests use Stripe test mode:

```python
# Set in test settings
STRIPE_SECRET_KEY = 'sk_test_...'
STRIPE_WEBHOOK_SECRET = 'whsec_test_...'
```

### Test Cards

Use Stripe test cards:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Requires authentication**: `4000 0025 0000 3155`

### Mocking

**No mocks allowed** per Phase 25 requirements:
- Tests use real Stripe test mode
- Real database transactions
- Real service layer calls

---

---

## Rate Limit Overrides (Phase 25.7.2)

### Per-Tenant Rate Limits

Rate limits can be overridden per tenant via `TenantConfig.rate_limits`:

```python
tenant_config.rate_limits = {
    'assets': {
        'burst_per_10s': 20,
        'sustained_per_min': 100,
        'daily_cap': 10000
    },
    'datasets': {
        'burst_per_10s': 10,
        'sustained_per_min': 50,
        'daily_cap': 5000
    }
}
```

### Per-Plan Rate Limits

Rate limits can also be defined in plan `limits_json`:

```json
{
  "max_assets": 100,
  "max_datasets": 500,
  "rate_limits": {
    "assets": {
      "burst_per_10s": 20,
      "sustained_per_min": 100
    }
  }
}
```

### Override Priority

1. **TenantConfig.rate_limits**: Highest priority (tenant-specific override)
2. **Plan limits_json.rate_limits**: Medium priority (plan default)
3. **Platform defaults**: Lowest priority (fallback)

### Configuration

Rate limits are configured via:

- **TenantConfig API**: `PATCH /api/v1/tenants/{id}/config/` with `rate_limits` field
- **Plan limits_json**: Set during plan creation or update
- **Platform defaults**: Defined in `hub.apps.tenants.validators.get_platform_defaults()`

---

## Related Documentation

- `docs/DATA_RESIDENCY.md` - Data residency and regional considerations
- `docs/TENANT_ISOLATION.md` - Tenant isolation and multi-tenancy (includes plan limits and suspension)
- `docs/ONBOARDING.md` - Self-service tenant onboarding

---

# Virtualization — ODBC Sources

This document describes how to configure and use ODBC sources for virtual datasets in the Data Interoperability Hub.

## Overview

ODBC (Open Database Connectivity) sources allow virtual datasets to query any database that exposes an ODBC driver. The Hub supports two configuration modes:

1. **Connection string** — Full ODBC connection string (e.g. `DRIVER={...};SERVER=...;DATABASE=...`)
2. **Host + Database** — Individual fields (host, port, database, username, password, driver)

## Configuration

### Connection String Mode

Use when you have a pre-built ODBC connection string or DSN:

```json
{
  "type": "odbc",
  "connection_string": "DRIVER={PostgreSQL Unicode};SERVER=localhost;PORT=5432;DATABASE=hub;UID=hub;PWD=hub"
}
```

Or with DSN:

```json
{
  "type": "odbc",
  "connection_string": "DSN=MyPostgresDSN;PWD=secret"
}
```

### Host + Database Mode

Use when configuring via individual fields (common for PostgreSQL, MySQL, SQL Server):

```json
{
  "type": "odbc",
  "host": "localhost",
  "port": 5432,
  "database": "hub",
  "username": "hub",
  "password": "hub",
  "driver": "PostgreSQL Unicode"
}
```

| Field      | Required | Description |
|-----------|----------|--------------|
| `host`    | Yes*     | Database host (*required when not using `connection_string`) |
| `port`    | No       | Port (default: 5432) |
| `database`| Yes*     | Database name (*required when not using `connection_string`) |
| `username`| No       | Username |
| `password`| No       | Password |
| `driver`  | No       | ODBC driver name (default: `PostgreSQL Unicode` for PostgreSQL) |

## Driver Requirements

### API / Docker Image

The Hub API image includes:

- `unixodbc` — ODBC driver manager
- `unixodbc-dev` — Development headers
- `odbc-postgresql` (psqlodbc) — PostgreSQL ODBC driver

For other databases (MySQL, SQL Server, etc.), install the appropriate driver in your deployment.

### PostgreSQL (psqlodbc)

Driver name is typically one of:

- `PostgreSQL Unicode`
- `PostgreSQL ANSI`
- `PostgreSQL` (depending on installation)

List available drivers:

```bash
odbcinst -q -d
```

### Local Development

For running integration tests or local API with ODBC:

```bash
# Ubuntu/Debian
sudo apt-get install -y unixodbc unixodbc-dev odbc-postgresql

# Verify
odbcinst -q -d
```

## Frontend UI

The virtual dataset create/edit UI provides:

- **Source type dropdown** — Select "ODBC"
- **Connection string** — Single text input for full connection string
- **Host + Database** — Driver, host, port, database, username, password

Toggle between modes via radio buttons. At least one mode must be filled.

## Security

- Credentials in `connection_string`, `password`, and `pwd` are masked in logs and audit events.
- Store secrets in environment variables or a secrets manager; avoid hardcoding in config.

## Troubleshooting

See [RUNBOOKS.md — ODBC Virtualization Issues](RUNBOOKS.md#odbc-virtualization-issues) for common failures and fixes.

## References

- Backend: `hub/apps/virtualization/services.py` — `_execute_odbc_query`
- Business rules: `hub/apps/virtualization/business_rules.py` — ODBC validation
- Integration tests: `hub/apps/virtualization/tests/test_real_source_integration.py` — `test_odbc_execute_against_hub_postgresql`, `test_odbc_execute_connection_string_mode`

---

## Phase 117+ Feature Additions

### Compliance Service Overhaul

- **25-jurisdiction support**: GDPR, HIPAA, SOX, LGPD, CCPA + 20 additional regional frameworks
- **Async scanning**: Compliance runs execute asynchronously via job queue, with `PENDING→RUNNING→SUCCEEDED/FAILED` status tracking
- **Risk scoring**: Automated risk level calculation (LOW/MEDIUM/HIGH/CRITICAL) based on detected data categories and applicable regulations
- **Regulation mapping**: JSON-based mapping of detected categories to specific regulatory requirements

### Scheduled Ingestion Enhancements

- **Cost tracking**: Per-run cost attribution via `BillingService.record_usage()` for `ingestion_runs` metric
- **Dead letter queue (DLQ)**: Failed records routed to DLQ for manual retry/investigation
- **Monitoring**: Prometheus metrics for run duration, row counts, failure rates

### Scheduled Export Lifecycle

- **Status management**: ACTIVE/PAUSED/ERROR states with automatic error recovery
- **Run history**: Detailed per-run tracking with items_processed, items_failed, error_message
- **Manual trigger**: On-demand export execution via `POST /{id}/trigger/`

### Webhook Hardening

- **SSRF guard**: URL validation blocks private/internal IPs (10.x, 172.16-31.x, 192.168.x, localhost)
- **Async delivery**: Webhook payloads delivered via background job queue with retry
- **HMAC signing**: Request signing with tenant-specific secrets for payload verification

### Marketplace & Governance Enhancements (Phase 117)

- **M1 Order→Entitlement lifecycle**: Order approval creates Entitlement, granting cross-tenant access
- **M3 Cross-tenant enforcement**: `require_entitlement()` check in dataset download, file download, virtual dataset query
- **G3 Access expiration**: `expires_at` field on AccessRequest (default 90 days), `revoke_expired_access` management command
- **G4 KYC expiration**: `kyc_expires_at` field on Tenant, `refresh_kyc_status` command, `can_publish()` blocks expired KYC
- **G5 Classification propagation**: Highest classification (PII/PHI/PCI) auto-propagates dataset→model→asset via `propagate_classification()`
- **ML-2 Inference usage metering**: `BillingService.record_usage()` for `ml_inference_requests` and `ml_inference_compute_ms`

---

## Phase 117+ Use Cases

### ML Use Cases

| ID | Use Case | Description |
|----|----------|-------------|
| UC-ML-001 | Train Model on Hub Dataset | Link dataset → submit training job → monitor → deploy |
| UC-ML-002 | Deploy Trained Model | TRAINED→DEPLOYED with deployment_id, serve predictions |
| UC-ML-003 | Version Switch | Atomic undeploy v1 + deploy v2 via `deploy_version()` |
| UC-ML-004 | Rollback Deployment | Revert to previous version via `rollback_deployment()` |
| UC-ML-005 | Publish Model to Marketplace | Create listing with ML metadata (model_type, version, status) |
| UC-ML-006 | Model Lineage Tracking | Automatic dataset→model→asset edge creation on link |

### Transformation Use Cases

| ID | Use Case | Description |
|----|----------|-------------|
| UC-TF-001 | Create Pipeline | Define node-based DAG with operations (filter, map, join, aggregate) |
| UC-TF-002 | Validate Pipeline | Check DAG connectivity, node configs, input/output compatibility |
| UC-TF-003 | Preview Results | Execute partial pipeline on sample data before full run |
| UC-TF-004 | Execute Pipeline | Submit full pipeline run with progress tracking |
| UC-TF-005 | Monitor Runs | Track run status, view errors, cancel in-progress runs |

### B2B2C Use Cases

| ID | Use Case | Description |
|----|----------|-------------|
| UC-B2B-001 | API Monetization | Tenant exposes APIs via BaaS, tracks per-key usage and billing |
| UC-B2B-002 | Marketplace Listing | Publish asset with pricing (FREE/AUTO_APPROVE/REQUEST_APPROVAL) |
| UC-B2B-003 | Cross-Tenant Access | Consumer requests access → approval → entitlement → download |
| UC-B2B-004 | Usage-Based Billing | Metered API calls, storage, inference requests per subscription tier |
| UC-B2B-005 | White-Label Portal | Custom-branded developer portal via BaaS SDK documentation |

---

## Phase 117+ User Journeys

### JOURNEY-MLE-001: Train → Deploy → Monetize

1. **Data Scientist** links training dataset to model (`link_model_to_dataset`)
2. Submits training job via ODH Training Operator
3. Monitors training progress (`watch` command / status polling)
4. Deploys trained model (`deploy_model` → DEPLOYED)
5. Publishes model to marketplace (`publish_model_to_marketplace`)
6. Consumers discover and request access via marketplace listing
7. Inference requests metered via `BillingService.record_usage()`

### JOURNEY-DE-001: Ingest → Transform → Publish

1. **Data Engineer** creates scheduled ingestion (S3/GCS/HTTP source)
2. Data ingested on schedule, DLQ captures failures
3. Creates transformation pipeline (filter → clean → aggregate)
4. Validates and previews pipeline on sample data
5. Executes full pipeline run, monitors progress
6. Output dataset versioned with semantic version
7. Publishes via marketplace or shares via access request

### JOURNEY-TA-B2B-001: API Monetization

1. **Tenant Admin** enables BaaS for tenant
2. Creates API keys with scoped permissions (`ml:read`, `datasets:read`)
3. Configures usage tiers and rate limits per plan
4. Consumers generate API keys via developer portal
5. Usage tracked per-key with `ml_inference_requests`, `api_calls` metrics
6. Monthly usage synced to Stripe via `sync_usage_to_stripe`
7. Invoices generated automatically based on plan pricing

---

## Billing & Subscription System (Phase 117 Detail)

### Plan Limits (20+ Keys)

| Limit Key | Description | Free | Pro | Enterprise |
|-----------|-------------|------|-----|------------|
| `max_assets` | Maximum assets per tenant | 10 | 100 | Unlimited |
| `max_contracts` | Maximum contracts | 5 | 50 | Unlimited |
| `max_datasets` | Maximum datasets | 20 | 200 | Unlimited |
| `max_files` | Maximum files | 50 | 500 | Unlimited |
| `max_api_calls_per_month` | Monthly API call limit | 10,000 | 100,000 | Unlimited |
| `max_scheduled_runs_per_month` | Scheduled ingestion/export runs | 10 | 100 | Unlimited |
| `max_file_size_bytes` | Maximum file upload size | 100MB | 1GB | 10GB |
| `max_ml_models` | Maximum ML models | 2 | 20 | Unlimited |
| `max_ml_training_jobs_per_month` | Monthly training jobs | 5 | 50 | Unlimited |
| `max_ml_inference_requests_per_month` | Monthly inference requests | 1,000 | 50,000 | Unlimited |
| `max_ml_deployed_models` | Concurrent deployed models | 1 | 5 | 20 |
| `max_virtual_datasets` | Virtual datasets | 5 | 50 | Unlimited |
| `max_transformation_pipelines` | Transformation pipelines | 3 | 30 | Unlimited |
| `max_marketplace_listings` | Marketplace listings | 2 | 20 | Unlimited |
| `max_webhook_subscriptions` | Webhook subscriptions | 5 | 50 | Unlimited |
| `max_access_requests_per_month` | Access requests | 10 | 100 | Unlimited |
| `max_retention_policies` | Retention policies | 5 | 50 | Unlimited |
| `max_compliance_runs_per_month` | Compliance scan runs | 5 | 50 | Unlimited |
| `max_dq_runs_per_month` | Data quality runs | 10 | 100 | Unlimited |
| `ml_training_timeout` | Training job timeout (seconds) | 3600 | 7200 | 14400 |

### Subscription Status Transitions

```
ACTIVE → PAST_DUE → CANCELLED
ACTIVE → CANCELLED (immediate)
TRIALING → ACTIVE (payment confirmed)
TRIALING → CANCELLED (trial expired)
```

### Billing Subsystems

- **SubscriptionStatusMiddleware**: Fail-closed (503) on DB outage for mutations; read ops continue (B1)
- **Downgrade validation**: `DOWNGRADE_LIMIT_EXCEEDED` error if current usage exceeds new plan limits (B2)
- **Refund processing**: Admin-only `POST /billing/refunds/` with amount validation (B3)
- **Usage sync**: `sync_usage_to_stripe` periodic task syncs UsageRecord → Stripe metered billing
- **Reconciliation**: `reconcile_stripe` command validates local state matches Stripe (B5)
- **Circuit breaker**: StripeCircuitBreaker (5 failures/60s → open 30s) prevents cascading failures (B6)
- **ML add-on plans**: PlanCategory BASE/ML_AI for separate ML subscription tiers
- **Webhook handler**: 10 Stripe event types (invoice.paid, subscription.updated, charge.refunded, etc.)
- **Idempotency**: StripeWebhookEvent deduplication prevents double-processing
- **Cleanup**: Webhook events retained 90 days, usage records 24 months

### P3: BaaS SDK Download Links

The developer portal provides SDK download links for each supported language:

- **Python SDK**: `GET /api/v1/baas/docs/sdks/python/` — pip install instructions + package URL
- **JavaScript SDK**: `GET /api/v1/baas/docs/sdks/javascript/` — npm install instructions + package URL
- **OpenAPI Schema**: `GET /api/v1/baas/openapi-schema/` — Full API spec for code generation

### P4: Customer Identity & Per-Key Billing

BaaS API keys support customer identity for per-key usage tracking and billing:

| Field | Type | Description |
|-------|------|-------------|
| `customer_id` | string | External customer identifier (maps to Stripe customer) |
| `customer_email` | string | Customer email for invoicing |
| `customer_name` | string | Display name |
| `pricing_tier` | enum | FREE / PRO / ENTERPRISE |

Per-key billing reports available via `GET /api/v1/baas/usage/?group_by=api_key`.
