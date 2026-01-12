# Features Documentation

Complete documentation of all features and capabilities in the Data Interoperability Hub.

## Table of Contents

1. [Contracts](#contracts)
2. [Assets](#assets)
3. [Datasets](#datasets)
4. [Data Quality](#data-quality)
5. [Compliance](#compliance)
6. [Marketplace](#marketplace)
7. [Governance](#governance)
8. [Search](#search)
9. [Observability](#observability)
10. [Workflows](#workflows)
11. [Lineage](#lineage)
12. [Versioning](#versioning)

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

### API Endpoints

- `GET /api/v1/marketplace/listings/` - List marketplace listings
- `POST /api/v1/marketplace/listings/` - Create listing
- `GET /api/v1/marketplace/listings/{id}/` - Get listing
- `POST /api/v1/marketplace/orders/` - Create order
- `GET /api/v1/marketplace/orders/{id}/` - Get order

### Documentation

- [API Endpoints Reference](API_ENDPOINTS_REFERENCE.md#marketplace)

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

### Key Features

- **Data Observability**: Monitor data health and freshness
- **Freshness Monitoring**: Track data update frequency
- **Lineage Tracking**: Track data lineage
- **SLA Monitoring**: Monitor data SLAs

### API Endpoints

- `GET /api/v1/observability/metrics/` - Get observability metrics
- `GET /api/v1/observability/freshness/` - Get freshness metrics
- `GET /api/v1/observability/lineage/` - Get lineage information

### Documentation

- [Data Observability](DATA_OBSERVABILITY.md)

---

## Workflows

Workflow orchestration for complex business processes.

### Key Features

- **Workflow Engine**: Execute workflows
- **Workflow Registry**: Register and discover workflows
- **Workflow State Management**: Manage workflow state
- **Workflow Versioning**: Version workflows

### Documentation

- [Workflow State Schema](WORKFLOW_STATE_SCHEMA.md)
- [Orchestration Documentation](../hub/apps/orchestration/README.md)

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

Version management for contracts, datasets, and workflows.

### Key Features

- **Version Management**: Manage versions of resources
- **Version Comparison**: Compare versions
- **Version Impact Analysis**: Analyze impact of version changes
- **Version Rollback**: Rollback to previous versions

### Documentation

- [Semantic Versioning](SEMANTIC_VERSIONING.md) (deprecated - see deprecated-doc)
- [Version Impact Analysis](VERSION_IMPACT_ANALYSIS.md) (deprecated - see deprecated-doc)

---

## Related Documentation

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [Architecture](ARCHITECTURE.md) - System architecture
- [User Journey Mapping](USER_JOURNEY_MAPPING.md) - User journeys and personas

