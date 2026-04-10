# Data Residency

Data residency controls ensure that tenant data is stored and processed only
within approved geographic regions. These controls are critical for satisfying
regulations such as GDPR (which restricts cross-border transfers) and LGPD
(which imposes similar requirements for Brazilian personal data).

## Tenant-Level Region Configuration

Each [tenant](../concepts/tenants.md) specifies a primary storage region at
creation time. All [assets](../concepts/assets.md), metadata, and audit events
belonging to that tenant are stored exclusively within the designated region.

```json
POST /api/v1/tenants
{
  "name": "acme-healthcare",
  "region": "eu-west-1",
  "compliance_regulations": ["gdpr", "hipaa"]
}
```

The `region` field is immutable after tenant creation in the MVP release. To
change a tenant's region, a migration request must be submitted through the
platform operator workflow.

## Storage Location Guarantees

- **Object storage** -- all uploaded files and dataset payloads are written to
  buckets scoped to the tenant's region.
- **Database records** -- metadata, compliance results, and audit events are
  stored in the regional database partition.
- **Search indices** -- the search subsystem replicates only within the same
  region to prevent data leakage across boundaries.
- **Backups** -- encrypted backups remain in the same region as the source data.

## Cross-Region Replication Controls

Cross-region replication is disabled by default. When two tenants in different
regions need to share data through the [marketplace](../concepts/marketplace-listings.md),
the platform enforces the following rules:

1. The source tenant's compliance regulations are evaluated. If any regulation
   prohibits cross-border transfer to the destination region, the share is
   blocked.
2. If the transfer is permitted, data is encrypted in transit using TLS 1.3 and
   a copy is created in the destination region. The original remains untouched.
3. The [audit trail](audit-trail.md) records both the source and destination
   regions for every cross-region transfer event.

## MVP Scope

The MVP release supports **single-region deployments only**. All tenants within
a single Meshant installation share one region. Multi-region federation --
allowing a single control plane to manage tenants across multiple geographic
regions -- is planned for the post-MVP roadmap.

## Further Reading

- [Tenants concept](../concepts/tenants.md)
- [Regulations](regulations.md)
- [Audit Trail](audit-trail.md)
- [Security Posture](security-posture.md)
