# UX v2 Staged Rollout

**Status**: Authoritative — follow this runbook for every UX v2 tenant enablement/rollback.
**Phase**: 278.S.2
**Owners**: Platform Engineering Lead, SRE, Frontend Lead
**Related**: [Feature-flag lifecycle policy](feature-flag-lifecycle.md)

## Why this exists

UX v2 (Phase 278) introduces a redesigned marketplace, persona-aware home
dashboard, product tour, unified approval inbox, and bulk-action patterns.
These surfaces are gated behind `Tenant.ux_v2_enabled` (BooleanField, default
`False` for existing tenants, `True` for new tenants). This runbook defines the
staged rollout procedure so we enable tenants in controlled waves, monitor for
regressions, and can roll back instantly without data loss.

## Pre-flight checks (before any tenant enablement)

1. **Deployment verification**: Confirm the target environment (staging/prod)
   has the latest `main` or release tag deployed. Check CI is green on the
   deployment commit.
   ```bash
   gh run list --workflow deploy --branch main --limit 5
   ```

2. **Database migration**: Verify `0077_add_ux_v2_enabled` has been applied.
   ```bash
   python manage.py showmigrations tenants | grep ux_v2
   # Expected: [X] 0077_add_ux_v2_enabled
   ```

3. **Capabilities endpoint**: Confirm `/api/v1/capabilities/` returns `ux_v2`
   for the target tenant. The `useUxV2Gate` hook on the frontend reads this
   value; if the capabilities endpoint is not serving `ux_v2`, the gate is
   broken and enablement is a no-op.

4. **Monitoring dashboards**: Open the marketplace-api-health and
   frontend-error-rate Grafana dashboards in a second monitor. Confirm
   baseline metrics are stable (no elevated 5xx, no P50 latency drift) for
   the target tenant before proceeding.

5. **Rollback contact**: Confirm the on-call SRE and frontend lead are
   available during the enablement window. UX v2 rollback is a single
   management command with zero data loss, but the operator needs to know
   WHO to notify.

## Wave plan

Enable tenants in escalating risk order. Each wave MUST soak for ≥48 hours
before the next wave begins.

| Wave | Tenant class | Count | Soak period | Success criteria |
|---|---|---|---|---|
| **1 — Canary** | Internal dev/test tenants (staging) | 1–2 | 24 hours | Zero JS errors, zero 5xx on marketplace endpoints, ProductTour renders |
| **2 — Friendly** | Friendly production tenants (early adopters) | 1–2 | 48 hours | Zero P0/P1 regressions; TTFA unchanged or improved; approval latency unchanged |
| **3 — Medium** | Mid-size production tenants | 2–3 | 48 hours | Same as wave 2 + zero rollback events |
| **4 — Broad** | Remaining production tenants | All | 72 hours | All KPIs stable; no open UX v2 P0/P1 bugs |
| **5 — Default flip** | Flip `_default_ux_v2_enabled` to True for all remaining | N/A | 7 days monitoring | GA declaration; Deprecation notice for classic UX issued |

### Wave gate checklist (per wave)

- [ ] Previous wave soaked for ≥minimum period
- [ ] Zero P0 regressions in previous wave
- [ ] P1 regressions triaged and either fixed or accepted with rationale
- [ ] UX research session completed with at least one user from previous wave (278.M.1)
- [ ] `list_ux_v2_tenants` shows accurate enabled/disabled counts
- [ ] Wave enablement recorded in audit log (`TENANT_UX_V2_ENABLED` events)

## Enablement procedure

### Enable UX v2 for a single tenant

```bash
python manage.py enable_ux_v2_for_tenant <subdomain>
```

Example:
```bash
python manage.py enable_ux_v2_for_tenant acme-corp
```

**What happens**:
1. Sets `Tenant.ux_v2_enabled = True` for the matching tenant.
2. Saves the tenant row (`update_fields=["ux_v2_enabled", "updated_at"]`).
3. Emits `TENANT_UX_V2_ENABLED` audit event with tenant_id, name, slug.
4. The capabilities endpoint picks up the change on the next request (within
   the 60-second cache TTL). The frontend `useUxV2Gate` hook re-evaluates on
   next page load or route change.
5. No restart required. No cache invalidation needed beyond the capabilities
   TTL.

### Enable UX v2 for multiple tenants (batch)

```bash
for subdomain in acme-corp beta-inc gamma-llc; do
  python manage.py enable_ux_v2_for_tenant "$subdomain"
done
```

### Verify enablement

```bash
python manage.py list_ux_v2_tenants
```

Look for `ENABLED` in the UX v2 column for the target tenant(s).

### Track rollout progress

```bash
# Human-readable table
python manage.py list_ux_v2_tenants

# Machine-readable (for CI/scripts)
python manage.py list_ux_v2_tenants --json

# Show only remaining (disabled) tenants
python manage.py list_ux_v2_tenants --disabled-only
```

## Rollback procedure

### Disable UX v2 for a single tenant (instant rollback)

```bash
python manage.py disable_ux_v2_for_tenant <subdomain> --reason "<detailed reason>"
```

Example:
```bash
python manage.py disable_ux_v2_for_tenant acme-corp \
  --reason "P0: marketplace listing cards render blank in UX v2. User reports 0 listings visible. Classic UX confirmed working. Tracking: #bug-1234"
```

**What happens**:
1. Sets `Tenant.ux_v2_enabled = False` for the matching tenant.
2. Saves the tenant row.
3. Emits `TENANT_UX_V2_DISABLED` audit event with the reason.
4. The frontend reverts to classic UX on next page load.
5. No data loss — all user data, saved views, drafts, and preferences are
   preserved. The UX v2 surfaces are hidden; the underlying data is untouched.

### Rollback triggers

Execute rollback immediately when ANY of the following occur:

| Trigger | Severity | Action |
|---|---|---|
| **JS error spike** — >5% of page loads throw uncaught errors on UX v2 surfaces (marketplace, home, governance/my-approvals) | P0 | Roll back all wave tenants; investigate before re-enabling |
| **Blank page** — Any UX v2-gated page renders white/empty for >1% of users | P0 | Roll back the affected tenant(s) and the entire current wave |
| **API 5xx spike** — Marketplace or governance endpoints return >1% 5xx correlated with UX v2 enablement | P0 | Roll back; check BE load pattern changes (UX v2 may issue different API call sequences) |
| **Approval regression** — Approve/reject actions from inbox fail at >0.5% error rate | P1 | Roll back; the classic governance page must remain functional as fallback |
| **TTFA regression** — Time-to-first-action (marketplace browse → purchase) increases >20% from baseline | P1 | Investigate before next wave; do NOT roll back unless correlated with P0 |
| **Accessibility regression** — Axe-core scan on UX v2 pages reports new critical violations | P1 | Fix before next wave; roll back only if violations block assistive-technology access |
| **User complaint volume** — >3 support tickets per wave tenant referencing UX v2 confusion | P2 | Schedule UX follow-up; do NOT roll back unless accompanied by P0/P1 |

### Post-rollback

1. Notify the affected tenant(s) via the standard incident communication channel.
2. File a P0/P1 bug with the `ux-v2-rollback` label.
3. The bug fix ships through the standard CI pipeline. After the fix is deployed
   and verified on staging, re-enable using `enable_ux_v2_for_tenant`.
4. The rollback event is fully audited — `TENANT_UX_V2_DISABLED` rows carry the
   reason and operator identity.

## Monitoring checklist (during and after each wave)

### Immediate (first 24 hours)

- [ ] Grafana `marketplace-api-health`: `/marketplace/listings/` latency and error rate stable
- [ ] Grafana `frontend-error-rate`: no new JS error patterns on UX v2 bundles
- [ ] Sentry: zero new unhandled exceptions with `ux_v2` tag
- [ ] `ProductTourGate` renders on first login for users with `has_seen_tour=false`
- [ ] `MyApprovalsInbox` renders at `/governance/my-approvals` with correct items
- [ ] `HomePage` shows persona-aware greeting ("Your Data Engineer Dashboard")

### Soak period (24–72 hours)

- [ ] No rollback events triggered
- [ ] User telemetry: TTFA, marketplace conversion rate, approval latency within baseline
- [ ] `usePersona()` resolves correctly for all 6 personas on enabled tenants
- [ ] Saved views (`User.saved_views`) persist across UX v2 / classic toggles
- [ ] Form drafts (`FormDraft` model) persist across UX v2 surfaces

### Wave completion

- [ ] `list_ux_v2_tenants` confirms expected enabled count
- [ ] Audit log shows `TENANT_UX_V2_ENABLED` events for each enabled tenant
- [ ] P1/P2 bugs filed with `ux-v2` label and priority
- [ ] Wave completion recorded in the rollout log (see Appendix)

## Management commands reference

| Command | Purpose | Arguments |
|---|---|---|
| `enable_ux_v2_for_tenant` | Enable UX v2 for one tenant | `<subdomain>` (required) |
| `disable_ux_v2_for_tenant` | Disable UX v2 for one tenant (rollback) | `<subdomain>` (required), `--reason` (required) |
| `list_ux_v2_tenants` | List UX v2 status for all tenants | `--enabled-only`, `--disabled-only`, `--json` |

All commands use `DATABASES["admin"]` (BYPASSRLS) as required by the tenant
isolation RLS contract. Audit events are emitted in a try/except so a
transient audit-DB outage never blocks a rollout or rollback operation.

## Audit trail

| Event | Trigger | Retention |
|---|---|---|
| `TENANT_UX_V2_ENABLED` | `enable_ux_v2_for_tenant` execution | 90 days |
| `TENANT_UX_V2_DISABLED` | `disable_ux_v2_for_tenant` execution | 90 days |

Both events carry `tenant_id`, `tenant_name`, `tenant_slug`, and the
operator identity (`enabled_by` / `disabled_by` = `management_command`).
`TENANT_UX_V2_DISABLED` additionally carries the `reason` field.

## Appendix A — Rollout log

| Date | Wave | Tenant | Action | Operator | Audit event ID |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Appendix B — GA declaration checklist

- [ ] All production tenants enabled (wave 4 complete)
- [ ] ≥7 days stability with zero rollback events post wave 4
- [ ] `_default_ux_v2_enabled` flipped to `True` via migration
- [ ] Classic UX code paths deprecated; deprecation notice issued
- [ ] Classic UX retirement date set (90 days from GA declaration)
- [ ] `ux_v2_enabled` column retirement scheduled per [feature-flag lifecycle](feature-flag-lifecycle.md)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
