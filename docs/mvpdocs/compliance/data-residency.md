# Data Residency

Data residency controls ensure that tenant data is stored and processed only
within approved geographic regions. These controls are critical for satisfying
regulations such as GDPR (which restricts cross-border transfers) and LGPD
(which imposes similar requirements for Brazilian personal data).

## MVP Scope and Limitations

> **Important:** The MVP release supports **single-region deployments only**.
> All tenants within a single Meshant installation share one AWS region.
> The `region` field on the Tenant model is stored as a preference but **not
> enforced** at the storage, database, or query level in the current release.
> Do not rely on region-based isolation for regulatory compliance until
> enforcement is implemented in a future release.

## Tenant-Level Region Configuration

Each [tenant](../concepts/tenants.md) may specify a preferred storage region at
creation time. In the MVP release this value is recorded but not enforced — all
data resides in the single deployment region regardless of the `region` value.

```json
POST /api/v1/tenants
{
  "name": "acme-healthcare",
  "region": "eu-west-1",
  "compliance_regulations": ["gdpr", "hipaa"]
}
```

## Storage Location Guarantees (Post-MVP)

The following guarantees are **planned for a future release** and are not
enforced in the MVP:

- **Object storage** -- files and dataset payloads written to region-scoped
  buckets.
- **Database records** -- metadata stored in regional database partitions.
- **Search indices** -- replication limited to the tenant's region.
- **Backups** -- encrypted backups remain in the same region as source data.

## Cross-Region Replication Controls (Post-MVP)

Cross-region sharing through the
[marketplace](../concepts/marketplace-listings.md) with automatic compliance
checks and audit logging is planned for post-MVP. In the current release, all
marketplace operations occur within the single deployment region.

## Further Reading

- [Tenants concept](../concepts/tenants.md)
- [Regulations](regulations.md)
- [Audit Trail](audit-trail.md)
- [Security Posture](security-posture.md)
