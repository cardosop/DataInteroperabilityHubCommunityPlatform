# Deployment Verification Checklist

Use this checklist to verify OpenTelemetry metrics deployment.

## Pre-Deployment

- [ ] All tests pass (unit, integration, E2E, performance)
- [ ] Code review completed
- [ ] Deployment plan approved
- [ ] Rollback plan prepared

## Staging Deployment

### 1. Deploy to Staging

- [ ] Services deployed successfully
- [ ] Database migrations completed
- [ ] All services healthy

### 2. Verify Metrics Endpoint Works

**Automated:**
```bash
./scripts/verify_metrics_deployment.sh staging http://staging.example.com
```

**Manual Checks:**
- [ ] Metrics endpoint accessible: `curl http://staging.example.com/metrics/`
- [ ] Returns HTTP 200 (or 503 if metrics disabled)
- [ ] Content-Type: `text/plain; version=0.0.4`
- [ ] Contains `# HELP` comments
- [ ] Contains `# TYPE` comments
- [ ] Contains metric names (http_requests_total, etc.)

### 3. Verify Prometheus Can Scrape

**Automated:**
```bash
python scripts/verify_prometheus_scraping.py \
    --url http://staging.example.com \
    --prometheus-url http://prometheus:9090
```

**Manual Checks:**
- [ ] Prometheus target shows "up"
- [ ] No scraping errors in Prometheus logs
- [ ] Metrics appear in Prometheus queries
- [ ] Query: `up{job="api-service"}` returns 1
- [ ] Query: `http_requests_total` returns data

### 4. Monitor for Errors

**Automated:**
```bash
python scripts/monitor_deployment_errors.py \
    --url http://staging.example.com \
    --duration 600 \
    --interval 30
```

**Manual Checks:**
- [ ] No errors in application logs
- [ ] No errors in metrics collection
- [ ] HTTP error rates normal
- [ ] Performance metrics normal
- [ ] No service crashes

### 5. Verify Grafana Dashboards

- [ ] System Health dashboard loads
- [ ] API Performance dashboard loads
- [ ] Job Processing dashboard loads
- [ ] Metrics display correctly
- [ ] No "No data" messages

### 6. Verify Alerts

- [ ] Alerts evaluate correctly
- [ ] No false positives
- [ ] Alert rules match metric names

## Production Deployment

### 1. Deploy to Production

- [ ] Services deployed successfully
- [ ] Database migrations completed
- [ ] All services healthy

### 2. Verify Metrics Endpoint Works

**Automated:**
```bash
./scripts/verify_metrics_deployment.sh production http://api.example.com
```

**Manual Checks:**
- [ ] Metrics endpoint accessible
- [ ] Returns valid Prometheus format
- [ ] All metric names present

### 3. Verify Prometheus Can Scrape

**Automated:**
```bash
python scripts/verify_prometheus_scraping.py \
    --url http://api.example.com \
    --prometheus-url http://prometheus.production:9090
```

**Manual Checks:**
- [ ] Prometheus target shows "up"
- [ ] Metrics appear in Prometheus
- [ ] No scraping errors

### 4. Monitor for Errors

**Automated:**
```bash
python scripts/monitor_deployment_errors.py \
    --url http://api.example.com \
    --duration 1800 \
    --interval 60
```

**Manual Checks:**
- [ ] No errors in logs
- [ ] Error rates normal
- [ ] Performance normal

### 5. Verify No Performance Issues

- [ ] P95 latency within 10% of baseline
- [ ] Error rates remain normal
- [ ] No memory leaks
- [ ] No CPU spikes
- [ ] Metrics collection overhead <100ms

## Post-Deployment (24 hours)

- [ ] Metrics being collected continuously
- [ ] No metric gaps
- [ ] Metric values reasonable
- [ ] No performance degradation
- [ ] No errors in logs
- [ ] Tracing still works
- [ ] Grafana dashboards working
- [ ] Alerts working

## Rollback Criteria

Rollback if:
- Metrics endpoint not accessible for >5 minutes
- Prometheus cannot scrape for >10 minutes
- Error rates increase >50%
- Performance degradation >20%
- Service crashes or instability

## Quick Reference

### Verification Scripts

```bash
# Basic metrics verification
./scripts/verify_metrics_deployment.sh [staging|production] [url]

# Prometheus scraping verification
python scripts/verify_prometheus_scraping.py --url [url] --prometheus-url [prometheus-url]

# Error monitoring
python scripts/monitor_deployment_errors.py --url [url] --duration [seconds]
```

### Manual Checks

```bash
# Check metrics endpoint
curl http://api.example.com/metrics/ | head -20

# Check Prometheus target
curl http://prometheus:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="api-service")'

# Query metrics
curl 'http://prometheus:9090/api/v1/query?query=http_requests_total'
```

## Support

For issues:
1. Check application logs
2. Check Prometheus logs
3. Review deployment documentation
4. Contact DevOps team

