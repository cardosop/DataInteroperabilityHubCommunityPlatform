# DataHub CLI

A standalone command-line tool for managing DataHub resources (assets, contracts, files, and jobs).

## Installation

### From Source

```bash
cd cli
pip install -e .
```

### From Package

```bash
pip install datahub-cli
```

## Configuration

The CLI stores configuration in `~/.datahub/config.yaml`. You can configure:

- `api_base_url`: API base URL (default: `http://localhost:8000/api/v1`)
- `api_key`: API key for authentication
- `default_tenant`: Default tenant ID

### Setting Configuration

```bash
# Set API base URL
datahub config set api_base_url http://localhost:8000/api/v1

# Set API key
datahub config set api_key your-api-key-here

# View configuration
datahub config get
```

## Authentication

### Login with Email/Password

```bash
datahub login
```

This will prompt for email and password, and store JWT tokens for subsequent requests.

### Using API Key

```bash
datahub config set api_key your-api-key-here
```

### Logout

```bash
datahub logout
```

## Usage

### Assets

```bash
# List assets
datahub assets list

# Get asset details
datahub assets get <asset-id>

# Create asset
datahub assets create --name "My Asset" --key "my-asset" --description "Description"

# Update asset
datahub assets update <asset-id> --name "Updated Name"

# Delete asset
datahub assets delete <asset-id>

# Activate asset
datahub assets activate <asset-id>
```

### Contracts

#### Basic Contract Operations

```bash
# List contracts
datahub contracts list

# Get contract details
datahub contracts get <contract-id>

# Create contract from file (auto-detects ODPS or ODCS)
datahub contracts create --file contract.yaml

# Create contract with explicit spec type
datahub contracts create --file contract.yaml --spec-type ODPS

# Validate contract
datahub contracts validate <contract-id>

# Lint contract
datahub contracts lint <contract-id>
```

#### ODPS (Open Data Product Standard) Commands

The CLI provides comprehensive support for ODPS contracts, including creation, linking, and information retrieval.

##### Creating ODPS Contracts

```bash
# Create ODPS contract with Product-First flow (extracts ODCS from ODPS)
datahub contracts create-odps --file product.odps.json --extract-odcs

# Create ODPS contract and link to existing ODCS contract
datahub contracts create-odps --file product.odps.json --link-odcs <odcs-contract-id>

# Create ODPS from YAML file
datahub contracts create-odps --file product.odps.yaml --extract-odcs

# Create ODPS with specific version
datahub contracts create-odps --file product.odps.json --extract-odcs --version 4.1

# Create ODPS without resolving external references
datahub contracts create-odps --file product.odps.json --extract-odcs --no-resolve-external-refs
```

##### ODPS Linking Commands

```bash
# Link ODPS contract to ODCS contract
datahub contracts link-odps <odcs-contract-id> <odps-contract-id>

# Unlink ODPS contract from ODCS contract
datahub contracts unlink-odps <odcs-contract-id>

# List all links for a contract (ODPS and ODCS links)
datahub contracts list-links <contract-id>
```

##### ODPS Information Commands

```bash
# Get contract details with ODPS information (pricing, access methods, payment gateways)
datahub contracts get <contract-id> --show-odps

# Get pricing plans for an ODPS contract
datahub contracts get-pricing <contract-id>

# Get pricing plans in JSON format
datahub contracts get-pricing <contract-id> --format json

# Get access methods for an ODPS contract
datahub contracts get-access-methods <contract-id>

# Get access methods in JSON format
datahub contracts get-access-methods <contract-id> --format json
```

##### ODPS Export and Download

```bash
# Export contract as ODPS format
datahub contracts export <contract-id> --format odps --output-format json

# Export contract as ODPS format in YAML
datahub contracts export <contract-id> --format odps --output-format yaml

# Download contract as ODPS file
datahub contracts download <contract-id> --format odps --output-format json --output product.odps.json
```

#### ODPS Usage Examples

##### Example 1: Create ODPS Product with Embedded ODCS Contract

```bash
# Create an ODPS product that includes an embedded ODCS contract
# The ODCS contract will be automatically extracted and created
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --asset-id <asset-id>

# Output shows both ODPS and ODCS contract IDs
# ODPS Contract: <odps-id>
# ODCS Contract: <odcs-id>
```

##### Example 2: Link Existing ODPS to ODCS Contract

```bash
# First, create an ODCS contract
datahub contracts create --file technical-contract.yaml

# Then, create and link an ODPS contract to it
datahub contracts create-odps \
  --file marketplace-product.odps.json \
  --link-odcs <odcs-contract-id>

# Verify the link
datahub contracts list-links <odcs-contract-id>
```

##### Example 3: View ODPS Marketplace Information

```bash
# Get full contract details including ODPS marketplace data
datahub contracts get <odps-contract-id> --show-odps

# Output includes:
# - Pricing Plans (planID, name, price, currency, billingPeriod)
# - Access Methods (type, endpoint, protocol)
# - Payment Gateways (if configured)

# Get just pricing information
datahub contracts get-pricing <odps-contract-id>

# Get just access methods
datahub contracts get-access-methods <odps-contract-id>
```

##### Example 4: Export ODPS Contract

```bash
# Export ODPS contract for sharing or backup
datahub contracts export <odps-contract-id> \
  --format odps \
  --output-format json \
  --cli-format json > product-backup.odps.json

# Download ODPS contract as file
datahub contracts download <odps-contract-id> \
  --format odps \
  --output-format yaml \
  --output product.odps.yaml
```

#### ODPS Command Reference

| Command | Description | Options |
|---------|-------------|---------|
| `create-odps` | Create ODPS contract | `--file`, `--extract-odcs`, `--link-odcs`, `--version`, `--resolve-external-refs` |
| `link-odps` | Link ODPS to ODCS contract | `<odcs-id> <odps-id>` |
| `unlink-odps` | Unlink ODPS from ODCS contract | `<odcs-id>` |
| `list-links` | List all contract links | `<contract-id>` |
| `get --show-odps` | Show ODPS information in contract details | `--show-odps` |
| `get-pricing` | Get pricing plans for ODPS contract | `--format json\|table` |
| `get-access-methods` | Get access methods for ODPS contract | `--format json\|table` |
| `export --format odps` | Export contract as ODPS format | `--format odps`, `--output-format json\|yaml` |
| `download --format odps` | Download contract as ODPS file | `--format odps`, `--output-format json\|yaml` |

#### ODPS Workflow Patterns

**Product-First Flow**: Create ODPS product with embedded ODCS contract
```bash
datahub contracts create-odps --file product.odps.json --extract-odcs
```

**Link Flow**: Create ODPS and link to existing ODCS contract
```bash
datahub contracts create-odps --file product.odps.json --link-odcs <odcs-id>
```

**Manual Linking**: Link existing ODPS to existing ODCS
```bash
datahub contracts link-odps <odcs-id> <odps-id>
```

**Information Retrieval**: Get ODPS marketplace information
```bash
datahub contracts get <odps-id> --show-odps
datahub contracts get-pricing <odps-id>
datahub contracts get-access-methods <odps-id>
```

### Files

```bash
# List files
datahub files list

# Upload file
datahub files upload /path/to/file.csv

# Download file
datahub files download <file-id> --output /path/to/output.csv

# Delete file
datahub files delete <file-id>
```

### Jobs

```bash
# List jobs
datahub jobs list

# Get job details
datahub jobs get <job-id>

# Cancel job
datahub jobs cancel <job-id>

# Watch job until completion
datahub jobs watch <job-id>
```

### Marketplace

The CLI provides comprehensive support for marketplace integration, allowing you to manage connections, sync jobs, connectors, and mappings between Hub assets and external marketplace listings.

#### Marketplace Connections

```bash
# List available connector types
datahub marketplace connectors list

# Get connector information
datahub marketplace connectors info SNOWFLAKE_DATA_MARKETPLACE

# Create marketplace connection
datahub marketplace connections create \
  --marketplace-type SNOWFLAKE_DATA_MARKETPLACE \
  --name "Snowflake Production" \
  --config '{"account": "myaccount", "user": "myuser", "token": "mytoken"}'

# List connections
datahub marketplace connections list

# Get connection details
datahub marketplace connections get <connection-id>

# Test connection
datahub marketplace connections test <connection-id>

# Update connection
datahub marketplace connections update <connection-id> --name "Updated Name"

# Delete connection
datahub marketplace connections delete <connection-id>
```

#### Marketplace Sync Jobs

```bash
# Start sync job (PULL from marketplace)
datahub marketplace sync start \
  --connection-id <connection-id> \
  --direction PULL

# Start sync job (PUSH to marketplace)
datahub marketplace sync start \
  --connection-id <connection-id> \
  --direction PUSH \
  --asset-ids <asset-id-1>,<asset-id-2>

# List sync jobs
datahub marketplace sync list

# Get sync job details
datahub marketplace sync get <sync-job-id>

# Watch sync job progress
datahub marketplace sync get <sync-job-id> --watch

# Cancel sync job
datahub marketplace sync cancel <sync-job-id>
```

#### Marketplace Mappings

```bash
# List mappings
datahub marketplace mappings list

# Get mapping details
datahub marketplace mappings get <mapping-id>

# Delete mapping
datahub marketplace mappings delete <mapping-id>
```

For detailed marketplace usage examples and workflows, see the [Marketplace Usage Guide](docs/MARKETPLACE_USAGE.md).

### BaaS (Backend as a Service)

The CLI provides comprehensive support for BaaS platform operations, including API key management, usage tracking, and developer portal access.

#### API Key Management

```bash
# Create a new API key
datahub baas api-keys create --name "My API Key" --tier FREE

# Create API key with expiration date
datahub baas api-keys create \
  --name "Temporary Key" \
  --tier PRO \
  --expires-at "2025-12-31T23:59:59Z"

# List API keys
datahub baas api-keys list

# List API keys with tier filter
datahub baas api-keys list --tier PRO

# Get API key details
datahub baas api-keys get <api-key-id>

# Update API key
datahub baas api-keys update <api-key-id> --name "Updated Name"

# Revoke API key
datahub baas api-keys revoke <api-key-id>
```

#### Developer Portal Documentation

```bash
# Show API documentation (default: HTML format)
datahub baas docs show

# Show API documentation in JSON format
datahub baas docs show --format json

# Show API documentation in Markdown format
datahub baas docs show --format markdown

# Get OpenAPI schema (default: JSON)
datahub baas docs openapi

# Get OpenAPI schema in YAML format
datahub baas docs openapi --format yaml

# List SDK download links
datahub baas docs sdks

# List SDK download links in JSON format
datahub baas docs sdks --format json
```

#### Usage Tracking

```bash
# Get API usage statistics
datahub baas usage get

# Get usage statistics for specific time range
datahub baas usage get --start-date "2025-01-01" --end-date "2025-01-31"
```

For detailed BaaS usage examples and workflows, see the [BaaS Usage Guide](docs/BAAS_USAGE.md).

### ML (Machine Learning) / ODH (Open Data Hub)

The CLI provides comprehensive support for ML model management, training, and inference operations with ODH (Open Data Hub) integration.

#### Model Registry

```bash
# List ML models
datahub ml models list

# List models with filters
datahub ml models list --asset-id <asset-id> --status TRAINED --limit 50

# Get model details
datahub ml models get <model-id>

# Create a new ML model link
datahub ml models create \
  --odh-model-id <odh-model-id> \
  --odh-model-name "My Model" \
  --odh-model-version "1.0.0" \
  --model-type CLASSIFICATION \
  --asset-id <asset-id> \
  --contract-id <contract-id>

# Update model
datahub ml models update <model-id> \
  --asset-id <new-asset-id> \
  --status DEPLOYED

# Delete model
datahub ml models delete <model-id>

# List all versions of a model
datahub ml models versions <model-id>
```

#### Training Jobs

```bash
# Submit a training job
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config training-config.json

# List training jobs
datahub ml training list

# List training jobs for a specific model
datahub ml training list --model-id <model-id> --status RUNNING

# Get training job details
datahub ml training get <job-id>

# Cancel a training job
datahub ml training cancel <job-id>

# Get training job logs
datahub ml training logs <job-id>
```

#### Inference Deployments

```bash
# Deploy a model for inference
datahub ml inference deploy \
  --model-id <model-id> \
  --config deployment-config.json

# Run inference prediction
datahub ml inference predict \
  --deployment-id <deployment-id> \
  --input-data input.json

# List inference deployments
datahub ml inference list

# Get deployment details
datahub ml inference get <deployment-id>

# Undeploy a model
datahub ml inference undeploy <deployment-id>

# Get inference metrics
datahub ml inference metrics <deployment-id>
```

#### Model Serving

Model serving provides API endpoints for deploying models as production-ready services with contract validation, quality monitoring, and A/B testing capabilities.

```bash
# Deploy a model for serving
datahub ml serving deploy \
  --model-id <model-id> \
  --endpoint /api/v1/models/my-model

# Run prediction via serving endpoint
datahub ml serving predict \
  --model-id <model-id> \
  --input input.json

# List serving deployments
datahub ml serving list

# Get serving deployment details
datahub ml serving get <serving-id>

# Undeploy a serving deployment
datahub ml serving undeploy <serving-id>

# Get serving metrics (accuracy, latency, error rate, data drift)
datahub ml serving metrics <serving-id>
```

#### A/B Testing

A/B testing allows you to compare model variants by splitting traffic between a base model and a variant model.

```bash
# Create an A/B test
datahub ml serving ab-test create \
  --model-id <base-model-id> \
  --variant-id <variant-model-id> \
  --traffic-split "50:50"

# List A/B tests
datahub ml serving ab-test list

# Get A/B test details with metrics
datahub ml serving ab-test get <ab-test-id>
```

#### Model Types

Supported model types:
- `CLASSIFICATION` - Classification models
- `REGRESSION` - Regression models
- `CLUSTERING` - Clustering models
- `NLP` - Natural Language Processing models
- `COMPUTER_VISION` - Computer Vision models
- `RECOMMENDATION` - Recommendation models
- `TIME_SERIES` - Time Series models
- `ANOMALY_DETECTION` - Anomaly Detection models
- `OTHER` - Other model types

#### Model Status

Model status values:
- `TRAINING` - Model is currently being trained
- `TRAINED` - Model training completed successfully
- `DEPLOYED` - Model is deployed for inference
- `FAILED` - Model training or deployment failed
- `ARCHIVED` - Model is archived

For detailed ML/ODH usage examples and workflows, see the [ODH Usage Guide](docs/ODH_USAGE.md).

For detailed model serving and A/B testing usage examples and workflows, see the [Model Serving Usage Guide](docs/MODEL_SERVING_USAGE.md).

## Output Formats

Most commands support `--format` option to choose output format:

- `table`: Human-readable table format (default)
- `json`: JSON format for scripting

Example:

```bash
datahub assets list --format json
```

## Examples

### Complete Workflow

```bash
# 1. Configure and login
datahub config set api_base_url http://localhost:8000/api/v1
datahub login

# 2. Create an asset
datahub assets create --name "Customer Data" --key "customer-data" --domain "sales"

# 3. Create a contract
datahub contracts create --file contract.yaml --asset-id <asset-id>

# 4. Upload a file
datahub files upload data.csv

# 5. Watch a job
datahub jobs watch <job-id>
```

### ODPS Workflow Example

```bash
# 1. Configure and authenticate
datahub config set api_base_url http://localhost:8000/api/v1
datahub config set api_key your-api-key

# 2. Create an ODPS product with embedded ODCS contract (Product-First flow)
datahub contracts create-odps \
  --file marketplace-product.odps.json \
  --extract-odcs \
  --asset-id <asset-id>

# This creates both:
# - ODPS contract (marketplace/product information)
# - ODCS contract (technical contract extracted from product.contract)

# 3. View ODPS marketplace information
datahub contracts get <odps-contract-id> --show-odps

# 4. Get pricing plans
datahub contracts get-pricing <odps-contract-id>

# 5. Get access methods
datahub contracts get-access-methods <odps-contract-id>

# 6. Export ODPS contract for backup
datahub contracts export <odps-contract-id> \
  --format odps \
  --output-format json \
  --cli-format json > product-backup.odps.json
```

### ODPS Linking Workflow Example

```bash
# 1. Create ODCS contract (technical specification)
datahub contracts create --file technical-spec.odcs.yaml

# 2. Create ODPS contract and link to ODCS
datahub contracts create-odps \
  --file marketplace-product.odps.json \
  --link-odcs <odcs-contract-id>

# 3. Verify the link
datahub contracts list-links <odcs-contract-id>

# 4. View linked ODPS information
datahub contracts get <odps-contract-id> --show-odps

# 5. If needed, unlink the contracts
datahub contracts unlink-odps <odcs-contract-id>
```

## Additional Documentation

- **[ODPS Usage Guide](docs/ODPS_USAGE.md)** - Comprehensive guide for ODPS (Open Data Product Standard) commands, workflows, and examples
- **[Marketplace Usage Guide](docs/MARKETPLACE_USAGE.md)** - Complete guide for marketplace integration commands, workflows, and examples
- **[BaaS Usage Guide](docs/BAAS_USAGE.md)** - Complete guide for BaaS (Backend as a Service) platform commands, workflows, and examples
- **[ODH Usage Guide](docs/ODH_USAGE.md)** - Complete guide for ML/ODH (Open Data Hub) commands, workflows, and examples
- **[Model Serving Usage Guide](docs/MODEL_SERVING_USAGE.md)** - Complete guide for model serving and A/B testing commands, workflows, and examples

## Development

### Running Tests

```bash
cd cli
pytest tests/
```

### Building Package

```bash
cd cli
python setup.py sdist bdist_wheel
```

## New Commands (Phase 118E)

### Transformation Pipelines

```bash
datahub transformation pipelines list [--status ACTIVE]
datahub transformation pipelines get <pipeline_id>
datahub transformation pipelines create --name "ETL Pipeline" [--description "..."] [--config '{}']
datahub transformation pipelines update <pipeline_id> [--name "..."] [--description "..."]
datahub transformation pipelines delete <pipeline_id> [--confirm]
datahub transformation pipelines validate <pipeline_id>
datahub transformation runs list [--pipeline-id <id>] [--status RUNNING]
datahub transformation runs get <run_id>
datahub transformation runs submit <pipeline_id> [--params '{}']
datahub transformation runs cancel <run_id>
datahub transformation plan-limits
```

### Semantic / SPARQL

```bash
datahub semantic sparql query --query "SELECT ?s WHERE { ?s a ?o }" [--accept application/sparql-results+json]
datahub semantic sparql query --file query.sparql
datahub semantic sparql service-description
datahub semantic ontology
datahub semantic void
datahub semantic shacl validate [--data data.ttl] [--shapes shapes.ttl]
```

### Billing (New Commands)

```bash
datahub billing plan-limits                              # Show plan limits
datahub billing usage [--resource-type api_calls]        # Usage records
datahub billing refund <pi_id> --amount 1000 --reason requested_by_customer
datahub billing reconcile [--dry-run]                    # Stripe reconciliation
```

### BaaS (New Commands)

```bash
datahub baas customers list
datahub baas customers usage <customer_id> [--period 2026-03]
datahub baas billing-reports list|get|generate|finalize|export|send
datahub baas api-keys rotate <id> [--grace-hours 24]
```

### ML (New Commands)

```bash
datahub ml deploy <model_id> [--config-file deploy.json]
datahub ml undeploy <model_id>
datahub ml rollback <model_odh_id> --version <v>
datahub ml plan show
datahub ml plan limits
datahub ml marketplace-publish <model_id> [--pricing-model REQUEST_APPROVAL]
```

### Compliance (New Commands)

```bash
datahub compliance scan-async --file-id <id> --regulations GDPR,HIPAA
datahub compliance scan-result <job_id>
datahub compliance regulations list
datahub compliance regulations get <key>
```

### Governance (New Commands)

```bash
datahub governance workflows list [--status PENDING]
datahub governance workflows get <id>
datahub governance workflows retry <id>
```

### Display Enhancements

- `datahub scheduled-ingestion get` now shows `Consecutive Failures` and `Auto-Pause Status`
- `datahub scheduled-ingestion run-detail` now shows `DLQ Sync Status`
- `datahub scheduled-export get` now shows `Consecutive Failures` and `Auto-Pause Status`
- `datahub dq watch` now displays fail-closed status (`UNKNOWN` / `POLL_TIMEOUT`) on timeout

## License

MIT License

