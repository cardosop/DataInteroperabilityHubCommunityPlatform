# JOURNEY-PA-001: Onboard Marketplace Instance

**Persona:** [Marketplace & Platform Admin](../personas/marketplace-platform-admin/)
**Use Cases:** UC-PA-001, UC-PA-002

## Overview

A Platform Admin provisions a new Meshant marketplace instance for a
tenant, configures branding and default policies, invites the first
users, and runs a smoke test to confirm the instance is operational.
This journey is the entry point for every new organization joining
the Meshant platform.

## Journey Steps

1. **Provision tenant** — The Platform Admin navigates to "Admin >
   Tenants > New Tenant" and fills in the tenant registration form:
   organization name, billing contact, plan tier (Starter, Professional,
   Enterprise), and preferred subdomain (e.g., `meshant-internal.example.com`).
   On submit the platform provisions the [tenant](../concepts/tenants.md)
   with isolated storage, a dedicated database schema, and default
   API rate limits based on the selected plan.

2. **Configure branding** — The admin customizes the tenant's visual
   identity: logo upload (SVG or PNG, max 2 MB), primary and secondary
   brand colors, custom favicon, and optional custom email templates
   for transactional emails (welcome, password reset, notifications).
   The branded experience applies to the tenant's marketplace
   subdomain and all user-facing emails.

3. **Set default policies** — The admin configures tenant-wide default
   settings:

   - **ODCS version:** The default data contract standard version
     (e.g., `odcs/v1`).
   - **DQ profile:** Default quality checks applied to new assets
     (completeness, uniqueness thresholds).
   - **Compliance threshold:** Maximum acceptable risk level for
     marketplace publication (e.g., `MEDIUM`).
   - **Retention policy:** Default data retention period per
     classification.
   - **Rate limits:** API request limits per user role and endpoint.

   These defaults can be overridden at the asset or policy level.

4. **Invite initial users** — The admin sends email invitations to
   the first users, assigning each an initial role:

   - **Tenant Admin:** Full administrative access.
   - **Data Product Owner:** Asset creation and management.
   - **Compliance Officer:** Compliance scanning and GDPR management.
   - **Data Consumer:** Marketplace browsing and purchasing.

   Invited users receive an email with a registration link that
   pre-fills their tenant association (see
   [JOURNEY-AUTH-001](JOURNEY-AUTH-001.md)).

5. **Run smoke test** — The admin executes the built-in smoke test
   suite from "Admin > Diagnostics." The smoke test verifies:

   - Tenant isolation: API calls are scoped to the correct tenant.
   - Storage access: File upload and download succeed.
   - Search: Indexing and query return expected results.
   - Authentication: Login, token refresh, and role enforcement work.
   - Compliance: A sample compliance scan completes.
   - Webhooks: A test webhook fires and reaches the configured URL.

   Results are displayed as a pass/fail checklist. Any failures
   include diagnostic information and recommended remediation steps.

6. **Handoff to tenant** — Once the smoke test passes the admin marks
   the tenant as `active` and notifies the organization's primary
   contact. An `tenant.onboarded` [audit event](../concepts/audit-events.md)
   is recorded with the provisioning details.

## Success Criteria

- The tenant is provisioned with isolated resources and correct plan
  limits.
- Branding is applied consistently across the subdomain and emails.
- Default policies are saved and applied to new assets automatically.
- All invited users receive invitation emails and can register.
- The smoke test passes all checks with no failures.
- A `tenant.onboarded` audit event is recorded.

## Related

- Concepts: [Tenants](../concepts/tenants.md), [Users and Roles](../concepts/users-and-roles.md), [Governance](../concepts/governance.md), [Audit Events](../concepts/audit-events.md)
- How-To: [MPA How-To Guides](../personas/marketplace-platform-admin/how-to/)
- Journeys: [JOURNEY-TA-007](JOURNEY-TA-007.md) (Monitor Costs), [JOURNEY-MPA-005](JOURNEY-MPA-005.md) (Admin Operations)
