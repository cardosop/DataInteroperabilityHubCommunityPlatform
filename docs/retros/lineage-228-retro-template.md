# Phase 228 — post-launch retro template

**Phase:** 228 (overall)
**Owner:** Engineering Lead + EM
**Cadence:** within **14 calendar days** of the F5 100% rollout
(228.DoD.5 + 228.DoD.6).
**Last reviewed:** 2026-05-01

This is the canonical post-launch retro template. Engineering Lead
schedules the meeting on the day F5 hits 100% (the final phase to
roll out). Attendance: every contributor to Phase 228 + on-call
who paged on a 228-related incident during the rollout window.

## Inputs to gather BEFORE the meeting

The facilitator pulls these from the production telemetry +
existing dashboards + tracker links:

| Input | Source |
|---|---|
| Total eng-days actual vs +25% buffer (~74 budgeted) | [docs/capacity/lineage-228-eng-days-tracker.md](../capacity/lineage-228-eng-days-tracker.md) |
| Production incidents (P1/P2) opened during rollout | `gh issue list --label P1,lineage --label P2,lineage --search "created:>=<rollout-start>"` |
| F4 round-trip CI gate trend | `.github/workflows/openlineage-f4-dod.yml` artifacts |
| F5 capacity invariant trend | `lineage_history_growth.py` JSON artifacts (quarterly) |
| Customer feedback (CS tickets tagged `lineage`) | Linear / Zendesk (whichever the team uses) |
| Per-phase audit-event volume | `LINEAGE_*` action counts on `AuditEvent` |
| Per-phase API error budget | Grafana — 5xx rate per route during the rollout |
| Per-phase capability flag flip timestamps | Helm value diff history (rollout PRs) |

## Agenda (90 min)

| Time | Topic |
|---|---|
| 0:00 - 0:10 | Recap — what shipped, the per-phase rollout timeline. |
| 0:10 - 0:30 | **What went well.** Each contributor names one thing. |
| 0:30 - 0:50 | **What didn't.** Same format. Examples: spec-vs-impl drift, audit-found-after-the-fact gaps, CI flakiness during the rollout, on-call paging. |
| 0:50 - 1:10 | **What we learned.** Patterns to keep / patterns to drop. Specifically: the multi-pass self-audit pattern (effective?), the operator-driven DoD items (drag on schedule?), the per-phase DoD format (clear?). |
| 1:10 - 1:25 | **Action items.** Track each as a follow-up issue with an owner + due date. |
| 1:25 - 1:30 | Close. |

## Specific evaluations to include

### Multi-pass self-audit pattern

The phase used a "implement → audit closeout → fix gaps" pattern
across F1-F5 + X. The retro evaluates whether it was worth the
overhead:

- [ ] Audits found real gaps (count gaps that became code changes
      vs gaps that were closeout-text fixes).
- [ ] Audit cost (eng-days) vs gap-prevention value.
- [ ] Should we keep this pattern in the next phase? If yes, with
      what tweaks?

### Operator-driven DoD items

- [ ] How long did each operator-driven DoD item actually take to
      close (e.g. F4.DoD.7 7-day soak, F5.DoD.6 phased rollout)?
- [ ] Did the automation (CI workflows + soak-status command) make
      closeout mechanical, or did operators still need to hand-hold?
- [ ] Should future phases pre-budget the operator-time alongside
      the eng-time?

### Customer impact

- [ ] How many tenants enabled each capability flag in the first
      14 days post-GA?
- [ ] What's the customer-reported / CS-channel adoption
      sentiment?
- [ ] Any CS escalations that point to a missing user-guide section
      or a broken onboarding flow?

## Action-item template

| Description | Owner | Due | Linked issue |
|---|---|---|---|
| _e.g. "Drop the inline-style anti-pattern in component X"_ | _alice@_ | 2026-05-30 | #1234 |

## Sign-off

| Role | Name | Date |
|---|---|---|
| Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |
| Product Lead | _to be filled_ | _YYYY-MM-DD_ |
| EM | _to be filled_ | _YYYY-MM-DD_ |

228.DoD.5 closes once the retro has happened (within 14 days of
F5 100% rollout) AND all action items are filed as tracked issues.

## Related

- [Eng-days tracker](../capacity/lineage-228-eng-days-tracker.md) — DoD.7
- [Capacity-review cadence](../capacity/lineage-capacity-review-cadence.md) — quarterly forward-looking
- [Announcement template](../announcements/lineage-228-announcement.md) — DoD.4
