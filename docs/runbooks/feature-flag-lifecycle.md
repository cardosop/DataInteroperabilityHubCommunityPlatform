# Feature-flag lifecycle policy

**Status**: Authoritative — every per-tenant or per-environment feature flag in the Hub MUST follow this policy.
**Phase**: 250.0.15 / D250.13
**Owners**: Platform Engineering Lead, SRE, EM

## Why this exists

Feature flags accumulate. Each unretired flag is a code-branching liability: every conditional in source has to be tested against both flag states; flag-related bugs hide for months because the unflipped branch is rarely exercised; the test surface grows quadratically with flag count. Without retirement, the codebase becomes a graveyard of half-shipped features.

This policy enforces a lifecycle: every flag has a created date, a retire-by date, a designated owner, and is auto-flagged for retirement once it ages past the threshold.

## Flag lifecycle stages

```
DRAFT → CANARY → GA → DEPRECATED → RETIRED
```

| Stage | Description | Default state |
|---|---|---|
| **DRAFT** | Code path exists but no tenant flips it. Used during pre-merge development. | `False` everywhere. |
| **CANARY** | Released; selected friendly tenants opt-in for testing. Telemetry collected. | `False` default; `True` per friendly tenant. |
| **GA** | Generally-available; default flips to `True` (or stays `False` for explicit-opt-in features). | Per-feature default; tenant can override. |
| **DEPRECATED** | Marked for removal. New tenants do not see it. Existing tenants on the path are notified. Retirement date set. | `True` for legacy users; UI shows deprecation notice. |
| **RETIRED** | Code path AND flag deleted. The feature is part of the standard surface (or removed entirely). | N/A — flag no longer exists. |

## Required metadata per flag

Every flag MUST be registered in [hub/apps/tenants/feature_flag_registry.py](../../hub/apps/tenants/feature_flag_registry.py) (NEW per Phase 250.0.15) with:

```python
@dataclass(frozen=True)
class FeatureFlag:
    name: str                  # e.g. "warehouse_connectivity_enabled"
    description: str            # one-line human-readable purpose
    owner_team: str             # e.g. "asset-creation-eng"
    owner_email: str            # team alias for ops escalation
    created_at: datetime        # when the flag was added to source
    stage: Literal["DRAFT", "CANARY", "GA", "DEPRECATED", "RETIRED"]
    retire_by: datetime | None  # mandatory if stage in {GA, DEPRECATED}
    default_existing_tenants: bool  # default value on existing tenants
    default_new_tenants: bool       # default value on new tenants
    related_phase: str          # e.g. "Phase 250.6.A"
    related_design_doc: str     # e.g. "D250.18"
    related_audit_event: str    # audit event emitted on flip; required for security-relevant flags
    requires_dpo_signoff: bool  # True for compliance / privacy flags
    requires_legal_signoff: bool  # True for cross-tenant data-sharing flags
```

## CI alert: stale-flag detection

A CI job (`detect-stale-feature-flags`) runs nightly and on flag-registry edits:

1. Iterates the registry.
2. For each flag with `stage in {GA, DEPRECATED}`: checks `retire_by` date.
3. Flags exceeding `retire_by` MORE than 180 days are CRITICAL.
4. Flags exceeding `retire_by` between 90-180 days are WARNING.
5. Flags exceeding `retire_by` between 0-90 days are INFO.

The CRITICAL / WARNING flags are surfaced in:
- The CI job output (visible in any PR).
- A weekly Slack digest to `#platform-eng`.
- A nightly Prometheus metric `feature_flag_stale_count{severity}` for Grafana alerts.

**The CI job does NOT block PRs**. Stale flags are tech debt; blocking unrelated PRs would cause merge-train churn. Instead, the job's output is reviewed during weekly Tech Debt review (every Friday).

## Retirement procedure

1. **Set `stage=DEPRECATED`** in the registry; assign a `retire_by` date 90 days out.
2. **Notify stakeholders**: post in `#integrations-eng` Slack + email to all tenants currently on the legacy path.
3. **Deprecation telemetry**: code path emits `<flag_name>_deprecated_path_used` audit event on every read of the legacy state.
4. **Wait 90 days**: existing tenants migrate organically.
5. **Remove the legacy code path**: delete the conditional + the legacy implementation. Set `stage=RETIRED`.
6. **Drop the flag column** from `Tenant` model: additive-then-subtractive migration (atomic = False; mirror D230.5 / D240.5 / D250.11).
7. **Catalogue update**: remove the flag's row from this document (or move to "Retired flags" appendix if customer documentation references it).

## Adding a new flag

1. **Pick a name**: `<area>_<feature>_enabled` (snake_case). Examples: `warehouse_connectivity_enabled`, `compliance_fail_closed_enabled`.
2. **Decide defaults** per D250.12 doctrine:
   - On NEW tenants: usually `False` until onboarding completes; `True` if the feature is genuinely default-on for new accounts.
   - On EXISTING tenants: usually `True` (preserves current behaviour) UNLESS the feature is fundamentally different from prior behaviour (in which case `False` + 30-day notice).
3. **Register in feature-flag registry** (Phase 250.0.15 deliverable).
4. **Wire into the `Tenant` model** via additive migration.
5. **Audit event**: emit `<FLAG_NAME>_FLIPPED` on every change; subscribe `PLATFORM_ADMIN` to a dashboard view.
6. **Document in the relevant phase tasks.md** with the design-decision link.
7. **Pre-merge announcement** per Phase 250.0.18 protocol if the flag changes behaviour for existing tenants.

## Flags currently in scope (Phase 250)

| Flag | Stage | Created | Retire-by | Owner |
|---|---|---|---|---|
| `compliance_fail_closed_enabled` | CANARY | 2026-05-03 | 2026-08-01 (move to GA) | asset-creation-eng |
| `allow_intake_on_compliance_degraded` | DRAFT | 2026-05-03 | n/a | asset-creation-eng |
| `federated_import_enabled` | DRAFT | 2026-05-03 | n/a | asset-creation-eng |
| `asset_creation_enabled` | GA | 2024-01-01 | 2027-01-01 (review) | asset-creation-eng |
| `asset_auto_activate_on_gate_pass` | DRAFT | 2026-05-03 | n/a | asset-creation-eng |
| `OPTIMISTIC_LOCK_REQUIRE_IF_MATCH` (env-var, not per-tenant) | CANARY | 2026-05-03 | 2026-05-10 (flip after 7d soak) | asset-creation-eng |

## CI gate implementation

The detection job lives at `.github/workflows/feature-flag-stale-detector.yml` (Phase 250.0.22 deliverable wires this).

The detector script at `scripts/detect_stale_feature_flags.py` (NEW deliverable):

```python
#!/usr/bin/env python3
"""Phase 250.0.15 — stale feature-flag detector.

Loads the registry, computes age-since-retire-by for each {GA, DEPRECATED}
flag, classifies severity, and prints a structured report. Exit 0 always
(this is informational, not a merge gate per the policy above).
"""
```

Lands as part of the 250.0.22 CI matrix additions.

## Audit trail

Every flag flip emits `TENANT_FEATURE_FLAG_FLIPPED` audit with `details_json={flag_name, old_value, new_value, reason}`. PLATFORM_ADMIN-only Grafana dashboard tracks flip volume + flag age.
