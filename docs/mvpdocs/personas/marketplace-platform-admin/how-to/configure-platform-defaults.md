# How-To: Configure Platform Defaults

Platform defaults define the baseline data quality, compliance, and
governance rules applied to all tenants. Tenants can override these
defaults with stricter (but not looser) settings.


## Data Quality Profiles

A DQ profile is a named collection of threshold rules applied to assets
during automated quality checks.

### Creating a Default Profile

1. In the Django Admin panel, navigate to **Governance > DQ Profiles**.
2. Click **Add DQ Profile**.
3. Set the name to `platform-default` (the reserved name for the
   platform-wide baseline).
4. Configure dimension thresholds:

| Dimension | Threshold | Severity |
|-----------|-----------|----------|
| Completeness | >= 90% | WARNING below, FAIL below 70% |
| Uniqueness | >= 95% | WARNING below, FAIL below 80% |
| Validity | >= 98% | WARNING below, FAIL below 90% |
| Freshness | <= 24 hours | WARNING above, FAIL above 72 hours |
| Consistency | >= 85% | WARNING below, FAIL below 60% |

5. Save the profile.

Any new asset that does not have a tenant-level or asset-level DQ profile
will be evaluated against `platform-default`.

### Overriding at the Tenant Level

Tenants with `TENANT_ADMIN` can create their own profiles that must be
**equal to or stricter** than the platform default. For example, a
healthcare tenant might require 99% validity instead of 98%.

To verify overrides are compliant, the admin panel shows a comparison
view: **Governance > DQ Profile Comparison**.


## Compliance Thresholds

### Enabling Automated Scanning

1. Navigate to **Governance > Compliance Settings**.
2. Toggle on the regulations you want to enforce platform-wide:
   - **GDPR** -- PII detection, consent tracking, retention.
   - **HIPAA** -- PHI detection, access controls, audit trail.
3. Set the **scan schedule** (daily is recommended for active
   marketplaces; weekly for smaller deployments).
4. Set the **minimum listing score**: assets below this score will not
   appear in the marketplace. Recommended starting point: 80%.

### Configuring Scan Rules

Each regulation has configurable rule sets:

```bash
datahub compliance rules --regulation GDPR --format table
```

This lists all available GDPR rules with their current enabled/disabled
status and severity. To modify:

1. Open **Governance > Compliance Rules** in the admin panel.
2. Enable or disable individual rules.
3. Set severity per rule (INFO, WARNING, CRITICAL).
4. Save changes. The next scan run will use the updated rule set.


## Retention Policies

Retention policies control how long data and metadata are preserved after
deletion or deactivation.

### Platform-Wide Defaults

1. Navigate to **Governance > Retention Policies**.
2. Configure default retention periods:

| Data Type | Default Retention | Configurable Range |
|-----------|------------------|--------------------|
| Asset data (after archive) | 90 days | 30--365 days |
| Audit logs | 365 days | 90--730 days |
| Billing records | 7 years | 5--10 years (regulatory) |
| User PII (after deletion) | 30 days | 0--90 days |

3. Save. These defaults apply unless overridden at the tenant level.


## Domain Taxonomy

The domain taxonomy defines the set of business domains available for
classifying assets (e.g., `finance`, `healthcare`, `marketing`).

### Managing Domains

1. Navigate to **Governance > Domains** in the admin panel.
2. Add, rename, or archive domains.
3. Assign a domain owner (optional) for each domain.
4. Domains cannot be deleted if assets are assigned to them; archive
   them instead.

Via CLI:

```bash
datahub governance domains --format table
```


## Verifying Configuration

After making changes, verify the platform state:

```bash
# Check tenant usage and plan limits
datahub tenants usage --format table

# Check DQ status for a sample asset
datahub dq status --asset-id <asset-id> --format table

# Check compliance rules
datahub compliance rules --regulation GDPR --format table
```


## See Also

- [How-To: Onboard Tenant](onboard-tenant.md)
- [How-To: Monitor Marketplace Metrics](monitor-marketplace-metrics.md)
- [MPA Reference](../reference.md)
