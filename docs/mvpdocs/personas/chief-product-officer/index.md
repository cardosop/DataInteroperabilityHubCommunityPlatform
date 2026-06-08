# Chief Product Officer (CPO)

> Also known as: Platform Owner, Product Strategy Lead, Head of Data Products

## Who You Are

You are responsible for product strategy, cost oversight, and marketplace
health within Meshant. You monitor billing and usage analytics, manage tenant
onboarding and KYC verification, configure platform-wide defaults, and ensure
the marketplace has healthy supply (providers) and demand (consumers).

Typical job titles that map to this persona:

- Chief Product Officer / Head of Product
- Platform Owner / Platform Operations Lead
- VP of Data Products
- Business Owner / General Manager — Data

## What You Care About

| Priority | Description |
|----------|-------------|
| Cost visibility | Real-time billing dashboards, per-tenant usage, revenue tracking. |
| Marketplace health | Supply-demand balance, listing quality, transaction volume. |
| Tenant onboarding | KYC verification, plan assignment, tenant lifecycle management. |
| Platform defaults | DQ profiles, compliance thresholds, rate limits, ODCS versions. |
| Growth metrics | Active providers, active consumers, monthly recurring revenue. |

## Your MVP Capabilities

1. **Billing oversight dashboard** — view per-tenant usage, plan limits,
   and revenue aggregates in real time.
2. **Tenant KYC onboarding** — review and approve tenant identity
   verification; manage tenant lifecycle (active, suspended, offboarded).
3. **Platform default configuration** — set organization-wide defaults
   for ODCS versions, DQ profiles, compliance risk thresholds, and API
   rate limits.
4. **Marketplace oversight** — approve, de-list, or feature marketplace
   listings; monitor transaction volumes and dispute rates.
5. **Global metrics monitoring** — track active tenants, published
   listings, monthly orders, and revenue trends.

## Key Journeys

- [Onboard a New Tenant](../../journeys/JOURNEY-CPO-001.md)
- [Review Marketplace Health](../../journeys/JOURNEY-CPO-006.md)
- [Configure Platform Defaults](../../journeys/JOURNEY-CPO-007.md)
- [Monitor Billing and Usage](../../journeys/JOURNEY-CPO-008.md)
- [Manage Tenant Lifecycle](../../journeys/JOURNEY-CPO-009.md)
- [Generate Platform Analytics Report](../../journeys/JOURNEY-CPO-010.md)

## Typical Day

1. Open the **CPO Dashboard** and review platform health metrics (active
   tenants, listing volume, revenue).
2. Review pending KYC applications — approve or request additional
   documentation.
3. Check billing alerts — investigate any tenant approaching plan limits.
4. Review flagged marketplace listings for compliance or quality issues.
5. Update platform default configuration based on recent policy changes.

## Related Concepts

- [Billing & Plans](../../concepts/billing.md) — subscription tiers and usage limits
- [Tenant Management](../../concepts/tenants.md) — tenant lifecycle and KYC
- [Marketplace Listings](../../concepts/marketplace-listings.md) — listing approval and oversight
- [Platform Configuration](../../concepts/platform-config.md) — organization-wide defaults

## Permissions and Roles

The CPO persona maps to the **PLATFORM_ADMIN** role in Meshant RBAC.
This role grants:

- Cross-tenant read access to all platform resources.
- Write access to tenant records (onboarding, KYC status, plan assignment).
- Write access to platform configuration (rate limits, defaults, feature flags).
- Read access to billing and usage data across all tenants.
- Execute permissions for marketplace oversight actions (approve, de-list).

## Get Started

- [5-Minute Quickstart](quickstart.md) — review your platform dashboard
- [How-To Guides](how-to/) — tenant onboarding, billing, platform config
- [API / CLI / SDK Reference](reference.md) — admin endpoints and commands
