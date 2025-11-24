# External Dependencies Documentation

This document lists all external dependencies required for the Interoperable Data Hub MVP implementation.

**Last Updated**: 2025-01-15

---

## 1. DataContract CLI

### Purpose
DataContract CLI is used for validating, linting, and converting data contracts between ODCS and DataContract.com formats.

### Installation

#### Option 1: Docker Container (Recommended)
```bash
docker pull datacontract/datacontract-cli:latest
```

#### Option 2: npm Package
```bash
npm install -g @datacontract/cli
```

#### Option 3: Python Package
```bash
pip install datacontract
```

### Version
- **Minimum**: Latest stable version
- **Recommended**: Latest from https://github.com/datacontract/datacontract-cli

### Integration
- Wrapped in internal microservice: `datacontract-service`
- Exposes HTTP endpoints: `/validate`, `/lint`, `/convert`
- Timeout: 30-60 seconds (configurable)

### Documentation
- Official: https://cli.datacontract.com
- GitHub: https://github.com/datacontract/datacontract-cli
- GPT Reference: https://gpt.datacontract.com/sources/cli.datacontract.com

### Testing
```bash
# Test installation
datacontract --version

# Test validation
datacontract validate contract.yaml

# Test linting
datacontract lint contract.yaml

# Test conversion
datacontract convert contract.yaml --format odcs
```

---

## 2. Great Expectations (GX)

### Purpose
Great Expectations is used as one of two data quality engines for running DQ checks on datasets.

### Installation
```bash
pip install great-expectations>=0.18.0
```

### Version
- **Minimum**: 0.18.0
- **Recommended**: Latest stable version

### Integration
- Wrapped in DQ service adapter: `GreatExpectationsAdapter`
- Executes `intake_basic` profile
- Returns normalized DQ results

### Documentation
- Official: https://docs.greatexpectations.io/
- Python API: https://docs.greatexpectations.io/docs/guides/connecting_to_your_data/

### Testing
```python
import great_expectations as gx

# Test installation
print(gx.__version__)

# Basic usage example
context = gx.get_context()
# ... configure expectations
```

### Profile: `intake_basic`
The `intake_basic` profile includes:
- Type checks (column data types)
- Null ratio checks
- Uniqueness checks
- Range checks (min/max values)
- Row count validation

---

## 3. Soda

### Purpose
Soda is used as the second data quality engine (alternative to Great Expectations).

### Installation
```bash
pip install soda-core>=3.0.0
```

### Version
- **Minimum**: 3.0.0
- **Recommended**: Latest stable version

### Integration
- Wrapped in DQ service adapter: `SodaAdapter`
- Executes `intake_basic` profile
- Returns normalized DQ results (same format as GX)

### Documentation
- Official: https://docs.soda.io/
- Python API: https://docs.soda.io/soda-core/quick-start.html

### Testing
```python
from soda.scan import Scan

# Test installation
scan = Scan()
# ... configure checks
```

### Profile: `intake_basic`
The `intake_basic` profile includes:
- Type checks (column data types)
- Null ratio checks
- Uniqueness checks
- Range checks (min/max values)
- Row count validation

---

## 4. Apache Jena Fuseki

### Purpose
Apache Jena Fuseki is used as the RDF triple store for the semantic layer.

### Installation

#### Option 1: Docker (Recommended)
```bash
docker pull apache/jena-fuseki:latest
```

#### Option 2: Manual Installation
1. Download from: https://jena.apache.org/download/
2. Extract and configure
3. Start Fuseki server

### Version
- **Minimum**: Latest stable
- **Recommended**: Latest from Apache

### Integration
- Exposed via `fuseki` service in Docker Compose
- SPARQL endpoint: `http://fuseki:3030/sparql`
- Dataset: `hub` (configurable)

### Documentation
- Official: https://jena.apache.org/documentation/fuseki2/
- SPARQL: https://www.w3.org/TR/sparql11-query/

### Testing
```bash
# Test SPARQL endpoint
curl http://localhost:3030/$/ping

# Test SPARQL query
curl -X POST http://localhost:3030/hub/sparql \
  -H "Content-Type: application/sparql-query" \
  -d "SELECT * WHERE { ?s ?p ?o } LIMIT 10"
```

---

## 5. PostgreSQL

### Purpose
Primary relational database for all metadata, contracts, assets, users, etc.

### Installation

#### Option 1: Docker (Recommended)
```bash
docker pull postgres:16-alpine
```

#### Option 2: System Package
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-16

# macOS
brew install postgresql@16
```

### Version
- **Minimum**: PostgreSQL 16.0
- **Recommended**: Latest 16.x

### Extensions Required
- `uuid-ossp` (UUID generation)
- `pg_trgm` (text search)

### Testing
```bash
# Test connection
psql -h localhost -U hub -d hub -c "SELECT version();"

# Test extensions
psql -h localhost -U hub -d hub -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
```

---

## 6. Redis

### Purpose
Message queue backend for job orchestration (django-rq or Celery).

### Installation

#### Option 1: Docker (Recommended)
```bash
docker pull redis:7-alpine
```

#### Option 2: System Package
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis
```

### Version
- **Minimum**: Redis 7.0
- **Recommended**: Latest 7.x

### Testing
```bash
# Test connection
redis-cli ping

# Test queue
redis-cli lpush test-queue "test message"
```

---

## 7. MinIO (S3-compatible Storage)

### Purpose
S3-compatible object storage for file uploads (local development).

### Installation

#### Option 1: Docker (Recommended)
```bash
docker pull minio/minio:latest
```

#### Option 2: Binary
Download from: https://min.io/download

### Version
- **Minimum**: Latest stable
- **Recommended**: Latest from MinIO

### Configuration
- Access Key: `minio` (dev)
- Secret Key: `minio123` (dev)
- Bucket: `hub-files`
- Console: http://localhost:9001

### Testing
```bash
# Test MinIO
curl http://localhost:9000/minio/health/live

# Create bucket (via Python)
python -c "import boto3; s3 = boto3.client('s3', endpoint_url='http://localhost:9000', aws_access_key_id='minio', aws_secret_access_key='minio123'); s3.create_bucket(Bucket='hub-files')"
```

---

## 8. Python Dependencies

All Python dependencies are listed in `requirements.txt` and `requirements-dev.txt`.

### Key Dependencies
- **Django**: 4.2+ (REST API framework)
- **django-rq**: 2.10.0+ (Job queue)
- **strawberry-graphql**: 0.200.0+ (GraphQL)
- **structlog**: 24.1.0+ (Structured logging)
- **prometheus-client**: 0.20.0+ (Metrics)
- **opentelemetry**: 1.20.0+ (Distributed tracing)
- **PyJWT**: 2.8.0+ (JWT authentication)
- **boto3**: 1.34.0+ (S3 client)
- **pandas**: 2.1.0+ (Data processing)
- **rdflib**: 7.0.0+ (RDF processing)

### Installation
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## 9. Node.js Dependencies (for SDK Generation)

### Purpose
Node.js is required for generating JavaScript/TypeScript SDKs from OpenAPI specs.

### Installation
```bash
# Using nvm (recommended)
nvm install 22
nvm use 22

# Or system package
# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# macOS
brew install node@22
```

### Version
- **Minimum**: Node.js 22.0
- **Recommended**: Latest 22.x LTS

### Tools
- **openapi-generator**: For SDK generation
- **npm/yarn**: Package manager

### Testing
```bash
node --version
npm --version
```

---

## 10. Verification Checklist

Before starting implementation, verify all dependencies:

- [ ] DataContract CLI installed and tested
- [ ] Great Expectations installed (`pip install great-expectations`)
- [ ] Soda installed (`pip install soda-core`)
- [ ] PostgreSQL 16.x running (via Docker or system)
- [ ] Redis 7.x running (via Docker or system)
- [ ] MinIO running (via Docker)
- [ ] Apache Jena Fuseki running (via Docker)
- [ ] Python 3.11+ installed
- [ ] Node.js 22.x installed (for SDK generation)
- [ ] All Python dependencies installed (`pip install -r requirements.txt`)

---

## 11. Quick Start Verification

Run this script to verify all dependencies:

```bash
#!/bin/bash
echo "Verifying dependencies..."

# Python
python3 --version | grep -q "3.11" && echo "✅ Python 3.11+" || echo "❌ Python 3.11+ required"

# Docker
docker --version && echo "✅ Docker" || echo "❌ Docker required"

# DataContract CLI
datacontract --version 2>/dev/null && echo "✅ DataContract CLI" || echo "⚠️  DataContract CLI not found (will use Docker)"

# Python packages
python3 -c "import django; print('✅ Django', django.__version__)" 2>/dev/null || echo "❌ Django not installed"
python3 -c "import great_expectations; print('✅ Great Expectations')" 2>/dev/null || echo "❌ Great Expectations not installed"
python3 -c "import soda; print('✅ Soda')" 2>/dev/null || echo "❌ Soda not installed"

# Docker services
docker ps | grep -q postgres && echo "✅ PostgreSQL running" || echo "⚠️  PostgreSQL not running"
docker ps | grep -q redis && echo "✅ Redis running" || echo "⚠️  Redis not running"
docker ps | grep -q minio && echo "✅ MinIO running" || echo "⚠️  MinIO not running"
docker ps | grep -q fuseki && echo "✅ Fuseki running" || echo "⚠️  Fuseki not running"

echo "Verification complete!"
```

---

## 12. Troubleshooting

### DataContract CLI Issues
- **Issue**: CLI not found
- **Solution**: Use Docker container or install via npm/pip

### Great Expectations Issues
- **Issue**: Import errors
- **Solution**: Ensure Python 3.11+ and install with `pip install great-expectations`

### Soda Issues
- **Issue**: Import errors
- **Solution**: Install with `pip install soda-core`

### Fuseki Connection Issues
- **Issue**: Cannot connect to Fuseki
- **Solution**: Check Docker container is running and port 3030 is accessible

### PostgreSQL Connection Issues
- **Issue**: Cannot connect to database
- **Solution**: Check Docker container, credentials in .env.dev, and network connectivity

---

**Document Owner**: Engineering Team  
**Review Cycle**: Update when dependencies change

