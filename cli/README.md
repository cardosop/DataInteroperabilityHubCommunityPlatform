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

```bash
# List contracts
datahub contracts list

# Get contract details
datahub contracts get <contract-id>

# Create contract from file
datahub contracts create --file contract.yaml

# Validate contract
datahub contracts validate <contract-id>

# Lint contract
datahub contracts lint <contract-id>
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

