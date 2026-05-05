# Internal eng announcement protocol

**Phase**: 250.0.18
**Status**: Authoritative — applies to every Phase 250 sub-phase that changes behaviour for existing tenants OR external integrators.
**Owners**: Phase Driver, EM (Eng)

## Why this exists

Prior phases (notably Phase 240 deploys with subtle webhook timing changes) discovered breaking-but-non-obvious changes in production after merge — internal teams hadn't been told because no protocol existed. Customer-support escalations + last-minute hotfixes followed.

This protocol formalizes pre-merge announcement so internal teams (Support, SDK, Frontend, Integrations Eng) can adapt before deploy.

## When to invoke

Invoke this protocol BEFORE merging a PR that:

1. Changes any public API contract (request shape, response shape, status code, error code, header semantics).
2. Changes timing semantics observable to external clients (latency budget, sync vs async, webhook firing order).
3. Introduces a per-tenant flag whose default-OFF-on-existing-tenants imposes opt-in friction.
4. Deprecates an endpoint, field, header, or feature flag.
5. Adds a new auth/authz requirement on an existing endpoint.
6. Changes any workflow's step ordering, persistence semantics, or compensation contract.

## Protocol (4 steps)

### Step 1 — Internal Slack announcement

Post in `#integrations-eng` AND `#support-eng` AND `#sdk-eng` (whichever apply) using this template:

```markdown
**[Phase 250.X.Y]** — <one-line summary>

Tracking: <PR URL or issue link>
Affects: <which integrators / clients / tenants>
Behaviour change: <before → after>
Deploy date: <YYYY-MM-DD>
Soak window: <N days> with `<flag_name>=False` on existing tenants per D250.12

📅 Office-hour Q&A: <date + zoom link>
📩 Async questions: thread in this post OR DM <author>

Affected docs:
- <link to ADR>
- <link to webhook reference>
- <link to runbook>

Action required from team:
- Support: <e.g. update internal kb article on asset-creation errors>
- SDK: <e.g. release new SDK version with polling helper>
- Integrations: <e.g. notify named webhook subscribers>
```

Post **at least 1 week before the deploy date** for HIGH-impact changes. Same-week is acceptable only for emergency hardening or pure bug fixes.

### Step 2 — Office-hour Q&A

Schedule a **30-minute Q&A session** at most 1 week before deploy. Format:

- 5 min: presenter walks through the change + behaviour-diff
- 5 min: presenter walks through the rollback plan
- 20 min: open Q&A; questions logged + answered async if not concluded in-meeting

Recording posted to `#asset-creation-eng` post-meeting. Skip the Q&A only if zero questions surface in the Slack thread within 48 hours of the announcement.

### Step 3 — External integrator communication (if applicable)

For changes that affect external integrators (webhook subscribers, SDK consumers, API clients), the **PM team** owns external comms via:

- Email blast to listed integrator contacts (sourced from `MarketplaceConnection` rows + tenant-admin emails).
- Public CHANGELOG entry merged with the PR.
- Status-page banner if breaking AND post-30-day notice (per D250.12).

External comms cadence:
- **30 days before deploy**: email + status page (for behaviour-change-on-existing-tenants).
- **7 days before deploy**: reminder email.
- **Day of deploy**: status-page deploy-window notice.
- **Day after deploy**: post-deploy summary email confirming success.

### Step 4 — Post-deploy verification

After the deploy lands:

- Author posts in the original Slack thread: "Deployed @ <timestamp>; flag flipped on N tenants; X audit events fired; zero customer escalations within 4h. Ticket closed."
- Support team confirms receipt in the same thread.
- Any in-flight Q&A questions get final answers.

## Templates

### Webhook-timing-change announcement (used for 250.1.A re-sequence)

```markdown
**[Phase 250.1.A]** — Asset creation workflow re-sequence: gates run BEFORE Asset row persistence

Tracking: PR #XXXX
Affects: All webhook subscribers receiving `asset.created` events; SDK + CLI consumers polling for asset existence; frontend AssetCreatePage flow.
Behaviour change:
  Pre-deploy: `asset.created` fires ~50ms after POST /api/v1/assets/data-first/.
  Post-deploy: `asset.created` fires only AFTER compliance + DQ gates pass — typically 5-30s after POST.
  Failed gates emit `ASSET_FAIL_CLOSED_REJECTED` audit event; `asset.created` is NOT fired.

Deploy date: 2026-06-15
Soak window: 30 days with `compliance_fail_closed_enabled=False` on existing tenants per D250.12.
After soak: flag default flipped to TRUE; existing tenants opt-out via `/settings/billing/disable-fail-closed`.

📅 Office-hour Q&A: 2026-06-08 14:00 UTC (zoom link in calendar)
📩 Async questions: thread below OR DM @<author>

Affected docs:
- ADR: docs/adr/asset-creation/ADR-AST-001-fail-closed-asset-persistence.md
- Webhook reference: docs/mvpdocs/api-reference/webhooks.md (asset.created entry updated)
- Audit report: docs/audit-reports/b2-6-asset-webhook-timing-2026-05-03.md
- Runbook: docs/runbooks/asset-fail-closed-rollback.md

Action required:
- Support: update KB article "Why didn't I get my asset.created webhook?" with the new fail-closed audit event link.
- SDK: ship 1.5.0 with `dim_workflow_polling.py` + retry-after-aware polling helper.
- Integrations: email named webhook subscribers (auto-generated from `Webhook.event_types LIKE '%asset.created%'`).
- Frontend: confirm AssetCreatePage polls workflow run state instead of asset existence.
```

### Federated-import opt-in announcement (used for 250.5.A)

```markdown
**[Phase 250.5.A]** — Federated import per-tenant flag introduced; default OFF

Tracking: PR #XXXX
Affects: Tenants currently using marketplace integrations to federate assets (sourced from rows where `Asset.source_type=FEDERATED`).
Behaviour change:
  Pre-deploy: implicit federated access whenever marketplace integration enabled.
  Post-deploy: explicit per-tenant opt-in via `Tenant.federated_import_enabled=True`. Existing tenants on legacy path keep working until 30-day notice expires; new tenants need DPO + Legal sign-off.

Deploy date: 2026-07-01
Soak window: 30 days with default-FALSE on existing tenants who have federated assets; UI shows "Federated import deprecating; enable explicitly to retain access" banner.

📅 Office-hour Q&A: 2026-06-24 14:00 UTC
📩 Async questions: thread below

Affected docs:
- ADR: docs/adr/asset-creation/ADR-AST-002-federated-import-flag-and-skip-dq.md
- Concept doc: docs/mvpdocs/concepts/federated-assets.md
- Compliance Q&A: docs/runbooks/federated-degradation.md

Action required:
- Support: handle "I lost access to federated assets" tickets; redirect to `/settings/integrations/enable-federated`.
- DPO: review the privacy review template for federated-import opt-in.
- Legal: review contract templates for cross-tenant data-sharing.
- PM: 30-day email blast to listed federated-asset-owning tenants.
```

## Cadence

- **Per Phase 250 sub-phase**: 1 announcement per behaviour-changing sub-phase. Phases 250.0 / 250.0.X are foundational; usually no announcement needed (purely additive code).
- **Per quarter**: review the protocol's effectiveness. Adjust template structure if tickets are arising despite announcements.

## Audit trail

Each announcement is archived to `docs/announcements/<YYYY-MM-DD>-<slug>.md` for historical record. The PR description references the archived announcement.
