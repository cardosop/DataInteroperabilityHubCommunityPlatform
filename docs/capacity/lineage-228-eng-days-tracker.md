# Phase 228 — eng-days tracker

**Phase:** 228 (overall — 228.0/F1/F2/F3/F4/F5 + X)
**Owner:** Engineering Lead + EM
**Last reviewed:** 2026-05-01

228.DoD.7 calls for tracking total eng-days spent vs the +25%
buffer (~74 eng-days budget). This doc is the running ledger.

## Budget envelope

| Component | Estimate | +25% buffer | Source |
|---|---|---|---|
| 228.0 Foundations | 9 | **11** | tasks.md "228.0 — Foundations (P0 prereq, ~11 eng-days w/ buffer)" |
| 228.F1 Cross-tenant marketplace | 5 | **6** | tasks.md "(P1, ~6 eng-days w/ buffer)" |
| 228.F4 OpenLineage | 9 | **11** | tasks.md "(P1, ~11 eng-days w/ buffer)" |
| 228.F2 Field-level mapping | 20 | **25** | tasks.md "(P1, ~25 eng-days w/ buffer)" |
| 228.F5 Time-travel + diff | 7 | **9** | tasks.md "(P1, ~9 eng-days w/ buffer)" |
| 228.F3 Notifications | 10 | **12** | tasks.md "(P1, ~12 eng-days w/ buffer)" |
| 228.X Cross-cutting | (concurrent) | (folded in) | tasks.md "runs concurrently with each phase" |
| **Total** | **60** | **74** | |

## Actuals

Update this section weekly. The format is intentionally simple —
one row per phase per ISO week, capturing the delta from the
previous reading. The retro (228.DoD.5) reads this table to
compute the variance vs budget.

| Week (ISO) | 228.0 | F1 | F4 | F2 | F5 | F3 | X | Notes |
|---|---|---|---|---|---|---|---|---|
| _e.g. 2026-W18_ | 11 | 6 | 11 | 25 | 9 | 0 | 4 | F3 not yet started; X concurrent — partial spend rolled into each phase. |

(Replace the placeholder row above with real readings as they
arrive.)

## Variance triggers

Trip an out-of-cycle EM check-in:

| Signal | Threshold | Action |
|---|---|---|
| Single phase exceeds its +25% buffer | actual > buffer for that phase | EM 1:1 with phase lead; assess scope vs schedule. |
| Cumulative spend exceeds 90% of total buffer | actual > 67 eng-days | Rebalance remaining work; defer non-DoD items. |
| Cumulative spend exceeds 100% of total buffer | actual > 74 eng-days | Engineering Lead escalation; explicit re-estimation OR descope. |

## Closeout

228.DoD.7 closes when:

1. The "Actuals" table has the **final** row (the week the F5 100%
   rollout ships).
2. The variance vs the +25% buffer is computed in the retro
   (228.DoD.5).
3. Any phase that exceeded its buffer carries a postmortem note
   in the retro action-items.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |
| EM | _to be filled_ | _YYYY-MM-DD_ |

## Related

- [Retro template](../retros/lineage-228-retro-template.md) — consumes this tracker.
- [Cost forecast](../cost/lineage-feature.md) — separate axis (AWS spend vs eng spend).
