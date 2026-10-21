# Pilot On-Call + Escalation + Incident Runbook Stub

Owner: platform owner (U) — names TBD before the first pilot customer.
Companion to `docs/operations/beta-ops-runbook.md` §1–2 (alert routing +
incident→RB-* runbook mapping). This stub defines the pilot's PEOPLE
path: who responds, in what order, and within what time.

## 1. Severity tiers

| Severity | Definition | Response target | Update cadence |
|---|---|---|---|
| SEV-1 | Pilot tenant is down or data at risk (API down, auth broken, data loss, security breach) | 15 min to triage, 4 h to resolve or workaround | every 30 min in the incident channel |
| SEV-2 | Single journey/feature broken (ingestion failures, marketplace checkout errors, degraded SPARQL) | 4 h to triage, next business day to resolve | every 4 h |
| SEV-3 | Cosmetic / non-blocking (UI glitch, delayed notification, slow-but-working) | next business day | daily |

## 2. On-call roster (fill before the first customer)

| Slot | Name | Contact |
|---|---|---|
| Primary on-call (week 1) | **U to name** | Slack `#pilot-incidents` + phone |
| Primary on-call (week 2) | **U to name** | |
| Secondary (backup) | **U to name** | |

Rotation: weekly, Monday 09:00. The outgoing primary hands over with the
open-alert list from the Alertmanager UI (`ALERTMANAGER_PORT` map in
`.env.staging`) + a note in the incident channel.

## 3. Escalation ladder

1. **Primary on-call** — first response; triage against the RB-* mapping
   (`docs/operations/beta-ops-runbook.md` §2); if no runbook matches,
   `docs/operations/game-day-runbook.md`.
2. **Platform owner (U)** — paged when: SEV-1 unresolved after 1 h, any
   security/credential incident (immediately), or the on-call needs a
   decision only the owner can make (kill switch, tenant deletion,
   external-provider contact).
3. **External providers** — Databricks/AWS/Stripe/email-provider support;
   opened by the platform owner with the pilot account IDs
   (`docs/operations/critical-path-index.md`).
4. **Stop-the-line authority**: any SEV-1 gives the on-call authority to
   flip the documented kill switches (`RB-AUTH-001-rls-kill-switch.md`,
   `docs/operations/change-freeze-calendar.md`); customer-visible
   rollbacks are announced in the support channel first.

## 4. Incident channel + records

- **Channel**: `#pilot-incidents` (create before go-live).
- Every incident gets a thread: timestamp, severity, affected surface,
  first hypothesis, runbook followed, resolution/rollback.
- Post-incident: `docs/operations/postmortem-template.md` within 5
  business days; link it from the weekly feedback sync notes
  (`docs/operations/beta-feedback-ledger.md`).

## 5. First-15-minutes checklist (SEV-1)

1. `make staging-ps` — which `hub-staging-*` container is unhealthy?
2. Prometheus UI (`PROMETHEUS_PORT` map) — which rule fired first?
3. `docker compose -f docker-compose.staging.yml logs api-service` —
   correlate the alert with the error signature.
4. Confirm the blast radius: is the TEST stack affected (peer sessions),
   or staging only? Never run destructive re-init during someone else's
   batch — `scripts/check_no_live_tests.py`.
5. Mitigate (restart / kill switch / rollback) BEFORE root-causing;
   root-cause and fix in the same window, then file the postmortem.

## 6. Rehearsal requirement (before go-live)

The pilot go/no-go (repo's U.6–U.8 gate series) includes a TABLE-TOP
incident drill with this stub: a simulated SEV-1 (staging API down) walked
through §5 by the named on-call, timed against §1 targets. Record the
drill in the go/no-go evidence pack.
