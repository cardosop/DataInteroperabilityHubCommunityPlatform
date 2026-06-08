# RB-SEC-001 — Credential Rotation Runbook

**Owner**: Platform Engineering  
**Last reviewed**: 2026-05-13  
**Next review**: 2026-08-13  

## Scope

This runbook covers rotation procedures for:

| Credential | Rotation window | Alert threshold | Automation |
|---|---|---|---|
| `INTERNAL_API_KEY` | 90 days | `internal_api_key_age_days > 80` (warning) | AWS Secrets Manager rotation Lambda — Phase 270.C.3 |
| Warehouse credentials (Snowflake, BigQuery, Databricks, Athena) | 90 days | `warehouse_credential_age_days > 80` (warning), `> 90` (critical) | Manual per-connector rotation |
| Webhook signing keys | 180 days | Not yet instrumented | Manual via `/api/v1/webhooks/keys/rotate/` |

## INTERNAL_API_KEY Rotation

### Automated (Preferred)

The rotation Lambda in AWS Secrets Manager automatically:
1. Creates a new key version
2. Updates the `INTERNAL_API_KEY` secret with `current` + `previous` versions
3. ExternalSecrets Operator syncs both to K8s within 60 seconds
4. `InternalApiKeyMiddleware` accepts both keys during the 24h overlap window

### Manual (Fallback)

If the Lambda fails:
1. Generate new key: `openssl rand -hex 32`
2. Update AWS Secrets Manager: `aws secretsmanager put-secret-value --secret-id INTERNAL_API_KEY --secret-string '{"current":"<NEW>","previous":"<OLD>"}'`
3. Verify K8s sync: `kubectl get secret internal-api-key -n hub-staging -o jsonpath='{.data.current}' | base64 -d`
4. Confirm both keys accepted: `curl -H "Authorization: Bearer <OLD>" https://api.stagingmeshant-internal.example.com/health/` + `curl -H "Authorization: Bearer <NEW>" ...`
5. After 24h, remove old key from AWS Secrets Manager

## Warehouse Credential Rotation

### Snowflake
1. `ALTER USER meshant_etl SET RSA_PUBLIC_KEY='<NEW>'`
2. Update `hub.apps.warehouses.WarehouseConnection.config` with new key material
3. Verify: `SELECT CURRENT_USER(), CURRENT_ROLE()` via connector
4. Disable old key: `ALTER USER meshant_etl SET RSA_PUBLIC_KEY_2=''`

### BigQuery
1. Create new service account key in GCP Console
2. Update `WarehouseConnection.config.credentials_json`
3. Verify: run a sample query
4. Delete old key from GCP Console

### Databricks
1. Generate new PAT: Databricks Workspace → User Settings → Developer → Generate New Token
2. Update `WarehouseConnection.config.personal_access_token`
3. Verify: `SHOW TABLES` via connector
4. Revoke old token

### Athena
1. Rotate IAM access key via AWS Console or `aws iam update-access-key`
2. Update `WarehouseConnection.config.aws_access_key_id` + `aws_secret_access_key`
3. Verify: `SELECT 1` via connector
4. Deactivate old key

## Webhook Signing Key Rotation

1. `POST /api/v1/webhooks/keys/rotate/` — creates new key, marks old as `rotating`
2. Old key continues to sign outbound deliveries during the 24h overlap
3. After 24h, old key is auto-revoked
4. Verify: `GET /api/v1/webhooks/keys/` shows `active` + `rotating`

## Alert Response

### `WarehouseCredentialNearExpiry` (warning, >80 days)
- **Action**: Schedule rotation within 10 days
- **Escalate if**: Not rotated by day 85

### `WarehouseCredentialExpired` (critical, >90 days)
- **Action**: PagerDuty → rotate immediately
- **Impact**: Expired credentials cause connector authentication failures
- **Mitigation**: All connectors use circuit breakers — expired credentials trigger OPEN → queries fail gracefully

### `InternalApiKeyNearExpiry` (warning, >80 days)
- **Action**: Trigger Lambda rotation or follow manual procedure
- **Escalate if**: Not rotated by day 90

## Recovery Verification

After any rotation:
1. `GET /health/` — all subsystems healthy
2. `GET /health/circuit-breakers/` — no OPEN breakers
3. Run a sample query/data operation through the rotated credential
4. Verify Prometheus `credential_age_days` gauge reset to 0

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
