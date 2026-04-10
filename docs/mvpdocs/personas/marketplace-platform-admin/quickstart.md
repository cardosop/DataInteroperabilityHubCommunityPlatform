# Marketplace & Platform Admin Quickstart

This guide walks you through the first tasks a new Marketplace & Platform
Admin performs after gaining access. By the end, you will have reviewed a
tenant application, configured platform defaults, and checked marketplace
metrics.

**Prerequisites:**

- A Meshant account with `TENANT_ADMIN` role and `is_staff=true`.
- Access to the Django Admin panel at `/admin/`.


## Step 1: Access the Admin Dashboard

Log in to the Meshant web UI. Staff users see an **Admin** link in the
top navigation bar that opens the Django Admin panel.

Key sections in the admin panel:

| Section | Purpose |
|---------|---------|
| **Tenants** | Manage tenant lifecycle (KYC, activation, suspension) |
| **Users** | Cross-tenant user management and role assignment |
| **Billing** | Plan tiers, invoices, usage reports |
| **Governance** | DQ profiles, compliance thresholds, retention policies |
| **Audit Log** | Platform-wide activity log |


## Step 2: Review Tenant KYC Status

Navigate to **Tenants** in the admin panel. Pending tenants appear with
a KYC status of `PENDING_REVIEW`.

For each pending tenant:

1. Open the tenant detail view.
2. Review the submitted KYC documentation (business registration,
   contact details, intended use case).
3. Verify against your platform's onboarding criteria.
4. Click **Approve** to activate the tenant, or **Reject** with a
   reason that will be sent to the applicant.

Via CLI:

```bash
# List tenants by KYC status
datahub-cli tenants usage --format table
```

For full KYC management workflows, see
[How-To: Onboard Tenant](how-to/onboard-tenant.md).


## Step 3: Configure Platform Defaults

Navigate to **Governance** in the admin panel. Here you set the baseline
rules that apply to all tenants unless overridden.

### Data Quality Profiles

1. Open **DQ Profiles**.
2. Create or edit the **Default** profile.
3. Set thresholds for each dimension:
   - Completeness: minimum 90%
   - Uniqueness: minimum 95% (for key columns)
   - Validity: minimum 98%
   - Freshness: maximum 24 hours since last update
4. Save the profile. New assets will inherit this profile unless the
   tenant configures a custom one.

### Compliance Thresholds

1. Open **Compliance Settings**.
2. Enable automatic scanning for GDPR and/or HIPAA.
3. Set the scan schedule (e.g., daily, weekly).
4. Configure the minimum compliance score required for a listing to
   appear in the marketplace (e.g., 80%).

For detailed configuration, see
[How-To: Configure Platform Defaults](how-to/configure-platform-defaults.md).


## Step 4: Check Marketplace Metrics

Navigate to the **Marketplace Dashboard** (available from the admin
panel or the main web UI under **Analytics**).

Key metrics to review on first login:

| Metric | What to Look For |
|--------|-----------------|
| **Total Tenants** | Baseline count after initial setup |
| **Active Listings** | Number of ACTIVE marketplace listings |
| **Total Revenue (MTD)** | Month-to-date revenue across all tenants |
| **Pending KYC** | Applications awaiting review |
| **DQ Pass Rate** | Percentage of assets passing quality checks |
| **Compliance Score** | Average compliance scan score across listings |

For ongoing monitoring practices, see
[How-To: Monitor Marketplace Metrics](how-to/monitor-marketplace-metrics.md).


## Step 5: Verify Billing Configuration

Navigate to **Billing** in the admin panel:

1. Confirm that **plan tiers** are configured (e.g., Free, Starter,
   Professional, Enterprise).
2. Verify **usage quotas** per tier (asset count, storage, API calls).
3. Check that the **payment processor** integration is active.
4. Review any **pending invoices** and confirm they match expected
   amounts.

Via CLI:

```bash
datahub-cli tenants usage --format table
```


## What Next?

- [How-To: Onboard Tenant](how-to/onboard-tenant.md) -- full KYC
  approval workflow
- [How-To: Configure Platform Defaults](how-to/configure-platform-defaults.md)
  -- DQ profiles, compliance, retention
- [How-To: Monitor Marketplace Metrics](how-to/monitor-marketplace-metrics.md)
  -- revenue, SLAs, growth tracking
- [Reference](reference.md) -- full API, CLI, and SDK links
