# Data Residency

**Last Updated**: 2026-02-03

This document describes the current data residency behavior and roadmap for multi-region support.

---

## Current Behavior

### Single Region Deployment

The platform currently operates in a **single region** deployment model:

- All tenant data is stored in the same cloud region
- The `Tenant.region` field is **informational only** and does not affect data storage location
- All services (API, database, storage, compute) run in the same region
- No cross-region data replication or failover is currently implemented

### Tenant Region Field

The `Tenant.region` field in the Tenant model:

- **Purpose**: Informational field for tracking tenant preferences or compliance requirements
- **Current behavior**: Does not affect where data is stored or processed
- **Future use**: Will be used to determine data storage location in multi-region deployments

**Example**:
```python
tenant = Tenant.objects.create(
    name="EU Customer",
    slug="eu-customer",
    region="eu-west-1"  # Informational only
)
```

---

## Roadmap: Multi-Region Support

### Phase 1: Multi-Region Data Storage (Planned)

**Goal**: Store tenant data in the region specified by `Tenant.region`

**Requirements**:
- Database sharding or replication by region
- S3-compatible storage buckets per region
- Region-aware service routing
- Cross-region data synchronization for federated assets

**Implementation considerations**:
- Tenant region cannot be changed after creation (data migration complexity)
- Platform admin operations may require cross-region access
- Audit logs and compliance data must respect regional requirements

### Phase 2: Regional Failover (Future)

**Goal**: Automatic failover to backup region in case of primary region failure

**Requirements**:
- Cross-region data replication
- Health monitoring and automatic failover
- DNS-based region routing
- Data consistency guarantees

---

## Job Queue Fairness

### Current Implementation

Job queues (django-rq) operate with tenant-aware fairness:

- **Reserved slots**: Each tenant can reserve a minimum number of concurrent job slots
- **Shared slots**: Additional slots are shared across tenants based on demand
- **Per-tenant limits**: Maximum concurrent jobs per tenant enforced via `TenantConfig.max_job_concurrency`

### Configuration

Job queue fairness is configured via:

1. **TenantConfig.max_job_concurrency**: Maximum concurrent running jobs for the tenant
2. **TenantConfig.max_queued_jobs**: Maximum queued jobs for the tenant
3. **Platform defaults**: Applied when tenant-specific config is not set

### Fairness Algorithm

1. Check tenant's reserved slots availability
2. If reserved slots available, allocate job immediately
3. If reserved slots full, check shared pool availability
4. If shared pool available and tenant hasn't exceeded max_job_concurrency, allocate job
5. Otherwise, queue job (up to max_queued_jobs limit)

### Per-Tenant Limits

Per-tenant limits are enforced at:

- **Job creation**: `hub.apps.jobs.utils.check_tenant_job_limits()`
- **Service layer**: `GovernanceService.check_tenant_resource_limits()`
- **Business rules**: Job creation workflows validate limits before queuing

**See also**:
- `docs/SERVICES_ARCHITECTURE.md` - Service architecture and job processing
- `docs/RUNBOOKS.md` - Operational runbooks including job queue management

---

## Compliance Considerations

### GDPR

- **Data location**: Currently all data stored in single region (may not meet GDPR requirements for EU data)
- **Data transfer**: Cross-region data transfers may require additional compliance measures
- **Right to erasure**: Must be implemented per-region when multi-region is deployed

### Regional Compliance

Different regions may have specific compliance requirements:

- **EU**: GDPR requires data to remain in EU
- **US**: Some states require data to remain in-state
- **China**: Data localization requirements

**Current limitation**: Single-region deployment may not meet all regional compliance requirements.

---

## Migration Path

When multi-region support is implemented:

1. **Existing tenants**: Will remain in default region unless explicitly migrated
2. **New tenants**: Can specify region at creation time
3. **Region migration**: Will require data migration and downtime (to be documented separately)

---

## Related Documentation

- `docs/TENANT_ISOLATION.md` - Tenant isolation and multi-tenancy
- `docs/SERVICES_ARCHITECTURE.md` - Service architecture including job queues
- `docs/RUNBOOKS.md` - Operational runbooks
