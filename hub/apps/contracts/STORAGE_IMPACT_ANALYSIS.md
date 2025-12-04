# Storage Impact Analysis for Enhanced Contract Normalization & Semantic Mapping (GAP-11.2.3)

This document analyzes the storage impact of Phase 7+ features including enhanced normalization, RDF mapping, and standard vocabulary integration.

## Table of Contents

1. [Storage Components](#storage-components)
2. [Baseline Storage](#baseline-storage)
3. [Enhanced Storage](#enhanced-storage)
4. [Storage Growth Projections](#storage-growth-projections)
5. [Optimization Strategies](#optimization-strategies)
6. [Cost Analysis](#cost-analysis)

---

## Storage Components

### 1. Database Storage (PostgreSQL)

- **Contract Table**: `hub_contract_json` (JSONB field)
- **Indexes**: GIN indexes on JSON fields
- **Metadata**: Normalization status, validation status, etc.

### 2. RDF Storage (Fuseki/TDB2)

- **Triples**: RDF triples for contracts, fields, quality rules, etc.
- **Indexes**: TDB2 indexes for query performance
- **Named Graphs**: Per-tenant named graphs

### 3. Cache Storage (Redis)

- **Normalized Contracts**: Cached normalized contracts
- **RDF Graphs**: Cached RDF graphs
- **Query Results**: Cached SPARQL query results

---

## Baseline Storage

### Small Contract (10 fields, basic sections)

| Component | Size | Notes |
|-----------|------|-------|
| **Contract JSON** | ~5KB | Basic info, schema (10 fields), minimal quality/compliance |
| **RDF Triples** | ~50 triples | Basic contract, fields, minimal metadata |
| **Fuseki Storage** | ~25KB | Compressed TDB2 storage |
| **Database Index** | ~2KB | GIN index on JSON field |
| **Total** | ~32KB | Per contract |

### Medium Contract (100 fields, all sections)

| Component | Size | Notes |
|-----------|------|-------|
| **Contract JSON** | ~10KB | Full info (owners, tags), schema (100 fields), quality (10 rules), compliance, lifecycle, marketplace |
| **RDF Triples** | ~100 triples | Contract, fields, quality rules, compliance policies |
| **Fuseki Storage** | ~50KB | Compressed TDB2 storage |
| **Database Index** | ~5KB | GIN index on JSON field |
| **Total** | ~65KB | Per contract |

### Large Contract (1000 fields, all sections)

| Component | Size | Notes |
|-----------|------|-------|
| **Contract JSON** | ~50KB | Full info, schema (1000 fields), quality (50 rules), compliance, lifecycle, marketplace |
| **RDF Triples** | ~500 triples | Contract, fields, quality rules, compliance policies |
| **Fuseki Storage** | ~250KB | Compressed TDB2 storage |
| **Database Index** | ~25KB | GIN index on JSON field |
| **Total** | ~325KB | Per contract |

---

## Enhanced Storage (Phase 7+)

### Small Contract (10 fields, all sections with enhanced properties)

| Component | Size | Increase | Notes |
|-----------|------|----------|-------|
| **Contract JSON** | ~7KB | +40% | Enhanced field properties (semantic_type, format, pattern, etc.) |
| **RDF Triples** | ~200 triples | +300% | All sections with standard vocabulary links (DQV, DPV, PROV-O, ODRL, SHACL, Schema.org, FOAF) |
| **Fuseki Storage** | ~100KB | +300% | Compressed TDB2 storage with standard vocabularies |
| **Database Index** | ~3KB | +50% | Enhanced GIN index |
| **Total** | ~110KB | +244% | Per contract |

### Medium Contract (100 fields, all sections with enhanced properties)

| Component | Size | Increase | Notes |
|-----------|------|----------|-------|
| **Contract JSON** | ~15KB | +50% | Enhanced field properties for all 100 fields |
| **RDF Triples** | ~500 triples | +400% | All sections with standard vocabulary links |
| **Fuseki Storage** | ~200KB | +300% | Compressed TDB2 storage |
| **Database Index** | ~8KB | +60% | Enhanced GIN index |
| **Total** | ~223KB | +243% | Per contract |

### Large Contract (1000 fields, all sections with enhanced properties)

| Component | Size | Increase | Notes |
|-----------|------|----------|-------|
| **Contract JSON** | ~75KB | +50% | Enhanced field properties for all 1000 fields |
| **RDF Triples** | ~2500 triples | +400% | All sections with standard vocabulary links |
| **Fuseki Storage** | ~1MB | +300% | Compressed TDB2 storage |
| **Database Index** | ~40KB | +60% | Enhanced GIN index |
| **Total** | ~1.1MB | +238% | Per contract |

---

## Storage Growth Projections

### Assumptions

- **Contract Distribution**:
  - Small contracts: 60% (10 fields)
  - Medium contracts: 35% (100 fields)
  - Large contracts: 5% (1000 fields)

- **Average Contract Size**:
  - Baseline: ~65KB per contract
  - Enhanced: ~223KB per contract
  - Increase: +243%

### Projections

| Scenario | Contracts | Baseline Storage | Enhanced Storage | Increase |
|----------|-----------|------------------|------------------|----------|
| **Small Scale** | 1,000 | 65MB | 223MB | +158MB |
| **Medium Scale** | 10,000 | 650MB | 2.2GB | +1.6GB |
| **Large Scale** | 100,000 | 6.5GB | 22.3GB | +15.8GB |
| **Enterprise Scale** | 1,000,000 | 65GB | 223GB | +158GB |

### Breakdown by Component

#### Database Storage (PostgreSQL)

| Scale | Baseline | Enhanced | Increase |
|-------|----------|----------|----------|
| **Small** | 17MB | 25MB | +8MB |
| **Medium** | 170MB | 250MB | +80MB |
| **Large** | 1.7GB | 2.5GB | +800MB |
| **Enterprise** | 17GB | 25GB | +8GB |

#### RDF Storage (Fuseki/TDB2)

| Scale | Baseline | Enhanced | Increase |
|-------|----------|----------|----------|
| **Small** | 50MB | 200MB | +150MB |
| **Medium** | 500MB | 2GB | +1.5GB |
| **Large** | 5GB | 20GB | +15GB |
| **Enterprise** | 50GB | 200GB | +150GB |

#### Cache Storage (Redis)

| Scale | Baseline | Enhanced | Increase |
|-------|----------|----------|----------|
| **Small** | 10MB | 30MB | +20MB |
| **Medium** | 100MB | 300MB | +200MB |
| **Large** | 1GB | 3GB | +2GB |
| **Enterprise** | 10GB | 30GB | +20GB |

---

## Optimization Strategies

### 1. Compression

**Strategy**: Use compression for stored data.

**Implementation**:
- PostgreSQL: Enable `TOAST` compression for large JSON fields
- Fuseki: Use TDB2 compression (already enabled)
- Redis: Use compression for cached data

**Expected Impact**: 30-50% reduction in storage size.

### 2. Data Deduplication

**Strategy**: Deduplicate common data across contracts.

**Implementation**:
- Store common field properties in separate table
- Reference common properties from contracts
- Store standard vocabulary mappings once

**Expected Impact**: 20-30% reduction in storage size for large deployments.

### 3. Archival Strategy

**Strategy**: Archive old/inactive contracts.

**Implementation**:
- Archive contracts with status RETIRED
- Move archived contracts to cold storage (S3)
- Keep only active contracts in hot storage

**Expected Impact**: 50-70% reduction in active storage.

### 4. Selective RDF Storage

**Strategy**: Store RDF only for contracts that need semantic queries.

**Implementation**:
- Store RDF only for contracts with:
  - Quality rules
  - Compliance policies
  - Marketplace listings
  - Semantic queries
- Skip RDF storage for simple contracts

**Expected Impact**: 40-60% reduction in RDF storage.

### 5. Incremental RDF Updates

**Strategy**: Update only changed triples instead of regenerating all.

**Implementation**:
- Track which sections changed
- Remove old triples for changed sections
- Add new triples for changed sections

**Expected Impact**: Reduced storage churn, but no net reduction.

---

## Cost Analysis

### Storage Costs (AWS Example)

#### Database Storage (PostgreSQL on RDS)

| Scale | Baseline | Enhanced | Additional Cost |
|-------|----------|----------|-----------------|
| **Small** | $0.10/GB/month | $0.10/GB/month | +$0.80/month |
| **Medium** | $1.00/GB/month | $1.00/GB/month | +$8.00/month |
| **Large** | $10.00/GB/month | $10.00/GB/month | +$80.00/month |
| **Enterprise** | $100.00/GB/month | $100.00/GB/month | +$800.00/month |

#### RDF Storage (Fuseki on EBS)

| Scale | Baseline | Enhanced | Additional Cost |
|-------|----------|----------|-----------------|
| **Small** | $0.10/GB/month | $0.10/GB/month | +$15.00/month |
| **Medium** | $1.00/GB/month | $1.00/GB/month | +$150.00/month |
| **Large** | $10.00/GB/month | $10.00/GB/month | +$1,500.00/month |
| **Enterprise** | $100.00/GB/month | $100.00/GB/month | +$15,000.00/month |

#### Cache Storage (Redis on ElastiCache)

| Scale | Baseline | Enhanced | Additional Cost |
|-------|----------|----------|-----------------|
| **Small** | $0.10/GB/month | $0.10/GB/month | +$2.00/month |
| **Medium** | $1.00/GB/month | $1.00/GB/month | +$20.00/month |
| **Large** | $10.00/GB/month | $10.00/GB/month | +$200.00/month |
| **Enterprise** | $100.00/GB/month | $100.00/GB/month | +$2,000.00/month |

### Total Additional Cost

| Scale | Additional Cost/Month | Additional Cost/Year |
|-------|----------------------|----------------------|
| **Small** | $17.80 | $213.60 |
| **Medium** | $178.00 | $2,136.00 |
| **Large** | $1,780.00 | $21,360.00 |
| **Enterprise** | $17,800.00 | $213,600.00 |

---

## Recommendations

### 1. Acceptable Trade-off

The storage increase (243% on average) is acceptable given:
- Enhanced functionality (semantic mapping, standard vocabularies)
- Improved query capabilities (SPARQL queries)
- Better interoperability (standard vocabularies)
- Performance optimizations can mitigate some impact

### 2. Optimization Priority

1. **High Priority**: Compression, selective RDF storage
2. **Medium Priority**: Data deduplication, archival strategy
3. **Low Priority**: Incremental RDF updates (performance benefit, not storage)

### 3. Monitoring

- Monitor storage growth over time
- Set alerts for storage thresholds
- Track storage costs
- Review and optimize regularly

---

## Conclusion

The enhanced features add significant value (semantic mapping, standard vocabularies, improved queries) with a 243% storage increase. This is an acceptable trade-off, especially with optimization strategies in place. The storage costs are manageable for most deployment scales, and can be further optimized through compression, deduplication, and archival strategies.

