# Incident Response

**Maintained by:** Meshant Platform Engineering (on-call rotation)
**Last updated:** 2026-05-13

This document defines the incident response process for the Meshant
platform.  Every engineer on the on-call rotation must be familiar
with this document before their first shift.  It is the single source
of truth for severity classification, escalation paths, war-room
protocol, communication templates, and post-mortem requirements.

For customer-facing operational guidance, see
[docs/mvpdocs/operations/incident-response.md](docs/mvpdocs/operations/incident-response.md).

---

## 1. Severity levels

| Level | Description | Response time | Notification | Example |
|---|---|---|---|---|
| **P0** | Platform-wide outage; data loss or corruption in progress; auth bypass affecting all tenants | 15 min | Page on-call (PagerDuty) + `#incident-p0` Slack | All API endpoints returning 5xx; RCE confirmed in production; tenant-isolation bypass |
| **P1** | Major feature broken for all tenants with no workaround; security incident with limited blast radius | 30 min | Page on-call + `#incident-p1` Slack | Auth failing for a subset of tenants; marketplace payments stuck; webhook delivery halted |
| **P2** | Feature degraded with workaround available; single-tenant impact; non-critical data delay | 2 hours | `#incident-p2` Slack (no page) | Search returning stale results; scheduled ingestion delayed; Grafana dashboard blank |
| **P3** | Minor issue; cosmetic; edge case affecting <1% of users | Next business day | Create GitHub issue with `incident` label | Tooltip misaligned; docs typo; non-blocking CI flake |

### Severity upgrade triggers

- A P1 incident that persists > 4 hours without a mitigation becomes **P0**.
- A P2 incident involving PII exposure or security boundary crossing becomes **P1**.
- Any incident where the on-call engineer cannot identify the root cause within 1 hour escalates one level.

---

## 2. On-call rotation

### Schedule

- Primary on-call: weekly rotation, hand-off **Monday 10:00 UTC**.
- Secondary (escalation): the engineer who was primary the previous week.
- Rotation managed in PagerDuty — see `#oncall-schedule` Slack channel.

### Responsibilities

1. Acknowledge every page within **5 minutes**.
2. Own the incident until it is resolved or handed off.
3. Post a status update every **30 minutes** for P0/P1 in the incident Slack channel.
4. File the post-mortem ticket before your shift ends if a P0/P1 occurred.

### Hand-off checklist

- [ ] All open incidents are resolved or have a clear owner.
- [ ] The incoming on-call engineer has been briefed on any active degradations.
- [ ] Post-mortem tickets for P0/P1 incidents during the shift have been created.
- [ ] The `#oncall-handoff` Slack message has been posted.

---

## 3. Escalation path

```
On-call engineer (primary)
  └─> Secondary on-call (after 30 min unresolved)
       └─> Engineering lead (after 1 hour unresolved, or any P0)
            └─> VP Engineering (any data-loss or security incident)
                 └─> CTO (customer-visible outage > 4 hours)
```

### When to escalate

- **Always** escalate P0 incidents to the engineering lead immediately.
- Escalate if you cannot identify the root cause within **60 minutes**.
- Escalate if a mitigation attempt fails and the incident worsens.
- Escalate if the incident involves a third-party dependency (Stripe, AWS) that needs an account-owner contact.

### Escalation contacts

| Role | Slack handle | PagerDuty escalation policy |
|---|---|---|
| Primary on-call | `@oncall-primary` | `meshant-primary` |
| Secondary on-call | `@oncall-secondary` | `meshant-secondary` |
| Engineering lead | `@eng-lead` | `meshant-eng-lead` |
| Platform / infra lead | `@infra-lead` | `meshant-infra-lead` |
| Security lead | `@security-lead` | `meshant-security` |

---

## 4. Incident roles

### Incident Commander (IC)

The **on-call engineer** is the IC by default.  The IC may delegate
the role to a more senior engineer if needed.  The IC is responsible for:

- Declaring the incident severity.
- Opening the war room (Slack huddle or Google Meet for P0).
- Assigning investigation threads to other engineers.
- Posting status updates on the agreed cadence.
- Making the call to roll back, feature-flag off, or fail over.
- Declaring the incident resolved.

### Communications Lead (CL)

For P0 and P1 incidents lasting > 30 minutes, the IC should designate
a CL (or own this role themselves).  The CL:

- Posts customer-facing status updates to `meshant-internal.example.com`.
- Drafts the internal `#incident-summary` post.
- Notifies affected enterprise customers via email (template below).

### Scribe

For P0 incidents, designate a scribe to maintain a timeline in the
shared incident doc.  This timeline becomes the backbone of the
post-mortem.

---

## 5. Response procedure

### Phase 1 — Detect & Acknowledge (0–5 min)

1. Alert fires in PagerDuty / Slack.
2. On-call engineer acknowledges the alert.
3. Join the appropriate Slack channel (`#incident-p0`, `#incident-p1`, `#incident-p2`).
4. If P0: create a Google Meet link and pin it to the channel.

### Phase 2 — Assess & Declare (5–15 min)

1. Determine severity using [§1](#1-severity-levels).
2. Declare the severity in the incident channel with a brief summary:
   ```
   INCIDENT DECLARED — P1
   Symptom: marketplace orders failing with 500 since 14:32 UTC
   Suspected cause: Stripe API key rotation incomplete
   IC: @alice
   ```
3. If P0 or P1: open a shared incident doc (copy the template from
   [docs/runbooks/incident-doc-template.md](#)) and pin the link.
4. Notify the escalation path per [§3](#3-escalation-path).

### Phase 3 — Investigate (15–60 min)

1. Check the primary dashboards for the affected subsystem:
   - [System Health](monitoring/grafana/dashboards/system-health.json)
   - [API Performance](monitoring/grafana/dashboards/api-performance.json)
   - Subsystem-specific dashboards in `monitoring/grafana/dashboards/`
2. Examine recent deploys: `helm history meshant` and `git log --oneline -20`.
3. Check audit logs for unusual patterns: `AdminAuditLogPage` in the UI
   or query `audit_events` directly for the affected tenant / time window.
4. Run the health-check suite:
   ```sh
   curl -s https://api.stagingmeshant-internal.example.com/api/v1/health/ | jq .
   curl -s https://api.stagingmeshant-internal.example.com/api/v1/health/business-rules | jq .
   ```

### Phase 4 — Mitigate (as soon as possible)

1. **If a recent deploy caused it:** roll back.
   ```sh
   helm rollback meshant <previous-revision> --namespace hub-staging
   ```
2. **If a feature flag caused it:** flip the flag off.
   ```sh
   # Via admin API — see docs/runbooks/feature-flag-emergency-flip.md
   ```
3. **If a third-party dependency is down:** check the vendor status page
   and follow the vendor-failure runbook (e.g. `docs/runbooks/vendor-failure-*.md`).
4. **If a tenant is abusive:** use the tenant-suspend runbook
   (`docs/runbooks/RB-TENANT-001-suspend.md`).
5. **If a security incident:** follow `docs/runbooks/RB-SEC-002-incident-response.md`
   and notify the security lead immediately.

### Phase 5 — Communicate (every 30 min for P0/P1)

Post updates in `#incident-summary` Slack channel using this template:

```
INCIDENT UPDATE — P1 — 15:00 UTC
Status: Investigating
Symptom: marketplace orders failing with 500
Scope: all tenants; started 14:32 UTC
Actions taken: rollback to helm revision 42 completed; monitoring for recovery
Next update: 15:30 UTC
```

For customer-facing updates (P0, or P1 > 1 hour), post to the status
page.  Template:

```
Investigating — Marketplace orders may fail with a 500 error.
We are aware of an issue affecting marketplace order processing
and are actively investigating.  Next update in 30 minutes.
```

### Phase 6 — Resolve (when confirmed fixed)

1. Confirm resolution via health checks and dashboard metrics.
2. Post the resolution notice:
   ```
   INCIDENT RESOLVED — P1 — 15:45 UTC
   Duration: 73 minutes (14:32–15:45 UTC)
   Root cause: Stripe API key rotation missed the webhook secret update
   Fix: updated STRIPE_WEBHOOK_SECRET in AWS Secrets Manager; helm rollback not needed
   Post-mortem ticket: https://github.com/org/meshant/issues/XXXX
   ```
3. Create the post-mortem ticket (see [§6](#6-post-mortem)).
4. If a security incident: preserve all logs, audit events, and access
   records for the forensic review.

---

## 6. Post-mortem

### When required

- **P0 incident** — always.
- **P1 incident** — always.
- **P2 incident** — if the same root cause recurs within 30 days.
- **Security incident** — always, regardless of severity.
- **Data-loss incident** — always.

### Timeline

- Draft post-mortem within **48 hours** of resolution.
- Review with the engineering team within **5 business days**.
- Publish (anonymised if needed) to the internal runbook index within
  **10 business days**.

### Template

Post-mortems follow the template at
`docs/runbooks/postmortem-template.md`.  At minimum, every post-mortem
covers:

1. **Timeline** — all times in UTC; detection, acknowledgement,
   investigation start, mitigation applied, resolution.
2. **Impact** — users affected, data affected, revenue impact (if any).
3. **Root cause** — 5-whys analysis.
4. **Detection** — how was it caught?  (Alert?  Customer report?
   Manual observation?)  Time-to-detect.
5. **Resolution** — steps taken; time-to-resolve.
6. **Prevention items** — each with an owner and a due date.
7. **Lessons learned** — what went well, what went poorly, what
   should change in the response process itself.

### Review

Post-mortems are reviewed in the next team meeting after publication.
The review focuses on the prevention items — are they correctly scoped,
correctly owned, and on track?

---

## 7. War room protocol (P0 only)

1. **Channel:** `#incident-p0` Slack channel.  Pin the Google Meet link.
2. **Attendance:** IC (mandatory), CL (mandatory), engineering lead
   (mandatory), infra lead (on standby).
3. **No blame.**  The war room exists to resolve the incident, not to
   assign fault.  Blame-oriented language ("who broke this?") is
   explicitly forbidden.  Focus on "what is happening" and "how do
   we fix it."
4. **One conversation at a time.**  The IC moderates; side
   investigations happen in threads.
5. **No uncoordinated changes.**  Every remediation action is
   announced in the channel before execution.
6. **Scribe maintains the timeline** in the shared incident doc.
7. **After resolution:** the IC calls a 5-minute "hot wash" to
   capture immediate observations before memory fades.  The scribe
   adds these to the incident doc for the post-mortem author.

---

## 8. Communication templates

### Internal — initial declaration

```
INCIDENT DECLARED — <SEVERITY> — <TIME UTC>
Symptom: <one-line description>
Scope: <all tenants | tenant X | region>
Suspected cause: <best guess, or "unknown">
IC: @<name>
Incident doc: <link>
```

### Internal — status update (every 30 min)

```
INCIDENT UPDATE — <SEVERITY> — <TIME UTC>
Status: <Investigating | Mitigating | Monitoring>
Symptom: <re-state or update>
Actions taken: <bullet list>
Next update: <TIME UTC + 30 min>
```

### Internal — resolution

```
INCIDENT RESOLVED — <SEVERITY> — <TIME UTC>
Duration: <X hours/minutes> (<start>–<end> UTC)
Root cause: <one-line>
Fix: <one-line>
Post-mortem: <ticket link>
```

### Customer-facing — status page (P0 / long-running P1)

```
<Investigating | Identified | Monitoring | Resolved> — <one-line summary>
<Detail paragraph — what customers see, what we're doing.>
Next update: <time or "upon resolution">
```

---

## 9. Related documents

- [Runbook Index](docs/runbooks/README.md) — service-specific recovery procedures
- [Disaster Recovery](docs/mvpdocs/operations/disaster-recovery.md) — RTO/RPO targets and failover
- [Monitoring](docs/mvpdocs/operations/monitoring.md) — dashboards and alerting stack
- [Health Checks](docs/mvpdocs/operations/health-checks.md) — health endpoints and K8s probes
- [Post-Mortem Template](docs/runbooks/postmortem-template.md) — blameless post-mortem format
- [Post-Mortem Process](docs/process/postmortems.md) — when post-mortems are required and how they are reviewed
- [Security Incident Response](docs/runbooks/RB-SEC-002-incident-response.md) — security-specific response procedures
- [SECURITY.md](SECURITY.md) — vulnerability disclosure and bug bounty
- [Feature Flag Emergency Flip](docs/runbooks/feature-flag-emergency-flip.md) — flipping kill-switches under incident conditions

---

## 10. Drills

The incident response process must be exercised regularly:

- **Quarterly tabletop drill** — the on-call rotation walks through a
  simulated P1 incident using this document.  The drill must cover
  declaration, escalation, war-room setup, status updates, and
  resolution.  The drill is scheduled by the engineering lead.
- **Semi-annual live-fire drill** — a non-production environment has a
  real incident injected (e.g. `kubectl scale deployment --replicas=0`
  on a staging service) and the on-call engineer must respond with
  the full procedure.  The RTO clock is measured and compared against
  the target in [Disaster Recovery](docs/mvpdocs/operations/disaster-recovery.md).
- **Post-drill review** — within one week, the engineering lead reviews
  drill performance and updates this document if the procedure proved
  incomplete or ambiguous.
