# Technology Stack Decisions (MVP)

This document defines the **specific technology choices** for the Interoperable Data Hub MVP implementation. These decisions are binding for all development work and must be referenced in implementation code.

**Status**: Approved for MVP v1  
**Last Updated**: 2025-01-15

---

## 1. Core Application Stack

### 1.1 REST API Framework

**Technology**: Django  
**Version**: 4.2+ (latest stable)  
**Rationale**:
- Mature, production-ready framework with excellent ORM
- Built-in admin interface for operational tasks
- Strong security features and community support
- Excellent for multi-tenant applications

**Documentation**: https://docs.djangoproject.com/

### 1.2 Database ORM

**Technology**: Django ORM  
**Version**: Built-in with Django  
**Rationale**:
- Native Django integration
- Excellent multi-tenancy support via `tenant_id` filtering
- Automatic migration management
- Type-safe model definitions

**Documentation**: https://docs.djangoproject.com/en/stable/topics/db/

### 1.3 Message Queue

**Technology**: Redis-backed queue  
**Version**: Redis 7.x  
**Queue Library**: `django-rq` or `celery` with Redis broker  
**Rationale**:
- Simple setup and operation
- Good performance for job queues
- Easy to scale horizontally
- Well-integrated with Django

**Documentation**: 
- Redis: https://redis.io/docs/
- django-rq: https://github.com/rq/django-rq
- Celery: https://docs.celeryproject.org/

### 1.4 GraphQL Library

**Technology**: Strawberry GraphQL  
**Version**: Latest stable (0.200+)  
**Django Integration**: `strawberry-django`  
**Rationale**:
- Native Django integration
- Type-safe with Python type hints
- Excellent performance
- Supports DataLoader pattern (required for N+1 query prevention)
- Active maintenance and community

**Documentation**: https://strawberry.rocks/docs/integrations/django

---

## 2. Observability & Monitoring

### 2.1 Logging Library

**Technology**: structlog  
**Version**: Latest stable (24.1+)  
**Django Integration**: `django-structlog`  
**Rationale**:
- Structured JSON logging (required by documentation)
- Excellent Django integration
- Contextual logging (request_id, tenant_id, etc.)
- PII redaction support
- Works seamlessly with standard Python logging

**Documentation**: 
- structlog: https://www.structlog.org/
- django-structlog: https://github.com/jrobichaud/django-structlog

**Configuration Requirements**:
- Output format: JSON
- Required fields: `timestamp`, `level`, `service`, `message`, `request_id`, `tenant_id`, `user_id`
- PII redaction: Automatic for sensitive fields

### 2.2 Metrics Client

**Technology**: prometheus-client  
**Version**: Latest stable (0.20+)  
**Django Integration**: `django-prometheus`  
**Rationale**:
- Official Prometheus Python client
- Django middleware available
- Exposes `/metrics` endpoint automatically
- Supports all metric types (counter, gauge, histogram)
- Well-documented and widely used

**Documentation**: 
- prometheus-client: https://github.com/prometheus/client_python
- django-prometheus: https://github.com/korfuri/django-prometheus

**Configuration Requirements**:
- Metrics endpoint: `/metrics`
- Format: Prometheus text format
- Cardinality limits: ≤ 10,000 time series per metric

### 2.3 Distributed Tracing

**Technology**: OpenTelemetry  
**Version**: Latest stable (1.20+)  
**Django Integration**: `opentelemetry-instrumentation-django`  
**Backend**: Jaeger (MVP)  
**Rationale**:
- Industry standard for distributed tracing
- Excellent Django auto-instrumentation
- Supports multiple backends (Jaeger, Tempo, etc.)
- Correlates with `request_id` and logs

**Documentation**: 
- OpenTelemetry Python: https://opentelemetry.io/docs/instrumentation/python/
- Django Instrumentation: https://opentelemetry.io/docs/instrumentation/python/automatic/django/

---

## 3. Runtime & Infrastructure

### 3.1 Python Version

**Version**: Python 3.11  
**Rationale**:
- Latest stable Python version with performance improvements
- Excellent type hinting support (required for Strawberry GraphQL)
- Good security and maintenance support

**Documentation**: https://www.python.org/downloads/

### 3.2 Node.js Version

**Version**: Node.js 22.x  
**Rationale**:
- Latest LTS version
- Required for SDK generation and frontend tooling
- Good performance and security

**Documentation**: https://nodejs.org/

### 3.3 Docker Base Images

**Python Services**:
```dockerfile
FROM python:3.11-slim
```
- Official Python image
- `slim` variant for smaller image size
- Security updates maintained

**Node.js Services** (if any):
```dockerfile
FROM node:22-slim
```
- Official Node.js image
- `slim` variant for smaller image size

**PostgreSQL**:
```dockerfile
FROM postgres:16-alpine
```
- Official PostgreSQL image
- Alpine variant for minimal size
- PostgreSQL 16 (latest stable)

**Redis**:
```dockerfile
FROM redis:7-alpine
```
- Official Redis image
- Alpine variant
- Redis 7 (latest stable)

**MinIO** (S3-compatible storage):
```dockerfile
FROM minio/minio:latest
```
- Official MinIO image
- S3-compatible object storage

**Apache Jena Fuseki** (Triple Store):
```dockerfile
FROM apache/jena-fuseki:latest
```
- Official Apache Jena Fuseki image
- RDF triple store for semantic layer

---

## 4. CI/CD Tooling

### 4.1 CI/CD Platform

**Technology**: GitHub Actions  
**Rationale**:
- Native GitHub integration
- Excellent for open-source and private repositories
- Extensive marketplace of actions
- Good documentation and community support

**Documentation**: https://docs.github.com/en/actions

### 4.2 Key Workflows

**Required Workflows**:
1. **OpenAPI Validation**: Lint and validate OpenAPI specs
2. **Code Quality**: Linting, type checking, security scanning
3. **Testing**: Unit tests, integration tests, database migrations
4. **Build**: Docker image builds for all services
5. **Deploy**: Staging/production deployments (with approval gates)

---

## 5. Database & Storage

### 5.1 Primary Database

**Technology**: PostgreSQL  
**Version**: 16.x  
**Rationale**:
- Excellent JSONB support (required for HubContract storage)
- Strong multi-tenancy support
- Excellent performance and reliability
- Industry standard

**Documentation**: https://www.postgresql.org/docs/

### 5.2 Object Storage

**Technology**: S3-compatible storage  
**Local Development**: MinIO  
**Production**: AWS S3, Google Cloud Storage, or Azure Blob Storage  
**Rationale**:
- Industry standard for object storage
- Pre-signed URL support (required)
- Multi-tenant isolation via key prefixes
- Encrypted at rest

**Documentation**: 
- MinIO: https://min.io/docs/
- AWS S3: https://aws.amazon.com/s3/

### 5.3 Triple Store (Semantic Layer)

**Technology**: Apache Jena Fuseki  
**Version**: Latest stable  
**Storage Backend**: TDB2  
**Rationale**:
- Open source, widely used in RDF/SPARQL ecosystem
- Easy to containerize
- Good performance for medium-sized graphs (10–100M triples)
- Supports SPARQL 1.1

**Documentation**: https://jena.apache.org/documentation/fuseki2/

---

## 6. Development Tools

### 6.1 Code Quality

**Linting**: `ruff` (Python)  
**Type Checking**: `mypy`  
**Formatting**: `black`  
**Rationale**:
- Modern, fast Python tooling
- Excellent Django support
- Type safety for GraphQL and API contracts

### 6.2 Testing

**Framework**: `pytest` with `pytest-django`  
**Coverage**: `pytest-cov`  
**Rationale**:
- Industry standard for Python testing
- Excellent Django integration
- Good fixture support for multi-tenant testing

---

## 7. SDK Generation

### 7.1 OpenAPI to SDK

**Technology**: `openapi-generator` or `openapi-python-client`  
**Rationale**:
- Industry standard for SDK generation
- Supports multiple languages (Python, JavaScript/TypeScript)
- Maintains consistency with API contracts

**Documentation**: 
- openapi-generator: https://openapi-generator.tech/
- openapi-python-client: https://github.com/openapi-generators/openapi-python-client

---

## 8. Security & Authentication

### 8.1 JWT Library

**Technology**: `PyJWT`  
**Version**: Latest stable (2.8+)  
**Rationale**:
- Industry standard JWT library
- Excellent Django integration
- Supports RS256/ES256 algorithms
- Good security practices

**Documentation**: https://pyjwt.readthedocs.io/

### 8.2 Password Hashing

**Technology**: Django's built-in password hashing (PBKDF2/Argon2)  
**Rationale**:
- Built into Django
- Secure by default
- Configurable algorithms

---

## 9. Data Processing

### 9.1 Data Quality Engines

**Great Expectations**: Python package (latest stable)  
**Soda**: Python package (latest stable)  
**Rationale**:
- Industry standard DQ frameworks
- Python-native (matches stack)
- Good documentation and community

### 9.2 Compliance Detection

**Technology**: Custom implementation with regex/dictionary/ML  
**Libraries**: `pandas`, `numpy` for data processing  
**Rationale**:
- Full control over detection logic
- Can integrate with external ML models
- Python-native processing

---

## 10. Dependency Management

### 10.1 Python Dependencies

**Format**: `requirements.txt` and `requirements-dev.txt`  
**Version Pinning**: Pin all production dependencies  
**Rationale**:
- Reproducible builds
- Security scanning support
- Clear dependency tree

### 10.2 Node.js Dependencies

**Format**: `package.json` with `package-lock.json`  
**Version Pinning**: Lock file for reproducible builds  
**Rationale**:
- Standard Node.js practice
- Reproducible builds
- Security scanning support

---

## 11. Version Compatibility Matrix

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.11.x | Minimum 3.11.0 |
| Django | 4.2+ | Latest stable |
| PostgreSQL | 16.x | Minimum 16.0 |
| Redis | 7.x | Minimum 7.0 |
| Node.js | 22.x | For SDK generation and tooling |
| Docker | 24+ | For container builds |

---

## 12. Migration Path

**Current State**: Documentation defines requirements  
**Target State**: Implementation using above stack  
**Migration Notes**:
- All new code MUST use these technologies
- Existing code (if any) should be migrated to match
- No deviations without explicit approval

---

## 13. References

- Django Documentation: https://docs.djangoproject.com/
- Strawberry GraphQL: https://strawberry.rocks/
- structlog: https://www.structlog.org/
- Prometheus Python Client: https://github.com/prometheus/client_python
- OpenTelemetry Python: https://opentelemetry.io/docs/instrumentation/python/
- PostgreSQL: https://www.postgresql.org/docs/
- Redis: https://redis.io/docs/
- GitHub Actions: https://docs.github.com/en/actions

---

**Document Owner**: Engineering Team  
**Review Cycle**: Quarterly or when major technology changes are needed

