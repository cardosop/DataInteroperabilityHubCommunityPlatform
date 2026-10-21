# Lineage F1 — Cross-tenant marketplace lineage

**Audience:** Data product owners, marketplace consumers
**Capability flag:** `lineage.cross_tenant_marketplace`

## What it does

When you browse a marketplace listing, the **Lineage** tab now shows
the upstream contracts the listing's data product depends on —
even when those upstreams live in another tenant's catalog.

Two detail tiers:

- **Summary** (pre-purchase) — graph topology only; transformation
  IP (the SQL / dbt / job-id metadata) is stripped server-side.
- **Full** (post-purchase) — same graph, with transformation IP
  visible. Available only after your tenant holds an ACTIVE
  Entitlement for the listing's backing asset.

## How to use

1. Open a marketplace listing.
2. Click the **Lineage** tab.
3. Toggle "Summary" / "Full" — Full requires an active
   entitlement.

## Common questions

See [the support FAQ](../support/lineage-faq.md) for cross-tenant
escalation procedures.
