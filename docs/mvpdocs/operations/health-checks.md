# Health Checks

Health endpoints for the Meshant platform and their integration with
monitoring and alerting.

## Endpoints

| Endpoint         | Purpose                              | Expected Response |
|------------------|--------------------------------------|-------------------|
| `/health/`       | Basic liveness check                 | 200 OK            |
| `/health/live/`  | Kubernetes liveness probe            | 200 OK            |
| `/health/ready/` | Kubernetes readiness probe           | 200 OK            |

### `/health/`

Returns 200 if the application process is running. Does not check
backing services. Used for basic uptime monitoring.

### `/health/live/`

Kubernetes liveness probe. Returns 200 if the process is healthy.
If this fails, Kubernetes restarts the pod. Should not depend on
external services to avoid cascading restarts.

### `/health/ready/`

Kubernetes readiness probe. Returns 200 only when the application
can serve traffic. Checks:

- Database connectivity (PostgreSQL)
- Cache connectivity (Redis)
- Migration state (all migrations applied)

If this fails, Kubernetes removes the pod from the Service endpoints
until it recovers.

## Kubernetes Configuration

Probes are configured in the Helm chart:

```yaml
livenessProbe:
  httpGet:
    path: /health/live/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 3
```

## Monitoring Integration

- **Prometheus** scrapes health endpoints and records
  `health_check_status` (1 = healthy, 0 = unhealthy).
- **Grafana** dashboard shows health status per pod.
- **Alerting** fires if any pod fails readiness for more than
  2 minutes.

## Alerting Thresholds

| Condition                              | Severity | Action             |
|----------------------------------------|----------|--------------------|
| Liveness probe fails 3 times           | P1       | Pod auto-restarts  |
| Readiness probe fails for 2+ minutes   | P2       | Investigate logs   |
| All pods unready for 1+ minute         | P0       | Immediate response |

## Related

- [Monitoring](monitoring.md) -- dashboards and alerting
- [Incident Response](incident-response.md) -- responding to health failures
- [OPERATIONS.md](../../OPERATIONS.md) -- full operations reference
