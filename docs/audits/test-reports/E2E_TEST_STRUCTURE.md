# E2E Test Structure and Verification Framework

## Overview

The E2E test suite provides comprehensive end-to-end testing of the Data Interoperability Hub, verifying all services, integrations, and state consistency across the entire system.

## Test Statistics

- **Total Tests**: 361
- **Passing**: 360 (99.7%)
- **Skipped**: 1 (intentional - documented limitation)
- **Test Files**: 33
- **Test Categories**: 15+

## Test Structure

### Base Test Class: `E2ETestBase`

All E2E tests inherit from `E2ETestBase` in `conftest.py`, which provides:

1. **Automatic Service Health Checks**
   - Verifies all required services are available before running tests
   - Skips tests if services are unavailable
   - Services checked: Compliance, DQ, DataContract, Semantic

2. **Common Setup**
   - Creates test tenant
   - Creates test user with proper authentication
   - Configures API client with authentication
   - Sets up S3/MinIO bucket if needed

3. **Helper Methods**
   - Asset creation and management
   - File upload/download operations
   - Dataset operations
   - Contract operations
   - Compliance and DQ checks
   - Marketplace operations

## Comprehensive State Verification

The E2E test suite verifies state across all system components:

### 1. Database State Verification

**Methods:**
- `verify_asset_state()` - Verifies asset status, DQ status, compliance status, and custom fields
- `verify_contract_state()` - Verifies contract status, validation status, normalization status
- `verify_job_completion()` - Verifies job status and completion
- `verify_entitlement_created()` - Verifies marketplace entitlements

**What's Verified:**
- Model state (status, relationships, fields)
- Database constraints
- Foreign key relationships
- Optimistic locking (version fields)

**Example:**
```python
self.verify_asset_state(
    asset_id,
    status=AssetStatus.ACTIVE,
    dq_status=DQStatus.PASS,
    compliance_status=ComplianceStatus.PASS
)
```

### 2. S3/MinIO Storage Verification

**Methods:**
- `verify_file_in_s3()` - Verifies file exists in S3 with correct content and metadata

**What's Verified:**
- File existence in S3 bucket
- File size matches expected value
- File content matches expected content
- Storage path correctness

**Example:**
```python
self.verify_file_in_s3(
    file_id,
    expected_content=test_content,
    expected_size=len(test_content)
)
```

### 3. Redis/Job Queue Verification

**Methods:**
- `verify_job_completion()` - Verifies job status in Redis queue

**What's Verified:**
- Job status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- Job completion within timeout
- Job result data

**Example:**
```python
self.verify_job_completion(
    job_id,
    expected_status=JobStatus.COMPLETED,
    max_wait=120
)
```

### 4. RDF/Fuseki Triple Store Verification

**Methods:**
- `verify_rdf_triples()` - Verifies RDF triples exist in Fuseki
- `wait_for_semantic_mapping()` - Waits for semantic resource mapping

**What's Verified:**
- RDF triples exist for resource URI
- Expected number of triples
- Expected predicates (properties)
- Semantic resource creation and status

**Example:**
```python
self.verify_rdf_triples(
    resource_uri,
    expected_triples_count=5,
    expected_predicates=['hub:name', 'hub:status']
)
```

### 5. Audit Log Verification

**Methods:**
- `verify_audit_log()` - Verifies audit log entry created

**What's Verified:**
- Audit event exists for action
- Resource type matches
- Resource ID matches
- Additional fields (result, user, etc.)

**Example:**
```python
self.verify_audit_log(
    action='ASSET_ACTIVATED',
    resource_type='ASSET',
    resource_id=asset_id,
    result='SUCCESS'
)
```

### 6. Semantic Resource Verification

**Methods:**
- `verify_semantic_resource()` - Verifies semantic resource created and mapped
- `verify_cross_service_consistency()` - Verifies consistency across all services

**What's Verified:**
- Semantic resource exists in database
- Semantic resource status (ACTIVE, DEGRADED)
- URI resolution works
- RDF triples exist in Fuseki

**Example:**
```python
self.verify_semantic_resource(
    resource_type='ASSET',
    resource_id=asset_id,
    expected_status='ACTIVE'
)
```

## Real Service Integration

All E2E tests use **real services** (no mocks). The following services are tested:

### Core Services

1. **PostgreSQL Database**
   - Tested via Django ORM
   - All model operations verified
   - Transaction isolation verified

2. **Redis (Job Queue)**
   - Tested via django-rq
   - Job creation, execution, completion verified
   - Job status tracking verified

3. **MinIO (S3 Storage)**
   - Tested via boto3
   - File upload/download verified
   - File content and metadata verified

4. **Apache Jena Fuseki (Triple Store)**
   - Tested via SPARQL queries
   - RDF triple storage verified
   - SPARQL query execution verified

### Microservices

5. **Semantic Service** (FastAPI)
   - Health checks verified
   - URI resolution verified
   - SPARQL endpoint verified
   - RDF mapping verified

6. **DataContract Service** (FastAPI)
   - Health checks verified
   - Contract normalization verified
   - Contract validation verified
   - Contract migration verified

7. **Compliance Service** (FastAPI)
   - Health checks verified
   - PII detection verified
   - Compliance scanning verified
   - Risk calculation verified

8. **DQ Service** (FastAPI)
   - Health checks verified
   - DQ run execution verified
   - DQ result processing verified

### Django API Service

9. **Django API Service**
   - All REST endpoints tested
   - Authentication/authorization tested
   - Multi-tenant isolation tested
   - Error handling tested

## Test Categories

### 1. Onboarding Flows
- **Data-First Onboarding**: Complete journey from file upload to asset activation
- **Contract-First Onboarding**: Complete journey from contract creation to asset activation
- **Contract-Only Onboarding**: Contract creation and activation without data

### 2. Marketplace Flows
- **Publishing**: Create listings, publish to marketplace
- **Browsing**: Search, filter, view listings
- **Purchasing**: Create orders, approve/reject, create entitlements

### 3. Multi-Tenant Isolation
- **Data Isolation**: Verify tenants cannot access each other's data
- **Security Boundaries**: Verify permission checks
- **Cross-Tenant Access**: Verify entitlements work correctly

### 4. Semantic Layer
- **URI Resolution**: Verify stable URIs resolve to JSON-LD
- **RDF Mapping**: Verify resources mapped to RDF triples
- **SPARQL Queries**: Verify SPARQL query execution

### 5. Audit & Compliance
- **Audit Logging**: Verify all actions logged
- **Compliance Scanning**: Verify PII detection and risk calculation
- **Compliance Workflows**: Verify compliance officer workflows

### 6. Error Handling
- **Error Codes**: Verify correct HTTP status codes
- **Error Format**: Verify consistent error response format
- **Service Failures**: Verify graceful degradation

### 7. Health & Observability
- **Health Checks**: Verify all service health endpoints
- **Metrics**: Verify Prometheus metrics endpoint
- **API Documentation**: Verify OpenAPI/Swagger/ReDoc endpoints

## Verification Framework

### Cross-Service Consistency

The `verify_cross_service_consistency()` method verifies that resource state is consistent across:
- Database (Django models)
- Semantic store (RDF triples in Fuseki)
- Semantic resources (SemanticResource model)

### Service Health Checks

Before running tests, the framework:
1. Checks service health endpoints
2. Skips tests if services unavailable
3. Provides clear error messages for missing services

### Retry Logic

The framework includes retry logic for:
- Service calls (exponential backoff)
- Semantic mapping (waits for async operations)
- Job completion (polls until complete)

## Test Execution

### Prerequisites

1. **Docker Compose Services Running:**
   ```bash
   docker-compose up -d
   ```

2. **Services Required:**
   - PostgreSQL
   - Redis
   - MinIO
   - Fuseki
   - Semantic Service
   - DataContract Service
   - Compliance Service
   - DQ Service

3. **Environment Variables:**
   - `DJANGO_SETTINGS_MODULE=hub.settings`
   - Service URLs (defaults to localhost)

### Running Tests

```bash
# All E2E tests
pytest tests/e2e/ -v

# Specific test file
pytest tests/e2e/test_semantic_layer.py -v

# Specific test
pytest tests/e2e/test_semantic_layer.py::SemanticLayerE2ETest::test_uri_resolution_for_field -v

# With coverage
pytest tests/e2e/ --cov=hub --cov-report=html
```

## Test Limitations

See `TEST_LIMITATIONS.md` for documented limitations:
- Tenant suspension middleware (Django test client limitation)
- Semantic service timing/consistency (Fuseki eventual consistency)
- Service restart requirements

## Best Practices

1. **Use Real Services**: Never mock services in E2E tests
2. **Verify State**: Always verify state across all systems
3. **Clean Up**: Tests should be independent and clean up after themselves
4. **Service Health**: Check service health before critical operations
5. **Retry Logic**: Use retry logic for eventual consistency
6. **Clear Assertions**: Provide clear error messages in assertions

## Maintenance

### Adding New Tests

1. Inherit from `E2ETestBase`
2. Use helper methods for common operations
3. Verify state across all systems
4. Document any limitations

### Updating Verification Methods

1. Update `E2ETestBase` in `conftest.py`
2. Ensure backward compatibility
3. Update documentation
4. Update existing tests if needed

## Coverage Summary

### Services Covered
- ✅ PostgreSQL (via Django ORM)
- ✅ Redis (via django-rq)
- ✅ MinIO/S3 (via boto3)
- ✅ Fuseki (via SPARQL)
- ✅ Semantic Service (via HTTP)
- ✅ DataContract Service (via HTTP)
- ✅ Compliance Service (via HTTP)
- ✅ DQ Service (via HTTP)

### State Verification
- ✅ Database state
- ✅ S3 storage
- ✅ Redis/Job queue
- ✅ RDF triples
- ✅ Audit logs
- ✅ Semantic resources

### Integration Points
- ✅ All onboarding flows
- ✅ All marketplace flows
- ✅ All semantic operations
- ✅ All compliance operations
- ✅ All DQ operations
- ✅ All audit operations

## Conclusion

The E2E test suite provides comprehensive verification of the entire system, ensuring:
- All services work correctly
- State is consistent across all systems
- Real-world scenarios are tested
- Integration points are verified
- Error handling works correctly

The framework is designed to be maintainable, extensible, and reliable, providing confidence in system behavior before deployment.

