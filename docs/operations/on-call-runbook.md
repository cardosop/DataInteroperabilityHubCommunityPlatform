# On-Call Runbook — Meshant Platform

**Last updated:** 2026-05-15
**Reviewers required:** 2 engineers (sign-off below)

## Rotation Schedule

| Role | Primary | Secondary | Escalation |
|---|---|---|---|
| Platform SRE | Weekly rotation (Mon 09:00 UTC) | Next on-call in rotation | Engineering Lead |
| Data Pipeline | Weekly rotation (Mon 09:00 UTC) | Next on-call in rotation | Data Engineering Lead |
| Security | 24/7 PagerDuty auto-escalation | Security Lead | CTO |

**Rotation management:** PagerDuty schedule `Meshant Platform On-Call`
**Handoff:** Monday 09:00 UTC — 30 min sync via `#platform-oncall` Slack
**Override:** Swap via PagerDuty override. Notify `#platform-oncall` 24h in advance.

## Alert Routing

| Alert Severity | Notification Channel | Response Time | Auto-Escalation |
|---|---|---|---|
| **P0** (critical) | PagerDuty page + `#incident-p0` Slack | 15 min | Escalate to secondary if not acked in 5 min |
| **P1** (warning, infra) | PagerDuty page + `#incident-p1` Slack | 30 min | Escalate to secondary if not acked in 15 min |
| **P2** (warning, app) | `#incident-p2` Slack | 2 hours | Ticket auto-created in Linear `INGEST` project |
| **P3** (info) | GitHub issue with `incident` label | Next business day | No escalation |

**PagerDuty service:** `Meshant Platform`
**Alertmanager → PagerDuty:** via `alertmanager/pagerduty.yml` webhook

## Escalation Path

```
Primary On-Call (ack within 5/15 min)
  │
  ├── UNACKED → Secondary On-Call (ack within 15 min)
  │     │
  │     └── UNACKED → Engineering Lead (phone call)
  │           │
  │           └── UNACKED → CTO (phone call)
  │
  └── ACKED but unresolved > 4h → Engineering Lead joins war room
```

**Engineering Lead:** Refer to `docs/runbooks/internal-eng-announcement-protocol.md` for customer communication templates.

## Shift Checklist

### Start of shift (Monday 09:00 UTC)
- [ ] Review handoff notes from previous on-call
- [ ] Verify PagerDuty contact methods (phone, push notifications)
- [ ] Check Grafana dashboard for anomalies (last 24h): `meshant-internal.example.com/d/api-latency`
- [ ] Review Linear `INGEST` project for open incident tickets
- [ ] Confirm AWS Console access (staging profile: `--profile staging`)
- [ ] Confirm `kubectl` access to staging cluster (`meshant-staging`)

### During shift
- [ ] Acknowledge PagerDuty pages within response time SLA
- [ ] For P0/P1: open war room in `#incident-p0` or `#incident-p1` Slack
- [ ] For P0/P1: appoint incident commander (first responder)
- [ ] Post status updates every 30 min during active incidents
- [ ] Escalate per policy if root cause not identified within 1h

### End of shift
- [ ] Write handoff notes in `#platform-oncall` Slack
- [ ] Update Linear tickets with current status
- [ ] Verify all acknowledged alerts are resolved or handed off

## War Room Protocol

1. **Incident Commander** declares the war room open in Slack
2. **Scribe** starts a shared document (Google Docs) — copy `postmortem-template.md`
3. **Communications Lead** posts initial status to `#incident-p0`/`#incident-p1`
4. Engineers join the war room; IC assigns investigation threads
5. Status updates every 30 min; customer-facing update every 1h
6. Upon resolution: IC declares incident resolved, scribe finalizes timeline

## Communication Templates

### Initial P0 notification
```
🚨 P0 INCIDENT: {brief description}
- Impact: {what users see}
- Start: {UTC timestamp}
- Incident Commander: {name}
- War room: #incident-p0
- Status page: meshant-internal.example.com
```

### Status update (every 30 min)
```
📡 P0 UPDATE ({time} UTC): {one-line status}
- Root cause: {identified / still investigating}
- Mitigation: {in progress / deployed / pending}
- ETA to resolution: {estimate or "no ETA yet"}
```

### Resolution
```
✅ RESOLVED: {brief description}
- Duration: {start} → {end} UTC ({total minutes})
- Root cause: {one-line summary}
- Mitigation: {what was done}
- Postmortem: {link to doc} (due within 5 business days)
```

## Key Runbooks (by incident type)

| Incident | Runbook |
|---|---|
| API 5xx spike | `runbooks/RB-SVC-001.md` |
| Database connection exhaustion | `runbooks/RB-DB-001.md` |
| Database failover | `runbooks/RB-DB-002.md` |
| Redis connection failure | `runbooks/RB-QUEUE-001.md` |
| Staging deploy failure | `runbooks/RB-DEPLOY-001.md` |
| Staging deploy rollback | `runbooks/RB-DEPLOY-002.md` |
| Security incident | `runbooks/RB-SEC-001.md` |
| Credential rotation | `runbooks/RB-SEC-001-credential-rotation.md` |
| Webhook DLQ investigation | `runbooks/RB-WH-001-webhook-dlq-investigation.md` |
| Stripe payout failure | `runbooks/RB-MKT-003-payout-failure-investigation.md` |
| Marketplace KYC failure | `runbooks/RB-MKT-001-stripe-connect-onboarding-failure.md` |
| Scheduled ingestion stuck | `docs/runbooks/scheduled-ingestion-stuck.md` |
| Fuseki outage | `docs/runbooks/semantic-degraded.md` |
| File virus scan incident | `docs/runbooks/file-virus-scan-incident.md` |

## Review Sign-off

- [ ] Engineer 1: _____________  Date: _________
- [ ] Engineer 2: _____________  Date: _________
