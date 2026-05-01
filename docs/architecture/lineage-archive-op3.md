# Lineage archive — OP-3 sign-off

**Phase:** 228 F5 (228.F5.1)
**Owner:** Data Platform Eng (proposer); Compliance (approver); SRE (operator)
**Status:** SIGN-OFF SCAFFOLD — awaits Compliance signature
**Last reviewed:** 2026-05-01

This doc captures the operational decision (OP-3) on the
lineage-data lifecycle: how long lineage edges remain queryable
in the hot tier, when they migrate to warm/cold tiers, and what
compliance constraints govern each stage.

## Decision (proposed)

**Tier transitions** (aligned with spec REQ-LIN-F5-004):

| Stage | Storage | Duration | Query latency target |
|---|---|---|---|
| 1. Hot | Postgres `contracts_lineage_edge` | 0 — 12 mo | < 100 ms (P95) |
| 2. Archive | Postgres `contracts_lineage_edge_archive` | 12 — 36 mo | < 1 s (P95) |
| 3. Cold (Glacier) | S3 Glacier Flexible Retrieval, jsonl.gz bundles | 36 — 84 mo | minutes — 12 h (restore) |
| 4. Deep Archive | S3 Glacier Deep Archive | 84 mo — 25 y | 12 — 48 h (restore) |
| 5. Hard expiry | (deleted) | > 25 y | n/a |

The S3 lifecycle policy in [infrastructure/terraform/lineage_archive/](../../infrastructure/terraform/lineage_archive/) implements stages 3-5 — objects land in S3 Standard initially (the mgmt command's PUT goes to Standard), then S3 lifecycle transitions them to Glacier at 1095 days (36 mo) and to Deep Archive at 2557 days (84 mo). The `archive_lineage_edges --target=s3` step DELETES the archive row from `LineageEdgeArchive` after a successful PUT (per REQ-LIN-F5-004 spec scenario "Archive to S3"); the S3 object becomes the canonical record for stages 3-5.

**Quarterly invariant:** `rows(LineageEdge) <= 1.5 * open_edges`. A
violation triggers an immediate archival run + opens a P1 capacity
ticket. Pinned by [scripts/lineage_history_growth.py](../../scripts/lineage_history_growth.py).

## Compliance check-list

Compliance approval requires (1) the deletion at end-of-life is
documented (✅ — Terraform `lifecycle.expiration.days` set to 9125
= 25 y), (2) the data is encrypted at rest at every tier (✅ —
RDS at-rest encryption is on by default on the platform RDS;
S3 SSE-AES256 enforced via the Terraform module + denied non-TLS
access at the bucket policy), (3) tenant deletion cascades into
the archive table (✅ — `tenant` FK on `LineageEdgeArchive` uses
`on_delete=CASCADE`), (4) audit trail of any restore operation
(✅ — RDS PITR + S3 access logs).

## Sign-off table

| Role | Name | Signed | Date |
|---|---|---|---|
| Data Platform Eng (proposer) | _to be filled_ | ☐ | _YYYY-MM-DD_ |
| Compliance | _to be filled_ | ☐ | _YYYY-MM-DD_ |
| SRE (operator) | _to be filled_ | ☐ | _YYYY-MM-DD_ |

## Cost basis

The 12-month forecast for lineage storage costs is at
[docs/capacity/lineage-cost-12mo.md](../capacity/lineage-cost-12mo.md).
The dominant lever is the warm-tier RDS row count; once a tenant's
edge volume crosses a project-defined threshold, the hot/warm
split should compress.

## Related

- [Capacity script](../../scripts/lineage_history_growth.py)
- [Archive command](../../hub/apps/contracts/management/commands/archive_lineage_edges.py)
- [Terraform module](../../infrastructure/terraform/lineage_archive/main.tf)
- [PITR + RTO/RPO](../runbooks/lineage-pitr-rto-rpo.md)
- [Failure runbook](../runbooks/lineage-archive-job-failure.md)
