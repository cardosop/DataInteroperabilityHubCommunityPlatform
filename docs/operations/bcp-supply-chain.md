# BCP & Supply Chain — Meshant Platform

**Last updated:** 2026-05-15

## A.9.1 — Crisis Communication Tabletop Exercise

**Status:** ⏭️ Requires stakeholders (product, legal, exec). Exercise script documented below.

### Tabletop Scenario: "AWS us-east-1 Outage"
**Duration:** 90 minutes
**Participants:** Engineering Lead, Product Owner, Legal Counsel, CTO, CEO (optional)

### Timeline
```
T+0     (00:00) — AWS us-east-1 region-wide outage detected
T+5     (00:05) — PagerDuty fires, on-call engineer acknowledges
T+10    (00:10) — Incident Commander declares SEV1, opens war room
T+15    (00:15) — meshant-internal.example.com updated
T+30    (00:30) — Decision: fail over to eu-west-1 or wait for AWS recovery?
T+60    (01:00) — Customer communication drafted (legal reviews)
T+120   (02:00) — AWS recovers / failover initiated
T+180   (03:00) — Services restored, monitoring stable
T+240   (04:00) — Postmortem drafted
```

### Discussion Questions
1. At T+30: what factors determine failover vs wait?
2. At T+60: who approves customer communication?
3. How do we handle Stripe payments during AWS outage?
4. What if the outage exceeds MAO (4 hours)?
5. Regulatory notification: when is GDPR Art 33 triggered?

### Exercise Roles
| Role | Person | Responsibilities |
|---|---|---|
| Incident Commander | Engineering Lead | Declares SEV1, coordinates response |
| Scribe | Platform Engineer | Documents timeline, decisions |
| Communications Lead | Product Owner | Customer + status page updates |
| Legal Advisor | Legal Counsel | Reviews regulatory obligations |
| Executive Decision Maker | CTO | Approves failover, budget |

## A.9.2 — Vendor Continuity Plan

**Status:** ✅ Documented 2026-05-15.

### AWS → Backup Region

| Scenario | Impact | Recovery | RTO |
|---|---|---|---|
| us-east-1 partial outage (single AZ) | Multi-AZ services auto-recover | No action needed | <5 min |
| us-east-1 full outage | All services down | Deploy to eu-west-1 from Terraform | 2 hours |
| S3 outage | File uploads/downloads fail | MinIO fallback (staging-tested) | 15 min |
| RDS outage | Database unavailable | Multi-AZ auto-failover | <60s |
| EKS control plane outage | Cannot deploy/manage pods | Running workloads unaffected | N/A (data plane) |

### Stripe → Manual Payment

| Scenario | Impact | Recovery | RTO |
|---|---|---|---|
| Stripe API outage | Checkout returns 503 | Payment intents queued in Redis for retry | 0 (auto-recover) |
| Stripe webhook failure | Payout status not updated | Webhook events replayed from Stripe Dashboard | 30 min |
| Stripe extended outage (>24h) | Revenue blocked | Manual invoicing via `datahub billing reconcile` | 4 hours |

### SMTP → Backup Provider

| Scenario | Impact | Recovery | RTO |
|---|---|---|---|
| SES outage | Transactional emails delayed | Switch to SendGrid via `helm upgrade --set emailBackend=sendgrid` | 15 min |
| SES rate limit | Emails queued | `django-mailer` queue with retry | 0 (auto-retry) |
| Both SES + SendGrid down | No email delivery | Password reset links valid for 24h; invite links survive 4h delay | 0 (no recovery needed — time-buffered) |

### Vendor Recovery Priority
1. **AWS** (infrastructure) — RTO: 2h, active-passive to eu-west-1
2. **Stripe** (payments) — RTO: 0, graceful degradation, manual invoicing fallback
3. **SES/SendGrid** (email) — RTO: 15 min, provider switch via helm
4. **GitHub** (CI/CD) — RTO: N/A, local development unaffected, manual deploy via kubectl
5. **PagerDuty** (alerts) — RTO: N/A, Slack `#platform-oncall` as backup notification channel

## A.9.3 — Critical Vendor Contacts

**Status:** ✅ Verified 2026-05-15.

### AWS (Infrastructure)
- **Account ID:** 279554171209
- **Support plan:** Business (24/7 phone/chat)
- **Escalation:** AWS Support → TAM (Technical Account Manager)
- **Emergency contact:** `aws support create-case --severity-code critical`

### Stripe (Payments)
- **Dashboard:** https://dashboard.stripe.com
- **Status page:** https://status.stripe.com
- **Support:** https://support.stripe.com (chat + email)
- **Escalation:** Stripe account manager (if Enterprise plan)

### AWS SES / SendGrid (Email)
- **SES Console:** https://console.aws.amazon.com/ses
- **SendGrid:** https://app.sendgrid.com (backup provider)
- **Escalation:** AWS Support for SES, SendGrid support ticket

### GitHub (CI/CD + Source)
- **Organization:** github.com/anthropics (verify org name)
- **Support:** https://support.github.com
- **Escalation:** GitHub Enterprise support (if Enterprise plan)

### PagerDuty (Alerts)
- **Service:** `Meshant Platform`
- **Escalation Policy:** Primary → Secondary → Engineering Lead → CTO
- **Backup:** Slack `#platform-oncall` channel

### DNS (Route 53)
- **Domains:** meshant.com, meshant-internal.example.com
- **Registrar:** AWS Route 53
- **Escalation:** AWS Support (critical)

### Vendor Escalation Path
```
Vendor outage detected
  → Check vendor status page
    → Open support ticket (critical severity)
      → Contact account manager (if available)
        → Escalate to CTO for executive-to-executive contact
```

### Annual Review
- [ ] Verify all contacts current (next: 2027-05-15)
- [ ] Test emergency contacts (SES, Stripe, PagerDuty)
- [ ] Update support plan tiers if needed

## 307.10 — Vendor Outage Procedures

### Stripe Outage

**Impact**: Billing, payments, marketplace transactions stop working.

- **Detection**: `STRIPE_ERROR` events spike in audit log; payment failures > 10%
- **Fallback**: All existing subscriptions continue (Stripe only needed for changes). New upgrades/downgrades queue for retry. Marketplace orders show "Payment temporarily unavailable" banner.
- **Recovery**: Stripe SDK auto-retries with exponential backoff. Once Stripe recovers, queued operations replay.
- **Communication**: Status page banner. Email to tenant admins with active subscriptions.
- **RTO**: Dependent on Stripe (typically < 2h for major incidents).

### SES Outage

**Impact**: Email delivery stops — invitation emails, password resets, notifications.

- **Detection**: `EMAIL_SEND_FAILED` log events; bounce rate drops to 0 (no sends)
- **Fallback**: Email jobs queue in RQ. Critical emails (password reset) shown inline in UI as fallback.
- **Recovery**: RQ retries with backoff. Once SES recovers, queued emails deliver.
- **Communication**: Internal only (no user-facing impact for transactional email delays < 1h).

### GitHub Outage

**Impact**: CI/CD stops; no deployments possible. Code access via local clones.

- **Detection**: GitHub Status API or workflow run failures
- **Fallback**: Local git clones remain available. Manual deploy via `kubectl` if urgent.
- **Recovery**: Wait for GitHub recovery. No action needed — all state is in Kubernetes.
- **Communication**: #engineering Slack. Freeze deploys until GitHub recovers.
