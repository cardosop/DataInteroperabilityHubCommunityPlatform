# Beta Operations Runbook — Internal Beta (Phase U.6 / WS-6)

Operating model for the internal beta (20–50 users / 2–3 tenants / PRO plans)
running on the compose-path staging stack. Deliberately smaller than the
production `on-call-runbook.md` (PagerDuty rotations etc. activate at GA;
see `operational-expansion.md`).

**On-call: `admin`** — single owner for the beta window, per
`docs/operations/triage-owners.md` (bucket: ops / beta on-call). Response
SLA: 48 h triage for non-outage classes, 4 h for staging outage.

## 1. Alert routing

Staging Prometheus + Alertmanager run inside the compose stack
(PROMETHEUS_PORT=9092, ALERTMANAGER_PORT=9094 by the `.env.staging` port
map). Every beta-window alert routes to the admin's queue; no rotation.

| Source | Channel | Expected action |
|---|---|---|
| Prometheus firing alert | Alertmanager UI (`:9094`) + rule name | Map to the RB-* runbook below; triage within 48 h |
| `hub-staging-*` container unhealthy | `make staging-ps` | Restart the service; if recurring, root-cause before the weekly feedback sync |
| Staging outage (API down) | direct report (support channel) | 4 h response; follow `docs/operations/disaster-recovery-policy.md` restore drill |

## 2. Incident routing vs RB-* runbooks

Incidents in the beta window are routed by SERVICE/FEATURE to the existing
RB-* runbook set (`docs/runbooks/`). If no RB-* runbook matches, use the
generic `docs/operations/game-day-runbook.md` and file a new RB-* runbook
during the post-incident review.

| Incident class | Runbook |
|---|---|
| Auth broken / lockouts / session | `RB-AUTH-001-rls-kill-switch.md`, `RB-AUTH-002-cross-tenant-denial-investigation.md`, `RB-AUTH-003-cookie-mode-rollback.md` |
| Rate limiting / throttling | `RB-BaaS-001-rate-limit.md`, `RB-SEC-005-throttle-classes.md` |
| Billing / Stripe checkout / payouts | `RB-MKT-001-stripe-connect-onboarding-failure.md`, `RB-MKT-002-refund-discrepancy.md`, `RB-MKT-003-payout-failure-investigation.md`, `RB-BILLING-001-pricing-changes.md` |
| Data movement failures (ingestion/export) | `RB-DATA-001-scheduled-ingestion-failure.md`, `RB-DATA-002-export-failure.md`, `RB-DATA-004-file-storage-failure.md` |
| Search / SPARQL / semantic | `RB-SEM-001-graphql-ld.md`, `RB-SEM-002-semantic-inference-failure.md` |
| Compliance / DQ gates | `RB-COMP-001-compliance-fail-closed.md`, `RB-DQ-001-data-quality-operations.md`, `RB-GOV-001-compliance-blocked-approval-investigation.md` |
| Warehouse / virtualization / integrations | `RB-WAREHOUSES-001-connection-failure.md`, `RB-VIRT-001-virtualization-query-failure.md`, `RB-INTEGRATIONS-001-connector-failure.md` |
| Secret / credential exposure | `RB-SEC-001-credential-rotation.md`, `RB-AUTH-004-internal-api-key-rotation.md`, `docs/operations/staging-secrets-registry.md` |
| Beta tenant provisioning | `RB-TENANTS-001-provisioning.md` |

Post-incident: fill `docs/operations/postmortem-template.md` within 5
business days and link it from the weekly feedback sync notes.

## 3. Support channel + weekly feedback → triage

- **Channel:** `#hub-beta` (internal Slack/chat); invites land in the cohort
  invitation email itself (MailHog UI `:1026` shows what went out).
- **Feedback capture:** every report goes into the feedback ledger —
  `docs/operations/beta-feedback-ledger.md` — with reporter, date, severity
  (blocker/minor/idea), and a `TICKET=<id> EXPIRES=<YYYY-MM-DD>` annotation
  when a fix is deferred (GATE-40 enforces expiry).
- **Weekly cadence (Mondays 09:00 local):** the admin runs the feedback →
  triage sync:
  1. Pull new rows from the feedback ledger.
  2. Triage each: root-fix now / defer with ticket + expiry / product
     decision (record in the ledger, not silently).
  3. File follow-ups as openspec task items or GATE-40 annotations.
  4. Re-check the deferred ledger (expired entries block per GATE-40).
  5. Update the beta cohort summary at the top of the ledger (blocked
     count, top complaint, plan for the week).

## 4. Cost watch

Beta runs on the included-Actions tier + one compose host — costs are
watched weekly, evidence-based (U.2 budget rule):

- **GitHub Actions minutes:** Actions → Billing; the prepro01 concurrency
  group caps parallel spend. Flag at >50% of the included tier in a week.
- **Host resources:** `docker stats` for the staging stack (the `hub-staging-*`
  container set) during the weekly sync; flag sustained >70% memory/CPU.
- **Registry/storage:** `docker system df` reclaimable >30% → prune weekly
  (never `-v` without the backup check in §5 of the production runbook).
- **Escalation:** any overage → recorded in the feedback ledger and
  reviewed at the U.8 go/no-go (evidence for the Actions-tier upgrade
  decision).

## 5. Cohort invite (operator procedure)

The cohort joins through `hub/manage.py invite_beta_cohort`
(`hub/apps/users/management/commands/invite_beta_cohort.py`) — the SAME
service path as `POST /api/v1/users/` (`UserService.invite_user_to_tenant` +
hashed 7-day invitation token + `send_invitation_email` through the MailHog
relay). No mock path: the emails leave the stack and are verifiable in the
MailHog UI (`:1026`).

CSV format (header row required — template:
`docs/operations/beta-cohort.csv.example`):

| Column | Meaning |
|---|---|
| `tenant_slug` | Tenant the invitee joins (must already exist — `provision_tenant` first) |
| `email` | Invitee address (lowercased; re-runs skip already-invited emails) |
| `display_name` | Optional display name for newly created users |
| `role_names` | Comma-separated TENANT-scoped role names (e.g. `TENANT_ADMIN,DATA_PROVIDER`); unknown names are reported per-row and ignored — never a silent wrong-tenant assignment |

Procedure:

```bash
# 1. Dry-run — validates rows + tenant existence, writes nothing
docker compose -f docker-compose.staging.yml --env-file .env.staging \
  exec api-service python hub/manage.py invite_beta_cohort \
  --csv docs/operations/beta-cohort.csv.example --dry-run

# 2. Live run (idempotent — re-runs report skipped=)
docker compose -f docker-compose.staging.yml --env-file .env.staging \
  exec api-service python hub/manage.py invite_beta_cohort \
  --csv docs/operations/beta-cohort.csv.example \
  --actor-email admin@staging.hub.example.com

# 3. Verify the emails actually left the stack (MailHog capture)
curl -s "http://localhost:1026/api/v2/messages?limit=5" | \
  grep -o "invit[^\"]*" | head
```

Invitation emails carry the `#hub-beta` support-channel pointer (see §3).
The inviter actor defaults to the tenant's first TENANT_ADMIN; the command
fails loudly when a tenant has no eligible actor.

## 6. Exit criteria

The beta window ends when U.8 passes; this runbook's on-call/responses then
promote to the GA model (`on-call-runbook.md`) and the EKS migration ticket
(210.29) takes over the staging lifecycle.

**EKS deferral ticket**: ticket 210.29 (compose-path beta does not exercise
the Helm/EKS production path) — owner `admin`, EXPIRES 2026-09-30. The
go/no-go gate (`scripts/check_go_nogo.py`) machine-checks this annotation:
a ticket without an owner AND an ISO expiry blocks the go decision.
