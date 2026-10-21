# Risk register excerpt — Files & datasets hardening

| Risk ID | Description | Likelihood | Impact | Mitigation | Owner |
|---------|-------------|------------|--------|------------|-------|
| DSF-01 | Purge cron double-run deletes prod data | M | Crit | Distributed Redis lock + dry-run gates | Platform Eng |
| DSF-02 | ClamAV outage blocks uploads silently | L | High | Startup version check + RQ alerting | Security Eng |
| DSF-03 | SPA CORS mismatch blocks multipart upload | M | Med | IaC-reviewed bucket config + staging smoke | SRE |
| DSF-04 | Tenant isolation break via dedup fantasies | L | Crit | SHA-256 policy per ADR-DSF-007 | Compliance Eng |
| DSF-05 | Observability cardinality explosion | M | Med | Placeholder Grafana JSON until OTel budgeting | Observability |

Review quarterly alongside Phase 260 soak metrics.

