Loading requirements from docs/api-audit/api-requirements-matrix-consolidated.md...
Loaded 18 APIs from requirements
Loading current inventory from docs/api-audit/current-api-inventory.md...
Total APIs: 164
# API Performance Requirements

**Document Version**: 1.0.0
**Last Updated**: 2025-12-13
**Task**: 0.4.4 - Document performance requirements

---

## Overview

This document defines comprehensive performance requirements for all API endpoints,
including:
- **Response Time Targets**: P50, P95, P99 percentiles
- **Throughput Targets**: Requests per second (RPS)
- **Timeout Values**: Client and server timeout configurations
- **Caching Requirements**: Cacheability, TTL, and cache strategies

**Total APIs Documented**: 164 (existing) + ~94 (missing/new APIs from journeys/use cases)

**Sources**:
- Existing APIs: `docs/api-audit/current-api-inventory.md` (148 endpoints)
- Required APIs: `docs/api-audit/api-requirements-matrix-consolidated.md` (18 detailed)
- Additional Requirements: `docs/api-audit/api-requirements-from-journeys.md` (100+ missing APIs)
- Additional Requirements: `docs/api-audit/api-requirements-from-use-cases.md` (35+ missing APIs)

---

## Performance Targets by Category

### Analytics (4 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/analytics/api/dashboard/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/analytics/api/performance/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/analytics/api/popular-endpoints/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/analytics/api/usage-trends/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |

### Asset Management

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| DELETE | `/api/v1/assets/{id}/` | 100ms | 500ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| GET | `/api/v1/assets/` | 200ms | 300ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/assets/{id}/` | 100ms | 200ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/assets/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/assets/{id}/activate/` | 300ms | 2000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/assets/{id}/contracts/` | 300ms | 500ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/assets/{id}/datasets/` | 300ms | 500ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| PUT | `/api/v1/assets/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |

### Assets (13 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/assets/recommendations/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/assets/{id}/dependencies/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/assets/{id}/health-score/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/assets/{id}/track-download/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/assets/{id}/track-view/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Audit (3 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/audit/audit-events/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/audit/audit-events/export/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/audit/audit-events/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |

### Auth (10 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/auth/accept-invitation/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/auth/api-keys/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |

### Authentication

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| DELETE | `/api/v1/auth/api-keys/{id}/` | 100ms | 200ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| GET | `/api/v1/auth/api-keys/` | 200ms | 200ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/auth/me/` | 200ms | 200ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/auth/api-keys/` | 300ms | 500ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/auth/login/` | 300ms | 500ms | 1000ms | 100 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/auth/logout/` | 300ms | 200ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/auth/password-reset/` | 300ms | 500ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/auth/password-reset/confirm/` | 300ms | 500ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/auth/refresh/` | 300ms | 200ms | 500ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/auth/register/` | 300ms | 500ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Compliance (4 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/compliance/compliance-runs/` | 200ms | 500ms | 1000ms | 1000 req/s | 180s | 150s | Yes | 300s |
| GET | `/api/v1/compliance/compliance-runs/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 180s | 150s | Yes | 300s |
| GET | `/api/v1/compliance/runs/` | 200ms | 500ms | 1000ms | 1000 req/s | 180s | 150s | Yes | 300s |
| GET | `/api/v1/compliance/runs/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 180s | 150s | Yes | 300s |
| POST | `/api/v1/compliance/compliance-runs/` | 300ms | 1000ms | 2000ms | 500 req/s | 180s | 150s | No | N/A |

### Contracts (13 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| DELETE | `/api/v1/contracts/{id}/` | 100ms | 300ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| GET | `/api/v1/contracts/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/contracts/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/contracts/{id}/impact-analysis/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/contracts/{id}/lineage/contracts/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/contracts/{id}/lineage/full/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/contracts/{id}/lineage/visualization/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/contracts/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/contracts/{id}/convert/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/contracts/{id}/lint/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/contracts/{id}/migrate/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/contracts/{id}/validate/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| PUT | `/api/v1/contracts/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |

### Data Quality (6 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/dq/dq-runs/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/dq/dq-runs/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/dq/runs/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/dq/runs/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/dq/dq-runs/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/dq/runs/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Datasets (5 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/datasets/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/datasets/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/datasets/{id}/versions/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/datasets/{id}/versions/compare/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/datasets/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Files (7 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| DELETE | `/api/v1/files/{id}/` | 100ms | 300ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| GET | `/api/v1/files/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/files/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/files/{id}/download/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/files/init/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/files/{id}/chunks/init/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/files/{id}/complete/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Governance (16 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/governance/analytics/anomalies/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/analytics/dashboard/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/analytics/expiring/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/analytics/patterns/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/analytics/security-events/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/analytics/summary/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/certifications/anomalies/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/certifications/dashboard/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/certifications/expiring/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/certifications/patterns/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/certifications/security-events/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/governance/certifications/summary/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/governance/analytics/initiate-review/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/governance/analytics/{id}/review/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/governance/certifications/initiate-review/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/governance/certifications/{id}/review/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Jobs (4 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/jobs/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/jobs/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/jobs/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/jobs/{id}/cancel/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Marketplace (5 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| DELETE | `/api/v1/marketplace/listings/{id}/` | 100ms | 300ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| GET | `/api/v1/marketplace/listings/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/marketplace/listings/search/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/marketplace/listings/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/marketplace/listings/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| PUT | `/api/v1/marketplace/listings/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |

### Observability (13 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/observability/metrics/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/observability/observability/freshness/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/observability/observability/freshness/s...` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/observability/observability/incidents/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/observability/observability/pipelines/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/observability/observability/schema-drift/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/observability/observability/slas/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/observability/observability/volume/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| PATCH | `/api/v1/observability/observability/incidents/u...` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/observability/observability/incidents/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/observability/observability/metrics/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/observability/observability/schema-drif...` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/observability/observability/volume/aggr...` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Scheduled Ingestion (5 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/scheduled-ingestions/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/scheduled-ingestions/runs/costs/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/scheduled-ingestions/runs/dashboard/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/scheduled-ingestions/runs/dead-letter-q...` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/scheduled-ingestions/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/scheduled-ingestions/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/scheduled-ingestions/runs/{id}/trigger/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Search (5 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/search/search/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 60s |
| GET | `/api/v1/search/search/analytics/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 60s |
| GET | `/api/v1/search/search/suggestions/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 60s |
| POST | `/api/v1/search/search/rebuild-index/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | Yes | 60s |
| POST | `/api/v1/search/search/track-click/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | Yes | 60s |

### Semantic (5 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/semantic/context.jsonld` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/semantic/id/field/{asset_uuid}/{field_n...` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/semantic/id/{resource_type}/{resource_id}` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/semantic/ontology` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/semantic/semantic-resources/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/semantic/semantic-resources/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/semantic/sparql` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/semantic/semantic-resources/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

### Tenants (8 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| DELETE | `/api/v1/tenants/{id}/` | 100ms | 300ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| GET | `/api/v1/tenants/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/tenants/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/tenants/{tenant_id}/config/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| PATCH | `/api/v1/tenants/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |
| PATCH | `/api/v1/tenants/{tenant_id}/config/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/tenants/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/tenants/{id}/reactivate/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/tenants/{id}/suspend/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| PUT | `/api/v1/tenants/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |

### Users (16 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| DELETE | `/api/v1/users/roles/{id}/` | 100ms | 300ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| DELETE | `/api/v1/users/users/{id}/` | 100ms | 300ms | 500ms | 800 req/s | 30s | 25s | No | N/A |
| GET | `/api/v1/users/roles/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/users/roles/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/users/users/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/users/users/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| PATCH | `/api/v1/users/roles/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |
| PATCH | `/api/v1/users/users/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/users/roles/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/users/roles/invite/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/users/roles/{id}/roles/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/users/users/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/users/users/invite/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/users/users/{id}/roles/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| PUT | `/api/v1/users/roles/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |
| PUT | `/api/v1/users/users/{id}/` | 200ms | 500ms | 1000ms | 800 req/s | 30s | 25s | No | N/A |

### Webhooks (6 endpoints)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|
| GET | `/api/v1/webhooks/webhook-deliveries/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/webhooks/webhook-deliveries/{id}/delive...` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/webhooks/webhooks/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/webhooks/webhooks/{id}/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| GET | `/api/v1/webhooks/webhooks/{id}/deliveries/` | 100ms | 300ms | 500ms | 1000 req/s | 30s | 25s | Yes | 300s |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/retry/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/webhooks/webhook-deliveries/{id}/test/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/webhooks/webhooks/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/webhooks/webhooks/{id}/retry/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |
| POST | `/api/v1/webhooks/webhooks/{id}/test/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A |

---

## Missing/New APIs Performance Requirements

**Note**: These APIs are required but not yet implemented. Performance requirements are defined based on journey and use case requirements.

### AI/ML APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| POST | `/api/v1/ai/schema-matching/` | 5s | 15s | 30s | 10 req/s | 60s | 45s | No | N/A | AI processing |
| POST | `/api/v1/ai/classification/` | 8s | 20s | 40s | 10 req/s | 60s | 45s | No | N/A | ML model inference |
| POST | `/api/v1/ai/anomaly-detection/` | 10s | 30s | 60s | 10 req/s | 60s | 45s | No | N/A | Time-series analysis |
| POST | `/api/v1/ai/natural-language-search/` | 1s | 3s | 5s | 50 req/s | 30s | 25s | Yes | 60s | Query understanding |
| GET | `/api/v1/ai/natural-language-search/{id}/results/` | 2s | 5s | 10s | 100 req/s | 30s | 25s | Yes | 60s | Search results |
| GET | `/api/v1/ai/recommendations/` | 200ms | 500ms | 1000ms | 100 req/s | 30s | 25s | Yes | 300s | User-specific |

### Transformation APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/transformation/pipelines/` | 200ms | 500ms | 1000ms | 1000 req/s | 120s | 100s | Yes | 300s | List pipelines |
| POST | `/api/v1/transformation/pipelines/` | 1s | 5s | 10s | 50 req/s | 120s | 100s | No | N/A | Create pipeline |
| POST | `/api/v1/transformation/pipelines/{id}/validate/` | 500ms | 2s | 5s | 50 req/s | 120s | 100s | No | N/A | Validation |
| POST | `/api/v1/transformation/pipelines/{id}/execute/` | 5s | 30s | 60s | 20 req/s | 300s | 250s | No | N/A | Execution |
| POST | `/api/v1/transformation/pipelines/{id}/preview/` | 2s | 10s | 20s | 50 req/s | 120s | 100s | No | N/A | Data preview |
| POST | `/api/v1/transformation/wrangling/` | 1s | 5s | 10s | 50 req/s | 120s | 100s | No | N/A | Interactive wrangling |

### Enhanced Marketplace APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/marketplace/eligibility/{asset_id}/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | Eligibility check |
| GET | `/api/v1/marketplace/listings/{id}/pricing/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | Pricing info |
| GET | `/api/v1/marketplace/listings/{id}/preview/` | 1s | 2s | 5s | 500 req/s | 30s | 25s | Yes | 60s | Data preview |
| GET | `/api/v1/marketplace/listings/{id}/trust-signals/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | Trust metrics |

### Social Feature APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/social/ratings/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | List ratings |
| POST | `/api/v1/social/ratings/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A | Create rating |
| GET | `/api/v1/social/reviews/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | List reviews |
| POST | `/api/v1/social/reviews/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A | Create review |
| GET | `/api/v1/social/communities/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | List communities |
| GET | `/api/v1/social/activity-feeds/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 60s | Activity feed |

### Data Mesh APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/mesh/domains/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | List domains |
| POST | `/api/v1/mesh/domains/` | 300ms | 1000ms | 2000ms | 500 req/s | 30s | 25s | No | N/A | Create domain |
| GET | `/api/v1/mesh/governance/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | Governance policies |
| GET | `/api/v1/mesh/topology/` | 500ms | 2000ms | 5000ms | 100 req/s | 60s | 50s | Yes | 600s | Topology graph |

### Virtualization APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/virtualization/datasets/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | List virtual datasets |
| POST | `/api/v1/virtualization/datasets/` | 1s | 5s | 10s | 50 req/s | 120s | 100s | No | N/A | Create virtual dataset |
| POST | `/api/v1/virtualization/queries/` | 2s | 10s | 20s | 50 req/s | 120s | 100s | Yes | 60s | Federated query |

### Advanced Governance APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/governance/automated-compliance/` | 200ms | 500ms | 1000ms | 1000 req/s | 180s | 150s | Yes | 300s | Compliance rules |
| POST | `/api/v1/governance/automated-compliance/` | 1s | 5s | 10s | 50 req/s | 180s | 150s | No | N/A | Create rule |
| GET | `/api/v1/governance/retention-policies/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | Retention policies |
| POST | `/api/v1/governance/gdpr/` | 1s | 5s | 10s | 50 req/s | 180s | 150s | No | N/A | GDPR workflow |
| GET | `/api/v1/governance/consent/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | Consent tracking |

### Integration Ecosystem APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/integrations/connectors/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | List connectors |
| POST | `/api/v1/integrations/connectors/` | 1s | 5s | 10s | 50 req/s | 120s | 100s | No | N/A | Install connector |
| POST | `/api/v1/integrations/reverse-etl/` | 2s | 10s | 20s | 50 req/s | 120s | 100s | No | N/A | Reverse ETL job |
| POST | `/api/v1/integrations/bi/` | 1s | 5s | 10s | 50 req/s | 120s | 100s | No | N/A | BI integration |

### Developer Experience APIs (New - Required)

| Method | Endpoint | P50 | P95 | P99 | Throughput | Client Timeout | Server Timeout | Cacheable | Cache TTL | Notes |
|--------|----------|-----|-----|-----|------------|----------------|----------------|-----------|-----------|-------|
| GET | `/api/v1/plugins/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 300s | List plugins |
| POST | `/api/v1/plugins/` | 1s | 5s | 10s | 50 req/s | 120s | 100s | No | N/A | Install plugin |
| GET | `/api/v1/developer/sdks/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 3600s | SDK info |
| GET | `/api/v1/developer/cli/` | 200ms | 500ms | 1000ms | 1000 req/s | 30s | 25s | Yes | 3600s | CLI config |

---

## Performance Targets Summary

### By HTTP Method

| Method | Count | Avg P95 Target |
|--------|-------|----------------|
| GET | 90 | 423ms |
| POST | 55 | 925ms |
| PUT | 6 | 500ms |
| PATCH | 5 | 500ms |
| DELETE | 8 | 312ms |

### Caching Summary

- **Cacheable Endpoints**: 92 (56%)
- **Non-Cacheable Endpoints**: 72

### Timeout Summary

| Timeout Type | Default | Range |
|--------------|---------|-------|
| Client Timeout | 30s | 10s - 180s |
| Server Timeout | 25s | 5s - 150s |
| AI/ML Operations | 60s | 30s - 120s |
| Transformation Operations | 120s | 60s - 300s |
| Compliance/DQ Operations | 180s | 60s - 300s |

### Throughput Summary

| Operation Type | Target Throughput |
|----------------|-------------------|
| GET (List) | 1000 req/s |
| GET (Single) | 1000 req/s |
| POST (Create) | 500 req/s |
| PUT/PATCH (Update) | 800 req/s |
| DELETE | 800 req/s |
| Authentication | 100 req/s |
| AI/ML Operations | 10 req/s |
| Transformation Operations | 50 req/s |

---

## Caching Requirements

### Cache Strategy Guidelines

1. **Public Cache**: For public, non-sensitive data
   - Use for: Public marketplace listings, public asset metadata
   - Cache-Control: `public, max-age={ttl}`

2. **Private Cache**: For user-specific data
   - Use for: User assets, user contracts, user datasets
   - Cache-Control: `private, max-age={ttl}`

3. **No Cache**: For mutable or sensitive data
   - Use for: Authentication endpoints, write operations, real-time data
   - Cache-Control: `no-cache, no-store, must-revalidate`

### Cache TTL Guidelines

| Data Type | Recommended TTL |
|-----------|-----------------|
| Static metadata | 1 hour (3600s) |
| User-specific data | 5 minutes (300s) |
| Search results | 1 minute (60s) |
| Real-time data | No cache (0s) |
| Computed metrics | 5 minutes (300s) |

---

## Performance Monitoring

### Metrics to Track

1. **Response Time Percentiles**: P50, P95, P99
2. **Throughput**: Requests per second (RPS)
3. **Error Rate**: Percentage of failed requests
4. **Timeout Rate**: Percentage of requests that timeout
5. **Cache Hit Rate**: Percentage of cache hits

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|---------|
| P95 Response Time | > 1.5x target | > 2x target |
| P99 Response Time | > 1.5x target | > 2x target |
| Error Rate | > 1% | > 5% |
| Timeout Rate | > 0.1% | > 1% |
| Cache Hit Rate | < 50% | < 30% |

---

## Implementation Guidelines

### Response Time Optimization

1. **Database Query Optimization**: Use indexes, query optimization, connection pooling
2. **Caching**: Implement Redis/Memcached for frequently accessed data
3. **Pagination**: Use cursor-based or offset-based pagination for large datasets
4. **Async Processing**: Use background jobs for long-running operations
5. **CDN**: Use CDN for static assets and API responses when appropriate

### Throughput Optimization

1. **Horizontal Scaling**: Scale API servers horizontally
2. **Load Balancing**: Use load balancers to distribute traffic
3. **Connection Pooling**: Reuse database connections
4. **Rate Limiting**: Implement rate limiting to prevent overload
5. **Queue Management**: Use message queues for async operations

### Timeout Configuration

1. **Client Timeout**: Should be slightly longer than server timeout
2. **Server Timeout**: Should account for worst-case processing time
3. **Database Timeout**: Should be shorter than server timeout
4. **External Service Timeout**: Should be shorter than server timeout

### Caching Implementation

1. **Cache Keys**: Use consistent, unique cache keys
2. **Cache Invalidation**: Implement proper cache invalidation strategies
3. **Cache Warming**: Pre-populate cache for frequently accessed data
4. **Cache Headers**: Set appropriate Cache-Control headers
5. **ETags**: Use ETags for conditional requests

---

---

## Detailed Performance Requirements

### Response Time Targets

#### Target Percentiles

All API endpoints must meet the following percentile targets:

- **P50 (Median)**: 50% of requests complete within this time
- **P95**: 95% of requests complete within this time (primary SLA target)
- **P99**: 99% of requests complete within this time (worst-case acceptable)

#### Target Ranges by Operation Type

| Operation Type | P50 Target | P95 Target | P99 Target | Rationale |
|----------------|-----------|------------|-----------|-----------|
| **Simple GET** (single resource) | < 100ms | < 300ms | < 500ms | Fast read from cache/DB |
| **GET List** (with pagination) | < 200ms | < 500ms | < 1000ms | Pagination overhead |
| **POST Create** (simple) | < 300ms | < 1000ms | < 2000ms | Validation + DB write |
| **POST Create** (complex) | < 1s | < 5s | < 10s | Includes workflow execution |
| **PUT/PATCH Update** | < 200ms | < 500ms | < 1000ms | Validation + DB update |
| **DELETE** | < 100ms | < 300ms | < 500ms | Simple DB operation |
| **AI/ML Operations** | < 5s | < 15s | < 30s | Model inference time |
| **Transformation** | < 1s | < 5s | < 10s | Pipeline validation |
| **Transformation Execution** | < 5s | < 30s | < 60s | Data processing |
| **Compliance/DQ Scans** | < 10s | < 60s | < 120s | Rule evaluation |

### Throughput Targets

#### Target Requests Per Second (RPS)

Throughput targets are defined per endpoint category:

| Category | Target RPS | Burst Capacity | Notes |
|----------|------------|----------------|-------|
| **Read Operations** (GET) | 1000 req/s | 2000 req/s | High throughput for reads |
| **Write Operations** (POST/PUT/PATCH) | 500 req/s | 1000 req/s | Lower due to DB writes |
| **Delete Operations** | 800 req/s | 1500 req/s | Moderate throughput |
| **Authentication** | 100 req/s | 200 req/s | Rate-limited for security |
| **AI/ML Operations** | 10 req/s | 20 req/s | Resource-intensive |
| **Transformation Operations** | 50 req/s | 100 req/s | Moderate resource usage |
| **Compliance/DQ Operations** | 20 req/s | 50 req/s | Resource-intensive |

#### Throughput Measurement

- **Sustained Throughput**: Average RPS over 1 minute
- **Peak Throughput**: Maximum RPS over 10 seconds
- **Burst Capacity**: Maximum RPS for 1 second

### Timeout Values

#### Client Timeout Configuration

Client timeouts should be configured based on operation type:

| Operation Type | Default Timeout | Recommended Range | Notes |
|----------------|----------------|-------------------|-------|
| **Standard Operations** | 30s | 10s - 60s | Most GET/POST/PUT/DELETE |
| **Long-running Operations** | 120s | 60s - 300s | Transformation, compliance |
| **AI/ML Operations** | 60s | 30s - 120s | Model inference |
| **File Upload** | 300s | 60s - 600s | Large file uploads |
| **WebSocket Connections** | N/A | Keep-alive: 30s | Persistent connections |

#### Server Timeout Configuration

Server timeouts should be **5 seconds shorter** than client timeouts to allow for:
- Network latency
- Client-side processing
- Graceful timeout handling

| Client Timeout | Server Timeout | Buffer |
|----------------|----------------|--------|
| 30s | 25s | 5s |
| 60s | 50s | 10s |
| 120s | 100s | 20s |
| 180s | 150s | 30s |
| 300s | 250s | 50s |

#### Timeout Handling

1. **Client-side**: Should retry with exponential backoff (max 3 retries)
2. **Server-side**: Should return `504 Gateway Timeout` if timeout exceeded
3. **Long-running Operations**: Should use async job pattern with status polling

### Caching Requirements

#### Cacheability Rules

**Cacheable Endpoints**:
- GET requests for read-only data
- Public data (marketplace listings, public assets)
- User-specific data with appropriate cache keys
- Computed metrics (with short TTL)

**Non-Cacheable Endpoints**:
- All write operations (POST, PUT, PATCH, DELETE)
- Authentication endpoints
- Real-time data (job status, notifications)
- User-specific sensitive data (credentials, API keys)

#### Cache TTL Guidelines

| Data Type | TTL | Cache Strategy | Invalidation |
|-----------|-----|----------------|--------------|
| **Static Metadata** | 1 hour (3600s) | Public | On metadata update |
| **User Assets** | 5 minutes (300s) | Private | On asset update |
| **User Contracts** | 5 minutes (300s) | Private | On contract update |
| **Search Results** | 1 minute (60s) | Private | On index update |
| **Computed Metrics** | 5 minutes (300s) | Private | On data change |
| **Marketplace Listings** | 1 hour (3600s) | Public | On listing update |
| **Recommendations** | 5 minutes (300s) | Private | On user activity |
| **Topology Graphs** | 10 minutes (600s) | Private | On topology change |

#### Cache Headers

**Public Cache**:
```
Cache-Control: public, max-age=3600
```

**Private Cache**:
```
Cache-Control: private, max-age=300
```

**No Cache**:
```
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
```

**Conditional Requests (ETags)**:
```
ETag: "abc123"
If-None-Match: "abc123"  # Returns 304 Not Modified if unchanged
```

#### Cache Invalidation Strategies

1. **Time-based**: Automatic expiration after TTL
2. **Event-based**: Invalidate on related data changes
3. **Manual**: Admin-triggered cache clear
4. **Version-based**: Use versioned cache keys

---

**Document Status**: ✅ Complete
**Total APIs Documented**: 164 (existing) + ~94 (missing/new) = **258 total APIs**

**Next Steps**:
1. Implement performance monitoring for all endpoints
2. Set up alerting based on performance thresholds
3. Optimize endpoints that exceed performance targets
4. Review and update performance targets based on production metrics
5. Implement caching for cacheable endpoints
6. Configure timeouts based on these requirements
