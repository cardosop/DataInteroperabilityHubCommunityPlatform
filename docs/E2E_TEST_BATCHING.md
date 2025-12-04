# E2E Test Batching Guide

## Overview

E2E tests are organized into 5 batches to enable parallel execution and reduce overall test runtime. Each batch contains related tests that can run independently.

## Batch Organization

### Batch 1: Core API, Contracts, Assets
- REST API tests
- API documentation tests
- Contract operations
- Contract normalization
- Contract migration
- Asset operations
- Dataset operations
- File operations
- Schema inference

**Run:** `pytest tests/e2e/ -m e2e_batch1`

### Batch 2: Worker Service, Jobs, DQ, Compliance
- Worker service tests
- Job orchestration
- DQ service tests
- Compliance service tests
- Audit logging
- Audit compliance journeys

**Run:** `pytest tests/e2e/ -m e2e_batch2`

### Batch 3: Email, Notifications, Rate Limiting
- Email service tests
- Rate limiting tests
- Observability tests
- Health checks

**Run:** `pytest tests/e2e/ -m e2e_batch3`

### Batch 4: Tenant Config, Personas, CLI
- Tenant configuration tests
- Tenant management
- Persona tests (TENANT_ADMIN, DATA_PROVIDER, DATA_CONSUMER, AUDITOR, Platform Admin)
- CLI E2E tests
- Authentication
- User management
- Multi-tenant isolation

**Run:** `pytest tests/e2e/ -m e2e_batch4`

### Batch 5: Marketplace, Semantic, Monitoring, Edge Cases
- Marketplace comprehensive tests
- Marketplace listings
- Marketplace orders
- Marketplace purchase flow
- Entitlements
- Semantic layer
- GraphQL API
- Monitoring E2E tests
- Cross-capability E2E tests
- Complete user journeys
- Data first flows
- Error handling
- SDK Python tests

**Run:** `pytest tests/e2e/ -m e2e_batch5`

## Running Tests

### Using pytest directly:

```bash
# Run a specific batch
pytest tests/e2e/ -m e2e_batch1 -v

# Run all E2E tests
pytest tests/e2e/ -m e2e -v

# Run multiple batches
pytest tests/e2e/ -m "e2e_batch1 or e2e_batch2" -v
```

### Using the batch script:

```bash
# Run batch 1
./scripts/run_e2e_tests_batch.sh 1

# Run batch 2
./scripts/run_e2e_tests_batch.sh 2

# Run all batches
./scripts/run_e2e_tests_batch.sh all
```

### Running batches in parallel (if you have multiple machines):

```bash
# Terminal 1
pytest tests/e2e/ -m e2e_batch1 -v

# Terminal 2
pytest tests/e2e/ -m e2e_batch2 -v

# Terminal 3
pytest tests/e2e/ -m e2e_batch3 -v

# Terminal 4
pytest tests/e2e/ -m e2e_batch4 -v

# Terminal 5
pytest tests/e2e/ -m e2e_batch5 -v
```

## Estimated Runtime

- **Batch 1:** ~30-45 minutes
- **Batch 2:** ~20-30 minutes
- **Batch 3:** ~15-20 minutes
- **Batch 4:** ~25-35 minutes
- **Batch 5:** ~30-40 minutes
- **Total (sequential):** ~2-3 hours
- **Total (parallel):** ~30-45 minutes

## CI/CD Integration

In CI/CD, you can run batches in parallel:

```yaml
# Example GitHub Actions
strategy:
  matrix:
    batch: [1, 2, 3, 4, 5]
steps:
  - run: pytest tests/e2e/ -m e2e_batch${{ matrix.batch }} -v
```

## Adding New Tests

When adding new E2E tests, assign them to the appropriate batch by adding the marker:

```python
pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.e2e_batch1,  # Choose appropriate batch
]
```

Then run the marker script to update:

```bash
python3 scripts/add_e2e_batch_markers.py
```

