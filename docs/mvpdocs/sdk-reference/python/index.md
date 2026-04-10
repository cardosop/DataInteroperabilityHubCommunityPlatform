# Python SDK Reference

The Meshant Python SDK provides typed, ergonomic access to every Meshant API
from Python 3.10+.

## Installation

```bash
pip install datahub-interoperability
```

Or with optional extras:

```bash
pip install "datahub-interoperability[pandas]"   # DataFrame helpers
pip install "datahub-interoperability[async]"     # async/await support
```

## Quick Start

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="msh_live_...", base_url="https://meshant-internal.example.com")
assets = client.assets.list(page_size=10)
```

## Client Initialization

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `None` | API key (prefix `msh_live_` or `msh_test_`) |
| `base_url` | `str` | `https://meshant-internal.example.com` | Base URL of the Meshant API |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `tenant_id` | `str` | `None` | Override tenant context |

## SDK Classes

| Class | Attribute | Description |
|-------|-----------|-------------|
| [AssetsAPI](assets-api.md) | `client.assets` | Data asset lifecycle |
| [AuditAPI](audit-api.md) | `client.audit` | Audit event logging and export |
| [AuthAPI](auth-api.md) | `client.auth` | Authentication and token management |
| [BillingAPI](billing-api.md) | `client.billing` | Subscriptions, invoices, usage metering |
| [ComplianceAPI](compliance-api.md) | `client.compliance` | Compliance scanning and PII detection |
| [ContractsAPI](contracts-api.md) | `client.contracts` | Data contract authoring and validation |
| [DatasetsAPI](datasets-api.md) | `client.datasets` | Dataset creation and schema inference |
| [DQAPI](dq-api.md) | `client.dq` | Data quality checks and profiling |
| [FilesAPI](files-api.md) | `client.files` | File upload, download, listing |
| [GDPRAPI](gdpr-api.md) | `client.gdpr` | GDPR data subject rights |
| [GovernanceAPI](governance-api.md) | `client.governance` | Policy management and retention rules |
| [JobsAPI](jobs-api.md) | `client.jobs` | Background job tracking |
| [LineageAPI](lineage-api.md) | `client.lineage` | Data lineage graph traversal |
| [MarketplaceListingsAPI](marketplace-listings-api.md) | `client.marketplace_listings` | Marketplace product listings and orders |
| [ObservabilityAPI](observability-api.md) | `client.observability` | Platform metrics and alerting |
| [SearchAPI](search-api.md) | `client.search` | Full-text search and faceted filtering |
| [SemanticAPI](semantic-api.md) | `client.semantic` | Semantic URI resolution and SPARQL |
| [TenantsAPI](tenants-api.md) | `client.tenants` | Multi-tenancy management |
| [UsersAPI](users-api.md) | `client.users` | User CRUD and role assignment |
| [VersioningAPI](versioning-api.md) | `client.versioning` | Resource versioning and history |
| [WebhooksAPI](webhooks-api.md) | `client.webhooks` | Webhook registration and delivery logs |
| [WorkflowsAPI](workflows-api.md) | `client.workflows` | Orchestration workflow management |

## Error Handling

All SDK methods raise typed exceptions that map to HTTP error codes.
See [Error Codes](../../reference/error-codes.md) for the full list.

```python
from datahub_interoperability import DataHubClient, MVPGatedFeatureError

client = DataHubClient(api_key="msh_live_...")
try:
    result = client.assets.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- [API Reference](../../api-reference/index.md) -- REST endpoint documentation
- [CLI Reference](../../cli-reference/) -- command-line interface
- [Common Reference](../../reference/index.md) -- authentication, pagination, conventions
