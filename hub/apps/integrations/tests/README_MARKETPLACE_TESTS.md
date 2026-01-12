# Marketplace Connector Integration Tests

## Overview

Comprehensive integration tests for marketplace connector operations (CKAN and Swagger APIs) using **real marketplace instances** - no mocks or stubs.

## Test Files

- **`test_marketplace_instances_config.py`**: Tests marketplace instance configuration system
- **`test_marketplace_test_helpers.py`**: Tests marketplace test helper utilities
- **`test_factory_marketplace_instance.py`**: Tests marketplace connector factory
- **`test_ckan_connector_discovery.py`**: Tests discovery operations (list_listings, get_listing, list_resources)
- **`test_ckan_connector_pull.py`**: Tests pull/harvest operations (sync_pull, map_to_hub_asset)
- **`test_ckan_connector_sync.py`**: Tests sync operations (sync_pull, sync_push - push operations raise NotImplementedError)
- **`test_ckan_connector_push.py`**: **DEPRECATED** - Tests that push operations correctly raise NotImplementedError (marketplace connectors are harvest-only)
- **`test_dados_gov_br_integration.py`**: Integration tests for dados.gov.br Swagger API connector (DadosGovBrConnector)

## Prerequisites

### For Discovery Tests (Read Operations)

No special setup required - tests use public marketplace instances:
- `https://dados.gov.br` (Brazilian Government Open Data Portal - primary production instance, Swagger API)
- `https://demo.ckan.org` (default test instance, CKAN API)
- `https://data.gov` (fallback test instance, CKAN API)
- Custom instance via `CKAN_TEST_URL` environment variable

### Marketplace Instance Configuration

The marketplace connector system uses a centralized instance configuration system (`hub/apps/integrations/config/marketplace_instances.py`) that registers all known marketplace connector instances. The system supports both CKAN-standard APIs and custom Swagger APIs.

**Production Instances:**
- **dados.gov.br**: Brazilian Government Open Data Portal
  - Base URL: `https://dados.gov.br`
  - Country: BR
  - Language: pt-BR
  - Organization: Brazilian Government
  - Connector Type: **Swagger** (uses DadosGovBrConnector with Swagger API endpoints, NOT CKAN)
  - Swagger Spec URL: `https://dados.gov.br/v3/api-docs`
  - Swagger UI: `https://dados.gov.br/swagger-ui/index.html`
  - API Key: `DADOS_GOV_BR_API_KEY` (JWT Bearer token, required for authentication; deprecated: `CKAN_DADOS_GOV_BR_API_KEY` still works for backward compatibility)
  - **Important**: dados.gov.br uses custom Swagger APIs (`/dados/api/publico/conjuntos-dados`), NOT standard CKAN APIs

**Test/Demo Instances (CKAN API):**
- **demo.ckan.org**: CKAN Demo instance (default test instance)
  - Base URL: `https://demo.ckan.org`
  - Connector Type: **CKAN** (uses standard CKAN API endpoints)
  - No API key required for read operations

- **data.gov**: US Government Open Data Portal
  - Base URL: `https://data.gov`
  - Country: US
  - Connector Type: **CKAN** (uses standard CKAN API endpoints)
  - No API key required for read operations

### For Push Tests (Deprecated)

**Note**: Marketplace connectors are harvest-only (PULL only). Push operations (create_listing, update_listing, publish_resource, sync_push) now raise `NotImplementedError`. Push tests validate that these operations correctly raise `NotImplementedError` - no API key required.

## Running Tests

### Run All Marketplace Connector Tests

```bash
# Inside Docker container
docker compose exec api-service python -m pytest hub/apps/integrations/tests/test_ckan_connector*.py hub/apps/integrations/tests/test_marketplace_*.py -v

# Or locally (if dependencies installed)
pytest hub/apps/integrations/tests/test_ckan_connector*.py hub/apps/integrations/tests/test_marketplace_*.py -v
```

### Run Marketplace Configuration Tests

```bash
docker compose exec api-service python -m pytest hub/apps/integrations/tests/test_marketplace_instances_config.py hub/apps/integrations/tests/test_marketplace_test_helpers.py hub/apps/integrations/tests/test_factory_marketplace_instance.py -v
```

### Run Discovery Tests Only

```bash
docker compose exec api-service python -m pytest hub/apps/integrations/tests/test_ckan_connector_discovery.py -v
```

### Run Push Tests Only (Deprecated - Validates NotImplementedError)

```bash
# No API key needed - tests validate that push operations raise NotImplementedError
docker compose exec api-service python -m pytest hub/apps/integrations/tests/test_ckan_connector_push.py -v
```

## Test Results

### Expected Behavior

- **Discovery tests**: All tests should pass (no API key needed)
- **Pull tests**: All tests should pass (no API key needed)
- **Push tests**: All tests should pass - validate that push operations raise NotImplementedError (no API key needed)
- **Sync tests**: Pull tests pass, push tests validate NotImplementedError
- **Push tests**:
  - Without API key: Tests will skip with helpful messages
  - With API key: All tests should pass

### Understanding Skips

If push tests are skipped, it means:
1. No API key is configured
2. API key is invalid or expired
3. API key doesn't have write permissions

**Solution**: Run `./scripts/setup_ckan_test_credentials.sh` to set up credentials.

## Environment Variables

| Variable | Description | Required For | Default |
|----------|-------------|--------------|---------|
| `CKAN_TEST_URL` | Marketplace instance URL for testing (CKAN instances) | All tests | `https://demo.ckan.org` |
| `CKAN_TEST_API_KEY` | API key for test instance | Push tests (deprecated) | None |
| `DADOS_GOV_BR_API_KEY` | JWT Bearer token for dados.gov.br Swagger API | Required for dados.gov.br Swagger connector | None |
| `CKAN_DADOS_GOV_BR_API_KEY` | **DEPRECATED** - JWT Bearer token for dados.gov.br (use `DADOS_GOV_BR_API_KEY` instead) | Backward compatibility only | None |

### Environment Variable Setup

**For Local Development:**

1. **Using Docker Compose** (Recommended):
   ```bash
   # Add to docker-compose.yml or .env.dev
   DADOS_GOV_BR_API_KEY=your-api-key-here
   CKAN_TEST_URL=https://demo.ckan.org  # For CKAN instance testing
   ```

2. **Using Environment File**:
   ```bash
   # Create .env.test (gitignored)
   export DADOS_GOV_BR_API_KEY=your-api-key-here
   export CKAN_TEST_URL=https://demo.ckan.org
   ```

3. **Direct Export**:
   ```bash
   export DADOS_GOV_BR_API_KEY=your-api-key-here
   export CKAN_TEST_URL=https://demo.ckan.org
   ```

**For CI/CD:**

- Set `DADOS_GOV_BR_API_KEY` as a GitHub secret (primary)
- `CKAN_DADOS_GOV_BR_API_KEY` still works for backward compatibility
- The workflow (`.github/workflows/test-marketplace-integration.yml`) automatically uses it
- Tests work without API key for read-only operations

**Getting API Keys:**

- **dados.gov.br** (Swagger API):
  - Uses JWT Bearer token authentication
  - Token format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
  - Set via `DADOS_GOV_BR_API_KEY` environment variable (primary)
  - Deprecated: `CKAN_DADOS_GOV_BR_API_KEY` still works for backward compatibility
  - Required for Swagger API connector (DadosGovBrConnector)
  - **Important**: dados.gov.br uses Swagger APIs, NOT CKAN APIs
- **demo.ckan.org** (CKAN API):
  - Visit https://demo.ckan.org, create account, generate API key (optional)
  - Uses standard CKAN API endpoints
- **data.gov** (CKAN API):
  - Public read-only access, no API key needed
  - Uses standard CKAN API endpoints

## Test Coverage

### Discovery Operations
- ✅ List listings (basic, pagination, filters)
- ✅ Get listing (by ID, by name)
- ✅ List resources
- ✅ Data mapping (CKAN → MarketplaceListing/MarketplaceResource)
- ✅ Error handling

### Push Operations
- ✅ Create listing (basic, with tags, with metadata)
- ✅ Update listing
- ✅ Publish resource
- ✅ Hub asset to CKAN mapping
- ✅ Complete workflow (map → create → update → publish)
- ✅ Error handling (permissions, validation, connection)

## Troubleshooting

### Tests Skip Due to Missing API Key

**Symptom**: Push tests skip with message about API key

**Solution**:
1. Run `./scripts/setup_ckan_test_credentials.sh`
2. Or set `CKAN_TEST_API_KEY` environment variable

### Connection Errors

**Symptom**: Tests fail with connection errors

**Solution**:
1. Check internet connectivity
2. Verify marketplace instance URL is correct
3. Try a different instance:
   - For CKAN API: demo.ckan.org, data.gov
   - For Swagger API: dados.gov.br (requires API key)

### Authentication Failures

**Symptom**: Tests fail with permission errors even with API key

**Solution**:
1. Verify API key is correct
2. Check API key has write permissions
3. Regenerate API key if needed

## Best Practices

1. **Use Real Instances**: All tests use real marketplace instances (CKAN and Swagger APIs) - no mocks
2. **Clean Up**: Tests automatically clean up created test data
3. **Isolation**: Each test creates unique test data to avoid conflicts
4. **Error Handling**: Tests verify proper error handling and exception types
5. **API Type Awareness**: Understand which instances use CKAN APIs vs Swagger APIs

## Notes

- Test credentials are stored in environment variables (gitignored)
- Tests use unique IDs to avoid conflicts
- Some tests may take longer due to real API calls
- Public marketplace instances may have rate limiting
- **Marketplace connectors are harvest-only (PULL only)** - push operations raise `NotImplementedError`
- All tests use real marketplace instances - no mocks or stubs
- Instance configuration is centralized in `hub/apps/integrations/config/marketplace_instances.py` (supports both CKAN and Swagger connectors)
- **Important Distinction**:
  - **dados.gov.br**: Uses Swagger APIs (NOT CKAN) - requires `DADOS_GOV_BR_API_KEY`
  - **demo.ckan.org, data.gov**: Use CKAN APIs - standard CKAN endpoints

## dados.gov.br Integration

The marketplace connector system is configured to work with **dados.gov.br** (Brazilian Government Open Data Portal) as the primary production instance using **Swagger API endpoints** (NOT CKAN APIs).

### Swagger API Integration

dados.gov.br uses a **Swagger-based connector** (`DadosGovBrConnector`) that:
- Loads Swagger specification from `https://dados.gov.br/api/3/swagger.json`
- Resolves API endpoints from Swagger spec using operation IDs
- Uses JWT Bearer token authentication (`Authorization: Bearer <token>`)
- Falls back to standard CKAN endpoints if Swagger spec unavailable
- Maintains compatibility with `DataMarketplaceConnector` interface

### Configuration

- **Instance Name**: `dados.gov.br`
- **Base URL**: `https://dados.gov.br`
- **Connector Type**: `swagger` (uses DadosGovBrConnector)
- **Country**: BR (Brazil)
- **Language**: pt-BR (Portuguese - Brazil)
- **Organization**: Brazilian Government
- **Swagger Spec URL**: `https://dados.gov.br/api/3/swagger.json`
- **Swagger UI**: `https://dados.gov.br/swagger-ui/index.html`
- **JWT Token Environment Variable**: `DADOS_GOV_BR_API_KEY` (required, primary)
- **Deprecated**: `CKAN_DADOS_GOV_BR_API_KEY` still works for backward compatibility

### Usage

```python
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.integrations.factory import MarketplaceConnectorFactory

# Get configuration for dados.gov.br
config = get_marketplace_instance_config('dados.gov.br')
assert config.connector_type == "swagger"  # Uses Swagger connector (NOT CKAN)
assert config.api_key_env_var == "DADOS_GOV_BR_API_KEY"  # Uses new environment variable name

# Create connector using factory (automatically selects DadosGovBrConnector for Swagger API)
connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance('dados.gov.br')
# Or use backward-compatible method:
# connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance('dados.gov.br')

# Verify connector type
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
assert isinstance(connector, DadosGovBrConnector)

# Use connector for harvest operations
listings = connector.list_listings(limit=10)
```

### Direct Connector Creation

```python
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector

# Create connector directly
connector = DadosGovBrConnector(
    base_url="https://dados.gov.br",
    jwt_token="your-jwt-token-here",
    swagger_spec_url="https://dados.gov.br/api/3/swagger.json"
)

# Test connection
connector.test_connection()

# List datasets
listings = connector.list_listings(limit=10)
```

### Testing with dados.gov.br Swagger API

```bash
# Set JWT Bearer token (required for Swagger connector)
export DADOS_GOV_BR_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
# Or use deprecated variable for backward compatibility:
# export CKAN_DADOS_GOV_BR_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Run integration tests for Swagger connector
docker compose exec api-service python -m pytest hub/apps/integrations/tests/test_dados_gov_br_integration.py -v

# Run all marketplace connector tests (includes Swagger and CKAN connector tests)
docker compose exec api-service python -m pytest hub/apps/integrations/tests/test_ckan_connector*.py hub/apps/integrations/tests/test_marketplace_*.py -v
```

### Swagger API Endpoints

The Swagger connector uses the following endpoints (resolved from Swagger spec):
- **Search Datasets**: `/api/3/action/package_search` (operationId: `package_search`)
- **Get Dataset**: `/api/3/action/package_show` (operationId: `package_show`)
- **Get Resource**: `/api/3/action/resource_show` (operationId: `resource_show`)

### Authentication

dados.gov.br Swagger API requires JWT Bearer token authentication:
- Token format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- Header: `Authorization: Bearer <token>` (via `chave-api-dados-abertos` header)
- Set via `DADOS_GOV_BR_API_KEY` environment variable (primary)
- Deprecated: `CKAN_DADOS_GOV_BR_API_KEY` still works for backward compatibility

### Connector Type Distinction

**Swagger API Connectors** (dados.gov.br):
- `connector_type="swagger"`
- Uses `DadosGovBrConnector`
- Requires JWT Bearer token authentication
- Swagger spec automatically loaded from `https://dados.gov.br/v3/api-docs`
- Uses custom Swagger API endpoints (`/dados/api/publico/conjuntos-dados`)

**CKAN API Connectors** (demo.ckan.org, data.gov):
- `connector_type="ckan"` (default)
- Uses `CKANConnector`
- Uses standard CKAN API endpoints
- No Swagger spec required
- API key authentication (not JWT Bearer token)
- Standard CKAN endpoints (`/api/3/action/package_search`, etc.)

**Important**: The factory automatically selects the correct connector type based on instance configuration. Always use `get_marketplace_instance_config()` to get instance configuration, which includes the `connector_type` field.

