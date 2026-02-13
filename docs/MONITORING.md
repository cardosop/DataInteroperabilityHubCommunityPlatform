# Monitoring & Observability

Complete guide for monitoring and observability in the Data Interoperability Hub.

## Overview

The platform provides comprehensive monitoring and observability:

- **Metrics**: Prometheus metrics collection
- **Logging**: Structured logging with correlation IDs
- **Tracing**: Distributed tracing with Jaeger
- **Dashboards**: Grafana dashboards for visualization
- **Alerts**: Alertmanager for alerting

## Metrics

### Prometheus

Prometheus collects metrics from all services:

- **URL**: http://localhost:9090
- **Metrics Endpoint**: `/metrics` on each service

### Key Metrics

#### API Service Metrics

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration
- `http_requests_errors_total` - Error count
- `django_db_queries_total` - Database queries
- `django_cache_hits_total` - Cache hits

#### Worker Service Metrics

- `rq_jobs_total` - Total jobs processed
- `rq_jobs_duration_seconds` - Job duration
- `rq_jobs_failed_total` - Failed jobs
- `rq_queue_length` - Queue length

#### Database Metrics

- `postgres_connections` - Active connections
- `postgres_queries_total` - Query count
- `postgres_slow_queries_total` - Slow queries

### Accessing Metrics

```bash
# Prometheus UI
open http://localhost:9090

# Query metrics
curl http://localhost:9090/api/v1/query?query=http_requests_total

# Service metrics
curl http://localhost:8000/metrics
curl http://localhost:8080/metrics
```

## Logging

### Structured Logging

All services use structured logging with correlation IDs:

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    'Contract created',
    contract_id=contract.id,
    tenant_id=tenant.id,
    user_id=user.id,
    correlation_id=request.correlation_id
)
```

### Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General informational messages
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical errors

### Viewing Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs api-service

# Follow logs
docker compose logs -f api-service

# Filter logs
docker compose logs api-service | grep ERROR
```

### Log Aggregation

Logs are aggregated and can be exported to:
- **ELK Stack** (optional)
- **Loki** (optional)
- **CloudWatch** (production)

## Tracing

### Jaeger

Distributed tracing with Jaeger:

- **UI**: http://localhost:16686
- **HTTP Collector**: http://localhost:14268
- **UDP Collector**: localhost:6831

### Tracing Requests

Tracing is automatically enabled for:
- HTTP requests
- Database queries
- External service calls
- Background jobs

### Viewing Traces

```bash
# Open Jaeger UI
open http://localhost:16686

# Search traces
# - Service: api-service
# - Operation: GET /api/v1/contracts/
# - Tags: error=true
```

### W3C Trace Context and service coverage

All request-handling services (api-service, API Gateway, FastAPI microservices) **SHOULD** use [W3C Trace Context](https://www.w3.org/TR/trace-context/) (`traceparent`, `tracestate` headers) and export spans to the same backend (Jaeger or OTLP) so that traces are continuous across the stack.

| Service | W3C trace context / export to same backend | Notes |
|--------|--------------------------------------------|-------|
| **api-service** (Django) | **Yes** | `TraceIDMiddleware` and `SpanMiddleware` extract/emit traceparent; OpenTelemetry via `hub.apps.observability.otel_config` (Django + HTTPX instrumentation). Exports to Jaeger or OTLP per `OPENTELEMETRY_EXPORTER`. |
| **API Gateway** (FastAPI) | **Yes** | `shared.tracing.setup_opentelemetry_fastapi`; FastAPI and HTTPX instrumentation; Jaeger exporter. Propagates W3C headers on forwarded requests. |
| **semantic-service** (FastAPI) | **Yes** | `shared.tracing.setup_opentelemetry_fastapi`; FastAPI and HTTPX instrumentation; Jaeger exporter. |
| **dq-service** (FastAPI) | **Not yet** | No OpenTelemetry instrumentation. To align: add `shared.tracing.setup_opentelemetry_fastapi` and instrument the app. |
| **compliance-service** (FastAPI) | **Not yet** | No OpenTelemetry instrumentation. To align: add `shared.tracing.setup_opentelemetry_fastapi` and instrument the app. |
| **webhook-service** (FastAPI) | **Not yet** | OpenTelemetry deps present but not wired in main. To align: add `shared.tracing.setup_opentelemetry_fastapi` and instrument the app. |

Gateway and api-service both use W3C trace context: Django uses `hub.apps.api.middleware.tracing` (traceparent) and `get_trace_headers()` for outbound calls; OpenTelemetry SDK uses W3C by default. For full propagation details, see `infrastructure/tracing/README.md`.

## Dashboards

### Grafana

Grafana provides visualization dashboards:

- **URL**: http://localhost:3000
- **Default Credentials**: admin/admin

### Available Dashboards

1. **API Service Dashboard**
   - Request rate
   - Error rate
   - Response time
   - Database queries

2. **Worker Service Dashboard**
   - Job processing rate
   - Job duration
   - Queue length
   - Failed jobs

3. **Database Dashboard**
   - Connection count
   - Query rate
   - Slow queries
   - Database size

4. **System Dashboard**
   - CPU usage
   - Memory usage
   - Disk usage
   - Network traffic

### Creating Custom Dashboards

1. Open Grafana UI
2. Create new dashboard
3. Add panels with Prometheus queries
4. Save dashboard

## Alerts

### Alertmanager

Alertmanager manages alerts:

- **URL**: http://localhost:9093
- **Configuration**: `monitoring/alertmanager/alertmanager.yml`

### Alert Rules

Alert rules are defined in `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: api_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High error rate detected"
```

### Common Alerts

- **High Error Rate**: API error rate > 10%
- **Slow Response Time**: P95 response time > 1s
- **Database Connection Pool Exhausted**: Connection pool > 80%
- **Queue Backlog**: Queue length > 1000
- **Service Down**: Service health check failed

### Alert Notifications

Alerts can be sent to:
- **Email**: SMTP configuration
- **Slack**: Webhook integration
- **PagerDuty**: API integration
- **Custom Webhooks**: HTTP endpoints

## Health Checks

### Service Health Endpoints

All services expose health check endpoints:

```bash
# API Service
curl http://localhost:8000/health

# Worker Service
curl http://localhost:8080/healthz

# Workflow Engine
curl http://localhost:8088/healthz

# Microservices
curl http://localhost:8081/health  # Semantic
curl http://localhost:8082/health  # Compliance
curl http://localhost:8083/health  # DQ
```

### Health Check Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-15T10:30:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "minio": "healthy"
  }
}
```

## Observability Service

The Observability Service provides data observability:

- **URL**: http://localhost:8086
- **Metrics**: Data freshness, lineage, quality

### Features

- **Data Freshness**: Track data update frequency
- **Lineage Tracking**: Track data lineage
- **Quality Metrics**: Track data quality trends

## BaaS Platform Metrics

### API Gateway Metrics

The API Gateway (`services/api-gateway/`) exposes metrics for rate limiting and request routing:

- `api_gateway_requests_total` - Total API requests
- `api_gateway_request_duration_seconds` - Request duration
- `api_gateway_rate_limit_exceeded_total` - Rate limit violations
- `api_gateway_api_key_validations_total` - API key validations
- `api_gateway_tier_requests_total{ tier="FREE|PRO|ENTERPRISE" }` - Requests by tier

### Usage Tracking Metrics

The UsageTrackingService exposes metrics for API usage:

- `baas_usage_requests_total` - Total tracked requests
- `baas_usage_requests_by_endpoint_total{ endpoint="/api/v1/assets/" }` - Requests by endpoint
- `baas_usage_requests_by_tier_total{ tier="FREE|PRO|ENTERPRISE" }` - Requests by tier
- `baas_usage_quota_remaining{ tier="FREE|PRO|ENTERPRISE" }` - Remaining quota
- `baas_usage_response_time_seconds` - Response time histogram

### Grafana Dashboard

**BaaS Platform Dashboard** (`grafana/dashboards/baas-platform.json`):

- **API Gateway Overview**: Request rate, error rate, rate limit violations
- **Usage by Tier**: Requests, quota usage, quota remaining per tier
- **Usage by Endpoint**: Top endpoints by request count and response time
- **API Key Management**: API key creation, revocation, expiration

**Key Panels**:
- API Gateway Request Rate (requests/second)
- Rate Limit Violations by Tier
- Quota Usage Percentage by Tier
- Top 10 Endpoints by Request Count
- Average Response Time by Endpoint

### Alert Definitions

**BaaS Platform Alerts**:

```yaml
# Rate limit violations
- alert: BaaSRateLimitViolationsHigh
  expr: rate(api_gateway_rate_limit_exceeded_total[5m]) > 10
  for: 5m
  annotations:
    summary: "High rate limit violations detected"

# Quota exhaustion
- alert: BaaSQuotaExhausted
  expr: baas_usage_quota_remaining < 100
  for: 1m
  annotations:
    summary: "API quota nearly exhausted for tier"

# API key validation failures
- alert: BaaSAPIKeyValidationFailures
  expr: rate(api_gateway_api_key_validations_total{status="failed"}[5m]) > 5
  for: 5m
  annotations:
    summary: "High API key validation failure rate"
```

### Monitoring Best Practices

1. **Track Quota Usage**: Monitor quota remaining to prevent service disruption
2. **Monitor Rate Limits**: Track rate limit violations to identify abuse or scaling needs
3. **Endpoint Performance**: Monitor response times by endpoint to identify slow endpoints
4. **Tier Distribution**: Track request distribution across tiers for capacity planning

## ODH Integration Metrics

### Model Registry Metrics

The ModelRegistryBridgeService exposes metrics for model operations:

- `odh_models_total` - Total ML models
- `odh_models_by_status_total{ status="TRAINING|TRAINED|DEPLOYED|FAILED" }` - Models by status
- `odh_models_by_type_total{ type="CLASSIFICATION|REGRESSION|..." }` - Models by type
- `odh_model_operations_total{ operation="create|update|delete" }` - Model operations
- `odh_model_sync_duration_seconds` - Model sync duration

### Training Pipeline Metrics

The ModelTrainingWorkflow exposes metrics for training operations:

- `odh_training_jobs_total` - Total training jobs
- `odh_training_jobs_by_status_total{ status="RUNNING|COMPLETED|FAILED" }` - Jobs by status
- `odh_training_job_duration_seconds` - Training job duration
- `odh_training_job_failures_total` - Failed training jobs
- `odh_training_dataset_validation_duration_seconds` - Dataset validation duration

### Inference Service Metrics

The InferenceValidationService exposes metrics for inference operations:

- `odh_inference_predictions_total` - Total predictions
- `odh_inference_latency_seconds` - Inference latency histogram
- `odh_inference_errors_total` - Inference errors
- `odh_inference_validation_failures_total` - Input/output validation failures
- `odh_inference_data_drift_score` - Data drift score gauge

### Grafana Dashboard

**ODH Integration Dashboard** (`grafana/dashboards/odh-integration.json`):

- **Model Registry Overview**: Model count, status distribution, type distribution
- **Training Pipeline**: Training job status, duration, success rate
- **Inference Service**: Prediction rate, latency, error rate, data drift
- **ODH Service Health**: ODH service availability and response times

**Key Panels**:
- ML Models by Status
- Training Job Success Rate
- Inference Prediction Rate (predictions/second)
- Inference Latency (p50, p95, p99)
- Data Drift Score Trend
- ODH Service Response Time

### Alert Definitions

**ODH Integration Alerts**:

```yaml
# Training job failures
- alert: ODHTrainingJobFailuresHigh
  expr: rate(odh_training_job_failures_total[5m]) > 0.1
  for: 5m
  annotations:
    summary: "High training job failure rate"

# Inference latency high
- alert: ODHInferenceLatencyHigh
  expr: histogram_quantile(0.95, odh_inference_latency_seconds) > 0.5
  for: 5m
  annotations:
    summary: "High inference latency (p95 > 500ms)"

# Data drift detected
- alert: ODHDataDriftDetected
  expr: odh_inference_data_drift_score > 0.1
  for: 10m
  annotations:
    summary: "Data drift detected in inference inputs"

# ODH service unavailable
- alert: ODHServiceUnavailable
  expr: up{job="odh-service"} == 0
  for: 1m
  annotations:
    summary: "ODH service is unavailable"
```

### Monitoring Best Practices

1. **Model Lifecycle Tracking**: Monitor model status transitions (TRAINING → TRAINED → DEPLOYED)
2. **Training Performance**: Track training job duration and success rate
3. **Inference Quality**: Monitor inference latency, accuracy, and data drift
4. **ODH Service Health**: Monitor ODH service availability and response times
5. **Resource Usage**: Track resource consumption for training and inference

## Best Practices

### Metrics

1. **Use Histograms**: For latency measurements
2. **Use Counters**: For event counts
3. **Label Appropriately**: Use meaningful labels
4. **Avoid High Cardinality**: Limit label combinations

### Logging

1. **Use Structured Logging**: JSON format
2. **Include Correlation IDs**: For request tracing
3. **Log at Appropriate Levels**: Don't log everything as ERROR
4. **Avoid Sensitive Data**: Don't log passwords, tokens

### Tracing

1. **Trace Critical Paths**: Focus on important operations
2. **Keep Traces Small**: Limit trace size
3. **Use Sampling**: Sample traces in production

## Related Documentation

- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues
- [Runbooks](runbooks/README.md) - Operational procedures
- [Service Deployment Guide](SERVICE_DEPLOYMENT_GUIDE.md) - Service configuration

