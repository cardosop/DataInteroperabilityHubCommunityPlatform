# Loki Log Retention — GDPR Alignment Verification (280.C.6.7)

**Date:** 2026-05-15  
**Auditor:** Platform Engineering  
**Config file:** `monitoring/loki/loki.yaml`

## 1. Current Configuration

| Parameter | Value | Location |
|---|---|---|
| `retention_period` | 720h (30 days) | `limits_config.retention_period` |
| `retention_enabled` | true | `compactor.retention_enabled` |
| `retention_delete_delay` | 2h | `compactor.retention_delete_delay` |
| `retention_delete_worker_count` | 10 | `compactor.retention_delete_worker_count` |
| `delete_request_store` | s3 | `compactor.delete_request_store` |

## 2. GDPR Requirements Mapping

### 2.1 — Article 5(1)(e) — Storage Limitation

> Personal data shall be kept in a form which permits identification of data subjects for no longer than is necessary for the purposes for which the personal data are processed.

**Assessment:** Loki logs contain operational telemetry, not PII by design. Access logs drop `Authorization` and `Cookie` headers (Traefik `accessLog.fields.headers.names`). Structured application logs use `structlog` with PII redaction. 30-day retention is appropriate for operational debugging and security monitoring — logs older than 30 days have no operational value.

**Verdict:** ✅ Compliant. 30-day retention meets the storage limitation principle.

### 2.2 — Article 30 — Records of Processing

> Each controller shall maintain a record of processing activities under its responsibility.

**Assessment:** Loki is NOT the system of record for processing activities. Audit events (which ARE the RoPA source) are stored in PostgreSQL (`audit_events` table) with 30-day to 1-year retention depending on category. Loki logs are operational artifacts, not legal records.

**Verdict:** ✅ Compliant. Loki is not a RoPA data source.

### 2.3 — Article 32 — Security of Processing

> The controller shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk.

**Assessment:** Loki logs are encrypted at rest (SSE-S3) and in transit (TLS 1.2+). Access to Loki is restricted to the `hub-net-production` network and authenticated Grafana users. Logs older than 30 days are automatically deleted, reducing the attack surface for historical data exposure.

**Verdict:** ✅ Compliant. Encryption + access control + auto-deletion.

### 2.4 — Article 33/34 — Breach Notification

> In the case of a personal data breach, the controller shall notify the supervisory authority within 72 hours.

**Assessment:** 30-day log retention supports the 72-hour breach notification window with 27 days of headroom. Breach investigations typically require 7-14 days of logs. 30 days provides 2× headroom for complex multi-service incidents. However, if logs are the ONLY source of breach evidence, they must be preserved (legal hold) before the 30-day window expires.

**Verdict:** ✅ Compliant with caveat: implement legal-hold log preservation for active breach investigations.

### 2.5 — Audit Events vs. Logs

| Concern | Loki (logs) | RDS (audit_events) |
|---|---|---|
| PII content | Redacted (structlog processors) | May contain subject identifiers (by design) |
| Retention | 30 days | 30 days – 1 year (category-based) |
| Queryable | Via Grafana (LogQL) | Via Django admin / API |
| Legal hold | Manual S3 object lock | `GovernanceService.place_legal_hold()` |
| GDPR record | No (operational only) | Yes (audit_events are the formal record) |

## 3. Compliance Gaps

### Gap 1: No legal-hold mechanism for Loki logs

**Risk:** During a breach investigation, logs may be deleted by the compactor before the investigation completes.

**Mitigation:** Implement a Loki log preservation flag (`LOKI_PRESERVE_LOGS=true`) that temporarily disables the compactor. Documented in incident response runbook.

**Severity:** Medium  
**Status:** Open — add to incident response runbook

### Gap 2: No per-stream retention override for compliance-critical logs

**Risk:** All log streams share the same 30-day retention. Compliance audit logs may need longer retention.

**Mitigation:** Loki supports per-tenant retention overrides in `limits_config`. If compliance logs need >30-day retention, configure a separate retention period for the compliance log stream. Current workaround: audit events that need >30-day retention are written to RDS, not logs.

**Severity:** Low  
**Status:** Acceptable — audit events in RDS provide the long-term record

## 4. Configuration Change Recommendations

### 4.1 — Immediate (Post-Launch)

None required. 720h (30 days) is appropriate for operational logs.

### 4.2 — If Extended Retention Needed

```yaml
# monitoring/loki/loki.yaml — limits_config
limits_config:
  retention_period: 720h  # 30-day default for all streams
  
  # Per-tenant overrides (future: compliance-sensitive tenants)
  retention_stream:
    - selector: '{category="compliance"}'
      priority: 1
      period: 8760h  # 365 days for compliance logs
```

### 4.3 — Monitoring

```promql
# Alert if Loki log volume spikes (may indicate PII leakage before redaction)
rate(loki_distributor_bytes_received_total[5m]) > 3 * rate(loki_distributor_bytes_received_total[5m] offset 1h)
```

## 5. Verification Checklist

- [x] Loki `retention_period` = 720h (30 days)
- [x] Loki `retention_enabled` = true
- [x] Compactor running and deleting data beyond 30 days
- [x] Access logs drop Authorization and Cookie headers (Traefik config verified)
- [x] Application logs use structlog with PII redaction processors
- [x] Audit events in RDS have category-based retention (30d – 1y)
- [x] S3 bucket for Loki has SSE-S3 encryption enabled
- [ ] Legal-hold procedure for logs during breach investigation (Gap 1 — add to IR runbook)
