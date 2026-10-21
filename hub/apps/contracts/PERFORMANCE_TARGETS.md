# Performance Targets for Enhanced Contract Normalization & Semantic Mapping (GAP-11.2.1)

This document defines performance targets for Phase 7+ features including enhanced normalization, RDF mapping, and standard vocabulary integration.

## Table of Contents

1. [Normalization Performance](#normalization-performance)
2. [RDF Mapping Performance](#rdf-mapping-performance)
3. [SPARQL Query Performance](#sparql-query-performance)
4. [API Response Time](#api-response-time)
5. [Storage Impact](#storage-impact)

---

## Normalization Performance

### Target Metrics

| Operation | Target P50 | Target P95 | Target P99 | Notes |
|-----------|-----------|------------|------------|-------|
| **ODCS Normalization** | < 500ms | < 1s | < 2s | For contracts with up to 100 fields |
| **DataContract.com Normalization** | < 500ms | < 1s | < 2s | For contracts with up to 100 fields |
| **Field Property Extraction** | < 100ms | < 200ms | < 500ms | Per field (semantic_type, format, pattern, etc.) |
| **Large Contract Normalization** | < 5s | < 10s | < 20s | For contracts with 1000+ fields |
| **Normalization Status Calculation** | < 50ms | < 100ms | < 200ms | Coverage calculation |

### Test Scenarios

1. **Small Contract** (10 fields, basic sections)
   - Target: < 200ms P95
   - Sections: info, schema, quality (1 rule), compliance (basic)

2. **Medium Contract** (100 fields, all sections)
   - Target: < 1s P95
   - Sections: info (owners, tags), schema (100 fields), quality (10 rules), compliance (full), lifecycle, marketplace

3. **Large Contract** (1000 fields, all sections)
   - Target: < 10s P95
   - Sections: All sections with maximum complexity

4. **Field Property Extraction**
   - Target: < 200ms P95 per field
   - Properties: semantic_type, format, pattern, enum, default, min/max length/value, metadata

---

## RDF Mapping Performance

### Target Metrics

| Operation | Target P50 | Target P95 | Target P99 | Notes |
|-----------|-----------|------------|------------|-------|
| **Contract to RDF Mapping** | < 1s | < 2s | < 5s | For contracts with up to 100 fields |
| **Field Mapping** | < 10ms | < 20ms | < 50ms | Per field with all properties |
| **Quality Rule Mapping** | < 50ms | < 100ms | < 200ms | Per rule with DQV links |
| **Compliance Policy Mapping** | < 50ms | < 100ms | < 200ms | With DPV links |
| **Lifecycle Policy Mapping** | < 50ms | < 100ms | < 200ms | With PROV-O links |
| **Marketplace Policy Mapping** | < 50ms | < 100ms | < 200ms | With ODRL links |
| **Large Contract Mapping** | < 10s | < 20s | < 30s | For contracts with 1000+ fields |

### Test Scenarios

1. **Small Contract Mapping** (10 fields, basic sections)
   - Target: < 500ms P95
   - RDF triples: ~50-100 triples

2. **Medium Contract Mapping** (100 fields, all sections)
   - Target: < 2s P95
   - RDF triples: ~500-1000 triples

3. **Large Contract Mapping** (1000 fields, all sections)
   - Target: < 20s P95
   - RDF triples: ~5000-10000 triples

4. **Standard Vocabulary Integration**
   - Target: < 100ms P95 per section
   - Vocabularies: DQV, DPV, PROV-O, ODRL, SHACL, Schema.org, FOAF

---

## SPARQL Query Performance

### Target Metrics

| Query Type | Target P50 | Target P95 | Target P99 | Notes |
|------------|-----------|------------|------------|-------|
| **Simple SELECT** | < 100ms | < 200ms | < 500ms | Single contract, basic filters |
| **Quality Rules Query** | < 200ms | < 500ms | < 1s | With DQV vocabulary |
| **Compliance Policy Query** | < 200ms | < 500ms | < 1s | With DPV vocabulary |
| **Field Validation Query** | < 200ms | < 500ms | < 1s | With SHACL vocabulary |
| **Complex JOIN Query** | < 500ms | < 1s | < 2s | Multiple contracts, multiple sections |
| **Aggregation Query** | < 500ms | < 1s | < 2s | COUNT, GROUP BY operations |

### Test Scenarios

1. **Find Contracts with Quality Rules**
   - Target: < 500ms P95
   - Query: SELECT contracts with completeness quality rules (DQV)

2. **Find Contracts with GDPR Compliance**
   - Target: < 500ms P95
   - Query: SELECT contracts with GDPR jurisdiction (DPV)

3. **Find Fields with Validation Constraints**
   - Target: < 500ms P95
   - Query: SELECT fields with min/max length (SHACL)

4. **Complex Multi-Section Query**
   - Target: < 1s P95
   - Query: SELECT contracts with quality rules AND compliance policies

---

## API Response Time

### Target Metrics

| Endpoint | Target P50 | Target P95 | Target P99 | Notes |
|----------|-----------|------------|------------|-------|
| **GET /contracts** | < 100ms | < 300ms | < 500ms | List with filtering/sorting |
| **GET /contracts/{id}** | < 200ms | < 500ms | < 1s | Retrieve with computed fields |
| **POST /contracts** | < 500ms | < 1s | < 2s | Create with normalization |
| **PUT /contracts/{id}** | < 500ms | < 1s | < 2s | Update with normalization |
| **GET /contracts/{id}/schema_fields** | < 100ms | < 300ms | < 500ms | Computed field properties |

### Test Scenarios

1. **List Contracts with Filtering**
   - Target: < 300ms P95
   - Filters: owner_email, tag, quality_profile, compliance_regime
   - Sorting: quality_score, compliance_risk, created_at

2. **Retrieve Contract with Computed Fields**
   - Target: < 500ms P95
   - Fields: owners, tags, quality_rules, compliance_policy, lifecycle_policy, marketplace_policy, schema_fields

3. **Create Contract with Normalization**
   - Target: < 1s P95
   - Includes: normalization, field property extraction, status calculation

---

## Storage Impact

### Target Metrics

| Resource | Baseline | With Enhanced Features | Increase | Notes |
|----------|----------|----------------------|----------|-------|
| **Contract JSON Size** | ~10KB | ~15KB | +50% | For medium contract (100 fields) |
| **RDF Triple Count** | ~100 | ~500 | +400% | For medium contract with all sections |
| **Fuseki Storage** | ~50KB | ~200KB | +300% | Per contract (compressed) |
| **Database Index Size** | ~5KB | ~8KB | +60% | For JSON field indexes |

### Test Scenarios

1. **Small Contract Storage**
   - Baseline: ~5KB JSON, ~50 triples
   - Enhanced: ~7KB JSON, ~200 triples
   - Increase: +40% JSON, +300% triples

2. **Medium Contract Storage**
   - Baseline: ~10KB JSON, ~100 triples
   - Enhanced: ~15KB JSON, ~500 triples
   - Increase: +50% JSON, +400% triples

3. **Large Contract Storage**
   - Baseline: ~50KB JSON, ~500 triples
   - Enhanced: ~75KB JSON, ~2500 triples
   - Increase: +50% JSON, +400% triples

---

## Performance Test Implementation

### Test Files

1. **`hub/apps/contracts/tests/test_performance_normalization.py`**
   - Tests normalization performance for small/medium/large contracts
   - Validates field property extraction performance
   - Measures normalization status calculation time

2. **`services/semantic-service/tests/test_performance_mapping.py`**
   - Tests RDF mapping performance for small/medium/large contracts
   - Validates standard vocabulary integration performance
   - Measures triple generation time

3. **`services/semantic-service/tests/test_performance_sparql.py`**
   - Tests SPARQL query performance for various query types
   - Validates query execution time with standard vocabularies
   - Measures query result size impact

4. **`hub/apps/contracts/tests/test_performance_api.py`**
   - Tests API response time for contract endpoints
   - Validates filtering and sorting performance
   - Measures computed field generation time

### Running Performance Tests

```bash
# Run normalization performance tests
pytest hub/apps/contracts/tests/test_performance_normalization.py -v

# Run RDF mapping performance tests
pytest services/semantic-service/tests/test_performance_mapping.py -v

# Run SPARQL query performance tests
pytest services/semantic-service/tests/test_performance_sparql.py -v

# Run API performance tests
pytest hub/apps/contracts/tests/test_performance_api.py -v
```

---

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Normalization Latency**
   - Metric: `contract_normalization_duration_seconds`
   - Labels: `spec_type`, `contract_size`, `status`
   - Alert: P95 > 1s for medium contracts

2. **RDF Mapping Latency**
   - Metric: `contract_rdf_mapping_duration_seconds`
   - Labels: `contract_size`, `triple_count`
   - Alert: P95 > 2s for medium contracts

3. **SPARQL Query Latency**
   - Metric: `sparql_query_duration_seconds`
   - Labels: `query_type`, `result_count`
   - Alert: P95 > 1s for standard queries

4. **API Response Time**
   - Metric: `contract_api_response_time_seconds`
   - Labels: `endpoint`, `method`
   - Alert: P95 > 500ms for GET endpoints

5. **Storage Size**
   - Metric: `contract_storage_size_bytes`
   - Labels: `contract_size`
   - Alert: Storage growth > 100% baseline

---

## Optimization Strategies (GAP-11.2.2)

See [OPTIMIZATION_STRATEGIES.md](./OPTIMIZATION_STRATEGIES.md) for detailed optimization strategies.

---

## Storage Impact Analysis (GAP-11.2.3)

See [STORAGE_IMPACT_ANALYSIS.md](./STORAGE_IMPACT_ANALYSIS.md) for detailed storage impact analysis.

