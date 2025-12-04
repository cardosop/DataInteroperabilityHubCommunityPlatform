# Optimization Strategies for Enhanced Contract Normalization & Semantic Mapping (GAP-11.2.2)

This document outlines optimization strategies to meet performance targets for Phase 7+ features.

## Table of Contents

1. [Normalization Optimizations](#normalization-optimizations)
2. [RDF Mapping Optimizations](#rdf-mapping-optimizations)
3. [SPARQL Query Optimizations](#sparql-query-optimizations)
4. [API Response Optimizations](#api-response-optimizations)
5. [Caching Strategies](#caching-strategies)
6. [Database Optimizations](#database-optimizations)

---

## Normalization Optimizations

### 1. Lazy Field Property Extraction

**Strategy**: Extract field properties only when needed, not during initial normalization.

**Implementation**:
- Extract basic properties (name, data_type, nullable) during normalization
- Extract enhanced properties (semantic_type, format, pattern, etc.) on-demand
- Cache extracted properties in `hub_contract_json` for subsequent requests

**Expected Impact**: 30-50% reduction in normalization time for contracts with many fields.

### 2. Parallel Field Processing

**Strategy**: Process multiple fields in parallel during normalization.

**Implementation**:
- Use `concurrent.futures.ThreadPoolExecutor` for field property extraction
- Process fields in batches (e.g., 10 fields per batch)
- Merge results back into schema

**Expected Impact**: 40-60% reduction in normalization time for large contracts (1000+ fields).

### 3. Caching Normalized Contracts

**Strategy**: Cache normalized contracts based on original_raw hash.

**Implementation**:
- Compute hash of `original_raw` content
- Check cache before normalization
- Store normalized result in cache (TTL: 1 hour)
- Invalidate cache on contract update

**Expected Impact**: 90%+ reduction in normalization time for repeated normalizations.

### 4. Incremental Normalization

**Strategy**: Only re-normalize changed sections when contract is updated.

**Implementation**:
- Track which sections changed (info, schema, quality, etc.)
- Re-normalize only changed sections
- Merge with existing normalized contract

**Expected Impact**: 50-70% reduction in normalization time for contract updates.

---

## RDF Mapping Optimizations

### 1. Batch Triple Generation

**Strategy**: Generate RDF triples in batches instead of one-by-one.

**Implementation**:
- Collect all triples in memory first
- Use `rdflib.Graph.add()` in batches
- Minimize graph operations

**Expected Impact**: 20-30% reduction in RDF mapping time.

### 2. Lazy RDF Mapping

**Strategy**: Map contract to RDF only when needed (on-demand).

**Implementation**:
- Store contract in database without RDF mapping
- Map to RDF when:
  - SPARQL query is executed
  - Semantic service endpoint is called
  - Contract is published to marketplace
- Cache RDF graph in Redis (TTL: 1 hour)

**Expected Impact**: 100% reduction in RDF mapping time for contracts that are never queried.

### 3. Incremental RDF Updates

**Strategy**: Update only changed triples when contract is updated.

**Implementation**:
- Track which sections changed
- Remove old triples for changed sections
- Add new triples for changed sections
- Use SPARQL UPDATE for efficient updates

**Expected Impact**: 60-80% reduction in RDF update time for contract updates.

### 4. Standard Vocabulary Pre-computation

**Strategy**: Pre-compute standard vocabulary mappings and cache them.

**Implementation**:
- Cache DQV dimension mappings
- Cache DPV category/jurisdiction mappings
- Cache ODRL permission/prohibition mappings
- Cache SHACL property mappings
- Cache Schema.org type mappings
- Cache FOAF property mappings

**Expected Impact**: 10-20% reduction in RDF mapping time.

---

## SPARQL Query Optimizations

### 1. Query Result Caching

**Strategy**: Cache SPARQL query results for frequently executed queries.

**Implementation**:
- Cache query results in Redis (TTL: 5 minutes)
- Cache key: hash of query string + graph URI
- Invalidate cache on contract updates
- Support cache warming for common queries

**Expected Impact**: 80-90% reduction in query time for repeated queries.

### 2. Query Optimization

**Strategy**: Optimize SPARQL queries for better performance.

**Implementation**:
- Use FILTER early in query (before JOIN)
- Use LIMIT to reduce result set size
- Use SELECT DISTINCT only when needed
- Use indexed properties (hub:contractId, dct:title)
- Avoid complex nested queries

**Expected Impact**: 20-40% reduction in query time.

### 3. Fuseki Query Optimization

**Strategy**: Optimize Fuseki configuration for query performance.

**Implementation**:
- Enable query result caching in Fuseki
- Configure appropriate TDB2 indexes
- Use named graphs for tenant isolation
- Enable query timeout (30s default)
- Limit result set size (10,000 default)

**Expected Impact**: 10-20% reduction in query time.

### 4. Query Result Streaming

**Strategy**: Stream large query results instead of loading all into memory.

**Implementation**:
- Use Fuseki streaming query results
- Process results in batches
- Return results as JSON stream

**Expected Impact**: Reduced memory usage for large result sets.

---

## API Response Optimizations

### 1. Computed Field Caching

**Strategy**: Cache computed fields (owners, tags, quality_rules, etc.) in contract JSON.

**Implementation**:
- Store computed fields in `hub_contract_json` during normalization
- Update computed fields on contract update
- Return cached fields from serializer

**Expected Impact**: 50-70% reduction in API response time for contract retrieval.

### 2. Selective Field Loading

**Strategy**: Load only requested fields in API response.

**Implementation**:
- Support `?fields=id,name,owners` query parameter
- Use serializer `fields` parameter
- Skip expensive computations for unrequested fields

**Expected Impact**: 30-50% reduction in API response time for partial field requests.

### 3. Pagination for Large Lists

**Strategy**: Implement efficient pagination for contract lists.

**Implementation**:
- Use cursor-based pagination for large result sets
- Limit page size (default: 50, max: 100)
- Use database indexes for sorting

**Expected Impact**: Reduced query time for large contract lists.

### 4. Database Query Optimization

**Strategy**: Optimize database queries for contract filtering and sorting.

**Implementation**:
- Add indexes on `hub_contract_json` fields (GIN index)
- Use `jsonb_path_ops` for efficient JSON queries
- Optimize filtering queries (owner_email, tag, etc.)
- Use database-level sorting instead of Python sorting

**Expected Impact**: 40-60% reduction in query time for filtered/sorted lists.

---

## Caching Strategies

### 1. Multi-Level Caching

**Strategy**: Implement multi-level caching for contract data.

**Implementation**:
- **L1 Cache**: In-memory cache (Django cache framework)
  - TTL: 5 minutes
  - Size: 1000 contracts
- **L2 Cache**: Redis cache
  - TTL: 1 hour
  - Size: 10,000 contracts
- **L3 Cache**: Database (source of truth)

**Expected Impact**: 80-90% cache hit rate for frequently accessed contracts.

### 2. Cache Warming

**Strategy**: Pre-populate cache with frequently accessed contracts.

**Implementation**:
- Identify frequently accessed contracts (top 100)
- Warm cache on application startup
- Warm cache on contract creation/update
- Use background job for cache warming

**Expected Impact**: Improved response time for frequently accessed contracts.

### 3. Cache Invalidation

**Strategy**: Efficiently invalidate cache on contract updates.

**Implementation**:
- Invalidate cache on contract update
- Use cache tags for related contracts
- Invalidate related caches (asset, dataset, etc.)
- Use cache versioning for gradual invalidation

**Expected Impact**: Consistent cache state with minimal overhead.

---

## Database Optimizations

### 1. JSON Field Indexing

**Strategy**: Add indexes on frequently queried JSON fields.

**Implementation**:
- Add GIN index on `hub_contract_json`
- Add GIN index on `hub_contract_json->'info'->'owners'`
- Add GIN index on `hub_contract_json->'info'->'tags'`
- Add GIN index on `hub_contract_json->'quality'->'default_profile_key'`
- Add GIN index on `hub_contract_json->'privacy_compliance'->'jurisdictions'`

**Expected Impact**: 50-70% reduction in query time for JSON field filters.

### 2. Materialized Views

**Strategy**: Create materialized views for frequently queried contract data.

**Implementation**:
- Materialized view: `contracts_with_quality_rules`
- Materialized view: `contracts_with_compliance_policies`
- Refresh materialized views on contract update
- Use materialized views for complex queries

**Expected Impact**: 60-80% reduction in query time for complex queries.

### 3. Query Plan Optimization

**Strategy**: Optimize database query plans for contract queries.

**Implementation**:
- Use `EXPLAIN ANALYZE` to identify slow queries
- Add missing indexes
- Rewrite queries for better performance
- Use database query hints if needed

**Expected Impact**: 20-40% reduction in query time.

---

## Implementation Priority

### Phase 1: High Impact, Low Effort
1. ✅ Computed field caching
2. ✅ Query result caching
3. ✅ Database JSON field indexing
4. ✅ Selective field loading

### Phase 2: High Impact, Medium Effort
1. Lazy RDF mapping
2. Incremental normalization
3. Multi-level caching
4. Query optimization

### Phase 3: Medium Impact, High Effort
1. Parallel field processing
2. Incremental RDF updates
3. Materialized views
4. Cache warming

---

## Monitoring & Measurement

### Key Metrics
- Normalization latency (P50, P95, P99)
- RDF mapping latency (P50, P95, P99)
- SPARQL query latency (P50, P95, P99)
- API response time (P50, P95, P99)
- Cache hit rate
- Database query time
- Storage size

### Tools
- Prometheus for metrics collection
- Grafana for visualization
- Django Debug Toolbar for query analysis
- PostgreSQL `EXPLAIN ANALYZE` for query optimization

---

## Expected Overall Impact

With all optimizations implemented:

- **Normalization**: 50-70% reduction in latency
- **RDF Mapping**: 60-80% reduction in latency
- **SPARQL Queries**: 70-90% reduction in latency
- **API Response**: 50-70% reduction in latency
- **Storage**: 30-50% increase (acceptable trade-off)

