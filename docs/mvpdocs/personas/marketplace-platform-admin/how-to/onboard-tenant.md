# How-To: Onboard a Tenant

This guide covers the full tenant onboarding workflow, from KYC review
through activation and initial configuration.


## Tenant Lifecycle

A tenant progresses through these states:

```
PENDING_REVIEW  -->  APPROVED  -->  ACTIVE
                -->  REJECTED
ACTIVE          -->  SUSPENDED  -->  ACTIVE (reinstate)
                -->  DEACTIVATED
```

Only an MPA with `is_staff=true` can transition tenants between states.


## Reviewing KYC Applications

### Via the Admin Panel

1. Navigate to **Tenants** in the Django Admin panel.
2. Filter by KYC status: **PENDING_REVIEW**.
3. Open the tenant detail view.
4. Review the submitted documentation:
   - **Organization name** and registration number.
   - **Primary contact** name and email.
   - **Intended use case** (data provider, consumer, or both).
   - **Uploaded documents** (business registration certificate, proof of
     address, etc.).
5. Cross-check against your platform's onboarding criteria (e.g.,
   legitimate business entity, no sanctions list matches, acceptable
   jurisdiction).

### Approval

If the application meets all criteria:

1. Click **Approve** on the tenant detail page.
2. The system transitions the tenant to `APPROVED` and sends an
   activation email to the primary contact.
3. The tenant becomes `ACTIVE` once the contact confirms their email and
   sets up billing.

### Rejection

If the application does not meet criteria:

1. Click **Reject**.
2. Enter a **rejection reason** (visible to the applicant in their
   notification email).
3. The tenant transitions to `REJECTED`. They may reapply with updated
   documentation.


## Post-Approval Setup

After a tenant is approved, the MPA should:

1. **Assign a plan tier** -- Free, Starter, Professional, or Enterprise.
   This determines usage quotas (asset count, storage, API calls).
2. **Verify billing** -- Confirm the tenant has a valid payment method
   on file (for paid tiers).
3. **Set tenant-specific overrides** (optional) -- If the tenant needs
   custom DQ profiles or compliance thresholds that differ from platform
   defaults.
4. **Assign initial roles** -- Ensure the tenant's primary contact has
   the `TENANT_ADMIN` role so they can invite their own users.


## Suspending a Tenant

Suspension is appropriate for:

- Non-payment after grace period.
- Policy violations (e.g., publishing prohibited content).
- Security incidents requiring investigation.

To suspend:

1. Open the tenant in the admin panel.
2. Click **Suspend** and enter a reason.
3. All users in the tenant lose access immediately. Data is preserved.
4. The primary contact receives a suspension notification with the reason
   and instructions to contact support.

To reinstate, click **Reinstate** on the suspended tenant.


## Deactivating a Tenant

Deactivation is permanent (within the billing cycle). Use it for:

- Tenant-requested account closure.
- Prolonged non-payment with no response.

To deactivate:

1. Open the tenant in the admin panel.
2. Click **Deactivate** and confirm.
3. Data is retained for the configured retention period (default 90 days)
   before permanent deletion.


## See Also

- [How-To: Configure Platform Defaults](configure-platform-defaults.md)
- [How-To: Monitor Marketplace Metrics](monitor-marketplace-metrics.md)
- [MPA Reference](../reference.md)
