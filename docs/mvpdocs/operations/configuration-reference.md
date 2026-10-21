# Configuration Reference

Complete reference for all environment variables and Helm values used by the
Meshant platform. Variables are grouped by concern. For secrets management
details see [Secrets Management](secrets-management.md).

**Security class legend**: `public` = safe to log/expose; `internal` = not
secret but should not be in client responses; `secret` = must be stored in
Secrets Manager and never committed to version control.

---

## Database

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `POSTGRES_HOST` | `postgres` | string | Yes | internal | PostgreSQL hostname. In production, set to `pgbouncer` when PgBouncer is enabled. |
| `POSTGRES_DIRECT_HOST` | `postgres` | string | No | internal | Direct PostgreSQL hostname, bypassing PgBouncer. Used by `pg_dump` and backup scripts (PgBouncer transaction mode is incompatible with `COPY`). |
| `POSTGRES_PORT` | `5432` | int | Yes | public | PostgreSQL port. |
| `POSTGRES_DB` | `hub` | string | Yes | public | Database name. |
| `POSTGRES_USER` | `hub` | string | Yes | internal | Database user. |
| `POSTGRES_PASSWORD` | -- | string | Yes | secret | Database password. Synced from AWS SM `<prefix>/postgres`. |
| `PGBOUNCER_ENABLED` | `false` | bool | No | public | When `true`, Django sets `CONN_MAX_AGE=0` (required for PgBouncer transaction pooling). Production/staging must set `true`. |
| `PGBOUNCER_PORT` | `5433` | int | No | public | PgBouncer listening port (local dev only; in K8s, PgBouncer listens on 5432 via its Service). |
| `PGBOUNCER_AUTH_PASSWORD` | -- | string | Yes (prod) | secret | Password for the `pgbouncer` auth_query role. |
| `PGBOUNCER_ADMIN_PASSWORD` | -- | string | Yes (prod) | secret | Password for the `pgbouncer_admin` role. |

## Redis

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | string | Yes | secret | Legacy fallback URL. Maps to `REDIS_CACHE_URL` in ExternalSecrets. |
| `REDIS_CACHE_URL` | -- | string | Yes (prod) | secret | Cache backend connection string (full URL with auth). |
| `REDIS_QUEUE_URL` | -- | string | Yes (prod) | secret | RQ job queue connection string. |
| `REDIS_EVENTS_URL` | -- | string | Yes (prod) | secret | Event pub/sub channel connection string. |
| `REDIS_CHANNELS_URL` | -- | string | Yes (prod) | secret | Django Channels layer connection string. |
| `REDIS_HOST` | `redis` | string | No | internal | Redis hostname (local dev only). |
| `REDIS_PORT` | `6379` | int | No | public | Redis port (local dev only). |

## Storage (S3 / MinIO)

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `AWS_STORAGE_BUCKET_NAME` | `hub-files` | string | Yes | internal | S3 bucket for user-uploaded files. Staging: `hub-files-staging-<account_id>`. |
| `AWS_S3_REGION_NAME` | `us-east-1` | string | No | public | AWS region for the S3 bucket. |
| `AWS_S3_ENDPOINT_URL` | -- | string | No | internal | S3 endpoint URL. Set for MinIO (`http://minio:9000`). Leave unset for real AWS S3 so presigned URLs resolve from browsers. |
| `AWS_S3_USE_SSL` | `true` | bool | No | public | Use HTTPS for S3 connections. |
| `AWS_S3_VERIFY` | `true` | bool | No | public | Verify S3 TLS certificates. |
| `USE_S3` | `false` | bool | No | public | When `true`, Django uses S3 as the default file storage backend. |
| `AWS_ACCESS_KEY_ID` | -- | string | No | secret | Static S3 credentials (MinIO/dev only). In staging/prod, IRSA provides S3 auth. |
| `AWS_SECRET_ACCESS_KEY` | -- | string | No | secret | Static S3 secret key (MinIO/dev only). |
| `AWS_DEFAULT_REGION` | `us-east-1` | string | No | public | Default AWS region for CLI operations. |

## Authentication & Security

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `SECRET_KEY` | -- | string | Yes | secret | Django signing key for CSRF tokens, sessions, and cookie signing. |
| `JWT_SECRET_KEY` | -- | string | Yes | secret | Key used to sign JWT access and refresh tokens. |
| `JWT_ALGORITHM` | `HS256` | string | No | public | JWT signing algorithm. |
| `JWT_ACCESS_TOKEN_EXPIRY` | `900` | int | No | public | Access token lifetime in seconds (15 min default; staging uses 7200). |
| `JWT_REFRESH_TOKEN_EXPIRY` | `604800` | int | No | public | Refresh token lifetime in seconds (7 days). |
| `JWT_ISSUER` | `hub` | string | No | public | JWT `iss` claim value. |
| `ENCRYPTION_KEY` | -- | string | Yes | secret | Fernet key for field-level encryption (SSO configs, API keys at rest). |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | string | Yes | public | Comma-separated list of allowed HTTP Host headers. Use `*` with caution (staging only). |
| `CORS_ALLOWED_ORIGINS` | -- | string | No | public | Comma-separated allowed CORS origins. |
| `SECURE_SSL_REDIRECT` | `False` | bool | No | public | Redirect all HTTP to HTTPS. Typically `False` in K8s (Ingress handles TLS). |
| `SECURE_HSTS_SECONDS` | `31536000` | int | No | public | HTTP Strict Transport Security max-age (1 year). |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | bool | No | public | Include subdomains in HSTS. |
| `SECURE_HSTS_PRELOAD` | `True` | bool | No | public | Enable HSTS preload list eligibility. |
| `SESSION_COOKIE_SECURE` | `True` | bool | No | public | Cookies only sent over HTTPS. |
| `CSRF_COOKIE_SECURE` | `True` | bool | No | public | CSRF cookie only sent over HTTPS. |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | bool | No | public | Send `X-Content-Type-Options: nosniff`. |
| `PII_REDACTION_ENABLED` | `true` | bool | No | public | Enable PII redaction in API responses and logs. |
| `GRAPHQL_QUERY_COMPLEXITY_LIMIT` | `1000` | int | No | public | Maximum allowed GraphQL query complexity score. |
| `RATE_LIMIT_E2E_RELAX` | `false` | bool | No | public | Relax rate limits for E2E test suites (staging only). |

## Feature Flags

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `FEATURE_TENANT_SWITCH_ENABLED` | `true` | bool | No | public | Enable tenant switching via `/auth/me/tenants/` and `X-Tenant-Id` header. |
| `PERSONAL_TENANT_ON_REGISTRATION` | `true` | bool | No | public | Auto-create a personal tenant for new users on registration. |
| `VITE_FEATURE_TOAST_ENABLED` | `true` | bool | No | public | Frontend: enable toast notifications (baked at build time). |
| `VITE_FEATURE_BREADCRUMBS_ENABLED` | `true` | bool | No | public | Frontend: enable breadcrumb navigation (baked at build time). |
| `VITE_FEATURE_RESOURCE_PICKERS_ENABLED` | `true` | bool | No | public | Frontend: enable resource picker components (baked at build time). |

## Microservices

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `DATACONTRACT_SERVICE_URL` | `http://datacontract-service:8080` | string | Yes | internal | DataContract validation service base URL. |
| `DQ_SERVICE_URL` | `http://dq-service:8083` | string | Yes | internal | Data Quality scanning service base URL. |
| `COMPLIANCE_SERVICE_URL` | `http://compliance-service:8082` | string | Yes | internal | Compliance (PII scanning, regulatory mapping) service base URL. |
| `SEMANTIC_SERVICE_URL` | `http://semantic-service:8081` | string | Yes | internal | Semantic (ontology, SPARQL) service base URL. |
| `PREFECT_INTEGRATION_SERVICE_URL` | `http://prefect-integration-service:8084` | string | No | internal | Prefect deployment sync service base URL. |
| `INTERNAL_API_KEY` | -- | string | Yes (prod) | secret | Shared key for service-to-service authentication. |
| `FUSEKI_URL` | `http://fuseki:3030` | string | Yes | internal | Apache Jena Fuseki SPARQL endpoint. |
| `FUSEKI_DATASET` | `hub` | string | Yes | public | Fuseki dataset name. |
| `FUSEKI_ADMIN_PASSWORD` | -- | string | Yes | secret | Fuseki admin API password. |

## Worker Configuration

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `HUB_BASE_URL` | `http://api-service:8000` | string | Yes | internal | Hub API base URL used by Prefect flow-run pods for callbacks. |
| `HUB_WORKER_API_KEY` | -- | string | Yes (prod) | secret | API key for Prefect workers to call Hub internal endpoints. Supports scopes: `scheduled_ingestion:internal`, `scheduled_export:internal`. |
| `SCHEDULED_EXPORT_WORKER_KEY` | -- | string | No | secret | Optional separate API key for export-only workers. |
| `WORKER_MAX_CONCURRENCY` | `16` (light) / `4` (heavy) | int | No | public | Maximum concurrent jobs per worker pod. Heavy workers use lower concurrency to avoid OOM from simultaneous DataFrames. |
| `WORKER_HEALTH_PORT` | `8080` | int | No | public | Port for the worker health-check HTTP server. |
| `COMPLIANCE_SCANNER_WORKERS` | `4` | int | No | public | Number of in-process async scanner threads in the compliance service. |
| `COMPLIANCE_WORKER_THREADS` | `4` | int | No | public | Thread pool size for CPU-bound PII detection in the compliance RQ worker. |
| `COMPLIANCE_POLL_MAX_SECONDS` | `300` | int | No | public | Maximum seconds to poll compliance scan status before fail-closed (staging: 600). |
| `COMPLIANCE_ENGINE_PATH` | `/app/compliance_engine` | string | No | internal | Path to the bundled compliance engine package in the worker image. |
| `HUBCONTRACT_BACKFILL_BATCH_SIZE` | `200` | int | No | public | Batch size for the `renormalize_contracts` backfill task. |

## Billing (Stripe)

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `STRIPE_SECRET_KEY` | -- | string | No | secret | Stripe API secret key (`sk_test_...` or `sk_live_...`). When unset, Stripe-dependent features are disabled. |
| `STRIPE_WEBHOOK_SECRET` | -- | string | No | secret | Stripe webhook signing secret (`whsec_...`) for `/api/v1/billing/webhooks/stripe/`. |
| `STRIPE_MARKETPLACE_WEBHOOK_SECRET` | -- | string | No | secret | Separate Stripe webhook endpoint for marketplace purchases. |

## Observability

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `ENVIRONMENT` | `development` | string | Yes | public | Deployment environment name. Used in logs, traces, and metrics. |
| `APP_VERSION` | `1.0.0` | string | No | public | Application version string. |
| `DEBUG` | `True` | bool | No | public | Django debug mode. Must be `False` in production. |
| `LOG_LEVEL` | `INFO` | string | No | public | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `SENTRY_DSN` | -- | string | No | secret | Sentry error tracking DSN. When unset, Sentry is disabled. |
| `OPENTELEMETRY_ENABLED` | `true` | bool | No | public | Enable OpenTelemetry distributed tracing. |
| `OPENTELEMETRY_METRICS_ENABLED` | `true` | bool | No | public | Enable OpenTelemetry metrics export. |
| `OTEL_SERVICE_NAME` | varies | string | No | public | Service name in traces (e.g., `hub-api`, `hub-worker-light`). |
| `JAEGER_AGENT_HOST` | `jaeger` | string | No | internal | Jaeger agent hostname for trace export. |
| `JAEGER_AGENT_PORT` | `6831` | int | No | public | Jaeger agent UDP port. |
| `GENERATE_SOURCEMAPS` | `false` | bool | No | public | Generate JavaScript source maps in frontend build. |

## MVP Mode

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `MVP_MODE` | `false` | bool | No | public | When `true`, gates access to post-MVP features. Staging sets this `true`; production sets `false`. Read-only at runtime; set via Helm `--set api.env.MVP_MODE=true`. |

## Django Core

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `hub.settings` | string | Yes | public | Python path to the Django settings module. |
| `APP_NAME` | `Meshant` | string | No | public | Product name used in UI, emails, OpenAPI schemas, and SDKs. |
| `AWS_SECRETS_ENABLED` | `true` | bool | No | public | When `true`, Django loads secrets from AWS Secrets Manager at startup. Set `false` in staging (ExternalSecrets handles sync). |
| `GUNICORN_WORKERS` | -- | int | No | public | Number of Gunicorn worker processes. Formula: `(2 * CPU) + 1`. Overridden by `api.gunicornWorkers` Helm value. |

## Data Contract Versions

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `ODCS_VERSIONS_SUPPORTED` | `2.2.2,3.0.0,3.0.1,3.0.2,3.1.0` | string | No | public | Comma-separated supported ODCS spec versions. |
| `ODPS_VERSIONS_SUPPORTED` | `1.x,2.x,3.x,4.0,4.1,4.2,bitol-0.9.0,bitol-1.0.0` | string | No | public | Comma-separated supported ODPS spec versions. |

## CKAN Integration

| Variable | Default | Type | Required | Security Class | Description |
|---|---|---|---|---|---|
| `CKAN_DADOS_GOV_BR_API_KEY` | -- | string | No | secret | API key for the Brazilian government data portal (dados.gov.br). |
| `CKAN_TEST_URL` | -- | string | No | internal | CKAN instance URL for integration tests. |
| `CKAN_TEST_API_KEY` | -- | string | No | secret | CKAN API key for test write operations. |

---

## Helm Values Reference

Below are the most important Helm values for operator configuration. The
canonical source is `helm/values.yaml`; environment overrides live in
`helm/values.staging.yaml`.

### Global

| Key | Default | Description |
|---|---|---|
| `global.environment` | `production` | Environment label applied to all resources. |
| `global.imageRegistry` | `""` | Container registry prefix (e.g., `registry.example.com/`). |
| `global.imagePullSecrets` | `[]` | List of image pull secret names. |
| `global.busyboxImage` | `busybox:1.36` | Busybox image for init containers. Staging overrides to ECR pull-through cache. |

### API Service

| Key | Default | Description |
|---|---|---|
| `api.replicaCount` | `3` | Initial replica count (HPA manages scaling). |
| `api.gunicornWorkers` | `9` | Gunicorn workers per pod. Formula: `(2 * vCPU) + 1`. |
| `api.resources.requests.cpu` | `500m` | CPU request per API pod. |
| `api.resources.requests.memory` | `1Gi` | Memory request per API pod. |
| `api.resources.limits.cpu` | `2000m` | CPU limit per API pod. |
| `api.resources.limits.memory` | `4Gi` | Memory limit per API pod. |
| `api.hpa.enabled` | `true` | Enable horizontal pod autoscaling. |
| `api.hpa.minReplicas` | `2` | Minimum API replicas. |
| `api.hpa.maxReplicas` | `10` | Maximum API replicas. |
| `api.hpa.targetCPUUtilizationPercentage` | `70` | CPU target for scale-out. |
| `api.hpa.rpsMetric.enabled` | `true` | Scale on requests-per-second (requires prometheus-adapter). |
| `api.hpa.rpsMetric.targetAverageValue` | `100` | RPS per pod before scale-out. |
| `api.pdb.enabled` | `true` | Enable PodDisruptionBudget. |
| `api.pdb.minAvailable` | `1` | Minimum available pods during voluntary disruptions. |

### Worker Light

| Key | Default | Description |
|---|---|---|
| `worker.replicaCount` | `3` | Initial replicas for light workers (short-lived, I/O-bound jobs). |
| `worker.maxConcurrency` | `16` | Max concurrent jobs per pod. |
| `worker.resources.requests.memory` | `512Mi` | Memory request. |
| `worker.resources.limits.memory` | `2Gi` | Memory limit. |
| `worker.hpa.minReplicas` | `2` | Minimum light worker replicas. |
| `worker.hpa.maxReplicas` | `6` | Maximum light worker replicas. |
| `worker.hpa.queueDepthMetric.threshold` | `100` | Combined `job_default`+`job_low` queue depth before scale-out. |

### Worker Heavy

| Key | Default | Description |
|---|---|---|
| `workerHeavy.replicaCount` | `1` | Initial replicas for heavy workers (DQ scans, compliance runs). |
| `workerHeavy.resources.requests.memory` | `1Gi` | Higher memory for pandas DataFrames. |
| `workerHeavy.resources.limits.memory` | `2Gi` | Memory limit. |
| `workerHeavy.hpa.minReplicas` | `1` | At least 1 warm pod to avoid cold-start delay. |
| `workerHeavy.hpa.maxReplicas` | `4` | Capped to avoid DB connection saturation. |
| `workerHeavy.hpa.queueDepthMetric.threshold` | `1` | Scale up as soon as any critical job is queued. |

### GPU Worker (Optional)

| Key | Default | Description |
|---|---|---|
| `gpuWorker.enabled` | `false` | Opt-in when GPU nodes are available. |
| `gpuWorker.resources.requests.nvidia.com/gpu` | `1` | GPU request per pod. |
| `gpuWorker.hpa.minReplicas` | `0` | Scale-to-zero when no training jobs are queued. |

### Inference Serving (Optional)

| Key | Default | Description |
|---|---|---|
| `inferenceServing.enabled` | `false` | Opt-in when GPU nodes and models are available. |
| `inferenceServing.hpa.minReplicas` | `0` | Scale-to-zero when no inference traffic. |

### Frontend

| Key | Default | Description |
|---|---|---|
| `frontend.replicaCount` | `2` | Nginx SPA replicas. |
| `frontend.resources.requests.memory` | `128Mi` | Memory request. |

### PgBouncer

| Key | Default | Description |
|---|---|---|
| `pgbouncer.enabled` | `true` | Enable the PgBouncer connection pooler. |
| `pgbouncer.config.poolMode` | `transaction` | Must be `transaction` for multi-worker Gunicorn. |
| `pgbouncer.config.maxClientConn` | `200` | Maximum client connections to PgBouncer. |
| `pgbouncer.config.defaultPoolSize` | `54` | Server connections per database. Formula: `api.replicas * gunicornWorkers * 2`. |

### Ingress

| Key | Default | Description |
|---|---|---|
| `ingress.enabled` | `true` | Enable Ingress resource creation. |
| `ingress.className` | `nginx` | Ingress class name. |
| `ingress.host` | `hub.example.com` | Frontend hostname. |
| `ingress.apiHost` | `api.hub.example.com` | API hostname. |
| `ingress.tls.enabled` | `true` | Enable TLS termination. |
| `ingress.tls.secretName` | `hub-tls` | Name of the TLS Secret. |
| `ingress.annotations` | -- | Nginx annotations for proxy body size (100m), timeouts, etc. |

### Backup

| Key | Default | Description |
|---|---|---|
| `backup.enabled` | `true` | Enable the daily PostgreSQL backup CronJob. |
| `backup.schedule` | `0 2 * * *` | Cron schedule (daily at 02:00 UTC). |
| `backup.env.BACKUP_S3_BUCKET` | `hub-postgres-backups` | S3 bucket for backup storage. |
| `backup.env.BACKUP_RETENTION_DAYS` | `30` | Days to retain backups before automatic deletion. |

### ExternalSecrets

| Key | Default | Description |
|---|---|---|
| `externalSecrets.enabled` | `true` | Enable the ExternalSecrets operator integration. |
| `externalSecrets.refreshInterval` | `5m` | How often the operator polls AWS Secrets Manager. |
| `externalSecrets.targetSecretName` | `hub-secrets` | Name of the K8s Secret created by the operator. |
| `externalSecrets.s3StaticCredentials` | `false` | Sync static S3 credentials (only for MinIO/dev). |
| `externalSecrets.stripe.enabled` | `false` | Sync Stripe secrets (enable when billing is active). |
| `externalSecrets.ckan.enabled` | `false` | Sync CKAN integration secrets. |

### Observability

| Key | Default | Description |
|---|---|---|
| `otel.endpoint` | `http://otel-collector:4317` | OpenTelemetry Collector gRPC endpoint. |

### Security

| Key | Default | Description |
|---|---|---|
| `podSecurityContext.runAsNonRoot` | `true` | All pods run as non-root. |
| `podSecurityContext.runAsUser` | `1000` | UID for all pod processes. |
| `containerSecurityContext.readOnlyRootFilesystem` | `true` | Read-only root FS; `/tmp` uses emptyDir. |
| `containerSecurityContext.capabilities.drop` | `["ALL"]` | Drop all Linux capabilities. |
| `cosign.enabled` | `false` | Enforce cosign image signature verification. Enable after confirming images are signed. |
