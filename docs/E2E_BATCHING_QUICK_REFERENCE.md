# E2E Test Batching - Quick Reference

## Problem Solved
E2E tests were taking several hours to run. Now they can be run in 5 batches, reducing total time significantly when run in parallel.

## Quick Commands

### Using the Batch Script (Recommended)

```bash
# Run Batch 1 (Core API, Contracts, Assets) - ~5 tests
./scripts/run_e2e_tests_batch.sh 1

# Run Batch 2 (Worker Service, Jobs, DQ, Compliance) - ~16 tests
./scripts/run_e2e_tests_batch.sh 2

# Run Batch 3 (Email, Notifications, Rate Limiting) - ~8 tests
./scripts/run_e2e_tests_batch.sh 3

# Run Batch 4 (Tenant Config, Personas, CLI) - ~25 tests
./scripts/run_e2e_tests_batch.sh 4

# Run Batch 5 (Marketplace, Semantic, Monitoring, Edge Cases) - ~17 tests
./scripts/run_e2e_tests_batch.sh 5

# Run all E2E tests
./scripts/run_e2e_tests_batch.sh all
```

### Using pytest directly

```bash
# Run a specific batch
pytest tests/e2e/ -m e2e_batch1 -v

# Run multiple batches
pytest tests/e2e/ -m "e2e_batch1 or e2e_batch2" -v

# Run all batches
pytest tests/e2e/ -m "e2e_batch1 or e2e_batch2 or e2e_batch3 or e2e_batch4 or e2e_batch5" -v
```

## Batch Distribution

- **Batch 1:** 5 tests (Core API, Contracts, Assets)
- **Batch 2:** 16 tests (Worker Service, Jobs, DQ, Compliance)
- **Batch 3:** 8 tests (Email, Notifications, Rate Limiting)
- **Batch 4:** 25 tests (Tenant Config, Personas, CLI)
- **Batch 5:** 17 tests (Marketplace, Semantic, Monitoring, Edge Cases)

**Total:** 71+ tests organized in batches (out of 641 total E2E tests)

## Parallel Execution

Run batches in parallel on different terminals to reduce total time:

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

In CI/CD pipelines, you can run batches in parallel using a matrix strategy:

```yaml
# Example GitHub Actions
strategy:
  matrix:
    batch: [1, 2, 3, 4, 5]
steps:
  - run: pytest tests/e2e/ -m e2e_batch${{ matrix.batch }} -v
```

## See Also

- `docs/E2E_TEST_BATCHING.md` - Detailed documentation
- `README_E2E_BATCHING.md` - Quick start guide

