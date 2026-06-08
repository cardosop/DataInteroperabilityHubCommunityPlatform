# Alert Severity Classification — Meshant Platform

**Last updated:** 2026-05-15
**Source:** `monitoring/prometheus/alerts.yml`

## Severity Mapping

Prometheus alerts use `severity: critical` and `severity: warning` labels. The mapping to the incident response P0-P3 scale:

| Prometheus Label | Incident Severity | Response | Notification |
|---|---|---|---|
| `severity: critical` | **P0** | 15 min | PagerDuty page + `#incident-p0` Slack |
| `severity: warning` (infrastructure) | **P1** | 30 min | PagerDuty page + `#incident-p1` Slack |
| `severity: warning` (application) | **P2** | 2 hours | `#incident-p2` Slack, Linear ticket |
| `severity: info` (future) | **P3** | Next business day | GitHub issue |

## P0 Alerts — Page Immediately (22 alerts, `severity: critical`)

These alerts indicate platform-wide outages, data loss risk, or security boundary violations.

| Alert Name | Condition | Runbook |
|---|---|---|
| `TLSCertificateExpired` | Certificate expired (<24h) | cert-manager docs |
| `PostgresDown` | PostgreSQL unreachable (>1m) | `runbooks/RB-DB-001.md` |
| `RedisDown` | All Redis instances unreachable | `runbooks/RB-QUEUE-001.md` |
| `APIErrorRateHigh` | 5xx rate >5% for 5 min | `runbooks/RB-SVC-001.md` |
| `APILatencyHigh` | p95 latency >2s for 5 min | `runbooks/RB-SVC-001.md` |
| `FusekiDown` | Fuseki health check failing | `runbooks/semantic-degraded.md` |
| `DiskFull` | Any volume >90% full | `runbooks/RB-DB-003.md` |
| `CertificateExpired` | TLS cert expired | cert-manager manual renew |
| `KubernetesNodeNotReady` | Node not ready >5 min | `runbooks/RB-DEPLOY-001.md` |
| `KubernetesPodCrashLooping` | Pod in CrashLoopBackOff >5 min | `runbooks/RB-SVC-001.md` |
| `HighCPUUsage` | CPU >90% for 10 min | `runbooks/RB-SVC-001.md` |
| `HighMemoryUsage` | Memory >90% for 10 min | `runbooks/RB-SVC-001.md` |
| `PGBouncerDown` | PgBouncer unreachable | `runbooks/RB-DB-001.md` |
| `PrefectServerDown` | Prefect health check failing | `runbooks/prefect-runbook.md` |
| `MinioDown` | MinIO unreachable | `runbooks/RB-DB-003.md` |
| `TraefikDown` | No healthy Traefik pods | `runbooks/RB-DEPLOY-001.md` |
| `OOMKilled` | Any pod OOMKilled | `runbooks/RB-SVC-001.md` |
| `StaleBackup` | No successful DB backup in 25h | `runbooks/RB-DB-003.md` |
| `AlerManagerDown` | Alertmanager not firing | `runbooks/RB-SVC-001.md` |
| `PrometheusDown` | Prometheus not scraping | `runbooks/RB-SVC-001.md` |
| `ExternalSecretSyncFailed` | ExternalSecret `Synced=False` | `runbooks/RB-SEC-001-credential-rotation.md` |
| `DatabaseReplicationLag` | Replica lag >60s | `runbooks/RB-DB-002.md` |

## P1 Alerts — Page Within 1 Hour (~51 alerts, `severity: warning`)

Covers infrastructure warnings: moderate resource pressure, single-instance failures, delayed processing.

Key P1 alerts: `TLSCertificateExpiring` (7-day warning), `PostgresConnectionPoolHigh`, `RedisMemoryHigh`, `QueueDepthHigh`, `WebhookDeliveryDelay`, `StripeWebhookFailure`, `PrefectFlowFailure`, `ScheduledIngestionStuck`, `ComplianceScanDelayed`, `DQRunBacklog`.

## P2 Alerts — Ticket Within 24 Hours

Application-level warnings that don't indicate immediate outage: `SlowQueryDetected` (>1s, sporadic), `CacheMissRateHigh` (>50%), `EmailBounceRateHigh`, `FileUploadErrorRate`, `SearchIndexLag`.

## P3 — Informational (Future)

No P3 alerts currently configured. Candidates: `NewTenantCreated`, `PlanUpgraded`, `DailyActiveUsers`, `BackupSizeTrend`.

## Upgrade Triggers (from INCIDENT_RESPONSE.md)

- P1 unresolved >4h without mitigation → upgrade to P0
- P2 involving PII exposure or security boundary → upgrade to P1
- Any incident where root cause unidentified >1h → escalate one level
