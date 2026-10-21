# Phase 228.F2.2 / F2.35 — Lineage editor beta program

> **Purpose**: Operational scaffolding for the F2 beta program — 5
> internal + 5 external participants over 2 weeks before the
> capability flag flips to ON for everyone.
> **Audience**: Product, customer success, engineering leads.
> **Status**: Engineering-tranche scaffolding (the participant
> recruitment + capability flag rollout themselves are operational).

## Why a beta

The F2 lineage editor is a P1 surface that lands in the contracts
detail flow.  v1 ships with deliberately bounded scope (see
[v1 non-goals](../mvpdocs/concepts/lineage.md#field-level-lineage-editor--phase-228f2-v1-non-goals-req-lin-f2-006)).
The beta exists to:

1. Validate the v1 scope is enough for real customers.
2. Surface a11y / keyboard-navigation defects the F2.25 + F2.26
   tests miss (real users do unexpected things).
3. Validate the perf SLO (the F2 spec has no perf gate equivalent
   to F1.005 because the editor is a per-user write surface — but
   beta tells us if the round-trip feels slow).
4. Stress-test the SERIALIZABLE concurrency model — two beta
   testers editing the same contract surface 409s the F2.5 test
   suite simulates synthetically.

## Selection

### Internal (5)

Recruit from teams whose contracts already carry rich lineage:

- [ ] 1× Data Platform Eng (governance perspective)
- [ ] 1× Customer Success (voice-of-customer)
- [ ] 1× Marketing-Analytics tenant (pipeline complexity)
- [ ] 1× Compliance/Audit tenant (retention concerns)
- [ ] 1× ML/Feature-Store tenant (column-level mappings)

### External (5)

Same shape; recruit via the customer-success channel.  Beta
participants get a 4-week extension on their feedback NDA + a
$200 credit.  Selection criteria:

- Active tenant with ≥10 contracts.
- ≥1 active asset that's been published to the marketplace.
- A primary contact who can commit to ≥30 minutes / week of
  feedback over the 2-week window.

## Capability-flag rollout

The beta runs against staging.  Per-tenant flag flip via the
admin console (Phase 235.1 admin-feature-flag-management when
shipped — until then via a Django shell command):

```python
# scripts/beta/enable_f2_for_tenant.py (operator-driven; no CI)
from django.conf import settings
from hub.apps.tenants.models import Tenant

# Tenant-level override (overrides the global default).
# Currently `is_capability_enabled` reads a global setting; the
# per-tenant flag wiring is a follow-up that ships with Phase 235.
# For the beta we run staging with the global flag ON and rely
# on the participant list to gate access.
```

For v1 the global staging flag is set ON for the beta window and
back OFF after the 2 weeks if defects warrant.

## Feedback surfaces

- **Slack**: `#meshant-lineage-editor-beta` (internal).  External
  feedback aggregated by Customer Success and posted there.
- **GitHub**: issues filed with `f2-beta` label.
- **Telemetry**: every editor-page mount emits a console event
  (`window.dispatchEvent('lineage.editor.opened')`) — analytics
  adapter subscribes when wired (mirrors the F1.29 pattern).

## Exit criteria

The 2-week beta closes with this scorecard:

- [ ] No P0 / P1 bugs open against the F2 surface.
- [ ] At least 8 of 10 participants saved a non-trivial edit
  (≥3 edges) at least once.
- [ ] No customer reports the feature "would block adoption" of
  Meshant.
- [ ] a11y issues flagged in the screen-reader pass
  (F2.26) are either fixed or have shipped tickets with target
  dates.
- [ ] Pricing decision recorded (F2's parent F2.28 isn't a
  process gate — the broader F1.28 is, but if F2 lands behind
  a paid tier the decision is here).

## Sign-off

Beta program coordinator records the exit-criteria scorecard +
GitHub issue links here:

| Date | Coordinator | Pass / Fail | Notes |
| --- | --- | --- | --- |
| | | | |
