# Operational Expansion — Meshant Platform

**Last updated:** 2026-05-15

## B.6.1 — Support Process

### Channels

| Channel | Purpose | Response SLA |
|---|---|---|
| `support@meshant.com` | Customer-initiated tickets (Zendesk) | Auto-ack within 15 min |
| `#platform-support` Slack | Internal engineering escalations | Best-effort, no SLA |
| PagerDuty | Automated alert → incident | P0: 15 min, P1: 30 min |
| `meshant-internal.example.com` | Public status page | Updated within 15 min of incident declaration |

### Severity SLAs

| Severity | Definition | First Response | Resolution Target | Escalation |
|---|---|---|---|---|
| **SEV1** | Platform-wide outage, data loss, security breach | 1 hour | 4 hours | Engineering Lead if unacknowledged >30 min |
| **SEV2** | Major feature broken, single tenant blocked, performance degradation >50% | 4 hours | 24 hours | Engineering Lead if unresolved >8h |
| **SEV3** | Minor issue, cosmetic, workaround available, single user affected | 24 hours | 5 business days | Team lead if unresolved >3d |

### Escalation Path

```
Customer ticket (Zendesk)
  → Support Engineer (first responder, ack within SLA)
    → Engineering Lead (SEV1 unresolved >30 min, SEV2 unresolved >8h)
      → CTO (SEV1 unresolved >2h, security breach)
        → CEO (legal/regulatory notification required)
```

### Support Hours

- **Business hours:** Mon-Fri 09:00-18:00 UTC (SEV2/SEV3)
- **24/7 on-call:** PagerDuty rotation (SEV1 only)
- **Holidays:** Reduced staff — SEV1 only, SEV2/3 deferred to next business day

### Customer Communication Templates

**SEV1 initial notification:**
```
Subject: [SEV1] {brief description} — Incident #{id}
Body:
  We are investigating an issue affecting {service/feature}.
  Impact: {what users experience}
  Start time: {UTC timestamp}
  Next update: within 1 hour or upon status change
  Status page: https://meshant-internal.example.com
```

**Resolution notification:**
```
Subject: [RESOLVED] {brief description} — Incident #{id}
Body:
  The issue has been resolved.
  Duration: {start}–{end} UTC
  Root cause: {summary}
  Mitigation: {what was done}
  Follow-up: postmortem will be published within 5 business days
```

## B.6.2 — End-User Documentation Audit

**Audit date:** 2026-05-15

### Existing Documentation (from `docs/mvpdocs/`)

| Category | Location | Status |
|---|---|---|
| Getting Started | `docs/mvpdocs/index.md` | ✅ Exists |
| API Reference | `docs/mvpdocs/api-reference/` | ✅ Exists (webhooks) |
| CLI Reference | `docs/mvpdocs/cli-reference/` | ✅ Exists |
| SDK Reference | `docs/mvpdocs/sdk-reference/` | ✅ Exists |
| Persona How-Tos | `docs/mvpdocs/personas/` | ✅ 6 persona directories |
| Concepts | `docs/mvpdocs/concepts/` | ✅ (audit events, compliance, governance, webhooks) |
| Operations | `docs/mvpdocs/operations/` | ✅ (incident response) |
| Use Cases | `docs/mvpdocs/use-cases/` | ✅ |
| Journeys | `docs/mvpdocs/journeys/` | ✅ |
| Integrators | `docs/mvpdocs/integrators/` | ✅ |
| Product | `docs/mvpdocs/product/` | ✅ |

### Documentation Gaps

| Gap | Priority | Action |
|---|---|---|
| **FAQ page** | P1 | Create `docs/mvpdocs/faq.md` — top 20 customer questions |
| **Troubleshooting guide** | P1 | Create `docs/mvpdocs/operations/troubleshooting.md` |
| **Changelog for end users** | P2 | Surface `CHANGELOG.md` on docs site |
| **Video walkthroughs** | P3 | Record 5-min getting-started videos per persona |
| **Interactive API playground** | P3 | Swagger UI already at `/api/v1/docs/` — link from docs |

## B.6.3 — Tenant Onboarding Runbook

### Flow: Request → Approve → Provision → Verify

### Phase 1: Request
```
1. Customer submits request via https://meshant.com/signup or sales@meshant.com
2. Sales/Success creates Linear ticket in "Tenant Onboarding" project
3. Ticket includes: company name, plan tier, admin email, required features
```

### Phase 2: Approve
```
1. Sales Lead reviews plan tier + pricing
2. Legal reviews if Enterprise plan (DPA required)
3. Engineering Lead confirms capacity (no current SEV1, planned maintenance)
4. Approval recorded in Linear ticket → moves to "Ready to Provision"
```

### Phase 3: Provision

```bash
# 1. Create tenant + platform admin
python manage.py create_tenant \
    --name "Acme Corp" \
    --slug "acme-corp" \
    --plan "pro" \
    --admin-email "admin@acme.com"

# 2. Assign feature flags
datahub admin feature-flags update --tenant-id <tid> \
    --flag data_quality_enabled=true \
    --flag datasets_enabled=true \
    --flag marketplace_enabled=true

# 3. Assign plan limits
python manage.py assign_plan --tenant acme-corp --plan pro

# 4. Send invitation email
python manage.py invite_user --email admin@acme.com --role TENANT_ADMIN --tenant acme-corp
```

### Phase 4: Verify
```
1. Admin receives invitation email → clicks link → sets password → logs in
2. Admin creates first asset via UI
3. Admin verifies plan limits visible in Settings → Subscription
4. Support sends welcome email with docs links + support channel info
5. Linear ticket moved to "Done"
```

### Provisioning Checklist

- [ ] Tenant slug unique and URL-safe
- [ ] Plan tier matches sales agreement
- [ ] Feature flags configured per customer requirements
- [ ] Admin user created with TENANT_ADMIN role
- [ ] Invitation email sent and deliverable (not bounced)
- [ ] Welcome email sent with docs + support info
- [ ] Tenant added to monitoring dashboard
- [ ] First successful login logged
- [ ] Linear ticket closed with tenant slug + admin email recorded

## B.6.4 — Observability Stack Self-Monitoring

### Prometheus Self-Scrape

```yaml
# prometheus.yml — self-monitoring job
scrape_configs:
  - job_name: prometheus-self
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: /metrics
```

Verify: `curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="prometheus-self")'`

### Grafana Health Monitoring

```promql
# Alert: Grafana health check failing
up{job="grafana"} == 0
```

### Loki Ingestion Lag Alert

```promql
# Alert: Loki falling behind by >5 min
loki_distributor_latest_seen_timestamp_seconds - time() > 300
```

### Self-Monitoring Checklist

- [ ] Prometheus scrapes itself (`prometheus-self` job)
- [ ] Grafana health probe configured
- [ ] Alertmanager monitors itself
- [ ] Loki ingestion lag alert active
- [ ] All self-monitoring alerts routed to PagerDuty

## B.6.5 — GDPR Article 30 Data Flow Diagram

### PII Storage Locations

| Data Category | Storage | Location | Encryption | Retention |
|---|---|---|---|---|
| User emails | PostgreSQL `users` table | us-east-1 (RDS) | AES-256 (RDS) | Until account deletion + 30d |
| User names | PostgreSQL `users` table | us-east-1 (RDS) | AES-256 (RDS) | Until account deletion + 30d |
| Passwords (hashed) | PostgreSQL `users` table | us-east-1 (RDS) | bcrypt (app) + AES-256 (RDS) | Until account deletion |
| Session tokens | Redis cache | us-east-1 (ElastiCache) | TLS in transit | 24h (TTL) |
| API keys (hashed) | PostgreSQL `auth` table | us-east-1 (RDS) | SHA-256 (app) + AES-256 (RDS) | Until revocation |
| Audit logs | PostgreSQL `audit` table | us-east-1 (RDS) | AES-256 (RDS) | 30d (chain) / 90d (events) |
| File uploads | S3 `meshant-files` | us-east-1 (S3) | SSE-KMS | Tenant-configured |
| Consent records | PostgreSQL `consent` table | us-east-1 (RDS) | AES-256 (RDS) | Per legal basis |
| Stripe payment data | Stripe (processor) | Stripe US | Stripe-managed | Stripe policy |
| Email content (transactional) | AWS SES | us-east-1 (SES) | TLS in transit | 14d (SES logs) |

### Processing Services

| Service | PII Processed | Purpose | Legal Basis |
|---|---|---|---|
| hub-api | Email, name, session | Authentication, authorization | Contract (GDPR Art 6.1.b) |
| hub-worker | Email (logs only) | Async task processing | Legitimate interest (Art 6.1.f) |
| Stripe | Payment data, email | Payment processing | Contract (Art 6.1.b) |
| AWS SES | Email address | Transactional email delivery | Contract (Art 6.1.b) |
| Fuseki | None (RDF metadata only) | Semantic reasoning | N/A |

### Cross-Border Transfers

```
User (EU) → us-east-1 (AWS Virginia)
  │
  ├── Data at rest: us-east-1 only (no cross-region replication)
  ├── Stripe: US processing (Stripe SCCs in place)
  └── SES: us-east-1 (no cross-region sending)

Safeguards:
  - Standard Contractual Clauses (SCCs) with Stripe
  - AWS DPA in place (AWS Artifact)
  - Data Processing Agreement: docs/compliance/dpa-addendum.md
  - Encryption at rest: AES-256 (RDS), SSE-KMS (S3)
  - Encryption in transit: TLS 1.3 for all external endpoints
```

### Data Subject Rights (GDPR Art 15-22)

| Right | Implementation |
|---|---|
| **Access** (Art 15) | `datahub gdpr export-data` → machine-readable JSON |
| **Rectification** (Art 16) | User profile edit API `PATCH /users/me/` |
| **Erasure** (Art 17) | `datahub gdpr request-erasure` → 30-day processing |
| **Portability** (Art 20) | `datahub gdpr export-data --format json` |
| **Objection** (Art 21) | Consent withdrawal via `POST /governance/consent-records/withdraw/` |
