# Secrets Management

How Meshant stores, syncs, rotates, and audits secrets across all
environments.

## Where Secrets Live

| Environment | Store | Access Method | Sync Mechanism |
|---|---|---|---|
| Local dev | `.env` file | Loaded by Django `environ` | Manual; never committed to git |
| CI/CD | GitHub Actions Secrets | `${{ secrets.NAME }}` in workflows | Set in repo Settings > Secrets |
| Staging | AWS Secrets Manager | K8s pod via IRSA | ExternalSecrets Operator polls every 5m |
| Production | AWS Secrets Manager | K8s pod via IRSA | ExternalSecrets Operator polls every 5m |

In staging and production, pods never hold long-lived AWS credentials. IAM
Roles for Service Accounts (IRSA) provides temporary STS tokens via the
EKS OIDC provider. The ServiceAccount annotation
`eks.amazonaws.com/role-arn` links each workload to its least-privilege IAM
role (Phase 213.J).

## Secret Categories

### Django Core

| Secret | AWS SM Path | Purpose |
|---|---|---|
| `SECRET_KEY` | `<prefix>/django` | Django signing key (CSRF, sessions) |
| `JWT_SECRET_KEY` | `<prefix>/django` | JWT access/refresh token signing |
| `ENCRYPTION_KEY` | `<prefix>/django` | Field-level encryption (tenant SSO configs, API keys) |

### Database

| Secret | AWS SM Path | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | `<prefix>/postgres` | Primary database password |
| `PGPASSWORD` | `<prefix>/postgres` | Alias used by `pg_dump` and backup scripts |
| `PGBOUNCER_ADMIN_PASSWORD` | `<prefix>/pgbouncer` | PgBouncer admin console access |
| `FUSEKI_ADMIN_PASSWORD` | `<prefix>/fuseki` | Fuseki triple store admin API |

### Redis

| Secret | AWS SM Path | Purpose |
|---|---|---|
| `REDIS_CACHE_URL` | `<prefix>/redis` | Cache backend (full connection string with password) |
| `REDIS_QUEUE_URL` | `<prefix>/redis` | RQ job queue backend |
| `REDIS_EVENTS_URL` | `<prefix>/redis` | Event pub/sub channel |
| `REDIS_CHANNELS_URL` | `<prefix>/redis` | Django Channels layer |

### Service-to-Service

| Secret | AWS SM Path | Purpose |
|---|---|---|
| `HUB_WORKER_API_KEY` | `<prefix>/workers` | Prefect flow-run pods authenticate to Hub API |
| `INTERNAL_API_KEY` | `<prefix>/api` | Compliance/DQ/semantic services authenticate to Hub |

### Third-Party Integrations

| Secret | AWS SM Path | Purpose |
|---|---|---|
| `STRIPE_SECRET_KEY` | `<prefix>/stripe` | Billing API (gated by `externalSecrets.stripe.enabled`) |
| `STRIPE_WEBHOOK_SECRET` | `<prefix>/stripe` | Billing webhook signature verification |
| `STRIPE_MARKETPLACE_WEBHOOK_SECRET` | `<prefix>/stripe` | Marketplace purchase webhooks |
| `CKAN_DADOS_GOV_BR_API_KEY` | `<prefix>/ckan` | Brazilian government data portal (gated) |
| `SENTRY_DSN` | (env var) | Error tracking ingest URL |

### S3 / Object Storage

| Secret | AWS SM Path | Purpose |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `<prefix>/s3` | Static S3 credentials (gated, only for MinIO/dev) |
| `AWS_SECRET_ACCESS_KEY` | `<prefix>/s3` | Static S3 credentials (gated, only for MinIO/dev) |

In staging and production, IRSA provides S3 access; static credentials are
not synced (`externalSecrets.s3StaticCredentials: false`).

## ExternalSecrets Flow

The ExternalSecrets Operator reconciles secrets from AWS Secrets Manager into
a Kubernetes Secret named `hub-secrets` (configurable via
`externalSecrets.targetSecretName`). The flow:

1. A `SecretStore` CR references the AWS SM region and the IRSA-annotated
   ServiceAccount.
2. An `ExternalSecret` CR lists each `remoteRef` (AWS SM key + JSON property)
   mapped to a Kubernetes Secret key.
3. The operator polls AWS SM at `refreshInterval` (default 5m) and updates
   the K8s Secret.
4. Deployments mount the Secret via `envFrom.secretRef`, making all keys
   available as environment variables.

To check sync status:

```bash
kubectl get externalsecrets -n hub-production
kubectl describe externalsecret hub-secrets -n hub-production
```

A healthy ExternalSecret shows `SecretSynced` condition as `True`.

## Rotation Schedule

### Quarterly Rotation (Every 90 Days)

| Secret | Rotation Procedure |
|---|---|
| `SECRET_KEY` | Generate new key, update AWS SM, rolling restart (sessions invalidated) |
| `JWT_SECRET_KEY` | Generate new key, update AWS SM, rolling restart (active tokens invalidated) |
| `ENCRYPTION_KEY` | Requires data re-encryption migration -- coordinate with engineering |
| `POSTGRES_PASSWORD` | Update in RDS, update AWS SM, update PgBouncer userlist, rolling restart |
| `PGBOUNCER_ADMIN_PASSWORD` | Update in PgBouncer config, update AWS SM |
| `HUB_WORKER_API_KEY` | Regenerate via `manage.py create_api_key`, update AWS SM |
| `INTERNAL_API_KEY` | Update in AWS SM, rolling restart of all services |

### Annual Rotation

| Secret | Rotation Procedure |
|---|---|
| `STRIPE_SECRET_KEY` | Rotate in Stripe dashboard, update AWS SM |
| `STRIPE_WEBHOOK_SECRET` | Rotate webhook endpoint in Stripe, update AWS SM |
| `FUSEKI_ADMIN_PASSWORD` | Update Fuseki config, update AWS SM, restart StatefulSet |

### Rotation Steps

1. Generate the new secret value:
   ```bash
   # For random keys
   openssl rand -base64 32
   ```
2. Update the value in AWS Secrets Manager:
   ```bash
   aws secretsmanager update-secret \
     --secret-id production/hub/django \
     --secret-string '{"SECRET_KEY":"<new-value>","JWT_SECRET_KEY":"<existing>","ENCRYPTION_KEY":"<existing>"}'
   ```
3. Wait for ExternalSecrets to sync (up to 5 minutes) or force a sync:
   ```bash
   kubectl annotate externalsecret hub-secrets \
     force-sync=$(date +%s) -n hub-production --overwrite
   ```
4. Trigger a rolling restart so pods pick up the new Secret:
   ```bash
   kubectl rollout restart deploy/hub-api -n hub-production
   kubectl rollout restart deploy/hub-worker -n hub-production
   kubectl rollout restart deploy/hub-worker-heavy -n hub-production
   ```
5. Verify the deployment is healthy:
   ```bash
   curl -s https://apimeshant-internal.example.com/health/ | jq .
   ```

## Audit

### AWS CloudTrail

All access to AWS Secrets Manager is logged in CloudTrail. Key events to
monitor:

- `GetSecretValue` -- a pod or operator fetched a secret
- `UpdateSecret` -- a secret was rotated
- `DeleteSecret` -- a secret was removed (should trigger an alert)
- `CreateSecret` -- a new secret was provisioned

Filter CloudTrail logs for Secrets Manager events:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventSource,AttributeValue=secretsmanager.amazonaws.com \
  --start-time "2026-04-01" \
  --end-time "2026-04-09" \
  --query 'Events[].{Time:EventTime,Name:EventName,User:Username}'
```

### Kubernetes Audit

If the EKS cluster has audit logging enabled, Secret access events appear in
CloudWatch Logs under the `kube-apiserver-audit` log group. Look for:

- `get` or `list` operations on `secrets` resources
- `create` or `update` operations by the ExternalSecrets controller
- Any unexpected ServiceAccount accessing the `hub-secrets` Secret

### GitHub Actions Secrets

GitHub does not provide an API for secret access audit, but you can review:

- Workflow run logs (secrets are masked but usage is visible)
- Repository audit log (Settings > Audit log) for secret creation/deletion
  events

### Alerting on Secret Access Anomalies

Configure a CloudWatch Metric Filter on CloudTrail to alert when:

- `GetSecretValue` is called from an unexpected IAM role or source IP
- `DeleteSecret` is called (any invocation should be investigated)
- `UpdateSecret` is called outside of a scheduled rotation window
