# Alert Routing & On-Call

**Version**: 1.0 | **Owner**: Infrastructure Engineering

## Severity → Response SLA

| Severity | Alert Example | Response | Escalation |
|----------|--------------|----------|------------|
| **Critical (P1)** | API 5xx > 50%, DB down, complete outage | Page on-call, ack < 5min, resolve < 1h | CTO if > 2h |
| **Warning (P2)** | Elevated error rate, degraded service, circuit breaker open | Jira ticket, ack < 30min, resolve < 4h | Eng lead if > 8h |
| **Info (P3)** | Deprecation notice, low disk space, backup delay | Backlog, triage next sprint | None |

## Prometheus Alert → On-Call Mapping

| Alert Rule | Severity | Route |
|------------|----------|-------|
| `HighErrorBurnRate` | Critical | `#incidents` Slack + PagerDuty |
| `SearchLatencySLO` | Warning | `#incidents` Slack + Jira |
| `SPARQLLatencySLO` | Warning | `#incidents` Slack + Jira |
| `CircuitBreakerOpen` | Warning | `#incidents` Slack + Jira |
| `RDSHighCPUUsage` | Warning | `#infra-alerts` Slack |
| `RedisMemoryUsage` | Warning | `#infra-alerts` Slack |
| `CertificateExpiry` | Warning | `#infra-alerts` Slack + Jira |
| `BackupFailure` | Critical | `#incidents` Slack + PagerDuty |
| `PlanPricingDrift` | Warning | `#billing-alerts` Slack |
| `StripeTaxRegistrationRequired` | Info | `#billing-alerts` Slack |

## On-Call Rotation

- **Primary**: Infrastructure Engineering (weekly rotation)
- **Secondary**: Platform Engineering (weekly rotation)
- **Tertiary**: CTO (escalation only)
