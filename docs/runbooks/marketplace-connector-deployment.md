# Marketplace Connector Deployment Runbook

Complete operational guide for deploying and managing marketplace connectors (CKAN and Swagger APIs) in the Data Interoperability Hub.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Variable Setup](#environment-variable-setup)
4. [Deployment Procedures](#deployment-procedures)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)
7. [Monitoring](#monitoring)
8. [Security Best Practices](#security-best-practices)
9. [Maintenance](#maintenance)

---

## Overview

The marketplace connector system enables harvesting (PULL operations) of data from marketplace instances (CKAN and Swagger APIs) into the Data Interoperability Hub. The connectors are **harvest-only** - they do not support push operations as marketplace instances are public data portals that should be harvested FROM, not pushed TO.

### Supported Marketplace Instances

**Production Instances:**
- **dados.gov.br**: Brazilian Government Open Data Portal (primary production instance)
  - Base URL: `https://dados.gov.br`
  - Country: BR
  - Language: pt-BR
  - Organization: Brazilian Government
  - **API Type**: Custom Swagger APIs (NOT CKAN)
  - **Connector**: `DadosGovBrConnector` (Swagger-based)

**Test/Demo Instances:**
- **demo.ckan.org**: CKAN Demo instance (default test instance)
  - **API Type**: Standard CKAN APIs
  - **Connector**: `CKANConnector`
- **data.gov**: US Government Open Data Portal
  - **API Type**: Standard CKAN APIs
  - **Connector**: `CKANConnector`

### Key Features

- **Harvest Operations**: Discover and retrieve data from marketplace instances (CKAN and Swagger APIs)
- **Centralized Configuration**: Instance registry with metadata and environment variable-based API key resolution
- **Real Integration**: All operations use real marketplace instances - no mocks or stubs
- **Multi-API Support**: Supports both CKAN-standard APIs and custom Swagger APIs
- **Circuit Breaker**: Built-in resilience for handling API failures
- **Comprehensive Testing**: 141+ integration tests covering all functionality

---

## Prerequisites

### System Requirements

- Docker and Docker Compose installed
- PostgreSQL 16+ (via Docker Compose)
- Redis 7+ (via Docker Compose)
- Python 3.12+ (for local development)
- Network access to marketplace instances (dados.gov.br, demo.ckan.org, data.gov)

### Service Dependencies

The marketplace connector system requires:
- **PostgreSQL**: Database for storing harvested data
- **Redis**: Cache and circuit breaker state
- **API Service**: Django application service

### Verify Prerequisites

```bash
# Check Docker Compose services
docker compose ps postgres redis-cache redis-queue redis-events api-service

# Verify network connectivity to marketplace instances
curl -I https://dados.gov.br/v3/api-docs  # Swagger API
curl -I https://demo.ckan.org/api/3/action/status_show  # CKAN API
curl -I https://data.gov/api/3/action/status_show  # CKAN API
```

---

## Environment Variable Setup

### Swagger API Integration (dados.gov.br)

dados.gov.br uses a Swagger-based connector (`DadosGovBrConnector`) that requires JWT Bearer token authentication:

- **JWT Token**: Set `DADOS_GOV_BR_API_KEY` environment variable with JWT Bearer token (deprecated: `CKAN_DADOS_GOV_BR_API_KEY` still works for backward compatibility)
- **Token Format**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (JWT format)
- **Authentication**: Uses `Authorization: Bearer <token>` header (via `chave-api-dados-abertos` header)
- **Swagger Spec**: Automatically loaded from `https://dados.gov.br/v3/api-docs`
- **Connector Type**: Automatically selected based on instance configuration (`connector_type="swagger"`)
- **Important**: dados.gov.br uses custom Swagger APIs (`/dados/api/publico/conjuntos-dados`), NOT standard CKAN APIs

The factory (`MarketplaceConnectorFactory.create_marketplace_connector_from_instance()`) automatically:
- Detects `connector_type="swagger"` in instance configuration
- Creates `DadosGovBrConnector` for swagger-type instances (dados.gov.br)
- Creates `CKANConnector` for ckan-type instances (demo.ckan.org, data.gov)
- **Note**: `create_ckan_connector_from_instance()` still works for backward compatibility but is deprecated

### Standard CKAN Instances

Other CKAN instances (demo.ckan.org, data.gov) use standard CKAN connector:
- **API Key**: Standard CKAN API key (not JWT token)
- **Connector Type**: `connector_type="ckan"` (default)
- **Authentication**: Uses API key in `X-CKAN-API-Key` header or query parameter

## Environment Variable Setup

### Required Environment Variables

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `DADOS_GOV_BR_API_KEY` | JWT Bearer token for dados.gov.br Swagger API (NOT CKAN) | Yes** | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `CKAN_DADOS_GOV_BR_API_KEY` | **DEPRECATED** - Use `DADOS_GOV_BR_API_KEY` instead. Still supported for backward compatibility. | No | None | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `CKAN_TEST_URL` | Marketplace connector instance URL for testing (supports both CKAN and Swagger) | No | `https://demo.ckan.org` | `https://dados.gov.br` or `https://demo.ckan.org` |
| `CKAN_TEST_API_KEY` | API key for CKAN test instances (demo.ckan.org, data.gov) | No | None | `test-key...` |

**JWT Bearer token is required for dados.gov.br Swagger API connector. Token format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (JWT format). Other CKAN instances (demo.ckan.org, data.gov) use standard API keys and don't require JWT tokens.

### Development Environment

**Option 1: Docker Compose Environment File**

Create `.env.dev`:
```bash
# CKAN Integration Configuration
# New environment variable name (recommended)
DADOS_GOV_BR_API_KEY=your-dados-gov-br-api-key-here
# Backward compatibility (deprecated - will be removed in future version)
# CKAN_DADOS_GOV_BR_API_KEY=your-dados-gov-br-api-key-here
CKAN_TEST_URL=https://dados.gov.br
CKAN_TEST_API_KEY=your-test-api-key-here
```

**Option 2: Environment File**

Create `.env.test.ckan` (gitignored):
```bash
export DADOS_GOV_BR_API_KEY=your-dados-gov-br-api-key-here
# Backward compatibility (deprecated)
# export CKAN_DADOS_GOV_BR_API_KEY=your-dados-gov-br-api-key-here
export CKAN_TEST_URL=https://dados.gov.br
export CKAN_TEST_API_KEY=your-test-api-key-here
```

Load it:
```bash
source .env.test.ckan
```

**Option 3: Direct Export**

```bash
export DADOS_GOV_BR_API_KEY=your-dados-gov-br-api-key-here
# Backward compatibility (deprecated)
# export CKAN_DADOS_GOV_BR_API_KEY=your-dados-gov-br-api-key-here
export CKAN_TEST_URL=https://dados.gov.br
```

### Staging Environment

```bash
# In docker-compose.staging.yml or .env.staging
DADOS_GOV_BR_API_KEY=${DADOS_GOV_BR_API_KEY}
# Backward compatibility (deprecated)
# CKAN_DADOS_GOV_BR_API_KEY=${CKAN_DADOS_GOV_BR_API_KEY}
CKAN_TEST_URL=https://dados.gov.br
```

### Production Environment

```bash
# In docker-compose.prod.yml or .env.production
# Use secrets management (see Security Best Practices)
DADOS_GOV_BR_API_KEY=${DADOS_GOV_BR_API_KEY}  # From secrets manager
# Backward compatibility (deprecated)
# CKAN_DADOS_GOV_BR_API_KEY=${CKAN_DADOS_GOV_BR_API_KEY}
CKAN_TEST_URL=https://dados.gov.br
```

### Docker Compose Configuration

The `docker-compose.yml` file includes CKAN environment variables:

```yaml
api-service:
  environment:
    # Marketplace Connector Configuration (can be overridden in .env.dev)
    # dados.gov.br Swagger API (NOT CKAN) - uses DADOS_GOV_BR_API_KEY
    - DADOS_GOV_BR_API_KEY=${DADOS_GOV_BR_API_KEY:-}
    # CKAN instances (demo.ckan.org, data.gov) - use CKAN_TEST_URL and CKAN_TEST_API_KEY
    - CKAN_TEST_URL=${CKAN_TEST_URL:-}
    - CKAN_TEST_API_KEY=${CKAN_TEST_API_KEY:-}
    # Backward compatibility (deprecated - will be removed in future version)
    - CKAN_DADOS_GOV_BR_API_KEY=${CKAN_DADOS_GOV_BR_API_KEY:-${DADOS_GOV_BR_API_KEY:-}}
```

### Verifying Environment Variables

```bash
# Check environment variables in running container
docker compose exec api-service env | grep CKAN

# Test configuration loading (using Django shell)
docker compose exec api-service python manage.py shell << 'EOF'
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
config = get_marketplace_instance_config('dados.gov.br')
print(f'Instance: {config.name}')
print(f'Base URL: {config.base_url}')
print(f'API Key Set: {config.get_api_key() is not None}')
EOF
```

---

## Deployment Procedures

### Initial Deployment

#### Step 1: Prepare Environment

```bash
# Clone repository
git clone <repository-url>
cd DataInteroperabilityHub

# Checkout desired branch/tag
git checkout <branch-or-tag>

# Verify Docker Compose file
docker compose config
```

#### Step 2: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env.dev

# Edit .env.dev and add CKAN configuration
nano .env.dev
# Add:
# DADOS_GOV_BR_API_KEY=your-api-key-here
# Backward compatibility (deprecated):
# CKAN_DADOS_GOV_BR_API_KEY=your-api-key-here
# CKAN_TEST_URL=https://dados.gov.br
```

#### Step 3: Start Services

```bash
# Start required services
docker compose up -d postgres redis-cache redis-queue redis-events

# Wait for services to be healthy
docker compose ps

# Start API service
docker compose up -d api-service

# Verify API service is healthy
docker compose exec api-service curl http://localhost:8000/health
```

#### Step 4: Run Database Migrations

```bash
# Run migrations
docker compose exec api-service python manage.py migrate

# Verify migrations completed
docker compose exec api-service python manage.py showmigrations
```

#### Step 5: Verify Marketplace Connector

```bash
# Test connector configuration (using Django shell)
docker compose exec api-service python manage.py shell << 'EOF'
from hub.apps.integrations.config.ckan_instances import (
    get_ckan_instance_config,
    CKAN_INSTANCES
)
print('Registered instances:')
for name in sorted(MARKETPLACE_INSTANCES.keys()):
    config = MARKETPLACE_INSTANCES[name]
    print(f'  - {name}: {config.base_url}')
EOF

# Test connector creation (using Django shell)
docker compose exec api-service python manage.py shell << 'EOF'
from hub.apps.integrations.factory import MarketplaceConnectorFactory
connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance('dados.gov.br')
# Or use backward-compatible method (deprecated):
# connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance('dados.gov.br')
print(f'✓ Connector created for {connector.base_url}')
print(f'  Supported sync directions: {connector.supported_sync_directions}')
EOF
```

### Upgrading Deployment

#### Step 1: Backup Current State

```bash
# Backup database
docker compose exec postgres pg_dump -U hub hub > backup_$(date +%Y%m%d).sql

# Backup environment configuration
cp .env.dev .env.dev.backup_$(date +%Y%m%d)
```

#### Step 2: Pull Latest Changes

```bash
# Pull latest code
git pull origin main

# Checkout specific version if needed
git checkout <version-tag>
```

#### Step 3: Update Services

```bash
# Rebuild API service
docker compose build api-service

# Restart API service
docker compose up -d api-service

# Run migrations
docker compose exec api-service python manage.py migrate
```

#### Step 4: Verify Upgrade

```bash
# Run health checks
docker compose exec api-service curl http://localhost:8000/health

# Run Marketplace connector tests
docker compose exec api-service python -m pytest \
  hub/apps/integrations/tests/test_marketplace_instances_config.py \
  hub/apps/integrations/tests/test_factory_marketplace_instance.py \
  -v
```

### Rollback Procedure

If deployment fails:

```bash
# Stop new version
docker compose stop api-service

# Restore previous version
git checkout <previous-version-tag>

# Rebuild and restart
docker compose build api-service
docker compose up -d api-service

# Restore database if needed
docker compose exec -T postgres psql -U hub hub < backup_YYYYMMDD.sql
```

---

## Configuration

### Instance Configuration

Marketplace instances are configured in `hub/apps/integrations/config/marketplace_instances.py`:

```python
from hub.apps.integrations.config.marketplace_instances import (
    get_marketplace_instance_config,
    MARKETPLACE_INSTANCES
)

# Get configuration for specific instance
config = get_marketplace_instance_config('dados.gov.br')
print(f"Base URL: {config.base_url}")
print(f"Country: {config.country}")
print(f"Language: {config.language}")

# List all registered instances
for name, config in MARKETPLACE_INSTANCES.items():
    print(f"{name}: {config.base_url}")
```

### Connector Configuration

**Using Factory (Recommended):**

```python
from hub.apps.integrations.factory import MarketplaceConnectorFactory

# Create connector from instance configuration
connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
    instance_id='dados.gov.br',
    api_key=None  # Uses environment variable if not provided
)

# Create connector with API key override
connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
    instance_id='dados.gov.br',
    api_key='custom-api-key'
)
```

**Direct Instantiation:**

```python
from hub.apps.integrations.connectors.ckan_connector import CKANConnector

connector = CKANConnector(
    base_url='https://dados.gov.br',
    jwt_token=os.getenv('DADOS_GOV_BR_API_KEY') or os.getenv('CKAN_DADOS_GOV_BR_API_KEY', '')  # Backward compatibility
)
```

### Circuit Breaker Configuration

The connector includes a circuit breaker for resilience:

- **Failure Threshold**: 5 consecutive failures
- **Timeout**: 60 seconds
- **Success Threshold**: 2 successes to close circuit
- **Backend**: Redis (shared across instances)

Circuit breaker state is stored in Redis and shared across all connector instances.

---

## Troubleshooting

### Common Issues

#### Issue 1: Connection Errors

**Symptoms:**
- Tests fail with `ConnectionError`
- Connector cannot reach CKAN instance
- Timeout errors

**Diagnosis:**

```bash
# Test network connectivity
curl -v https://dados.gov.br/api/3/action/status_show

# Check DNS resolution
nslookup dados.gov.br

# Test from container
docker compose exec api-service curl -v https://dados.gov.br/api/3/action/status_show
```

**Solutions:**

1. **Check Network Connectivity**:
   ```bash
   # Verify internet access from container
   docker compose exec api-service ping -c 3 dados.gov.br
   ```

2. **Check Firewall Rules**:
   - Ensure outbound HTTPS (443) is allowed
   - Verify no proxy blocking CKAN domains

3. **Check DNS Resolution**:
   ```bash
   docker compose exec api-service nslookup dados.gov.br
   ```

4. **Verify CKAN Instance Status**:
   ```bash
   # Check CKAN instance status
   curl https://dados.gov.br/api/3/action/status_show
   ```

#### Issue 2: Authentication Failures

**Symptoms:**
- API key/JWT token appears set but operations fail
- Permission errors (401 Unauthorized, 403 Forbidden)
- Rate limiting errors

**For dados.gov.br Swagger API:**

**Diagnosis:**

```bash
# Verify JWT token is set (check new variable first, then deprecated)
docker compose exec api-service env | grep -E "DADOS_GOV_BR_API_KEY|CKAN_DADOS_GOV_BR_API_KEY"

# Test JWT token format (using Django shell)
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
config = get_marketplace_instance_config('dados.gov.br')
jwt_token = config.get_api_key()
if jwt_token:
    print(f'JWT Token Set: Yes')
    print(f'Token Length: {len(jwt_token)}')
    print(f'Token Format: {"JWT" if jwt_token.startswith("eyJ") else "Unknown"}')
    print(f'Token Preview: {jwt_token[:20]}...')
else:
    print('JWT Token Set: No')
EOF

# Test connector type
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
config = get_marketplace_instance_config('dados.gov.br')
print(f'Connector Type: {config.connector_type}')
print(f'Swagger Spec URL: {config.swagger_spec_url}')
EOF
```

**Solutions:**

1. **Verify JWT Token Format**:
   - JWT token should start with `eyJ` (base64-encoded JWT header)
   - Token format: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
   - Check for extra whitespace or newlines
   - Ensure token is not expired

2. **Verify Connector Type**:
   - dados.gov.br should use `connector_type="swagger"`
   - Factory should create `DadosGovBrConnector` (not `CKANConnector`)
   - Check instance configuration in `hub/apps/integrations/config/marketplace_instances.py`

3. **Test Swagger API Connection**:
   ```bash
   # Test Swagger spec loading
   curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
        https://dados.gov.br/api/3/swagger.json

   # Test API endpoint
   curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
        "https://dados.gov.br/api/3/action/package_search?rows=0"
   ```

4. **Regenerate JWT Token**:
   - Contact dados.gov.br administrator for new JWT token
   - Update `DADOS_GOV_BR_API_KEY` environment variable (or `CKAN_DADOS_GOV_BR_API_KEY` for backward compatibility)
   - Restart services

**For Standard CKAN Instances (demo.ckan.org, data.gov):**

**Solutions:**

1. **Verify API Key Format**:
   - API key should be a string (no quotes in environment variable)
   - Check for extra whitespace or newlines

2. **Regenerate API Key**:
   - Visit CKAN instance (e.g., https://demo.ckan.org)
   - Go to user profile
   - Generate new API key
   - Update environment variable

3. **Check API Key Permissions**:
   - Verify API key has read permissions
   - Some CKAN instances require specific permissions

#### Issue 3: Circuit Breaker Open

**Symptoms:**
- Requests fail immediately without attempting connection
- Error messages mention circuit breaker
- Redis connection errors

**Diagnosis:**

```bash
# Check Redis connectivity (using Django shell)
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.core.resilience.circuit_breaker import get_redis_client
redis = get_redis_client()
if redis:
    print(f'✓ Redis Connected: {redis.ping()}')
else:
    print('✗ Redis client not available (None returned)')
EOF

# Check circuit breaker state (using Django shell)
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.core.resilience.circuit_breaker import get_redis_client
redis_client = get_redis_client()
if redis_client:
    key = 'circuit_breaker:ckan-connector:state'
    state = redis_client.get(key)
    print(f'Circuit Breaker State: {state.decode() if state else "None"}')
else:
    print('Redis client not available')
EOF
```

**Solutions:**

1. **Reset Circuit Breaker**:
   ```bash
   docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
   from hub.apps.core.resilience.circuit_breaker import get_redis_client
   redis = get_redis_client()
   if redis:
       redis.delete('circuit_breaker:ckan-connector:state')
       print('✓ Circuit breaker reset')
   else:
       print('✗ Redis client not available')
   EOF
   ```

2. **Check Redis Health**:
   ```bash
   docker compose ps redis-cache
   docker compose logs redis-cache
   ```

3. **Wait for Automatic Recovery**:
   - Circuit breaker will automatically close after timeout period (60 seconds)
   - After 2 successful requests, circuit closes

#### Issue 4: Rate Limiting

**Symptoms:**
- HTTP 429 (Too Many Requests) errors
- Requests fail intermittently
- Error messages mention rate limit

**Solutions:**

1. **Add API Key**:
   - API keys typically have higher rate limits
   - Set `DADOS_GOV_BR_API_KEY` environment variable (or `CKAN_DADOS_GOV_BR_API_KEY` for backward compatibility)

2. **Implement Backoff**:
   - Connector includes automatic retry with exponential backoff
   - Check retry configuration in connector code

3. **Reduce Request Frequency**:
   - Batch requests where possible
   - Use pagination to limit request size

#### Issue 5: Test Failures

**Symptoms:**
- Integration tests fail
- Tests skip with "No CKAN instance available"

**Diagnosis:**

```bash
# Check test connectivity (using Django shell)
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.tests.utils.ckan_test_helpers import ckan_available
print(f'CKAN Available: {ckan_available()}')
EOF

# Run connectivity test (using Django shell)
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.tests.utils.ckan_test_helpers import verify_ckan_connection
result = verify_ckan_connection()
print(f'Connection Verified: {result}')
EOF
```

**Solutions:**

1. **Check Test Configuration**:
   ```bash
   # Verify test helpers can find instances (using Django shell)
   docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
   from hub.apps.integrations.tests.utils.ckan_test_helpers import get_test_ckan_config
   config = get_test_ckan_config()
   print(f'Test Config: {config.base_url if config else None}')
   EOF
   ```

2. **Verify Environment Variables**:
   ```bash
   docker compose exec api-service env | grep CKAN
   ```

3. **Check Network Access**:
   ```bash
   docker compose exec api-service curl -I https://demo.ckan.org/api/3/action/status_show
   ```

### Diagnostic Commands

**Check Connector Status:**

```bash
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.base import MarketplaceType

# Check if connector is registered
print(f'Marketplace Connector Registered: {MarketplaceConnectorFactory.is_supported(MarketplaceType.CKAN_INSTANCE)}')

# List registered instances
from hub.apps.integrations.config.marketplace_instances import MARKETPLACE_INSTANCES
print(f'Registered Instances: {list(MARKETPLACE_INSTANCES.keys())}')
EOF
```

**Test Connector Creation:**

```bash
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.factory import MarketplaceConnectorFactory

try:
    connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance('dados.gov.br')
    # Or use backward-compatible method (deprecated):
    # connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance('dados.gov.br')
    print(f'✓ Connector created successfully')
    print(f'  Base URL: {connector.base_url}')
    print(f'  Connector Type: {type(connector).__name__}')  # Should be DadosGovBrConnector for dados.gov.br
    # Check if connector has jwt_token (Swagger) or api_key (CKAN)
    if hasattr(connector, 'jwt_token'):
        print(f'  JWT Token Set: {connector.jwt_token is not None}')
    elif hasattr(connector, 'api_key'):
        print(f'  API Key Set: {connector.api_key is not None}')
    print(f'  Supported Directions: {connector.supported_sync_directions}')
except Exception as e:
    print(f'✗ Error creating connector: {e}')
EOF
```

**Test Connection:**

```bash
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.factory import MarketplaceConnectorFactory

connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance('dados.gov.br')
# Or use backward-compatible method (deprecated):
# connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance('dados.gov.br')
try:
    result = connector.test_connection()
    print(f'✓ Connection test: {result}')
except Exception as e:
    print(f'✗ Connection test failed: {e}')
EOF
```

---

## Monitoring

### Key Metrics

The Marketplace connector system exposes metrics for monitoring:

**Connector Metrics:**
- `ckan_connector_requests_total` - Total requests to marketplace instances
- `ckan_connector_request_duration_seconds` - Request duration
- `ckan_connector_errors_total` - Error count by type
- `ckan_connector_circuit_breaker_state` - Circuit breaker state (0=closed, 1=open)

**Instance-Specific Metrics:**
- `ckan_instance_requests_total{instance="dados.gov.br"}` - Requests per instance
- `ckan_instance_errors_total{instance="dados.gov.br"}` - Errors per instance

### Accessing Metrics

```bash
# Prometheus metrics endpoint
curl http://localhost:8000/metrics | grep ckan

# Query specific metrics
curl http://localhost:9090/api/v1/query?query=ckan_connector_requests_total
```

### Logging

**Structured Logging:**

The connector uses structured logging with correlation IDs:

```python
import logging
logger = logging.getLogger('hub.apps.integrations.connectors.ckan_connector')

# Logs include:
# - Instance name
# - Operation type
# - Request duration
# - Error details
# - Circuit breaker state
```

**View Logs:**

```bash
# All Marketplace connector logs
docker compose logs api-service | grep ckan

# Follow logs
docker compose logs -f api-service | grep ckan

# Filter by instance
docker compose logs api-service | grep "dados.gov.br"
```

### Health Checks

**Service Health:**

```bash
# Check API service health
curl http://localhost:8000/health

# Check Marketplace connector availability (using Django shell)
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.base import MarketplaceType
print(f'Marketplace Connector Available: {MarketplaceConnectorFactory.is_supported(MarketplaceType.CKAN_INSTANCE)}')
EOF
```

**Instance Health:**

```bash
# Test connection to each instance (using Django shell)
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.config.ckan_instances import CKAN_INSTANCES
from hub.apps.integrations.factory import MarketplaceConnectorFactory

for name, config in CKAN_INSTANCES.items():
    try:
        connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(name)
        result = connector.test_connection()
        print(f'{name}: {"✓ Healthy" if result else "✗ Unhealthy"}')
    except Exception as e:
        print(f'{name}: ✗ Error - {e}')
EOF
```

### Alerting

**Recommended Alerts:**

1. **Circuit Breaker Open**:
   - Alert when circuit breaker is open for >5 minutes
   - Indicates persistent connectivity issues

2. **High Error Rate**:
   - Alert when error rate >10% over 5 minutes
   - Indicates API issues or rate limiting

3. **High Latency**:
   - Alert when p95 latency >5 seconds
   - Indicates performance degradation

4. **Instance Unavailable**:
   - Alert when instance health check fails >3 times
   - Indicates instance outage

**Example Alert Rules (Prometheus):**

```yaml
groups:
  - name: ckan_connector
    rules:
      - alert: CKANCircuitBreakerOpen
        expr: ckan_connector_circuit_breaker_state == 1
        for: 5m
        annotations:
          summary: "Marketplace connector circuit breaker is open"

      - alert: CKANHighErrorRate
        expr: rate(ckan_connector_errors_total[5m]) / rate(ckan_connector_requests_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "Marketplace connector error rate is high"
```

---

## Security Best Practices

### API Key / JWT Token Management

#### 1. Never Commit API Keys or JWT Tokens

**❌ Bad:**
```python
# Never hardcode API keys
api_key = "abc123..."
```

**✅ Good:**
```python
# Use environment variables (new name preferred, backward compatibility supported)
api_key = os.getenv('DADOS_GOV_BR_API_KEY') or os.getenv('CKAN_DADOS_GOV_BR_API_KEY', '')
```

#### 2. Use Secrets Management

**Development:**
- Store in `.env.dev` (gitignored)
- Use `.env.test.ckan` for test credentials (gitignored)

**Staging/Production:**
- Use secrets management system (AWS Secrets Manager, HashiCorp Vault, etc.)
- Never store in code or configuration files
- Rotate API keys regularly

**Docker Compose:**
```yaml
# Use environment variable from secrets
api-service:
  environment:
    - DADOS_GOV_BR_API_KEY=${DADOS_GOV_BR_API_KEY}
    # Backward compatibility (deprecated)
    - CKAN_DADOS_GOV_BR_API_KEY=${CKAN_DADOS_GOV_BR_API_KEY:-${DADOS_GOV_BR_API_KEY}}
```

**Kubernetes:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ckan-secrets
type: Opaque
stringData:
  DADOS_GOV_BR_API_KEY: <api-key>
  # Backward compatibility (deprecated)
  CKAN_DADOS_GOV_BR_API_KEY: <api-key>
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: api-service
        env:
        - name: DADOS_GOV_BR_API_KEY
          valueFrom:
            secretKeyRef:
              name: marketplace-secrets
              key: DADOS_GOV_BR_API_KEY
        # Backward compatibility (deprecated)
        - name: CKAN_DADOS_GOV_BR_API_KEY
          valueFrom:
            secretKeyRef:
              name: marketplace-secrets
              key: CKAN_DADOS_GOV_BR_API_KEY
```

#### 3. API Key Rotation

**Rotation Procedure:**

1. **Generate New API Key**:
   - Visit CKAN instance (e.g., https://dados.gov.br)
   - Generate new API key
   - Keep old key active temporarily

2. **Update Environment Variable**:
   ```bash
   # Update in secrets manager or .env file
   DADOS_GOV_BR_API_KEY=new-api-key-here
   # Backward compatibility (deprecated)
   # CKAN_DADOS_GOV_BR_API_KEY=new-api-key-here
   ```

3. **Restart Service**:
   ```bash
   docker compose restart api-service
   ```

4. **Verify New Key Works**:
   ```bash
   docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
   from hub.apps.integrations.factory import MarketplaceConnectorFactory
   connector = MarketplaceConnectorFactory.create_marketplace_connector_from_instance('dados.gov.br')
   # Or use backward-compatible method (deprecated):
   # connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance('dados.gov.br')
   result = connector.test_connection()
   print(f'Connection test: {result}')
   EOF
   ```

5. **Revoke Old Key**:
   - After verification, revoke old API key in CKAN instance

**Rotation Schedule:**
- Rotate API keys every 90 days
- Rotate immediately if key is compromised
- Document rotation in change log

#### 4. Principle of Least Privilege

- Use API keys with minimal required permissions
- For harvest-only operations, read-only permissions are sufficient
- Never use admin-level API keys unless absolutely necessary

#### 5. Audit API Key Usage

**Monitor API Key Access:**

```bash
# Check API key usage in logs
docker compose logs api-service | grep "CKAN.*API.*key"

# Monitor failed authentication attempts
docker compose logs api-service | grep "permission\|unauthorized\|403"
```

**Review Access Logs:**
- Check CKAN instance access logs (if available)
- Monitor for unusual access patterns
- Alert on multiple failed authentication attempts

#### 6. Secure Storage

**Environment Files:**
- Use `.gitignore` to exclude `.env*` files
- Set file permissions: `chmod 600 .env.dev`
- Never share API keys via email or chat

**Secrets Managers:**
- Use encrypted storage
- Enable access logging
- Use IAM roles for access control
- Rotate encryption keys regularly

#### 7. Network Security

**Firewall Rules:**
- Allow outbound HTTPS (443) to marketplace instances
- Restrict inbound connections
- Use VPN for production environments if required

**TLS/SSL:**
- Always use HTTPS for CKAN API calls
- Verify SSL certificates
- Use certificate pinning for production if supported

### Security Checklist

- [ ] API keys / JWT tokens stored in secrets manager (not code)
- [ ] API keys / JWT tokens rotated every 90 days
- [ ] Environment files excluded from git (`.gitignore`)
- [ ] File permissions set correctly (`chmod 600`)
- [ ] JWT tokens validated for dados.gov.br Swagger API
- [ ] Connector type correctly configured (`swagger` for dados.gov.br, `ckan` for others)
- [ ] API keys have minimal required permissions
- [ ] Access logs monitored
- [ ] Failed authentication attempts alerted
- [ ] Network firewall rules configured
- [ ] TLS/SSL enabled for all connections
- [ ] Security updates applied regularly

---

## Maintenance

### Regular Maintenance Tasks

#### Weekly

- [ ] Review connector logs for errors
- [ ] Check circuit breaker state
- [ ] Verify instance availability
- [ ] Review metrics for anomalies

#### Monthly

- [ ] Review API key usage
- [ ] Check for CKAN instance updates/changes
- [ ] Review and update documentation
- [ ] Run full test suite

#### Quarterly

- [ ] Rotate API keys
- [ ] Review security practices
- [ ] Update connector dependencies
- [ ] Performance review

### Updating Instance Configuration

To add a new marketplace instance:

1. **Update Instance Registry** (`hub/apps/integrations/config/marketplace_instances.py`):

```python
MARKETPLACE_INSTANCES["new-instance.com"] = MarketplaceInstanceConfig(
    name="new-instance.com",
    base_url="https://new-instance.com",
    country="XX",
    language="en-US",
    organization="Organization Name",
    swagger_url="https://new-instance.com/api/3/swagger.json",
    api_key_env_var="CKAN_NEW_INSTANCE_API_KEY",  # Optional
    is_production=False,
    is_test_default=False,
)
```

2. **Add Environment Variable** (if API key needed):

```bash
# In .env.dev or secrets manager
CKAN_NEW_INSTANCE_API_KEY=api-key-here
```

3. **Update Documentation**:
   - Update this runbook
   - Update test README
   - Update instance list

4. **Test Configuration**:

```bash
docker compose exec api-service bash -c "cd /app/hub && python manage.py shell" << 'EOF'
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
config = get_ckan_instance_config('new-instance.com')
print(f'Instance configured: {config.base_url}')
EOF
```

### Backup and Recovery

**Configuration Backup:**

```bash
# Backup instance configuration
cp hub/apps/integrations/config/marketplace_instances.py \
   hub/apps/integrations/config/marketplace_instances.py.backup_$(date +%Y%m%d)
```

**Recovery:**

```bash
# Restore configuration
cp hub/apps/integrations/config/marketplace_instances.py.backup_YYYYMMDD \
   hub/apps/integrations/config/marketplace_instances.py

# Restart service
docker compose restart api-service
```

---

## References

- [CKAN API Documentation](https://docs.ckan.org/en/latest/api/)
- [Marketplace Test README](../hub/apps/integrations/tests/README_MARKETPLACE_TESTS.md)
- [Instance Configuration](../hub/apps/integrations/config/marketplace_instances.py)
- [Connector Implementation](../hub/apps/integrations/connectors/ckan_connector.py)
- [Factory Implementation](../hub/apps/integrations/factory.py)
- [Monitoring Guide](./MONITORING.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)

---

## Support

For issues or questions:

1. Check this runbook for troubleshooting steps
2. Review test documentation: `hub/apps/integrations/tests/README_MARKETPLACE_TESTS.md`
3. Check logs: `docker compose logs api-service | grep ckan`
4. Run diagnostic commands (see Troubleshooting section)
5. Contact DevOps team or create issue in repository

---

**Last Updated**: 2025-01-15
**Version**: 1.0
**Maintainer**: DevOps Team

