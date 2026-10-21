# File quota exhaustion

## Symptoms

Tenant hits storage ceiling; uploads return `FILES_DISABLED`/`RATE_LIMIT`.

## Steps

1. Confirm billing SKU vs actual usage via FinOps dashboards.
2. Negotiate uplift or archival per legal retention posture.
3. Optionally enable curated cold-storage tier when Phase 260.2 lands.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
