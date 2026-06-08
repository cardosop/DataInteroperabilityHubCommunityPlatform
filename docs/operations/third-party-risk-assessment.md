# Third-Party Dependency Risk Assessment — Meshant Platform

**Last updated:** 2026-05-15

## Dependency Risk Matrix

| Dependency | Critical Path | Failure Mode | Impact | Graceful Degradation |
|---|---|---|---|---|
| **Stripe Connect** | Marketplace payments, provider payouts, KYC onboarding | API outage, webhook delivery failure | P0 — payments halt, checkout returns 503 | Queue payment intents locally, replay when Stripe recovers. Show "Payments temporarily unavailable" banner. KYC onboarding paused. |
| **SMTP (AWS SES)** | User registration, password reset, email notifications | SES regional outage, rate limit exceeded | P2 — transactional emails delayed | Queue emails in `django-mailer`. Deliver when SES recovers. Password reset links use 24h expiry (generous). Critical: invite acceptance links survive 4h delay. |
| **Prefect Server** | Scheduled ingestion/export workflows, DQ run scheduling | Prefect Server crash, Prefect DB corruption | P2 — automated workflows pause | Manually trigger workflows via `datahub scheduled-ingestion trigger <id>`. DQ runs triggerable via `datahub dq run`. Workflow state recoverable from Prefect DB backup. |
| **CKAN Connector** | External data catalog sync (marketplace connector) | CKAN instance unreachable, API version mismatch | P3 — marketplace listing sync delayed | Stale listings served from last successful sync (cached in Postgres). "Last synced: {timestamp}" badge shown. Manual re-sync via `datahub marketplace sync start`. |
| **AWS S3** | File storage, static assets, DB backups | S3 regional outage | P1 — file uploads/downloads fail | Uploads queued locally (Django file storage fallback). Downloads return 503 with `Retry-After`. DB backups delayed (point-in-time recovery window extends). |
| **AWS SES** | Email delivery | See SMTP row above | P2 | Same SMS queue fallback + 24h link expiry |
| **Fuseki (Apache Jena)** | SPARQL queries, RDF ingest, semantic reasoning | Fuseki crash, TDB2 corruption | P1 — semantic features unavailable | Non-semantic APIs unaffected. Semantic endpoints return 503 with `Retry-After: 60`. Fuseki restart recovers TDB2 from write-ahead log (<30s). |
| **cert-manager** | TLS certificate auto-renewal | ACME issuer failure, rate limit | P1 (if unmitigated) — cert expiry in 7 days triggers warning alert | cert-manager retries with exponential backoff. Manual cert issuance via `kubectl cert-manager renew` as fallback. 7-day warning + 24h critical alerts. |
| **ExternalSecrets (K8s)** | AWS Secrets Manager → K8s Secret sync | ExternalSecrets operator crash, IRSA permission loss | P1 — pods fail to mount secrets on restart | Running pods keep existing secrets in memory. New pod starts fail. Alerts on ExternalSecret `Synced=False`. Manual kubectl secret creation as emergency fallback. |

## Graceful Degradation Architecture

### Payment Processing (Stripe outage)

```
User clicks "Pay" → CheckoutPage
  │
  ├── Stripe UP → PaymentIntent created → order fulfilled
  │
  └── Stripe DOWN → 503 response
        └── payment_intent queued in redis-queue
              └── Stripe recovers → worker processes queue → order fulfilled
                    └── User receives confirmation email
```

### Email Delivery (SES outage)

```
User triggers email (register, reset, invite)
  │
  ├── SES UP → email delivered immediately
  │
  └── SES DOWN → email queued in django-mailer
        └── SES recovers → cron job (every 5 min) drains queue
              └── Links valid for 24h from send time (not creation time)
```

### Workflow Scheduling (Prefect Server outage)

```
Scheduled time arrives
  │
  ├── Prefect UP → flow runs normally
  │
  └── Prefect DOWN → flow state logged to Prefect DB (if DB up)
        │              OR
        └── Operator notified via Prometheus alert
              └── Manual trigger: datahub scheduled-ingestion trigger <id>
```

## Recovery Time Objectives (RTO)

| Dependency | RTO Target | Recovery Method |
|---|---|---|
| Stripe | 0 (no action — self-heals when Stripe recovers) | Stripe status page: https://status.stripe.com |
| SES | 15 min (manual switch to SendGrid fallback) | `helm upgrade --set emailBackend=sendgrid` |
| Prefect Server | 5 min (automatic restart via liveness probe) | `kubectl rollout restart deploy prefect-server` |
| CKAN | N/A (degraded mode acceptable indefinitely) | Stale data served with timestamp badge |
| S3 | 0 (no action — AWS self-heals) | AWS status page: https://health.aws.amazon.com |
| Fuseki | 5 min (automatic restart) | `kubectl rollout restart deploy fuseki` |
| cert-manager | 30 min (manual renew if auto-fails) | `kubectl cert-manager renew` |
| ExternalSecrets | 15 min (manual kubectl create secret) | Runbook: `docs/runbooks/RB-SEC-001-credential-rotation.md` |

## Monitoring

- **Stripe**: Prometheus blackbox exporter probes `https://api.stripe.com/v1/` every 60s
- **SES**: CloudWatch `SES.SendQuota` metric → Grafana dashboard
- **Prefect**: `prefect_server_health` Prometheus metric (from OTEL collector)
- **S3**: CloudWatch `S3.5xxErrors` → Prometheus alert
- **Fuseki**: Kubernetes liveness probe `GET /$/ping` every 10s
- **cert-manager**: `certmanager_certificate_expiration_timestamp_seconds` metric
- **ExternalSecrets**: `externalsecret_status_condition` metric → alert on `Synced=False`
