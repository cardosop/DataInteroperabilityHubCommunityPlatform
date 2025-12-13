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

