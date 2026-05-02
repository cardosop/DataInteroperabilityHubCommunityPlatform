# Runbook — Data Quality (Phase 240)

> **Audience**: oncall + platform engineering.
> **Phase**: 240 — DQ feature hardening (spec parity + operational readiness).
> **Last updated**: 2026-05-02.

This runbook covers operational tasks for the Data Quality feature:
alert response, capacity sizing, kill switches, and the
Helm-canonical configuration migration (Phase 240.1.D).  Each alert
defined in `monitoring/prometheus/alerts/dq.yml` has a matching
anchor below — when the alert fires, the `runbook_url` annotation routes
oncall here.

---

## Service-level objectives (Phase 240.5.B.3)

The DQ feature is governed by three SLOs. Breaches trigger the
matching alert (anchored later in this document) and oncall
escalation per the on-call rotation.

| # | SLO | Target | Measurement window | Source / alert |
| - | --- | ------ | ------------------- | -------------- |
| 1 | **DQ run success rate** | ≥ 99 % | rolling 15 min | `sum(rate(dq_runs_total{status="success"}[15m])) / sum(rate(dq_runs_total[15m]))` — alert: [`DQRunFailureRateHigh`](#dq-run-failure-rate-high) |
| 2 | **DQ run latency p95** | < 5 min wall-clock | rolling 1 h | `histogram_quantile(0.95, rate(dq_run_duration_seconds_bucket[1h]))` — alert: [`DQRunDurationP95Regression`](#dq-run-duration-p95-regression) |
| 3 | **Alert delivery success rate** | ≥ 99.9 % | rolling 1 h | `sum(rate(dq_alert_delivery_total{outcome="delivered"}[1h])) / sum(rate(dq_alert_delivery_total[1h]))` — alert: [`DQAlertDeliveryFailing`](#dq-alert-delivery-failing) |

**Why these three:** they cover the three distinct failure modes
that make the feature unusable to a tenant — runs failing
outright (SLO #1), runs taking so long they break upstream job
SLAs (SLO #2), and alerts firing but not reaching the recipient
(SLO #3 — silent failure is the worst kind for an alerting
product). A breach of any one MUST page oncall.

---

## Quick reference

| Key | Value |
| --- | ----- |
| **API endpoints** | `POST /api/v1/dq/run` (HTTP-signed by hub via `INTERNAL_API_KEY`) |
| **Helm chart** | `helm/templates/dq-service/` (canonical — Kustomize tree decommissioned in 240.1.D.7) |
| **Image** | `ghcr.io/{org}/hub-dq-service` (built from `services/dq-service/Dockerfile`) |
| **AWS SM secrets** | `{secretsPrefix}/api` (INTERNAL_API_KEY) + `{secretsPrefix}/dq-service` (INTERNAL_PAYLOAD_SECRET) |
| **Per-tenant flag** | n/a — gating is via the existing Tenant plan limits (`max_dq_runs_per_month`) |
| **Replicas** | 1 in production, 2 in staging (`dqService.replicas` in `helm/values.staging.yaml`) |
| **PDB** | `minAvailable: 1` (`dqService.pdb`) |

---

## Alert anchors

The Prometheus rules in [monitoring/prometheus/alerts/dq.yml](../../monitoring/prometheus/alerts/dq.yml) annotate `runbook: docs/runbooks/data-quality.md#<anchor>` — anchors below correspond 1:1 with rule names.

### dq-run-failure-rate-high

**Alert**: `DQRunFailureRateHigh` — `>5%` failure rate over 15m.

**Likely cause**: dq-service regression, profile mis-configuration, or a tenant-side bad-data wave.

**Triage**:

```promql
# Top failing tenants
sum(rate(dq_runs_total{status="FAIL"}[5m])) by (tenant_id, engine)
# Per-engine breakdown
sum(rate(dq_runs_total{status="FAIL"}[5m])) by (engine)
```

If a single tenant dominates → contact the tenant + check their recent intake job for upstream schema drift. If multiple tenants → check recent dq-service deploys (`kubectl rollout history`) and consider rolling back.

### dq-run-duration-p95-regression

**Alert**: `DQRunDurationP95Regression` — p95 > 2× 7d-baseline for 15m.

**Likely cause**: dataset shape change (row-count growth), profile change, or dq-service node saturation.

**Triage**: pivot the Grafana board's "Per-engine duration histogram" panel to the affected engine; correlate with the `dq_async_queue_depth` panel (queue building means workers are saturated, not slow).

### dq-service-circuit-open

**Alert**: `DQServiceCircuitOpen` — `circuit_breaker_state{service="dq-service"} == 2` for 5m. **Severity: critical**.

**Likely cause**: dq-service pods unhealthy, network partition, or a recent bad deploy.

**Triage**:

1. `kubectl get pods -l app.kubernetes.io/component=dq-service` — confirm at least 1 pod is `Ready`.
2. `kubectl logs -l app.kubernetes.io/component=dq-service --tail=200` — look for OOMKill, panic, or auth failures.
3. Check `kubectl rollout history deployment/<release>-dq-service` — was there a recent deploy?

Roll back: `kubectl rollout undo deployment/<release>-dq-service`.

### dq-alert-delivery-failing

**Alert**: `DQAlertDeliveryFailing` — `>10%` of alert deliveries failing over 30m. **Severity: critical**.

**Likely cause**: delivery-channel credential expiry (SES quota, Slack token revoked, PagerDuty service-key rotation), or a bug in the delivery client.

**Triage**: pivot the Grafana board's "DQ alert rule firing count by channel" panel to confirm WHICH channel is failing. Then check the matching audit-event stream:

```sql
SELECT details_json->>'channel' AS channel,
       COUNT(*) AS fails,
       array_agg(DISTINCT details_json->>'error') AS recent_errors
FROM audit_events
WHERE action = 'DQ_ALERT_FAILED'
  AND timestamp > NOW() - INTERVAL '30 minutes'
GROUP BY channel;
```

### dq-engine-success-rate-drop

**Alert**: `DQEngineSuccessRateDrop` — `min by (engine)(dq_success_rate) < 0.9` for 1h.

**Likely cause**: engine adapter has a systemic problem (deps drift, profile bug, OOM).

**Triage**: check `kubectl logs -l app.kubernetes.io/component=dq-service` for `adapter_execute_failed`; pivot `rate(dq_runs_total{status="FAIL", engine="<engine>"}[1h])` by `profile_key`.

### dq-run-queue-depth

**Alert**: `DQRunQueueDepth` — `max(dq_async_queue_depth) > 100` for 30m.

**Likely cause**: workers under-scaled for current load OR stuck individual runs.

**Triage**:

1. Check the worker HPA: `kubectl get hpa -l app.kubernetes.io/component=worker`.
2. If `currentReplicas == maxReplicas`, bump `worker.hpa.maxReplicas` in `helm/values.<env>.yaml`.
3. If runs are stuck, the existing `recover-stuck-jobs` CronJob marks them FAILED after the threshold (default 120 min); check its last run.

### dq-audit-write-failing

**Alert**: `DQAuditWriteFailing` — `>1/min` audit-write errors for 5m. **Severity: critical**.

**Likely cause**: DB connection-pool exhaustion, a migration in flight, or transient network errors.

**Triage**:

1. `kubectl logs -l app.kubernetes.io/component=api --tail=200 | grep dq_audit_write_failed` — confirm the error class.
2. Check `pg_stat_activity` for connection saturation.
3. Compliance evidence is at risk while this fires — escalate to platform-security if it stays critical for >15m.

### dq-s3-payload-growth-anomaly

**Alert**: `DQS3PayloadGrowthAnomaly` — per-tenant S3 payload bytes >2σ above 7d baseline for 1h.

**Likely cause**: a profile that snapshots full datasets, a runaway ingestion, or stuck retention cleanup.

**Triage**: pivot the Grafana board's "S3 payload-bucket size trend" panel to the offending tenant. Cross-reference with their recent `dq_runs_total` rate. If the 240.1.C retention cleanup CronJob (`purge_dq_runs`) is failing, the soft-deleted rows accumulate.

---

## Phase 240.1.D — Helm-canonical configuration migration

The `k8s/dq-service/` Kustomize tree was deleted in Phase 240.1.D.7. **Helm is now the single source of truth for dq-service configuration**. This section documents the parity-check that gated the deletion.

### Parity-check procedure (one-shot, performed during 240.1.D rollout)

The procedure below verifies that a Helm-only deploy produces a functionally equivalent dq-service Deployment to the prior Kustomize-based one. Run on staging only.

**Pre-conditions**:

- `helm/values.yaml` `dqService.config` block contains every key from the prior `k8s/dq-service/base/configmap.yaml`.
- `helm/templates/dq-service/configmap.yaml` exists and renders.
- `helm/templates/dq-service/external-secret.yaml` exists and the AWS SM secrets at `{secretsPrefix}/api` + `{secretsPrefix}/dq-service` are populated.
- `helm/templates/dq-service/poddisruptionbudget.yaml` exists.

**Steps**:

1. **Helm template diff** — generate the Helm-rendered manifest set:
   ```bash
   helm template hub helm/ -f helm/values.staging.yaml \
       --show-only templates/dq-service > /tmp/helm-rendered.yaml
   ```
   Inspect for: ConfigMap with all 5 keys, ExternalSecret with both keys, Deployment using `envFrom.configMapRef` + `envFrom.secretRef`, PDB with `minAvailable: 1`.

2. **Deploy to staging** — `helm upgrade --install hub helm/ -f helm/values.staging.yaml`.

3. **Smoke test** — confirm the dq-service pods come up healthy:
   ```bash
   kubectl get pods -l app.kubernetes.io/component=dq-service
   kubectl exec -it <api-pod> -- python manage.py check_dq_service_health
   ```
   The check confirms the api-service can authenticate to dq-service via `INTERNAL_API_KEY` and run a trivial profile.

4. **Smoke test (run path)** — submit a tiny CSV to `/api/v1/dq/run`; assert HTTP 200 with `overall_status` populated.

5. **Audit-row verification** — confirm `SEMANTIC_*` and `DQ_*` audit rows are written to the audit-events table.

6. **Rollback dry-run** — `helm rollback hub <previous-revision> --dry-run` then re-apply the current revision. Confirms the chart is rollback-safe.

**Pass criteria**: all 6 steps complete without error; the dq-service Deployment in staging shows `READY 2/2` and `dq_runs_total{status="success"}` increments after the run-path smoke test.

**On failure**: do NOT proceed with the `k8s/dq-service/` deletion. Diagnose the gap (most likely an env var missing from `dqService.config`), patch values.yaml, and re-run from step 2.

### Migration history

| Step | When | Result |
| ---- | ---- | ------ |
| Helm chart authored | Phase 240.1.D.1–.4 | Configmap, ExternalSecret, PDB templates added; values.yaml `dqService.config` block migrated from `k8s/dq-service/base/configmap.yaml` verbatim |
| Staging replicas bumped | Phase 240.1.D.2 | `dqService.replicas: 2` + RollingUpdate strategy in `helm/values.staging.yaml` |
| Parity-check executed | Phase 240.1.D.6 | Recorded in PR description; smoke + rollback dry-run passed |
| Kustomize tree deleted | Phase 240.1.D.7 | `git rm -r k8s/dq-service/` |
| CI re-introduction guard | Phase 240.1.D.8 | `.github/workflows/no-kustomize-dq.yml` workflow rejects PRs that re-add `k8s/dq-service/` |

### Deliberate Kustomize divergence — public Ingress NOT reproduced

The deleted Kustomize tree (`k8s/dq-service/base/ingress.yaml`) defined a public Ingress at `dq.example.com` with cert-manager-issued TLS. **The Helm chart deliberately does NOT reproduce this** — and that is the correct, security-hardened state:

1. dq-service is an internal-only microservice. The api-service calls it intra-cluster at `http://dq-service:8083` (set via the `DQ_SERVICE_URL` env var on the api Deployment in `helm/values.yaml`).
2. Auth is enforced by `InternalApiKeyMiddleware` reading `INTERNAL_API_KEY` from env at module-import time (`services/shared/auth.py:53`). Public Ingress would expose the dq-service to the internet behind only an HTTP-header check — not the auth posture for a microservice that processes potentially-sensitive customer data.
3. The Kustomize ingress used `dq.example.com` — a placeholder hostname that was almost certainly never wired to a DNS record, suggesting it was vestigial template code rather than an active production endpoint.

If a future use case legitimately requires public dq-service exposure (e.g. partner-facing DQ-as-a-service tier), it MUST go through the api-gateway with mTLS + OAuth2, NOT a direct Ingress to `dq-service`.

---

## Phase 240.2.C — Distributed tracing across hub → dq-service

The dq-service is wired to OpenTelemetry per Phase 240.2.C.  Every request that crosses the hub → dq-service boundary produces a single connected trace in Tempo / Jaeger:

### Expected span tree

```text
parent_trace
└── Job: <queue_job_name>                      (hub api worker)
    └── DQService.create_dq_run                (hub.apps.dq.services.DQService)
        └── HTTP POST /run                     (httpx client, instrumented)
            ├── (network)                      (W3C traceparent header propagates)
            └── POST /run                      (dq-service FastAPI span,
                │                                FastAPIInstrumentor extracts
                │                                the inbound traceparent as parent)
                └── execute_profile             (custom span — dq-service main.py)
                    │                            attributes:
                    │                              dq.profile_key
                    │                              dq.engine
                    │                              dq.custom_check_count
                    │                              dq.total_rows
                    │                              dq.total_columns
                    └── (gx_adapter internals)
```

### Tempo query

```promql
{ service.name = "dq-service" } | trace.resource.service.version
```

filter further with the FastAPI span name (`POST /run`) or the custom `execute_profile` child span.

### W3C TraceContext propagation contract (D240.13)

- **Hub side** — `HTTPXClientInstrumentor` (already wired in [hub/apps/observability/otel_config.py](../../hub/apps/observability/otel_config.py)) auto-injects `traceparent` + `tracestate` headers on every outbound request from `httpx.Client` (which `DQServiceClient` uses).
- **dq-service side** — `FastAPIInstrumentor` (wired in [services/dq-service/main.py](../../services/dq-service/main.py) via `instrument_app(app)`) extracts those headers from the incoming request and materialises them as the parent SpanContext for every span emitted within the request's lifetime.
- **Verification** — pin via `services/dq-service/tests/test_tracing.py::test_default_propagator_understands_traceparent`. Production verification: query Tempo for a known trace id; the result tree should span both the hub api span (`service.name=hub-api`) and the dq-service span (`service.name=dq-service`) connected by the `traceparent` header.

### OTLP exporter

- **Endpoint**: `OTEL_EXPORTER_OTLP_ENDPOINT` env var (default `http://otel-collector:4317`).  Provisioned cluster-wide per Phase 4 (the same collector that receives api-service / semantic-service / compliance-service traces).
- **Protocol**: gRPC (`opentelemetry-exporter-otlp-proto-grpc`).
- **Sampling**: 100% in non-prod, 10% in production (via `TraceIdRatioBased`).  Override via `OTEL_TRACES_SAMPLER_ARG` env var.
- **Service name**: `dq-service` (fixed — Tempo / Jaeger queries depend on this exact value).

### Kill switch

Disable tracing without redeploy by flipping `OPENTELEMETRY_ENABLED=false` on the dq-service Deployment.  `setup_tracing()` checks the env var on every startup; `instrument_app()` checks it before wiring the FastAPI instrumentation.  No spans flow when the flag is false — useful when the otel-collector is in maintenance and exporter-side errors would otherwise spam the dq-service logs.

---

## Capacity sizing

| Resource | Default | Staging override |
| -------- | ------- | ---------------- |
| Replicas | 1 | 2 |
| CPU request | 100m | 100m |
| CPU limit | 500m | 500m |
| Mem request | 128Mi | 256Mi |
| Mem limit | 512Mi | 1Gi |
| HPA | not yet configured | not yet configured |

Phase 240.5 capacity work will add HPA + production replica bump based on observed P95 latency + queue depth.

---

## Kill switches

### Per-tenant — disable DQ runs

Today there is no per-tenant `Tenant.dq_enabled` flag (Phase 240 doesn't introduce one — DQ is a foundational platform feature, not an opt-in like federation/LDN/GraphQL-LD). To stop runs for a single tenant:

```python
# Drop their plan's monthly DQ-runs limit to 0 — the existing
# enforcement in hub.apps.dq.business_rules will reject new runs.
from hub.apps.tenants.models import Tenant, TenantPlan
t = Tenant.objects.get(slug="<tenant_slug>")
t.plan.limits_json["max_dq_runs_per_month"] = 0
t.plan.save(update_fields=["limits_json"])
```

### Cluster-wide — pause dq-service

Scale the Deployment to 0 replicas; the api-service circuit breaker opens within ~1 minute and queries return the documented fallback (`overall_status: "UNKNOWN"`):

```bash
kubectl scale deployment/<release>-dq-service --replicas=0
```

The `DQServiceCircuitOpen` alert fires on the next 5-minute eval. Restore by bumping replicas back.

---

## Retention & cleanup (Phase 240.1.C)

DQ runs accumulate row + S3-payload state per tenant. Two layers of cleanup, both running every day independently.

### Layer 1 — `purge_dq_runs` management command

Two-phase sweep, runs daily at **03:00 UTC** via the [`purge-dq-runs` Kubernetes CronJob](../../helm/templates/cronjob/purge-dq-runs.yaml):

1. **Soft-delete** — `DQRun` rows older than `tenant.dq_run_retention_days` (per-tenant; default 90, bounded `[7, 365]` per D240.7) are flagged `is_deleted=True`. Default manager hides them immediately; API surface area sees zero behavioural change.
2. **Hard-delete** — Soft-deleted rows whose `deleted_at < now() - 30d` (the fixed grace window) are removed from the DB **and** their `s3://<DQ_S3_BUCKET>/<DQ_S3_PREFIX>{run_id}/` payload prefix is wiped via [`S3StorageClient.delete_prefix`](../../hub/apps/files/storage.py).

Each phase emits a `DQ_RUN_PURGED` audit row per batch (`details_json={phase, tenant_id, count, dry_run, batch}`). The auditor can reconstruct retention timelines without log scraping.

### Dry-run safety net (D240.16)

For the **first 7 days post-deploy** the CronJob runs in dry-run mode. The Helm value `purgeDqRuns.dryRun: true` (default) sets the env var `DQ_PURGE_DRY_RUN=1` in the pod, which forces the command to report counts without mutating, regardless of CLI flags. Operators flip to `false` once confident the retention math is correct.

### Manual invocation

```bash
# Dry-run (default — reports what WOULD be purged):
docker compose exec api-service python manage.py purge_dq_runs --dry-run

# Override the env-var safety net for a real run:
docker compose exec api-service python manage.py purge_dq_runs --no-dry-run

# Single-tenant (incident response):
docker compose exec api-service python manage.py purge_dq_runs \
  --tenant-id <uuid> --no-dry-run

# Smaller batches for a tenant with very long row history:
docker compose exec api-service python manage.py purge_dq_runs \
  --batch-size 100 --no-dry-run
```

### Adjusting per-tenant retention

```python
from hub.apps.tenants.models import Tenant
t = Tenant.objects.get(slug="<tenant_slug>")
t.dq_run_retention_days = 30  # bound: [7, 365]
t.save(update_fields=["dq_run_retention_days"])
```

The next nightly purge sweep enforces the new value. To force-run immediately:

```bash
docker compose exec api-service python manage.py purge_dq_runs \
  --tenant-id <tenant_uuid> --no-dry-run
```

### Layer 2 — S3 lifecycle policy

The [`hub-dq-payloads-{env}` bucket](../../infrastructure/terraform/modules/s3-buckets/dq_payloads.tf) has a Terraform-managed lifecycle policy as a defense-in-depth floor:

- **Expire raw uploads after 14 days** — even if `purge_dq_runs` is disabled or fails, no DQ payload object lingers past two weeks.
- **Abort multipart uploads >24h** — incomplete uploads are reaped automatically.

The application-level purge runs first (per-tenant retention + soft-delete grace), so in steady state the lifecycle rule sees nothing to do — it's the safety net for an operator turning off the CronJob without realising the implication.

### Verifying retention is working

```bash
# Count soft-deleted rows by tenant (should match the daily purge audit)
docker compose exec postgres psql -U hub -d hub -c "
  SELECT tenant_id, COUNT(*) FROM dq_runs
  WHERE is_deleted = TRUE GROUP BY tenant_id;"

# Inspect the day's purge audit rows
docker compose exec api-service python manage.py shell -c "
from hub.apps.audit.models import AuditEvent
from datetime import timedelta
from django.utils import timezone
for e in AuditEvent.objects.filter(
    action='DQ_RUN_PURGED',
    timestamp__gte=timezone.now() - timedelta(days=1),
).order_by('-timestamp')[:20]:
    print(e.timestamp, e.details_json)
"
```

### When retention enforcement is causing trouble

If a tenant complains rows are disappearing too aggressively:

1. Check `tenant.dq_run_retention_days` — may have been set too low.
2. The hard-delete grace is **fixed at 30 days** in the source (`HARD_DELETE_GRACE_DAYS`); soft-deleted rows are still in the DB and queryable via `DQRun.all_objects` for that window.
3. After 30 days the row is gone permanently — no recovery short of pg_dump restore.

---

## Configurable thresholds (Phase 240.3.D)

The dq-service enforces two operational caps on every `/run` request,
both resolvable per-tenant with a Helm-baked default fallback (D240.15):

| Cap | Default (env) | Per-tenant override (Tenant column) | Bounds |
| --- | ------------- | ------------------------------------ | ------ |
| Input upload byte size | `DQ_INPUT_TOO_LARGE_BYTES` (500 MiB) | `Tenant.dq_input_max_bytes` | [10 MiB, 5 GiB] |
| Sampling threshold (rows) | `DQ_SAMPLING_THRESHOLD_ROWS` (1 M) | `Tenant.dq_sampling_threshold_rows` | [10 000, 100 000 000] |

### Wire-up

api-side `DQServiceClient.run_dq(...)` accepts an optional `tenant_id`
argument. When supplied AND the tenant has a non-NULL override, the
client forwards it as a header to dq-service:

- `X-Tenant-Threshold-Bytes: <int>` — input cap
- `X-Tenant-Threshold-Rows: <int>` — sampling threshold

The dq-service `/run` handler resolves each header via
`_resolve_input_max_bytes(...)` / `_resolve_sampling_threshold_rows(...)`,
both at module scope in `services/dq-service/main.py`. Resolution
order: header → env var → hard-coded default. Malformed header values
fall through to the env / default silently.

### Oversize uploads → 413

When `len(content) > limit_bytes` the handler raises:

```json
HTTP/1.1 413 Payload Too Large
{
  "detail": {
    "error_code": "DQ_INPUT_TOO_LARGE",
    "limit_bytes": <int>,
    "received_bytes": <int>
  }
}
```

The `error_code` field is stable — api-side callers parse this rather
than the human message so end-user messaging can localise around it.
The byte count returned is post-`await file.read()`, before any parse
attempt — pandas never sees the body.

### Deterministic sampling above threshold

When the parsed DataFrame has more rows than the resolved threshold,
`_deterministic_sample(df, threshold=...)` produces a stable subset.
The algorithm:

1. Compute `n_buckets = max(1, len(df) // threshold)` — so the
   expected sample size is the threshold (within bucket variance).
2. For each row, compute `int(sha256(row_pk).hexdigest(), 16) % n_buckets`.
3. Keep rows whose bucket equals `0`.

**Row identity (`row_pk`)** is derived in priority order:

- the value of any column whose name is `id` or ends in `_id`,
  `_pk`, `_uuid` (canonical primary-key candidates), OR
- the row's positional index (fallback — stable for a given input
  frame but breaks if the frame is re-ordered upstream).

### Why SHA-256 modulo (not random)

`random.sample()` would draw a different sample each call, breaking:

- **Re-run reproducibility** — auditors must be able to re-run a DQ
  run weeks later and see the same per-row check results.
- **Checksum cache hits** — the cache key in
  `hub.apps.dq.service_client.DQServiceClient.run_dq` is keyed on
  `sha256(file_content)`; identical input must produce identical
  output. A random sampler invalidates that.
- **Cross-run diff** — comparing two runs over the same dataset
  must surface only data drift, not sample drift.

SHA-256 modulo gives us all three for free.

### Operator playbook

**Symptom: tenant complains an upload was rejected with 413.**

1. Check the alert / log line — the dq-service emits
   `event=dq_run_completed outcome=client_error` with the response
   `detail.error_code=DQ_INPUT_TOO_LARGE`.
2. Inspect `tenant.dq_input_max_bytes` — `NULL` means the global
   default (500 MiB) applied.
3. If the tenant's plan warrants a larger cap, raise
   `dq_input_max_bytes` in the admin (bound: 10 MiB to 5 GiB). The
   change is picked up on the next request — no restart needed.

**Symptom: tenant complains DQ scores swing run-to-run on the same
file.**

1. Check the row count vs the resolved threshold. If sampling kicked
   in but the source CSV has no canonical PK column (`id`, `*_id`,
   `*_pk`, `*_uuid`), the index-based fallback is used — and the
   index is unstable if the upload pipeline re-orders rows.
2. Fix: surface a stable PK in the source data, OR raise the
   threshold so the entire dataset fits below it (bound: 10 000 to
   100 000 000 rows).

---

## Billing event emission (Phase 240.5.A)

Every successful DQ run emits a `billing.dq.run.completed` event on
the platform event bus. The event powers downstream usage metering
(Stripe metering, internal aggregation, finance reconciliation) and
is also forwarded to tenant-configured webhooks subscribed to the
`BILLING_DQ_RUN_COMPLETED` type.

### Wire constants

| Where | Value |
| --- | --- |
| Event type string | `billing.dq.run.completed` |
| Python constant | `hub.apps.billing.event_types.DQ_RUN_COMPLETED` |
| Webhook enum | `hub.apps.webhooks.models.WebhookEventType.BILLING_DQ_RUN_COMPLETED` |
| Producer site | [hub/apps/dq/views.py](../../hub/apps/dq/views.py) `execute_dq_run` (post-`SUCCEEDED` save) |
| Emitter helper | `hub.apps.billing.events.emit_event` |

### Payload shape

Matches the spec — seven keys, JSON-serialisable:

```json
{
  "tenant_id":              "<UUID-string>",
  "dq_run_id":              "<UUID-string>",
  "engine":                 "GX",
  "rows_inspected":         100,
  "columns_inspected":      4,
  "execution_time_seconds": 0.42,
  "quality_score":          99.5
}
```

### Emit semantics

- Fires **exactly once per `SUCCEEDED` DQ run.** Failed runs do NOT
  emit — failed runs are not billable per spec.
- **Best-effort.** A Redis outage, serialisation error, or any
  unexpected exception inside the bus is caught at the emit-helper
  layer (`hub.apps.billing.events.emit_event`); a `None` is returned
  and a `billing_event_emit_failed` log line is written at WARN. The
  DQ pipeline continues regardless — billing is observability, not
  load-bearing.
- An outer guard in the producer catches the (otherwise unreachable)
  case where the import path itself breaks (e.g., a circular-import
  regression). The guard logs `billing_emit_outer_guard_tripped` with
  `error` + `error_type` fields for one-line root-cause triage.
- Bus-level deduplication is keyed on `(event_type, payload)`. Since
  `dq_run_id` is unique per run, retries of `execute_dq_run` for the
  same row would dedup at the bus and return the same event ID — so
  downstream subscribers can't double-bill even if the producer is
  invoked twice.

### Billing event triage

| Symptom | Where to look |
| --- | --- |
| Billing system reports missing DQ usage | Check `dq_runs_total{status="success"}` Prometheus counter for the period vs. event-bus delivery count. Drift indicates `emit_event` returned `None` (Redis/bus outage); search logs for `billing_event_emit_failed`. |
| `billing_emit_outer_guard_tripped` warning fires | Indicates a regression in the import path (`hub.apps.billing.event_types` or `hub.apps.billing.events`). Check for circular imports introduced in a recent diff; the warning's `error_type` field names the exception class. |
| Tenant-configured webhook for `billing.dq.run.completed` not delivering | (1) Confirm the webhook subscribes to `BILLING_DQ_RUN_COMPLETED` (enum value, not the legacy frontend `DQ_RUN_COMPLETED` analytics constant). (2) Check `WebhookDelivery` table for the tenant's recent attempts. (3) The `webhook_subscriber` service consumes from the bus and dispatches; check its logs for delivery errors. |
| Need to replay a missed event | The DQRun row in PostgreSQL is the source of truth (`dq_run.details_json["metering"]` carries the same fields). A replay tool can read the row and call `emit_event` directly — the bus dedup will accept it because the original emit returned `None`. |

---

## Engine selection — Soda vs Great Expectations (Phase 240.5.B.3)

The DQ pipeline supports two execution engines. Choose per
`profile_key` (the tenant's selected DQ profile pins the engine).

### When to use Great Expectations (GX) — the default

- **Tabular CSV / Parquet / JSON** with a fixed schema and
  rule-based checks (column not null, regex match, range,
  uniqueness, foreign-key existence).
- **Standard tenants** running the canonical `intake_basic_gx`
  profile or any custom profile that doesn't need SQL-engine
  semantics. GX evaluates expectations row-by-row in pandas; the
  per-check overhead is low.
- **Default fallback** — if a profile_key doesn't end in
  `_soda`, the dispatcher routes to GX (see
  [`services/dq-service/dispatcher.py`](../../services/dq-service/dispatcher.py)
  `get_adapter_for_profile`).

### When to use Soda

- **SQL-native checks** that benefit from dask-sql's query
  planner — for example aggregate constraints
  (`row_count > 1000`), distribution checks
  (`group_by` + `having`), or any expression that's awkward to
  encode as a per-row GX expectation.
- **Profiles ending in `_soda` suffix** — the dispatcher routes
  these to `SodaAdapter`. The dq-service runs Soda atop dask-sql
  in a single worker; there's no Spark/Snowflake fan-out.
- **Caveat** — Soda can't aggregate object/string columns
  through dask-sql without a manual `category` dtype coercion
  (see Phase 240.3.A.5 audit fixes). The adapter does the
  coercion automatically; if you see weird `dask-sql` errors on
  string-only columns, check the adapter's coercion path didn't
  regress.

### Engine selection cannot be changed mid-run

The engine is pinned at profile-resolve time. A custom profile
that swaps engines mid-checks will fail validation; the only
clean migration path is to register a new `_soda` profile and
have tenants opt in.

### Sampling threshold tuning

Both engines respect the
[`DQ_SAMPLING_THRESHOLD_ROWS`](#configurable-thresholds-phase-2403d)
threshold and use the same SHA-256 modulo deterministic sampler.
Sampling decisions happen in dq-service BEFORE adapter dispatch,
so the engine sees a row count ≤ threshold. Per-tenant overrides
via `Tenant.dq_sampling_threshold_rows` apply uniformly to both
engines — there's no engine-specific tuning knob.

**When to lower the threshold**: tenants reporting OOM-like dq-service
restarts on large CSV uploads. The default is 1 M rows. Going
below 100 K starts producing unstable quality scores (sample
variance dominates).

**When to raise it**: tenants needing exhaustive checks on
moderately large datasets (e.g. nightly compliance scans).
Raising past 10 M rows requires bumping
[capacity sizing](#capacity-sizing) — pandas frames > 10 M rows
exceed the dq-service worker's default memory budget.

---

## Common failure modes (Phase 240.5.B.3)

Three failure modes account for ~90 % of DQ run failures
historically. Each has a deterministic recovery path.

### Memory exhaustion (OOM)

#### OOM symptoms

- `kubectl get pods -n hub-prod -l app=dq-service` shows pods in
  `OOMKilled` state.
- `dq_runs_total{status="error"}` rate spikes; affected runs are
  in `FAILED` status with `details_json.error` containing
  `"MemoryError"` or process-killed exit code.
- Grafana "DQ run duration p95" panel shows a long tail of runs
  exceeding the 5-minute SLO before timing out.

#### OOM root cause

Pandas frame size > worker memory budget. The canonical
dq-service pod requests 2 GiB memory; a 10 M-row CSV with 50
columns easily blows past that during pandas parse.

#### OOM recovery

1. Confirm sampling kicked in for the tenant: search dq-service
   logs for `dq_input_sampled` events with the tenant's most
   recent run ID. If absent, the row count was below threshold
   and the full frame was loaded.
2. Lower the tenant's `Tenant.dq_sampling_threshold_rows` via
   admin (or set the platform default
   `DQ_SAMPLING_THRESHOLD_ROWS` in
   [`helm/values.yaml`](../../helm/values.yaml)).
3. Restart the dq-service pods if any are stuck in OOMKilled
   loops: `kubectl rollout restart deploy/dq-service -n hub-prod`.
4. Backfill the failed runs by re-triggering the originating
   ingestion / scheduled scan.

### S3 ACL / permission issues

#### S3 ACL symptoms

- `details_json.error` contains `"AccessDenied"` or
  `"NoSuchBucket"`.
- `dq_runs_total{status="error"}` correlates with a recent
  Terraform apply on the [DQ payloads
  bucket](../../infrastructure/terraform/modules/s3-buckets/dq_payloads.tf).

#### S3 ACL root cause

The dq-service IAM role lost s3:GetObject / s3:HeadObject on the
configured bucket. Common after a bucket-policy reshuffle or ACL
tightening.

#### S3 ACL recovery

1. Validate the current role: `aws iam simulate-principal-policy`
   with the `dq-service` role and the failing object key.
2. Re-apply the Terraform module if the policy drifted.
3. Confirm the SSE-KMS key the bucket uses still grants the role
   `kms:Decrypt` — bucket access without KMS access shows up as
   `AccessDenied` even when the IAM policy looks correct.

### Schema mismatch

#### Schema mismatch symptoms

- `details_json.error` contains `"KeyError"` or
  `"unexpected column"`.
- DQ runs against a specific asset/dataset suddenly start
  failing while runs against other assets stay green.

#### Schema mismatch root cause

The source data's schema diverged from the DQ profile's
expectations. A column was renamed / removed upstream and the
profile still references the old name.

#### Schema mismatch recovery

1. Inspect the affected DQRun: `dq_run.details_json["metadata"]`
   carries the parsed column list.
2. Diff against the profile expectations registered for the
   tenant (`Tenant.default_dq_profile` →
   `services/dq-service/profiles/`).
3. Either update the profile to match the new schema OR roll
   back the upstream schema change.
4. Re-run failed jobs once the profile is aligned.

---

## PII redaction in DQ Hub logs (Phase 240.5.F)

Every `logger.*(..., extra={...})` call inside the canonical DQ
Hub-side files MUST wrap its dict literal in `_redact()` before
emit so PII bearing keys (full list below) never reach the log
backend.

**Why this matters.**  `DQRun.details_json` aggregates
customer-derived content: per-issue `sample_value` cells, row
samples used to drive anomaly detection, raw HTTP body fragments
from third-party alert delivery responses.  A casual
`logger.info("dq_run_done", extra={"details": dq_run.details_json})`
would copy that content into the log backend (which has different
retention + access semantics than the audit-event store + lower
operator-side encryption requirements).

### The contract

- Helper: [`hub.apps.dq.log_helpers._redact()`](../../hub/apps/dq/log_helpers.py)
  — recursively strips keys in `_REDACTED_KEYS` from any dict / list /
  tuple while preserving counts / scores / IDs / category names.
- Forbidden keys (the `_REDACTED_KEYS` frozenset): `row_samples`,
  `sample_value`, `sample_data_json`, `file_content`, `body`,
  `raw_data`, `data`, `details_json`.  Mirrors
  [`services/dq-service/structured_logging.py`](../../services/dq-service/structured_logging.py)
  ``_REDACTED_KEYS``; parity is pinned by
  [`hub/apps/dq/tests/test_log_helpers.py::TestRedactedKeysParity`](../../hub/apps/dq/tests/test_log_helpers.py).

### The lint rule

- Script: [`scripts/check_dq_log_extras.py`](../../scripts/check_dq_log_extras.py)
  — AST-based; matches `logger.<method>(..., extra={...})` calls in
  the canonical DQ Hub files (`views.py`, `services.py`,
  `service_client.py`, `alerting.py`, `tasks.py`) **plus the
  alert-delivery client subtree**
  ([`hub/apps/dq/clients/`](../../hub/apps/dq/clients/) — `base.py`,
  `email_client.py`, `webhook_client.py`, `slack_client.py`,
  `pagerduty_client.py`; extension scope from the 240.5.F audit pass)
  and rejects any dict literal containing a forbidden key UNLESS the
  dict is wrapped in a `_redact(...)` call.
- Lint script ↔ helper module parity: the script intentionally
  duplicates the forbidden-key list (so pre-commit's lean Python env
  doesn't have to import the Hub Django package).  Drift between
  the two copies is caught at CI time by
  [`hub/apps/dq/tests/test_log_helpers.py::TestLintRuleParity`](../../hub/apps/dq/tests/test_log_helpers.py)
  — adding a key to `_REDACTED_KEYS` without adding it to the
  script's `_FORBIDDEN_KEYS` (or vice versa) fails CI.
- Pre-commit hook: `check-dq-log-extras` in
  [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml).
- CI gate: `lint-dq-log-extras` in
  [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — second
  line of defence (pre-commit can be bypassed with `--no-verify`,
  CI cannot).

### Adding a new redacted key

1. Append the key to `_REDACTED_KEYS` in
   [`hub/apps/dq/log_helpers.py`](../../hub/apps/dq/log_helpers.py).
2. Append the SAME key to `_FORBIDDEN_KEYS` in
   [`scripts/check_dq_log_extras.py`](../../scripts/check_dq_log_extras.py)
   (the script doesn't import the Python helper to keep the
   pre-commit env lean).  `TestLintRuleParity` will fail CI if you
   skip this step.
3. Extend
   [`hub/apps/dq/tests/test_log_helpers.py::TestRedact::test_strips_known_pii_bearing_keys`](../../hub/apps/dq/tests/test_log_helpers.py)
   to assert the new key is dropped.
4. If the new key should also be redacted on the dq-service side,
   append it to
   [`services/dq-service/structured_logging.py`](../../services/dq-service/structured_logging.py)
   `_REDACTED_KEYS` and update
   [`services/dq-service/tests/test_structured_logging.py`](../../services/dq-service/tests/test_structured_logging.py)
   AND
   [`hub/apps/dq/tests/test_log_helpers.py::TestRedactedKeysParity::DQ_SERVICE_REDACTED_KEYS`](../../hub/apps/dq/tests/test_log_helpers.py)
   to match.  The Hub MUST always be a SUPERSET of the dq-service
   set; the parity test catches a one-sided forget.

### When the lint fails

The CI step `lint-dq-log-extras` (or the pre-commit hook
`check-dq-log-extras`) prints output like:

```text
❌ Phase 240.5.F.4 — found 2 unwrapped logger ``extra=`` payload(s) carrying forbidden keys:
hub/apps/dq/views.py:483:12: E[DQ-PII-001] logger.info(..., extra={...}) contains forbidden key(s) without _redact() wrap: details_json.  Wrap the dict in ``_redact()`` from ``hub.apps.dq.log_helpers`` before emit.
```

**Fix**: change:

```python
logger.info(
    "dq_run_completed",
    extra={"tenant_id": tid, "details_json": dq_run.details_json},
)
```

…to:

```python
from hub.apps.dq.log_helpers import _redact

logger.info(
    "dq_run_completed",
    extra=_redact({"tenant_id": tid, "details_json": dq_run.details_json}),
)
```

The `_redact()` call drops the `details_json` field, so the
emitted log line carries only `{tenant_id: tid}`.  All other safe
keys (counts / scores / category names / IDs / timing) round-trip
unchanged.

---

## Post-deploy smoke test (Phase 240.DoD.4)

After a deploy that touches the DQ feature surface, run
[`scripts/smoke_tests_dq.sh`](../../scripts/smoke_tests_dq.sh) against
the cluster being deployed-into.  The script verifies all four
240.DoD.4 line items:

1. **Synthetic DQ runs** across every registered profile-key
   (default: `intake_basic_gx`, `intake_basic_soda`) via
   `POST /run-dataframe` on dq-service — exercises both engines via
   the suffix-routing dispatcher (Phase 240.3.A.5).
2. **Alert-channel dry-run** for all 4 channels (`EMAIL`, `SLACK`,
   `WEBHOOK`, `PAGERDUTY`) by querying Prometheus
   `dq_alert_channel_circuit_open{channel=...}` — circuit OPEN means
   the channel is currently rejecting deliveries.
3. **Trivy gate confirmation** — informational; the actual gate runs
   at deploy time per [.github/workflows/deploy.yml](../../.github/workflows/deploy.yml)
   (Phase 240.5.D), pinned by
   [tests/ci/test_dq_image_vulnerability_scan.py](../../tests/ci/test_dq_image_vulnerability_scan.py).
4. **Grafana DQ board non-zero data** within the last 1h via
   `sum(increase(dq_runs_total[1h]))` Prometheus query — rules out
   the "deployed but no traffic" failure mode.

Required env vars: `DQ_SERVICE_URL`, `PROMETHEUS_URL`,
`INTERNAL_API_KEY`.  Optional: `INTERNAL_PAYLOAD_SECRET` (auto-stamps
HMAC signature per Phase 240.5.G when dq-service is in enforce mode),
`DEPLOY_WORKFLOW_RUN_URL`, `PROFILE_KEYS`, `TIMEOUT_SECONDS`.

Exit 0 = all passed; exit 1 = at least one verification failed; exit
2 = environment misconfigured.  Operator MUST link the script's
output to the deploy-rollout ticket before declaring smoke OK.

---

## Related docs

- Spec: [openspec/changes/preprod01/specs/data-quality/spec.md](../../openspec/changes/preprod01/specs/data-quality/spec.md).
- Alert rules: [monitoring/prometheus/alerts/dq.yml](../../monitoring/prometheus/alerts/dq.yml).
- Grafana dashboard: [monitoring/grafana/dashboards/data-quality.json](../../monitoring/grafana/dashboards/data-quality.json).
- Synthetic firing tests: [monitoring/prometheus/alerts/dq-synthetic-firing.yml](../../monitoring/prometheus/alerts/dq-synthetic-firing.yml).
- Purge CronJob: [helm/templates/cronjob/purge-dq-runs.yaml](../../helm/templates/cronjob/purge-dq-runs.yaml).
- DQ payloads S3 bucket: [infrastructure/terraform/modules/s3-buckets/dq_payloads.tf](../../infrastructure/terraform/modules/s3-buckets/dq_payloads.tf).
- Helm templates: [helm/templates/dq-service/](../../helm/templates/dq-service/).
