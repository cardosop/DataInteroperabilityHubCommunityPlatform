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

## License

MIT License

