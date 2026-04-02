# Compliance Service — Policy and Risk Threshold Configuration

**Last Updated**: 2026-02-20

## Purpose

The compliance service (PII detection, risk scoring, policy engine) supports **environment-based configuration** for policy and risk thresholds. Use these when you need to tighten or relax `allowed_to_store` and risk level behaviour without code changes.

## Environment variables

Set in the environment of the compliance-service container or process.

### Policy (allowed_to_store)

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPLIANCE_POLICY_DIRECT_PII_THRESHOLD` | 0.01 | Minimum match ratio for direct PII (e.g. card, SSN) to block storage. 0.01 = 1% of rows. |
| `COMPLIANCE_POLICY_RISK_SCORE_THRESHOLD` | 5.0 | Maximum risk score to allow storage; above this `allowed_to_store=false`. |

### Risk level thresholds

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPLIANCE_RISK_THRESHOLD_NONE` | 0.0 | Score &lt; LOW threshold → NONE. |
| `COMPLIANCE_RISK_THRESHOLD_LOW` | 0.1 | Score ≥ this → at least LOW. |
| `COMPLIANCE_RISK_THRESHOLD_MEDIUM` | 1.0 | Score ≥ this → at least MEDIUM. |
| `COMPLIANCE_RISK_THRESHOLD_HIGH` | 5.0 | Score ≥ this → at least HIGH. |
| `COMPLIANCE_RISK_THRESHOLD_CRITICAL` | 10.0 | Score ≥ this → CRITICAL. |

Invalid or missing values fall back to defaults. Restart the service after changing env.

## Request size and row limits (5.3.1)

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPLIANCE_MAX_REQUEST_BYTES` | 52428800 (50 MiB) | Max request body size in bytes. Over limit → **413 Payload Too Large** with message. |
| `COMPLIANCE_MAX_ROWS` | 1000000 | Max rows per file or dataframe. Over limit → **400** with message to reduce or split. |

- Enforced in `POST /scan-file` (after reading body and after parsing rows) and `POST /scan-dataframe` (Content-Length when present; row count after building DataFrame).
- For `scan-dataframe`, body size is only enforced when the client sends a `Content-Length` header.

## Health and readiness (5.4.4)

- **`GET /health`** — Returns 200 and `{"status": "healthy", "service": "compliance-service"}` when the service can serve. Use for liveness.
- **`GET /ready`** — Returns 200 and `{"status": "ready", "service": "compliance-service"}` when ready to accept traffic. Use for readiness probes.

Docker Compose and CI health checks typically use `/health`. Restart the service after changing configuration.

## References

- [Compliance Service README](../../services/compliance-service/README.md) — API, PII categories, policy thresholds, limits, observability (shared.metrics)

---

## Phase 19 Compliance Overhaul

### 25-Jurisdiction Support

The compliance service now supports 25 jurisdictions. Configure applicable regulations per tenant:

| Jurisdiction | Key | Notes |
|-------------|-----|-------|
| GDPR | `GDPR` | EU General Data Protection |
| HIPAA | `HIPAA` | US Health data |
| SOX | `SOX` | US Financial reporting |
| LGPD | `LGPD` | Brazil data protection |
| CCPA | `CCPA` | California Consumer Privacy |
| PIPEDA | `PIPEDA` | Canada |
| POPI | `POPI` | South Africa |
| PDPA | `PDPA` | Singapore/Thailand |
| APPs | `APPs` | Australia |
| DPDP | `DPDP` | India |

Additional jurisdictions available via `VALID_COMPLIANCE_REGIMES` in `hub/apps/tenants/validators.py`.

### Async Scanning

Compliance runs now execute asynchronously:

```bash
# Monitor a running compliance scan
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.compliance.models import ComplianceRun
run = ComplianceRun.objects.get(id='<run-id>')
print(f'Status: {run.status}, Risk: {run.risk_level}')
"
```

Status flow: `PENDING → RUNNING → SUCCEEDED | FAILED`

### Risk Score Thresholds

| Level | Threshold | Action |
|-------|-----------|--------|
| LOW | 0-25 | Allowed to store |
| MEDIUM | 26-50 | Review recommended |
| HIGH | 51-75 | Restricted storage |
| CRITICAL | 76-100 | Storage denied |

Configure via `COMPLIANCE_RISK_THRESHOLD_HIGH` and `COMPLIANCE_RISK_THRESHOLD_CRITICAL` environment variables.
