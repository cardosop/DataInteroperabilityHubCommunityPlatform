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
