# Production Deployment Guide

Complete guide for deploying the Data Interoperability Hub to production environments.

## Table of Contents

1. [Overview](#overview)
2. [Deployment Strategy](#deployment-strategy)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Deployment Procedures](#deployment-procedures)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Rollback Procedures](#rollback-procedures)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This document describes the production deployment process for the Data Interoperability Hub. Production deployments require careful planning, thorough testing, and comprehensive monitoring.

### Key Principles

- **Zero-downtime deployments**: Use blue-green or rolling deployment strategies
- **Automated rollback**: Ability to quickly revert to previous version
- **Comprehensive monitoring**: Real-time visibility into system health
- **Gradual rollout**: Canary deployments for high-risk changes
- **Database safety**: All migrations are backward-compatible

### Deployment Methods

- **Kubernetes**: Primary production deployment method
- **Docker Compose**: Alternative for smaller deployments
- **CI/CD**: Automated via GitHub Actions with manual approval gates

---

## Deployment Strategy

### Strategy Selection

The recommended deployment strategy depends on your infrastructure and requirements:

#### 1. Blue-Green Deployment (Recommended)

**Best for**: Zero-downtime deployments, critical production environments

**How it works**:
- Deploy new version to "green" environment
- Run smoke tests and verification
- Switch traffic from "blue" (current) to "green" (new)
- Keep "blue" running for quick rollback

**Advantages**:
- Zero downtime
- Instant rollback capability
- Full testing before traffic switch
- No impact on running requests

**Disadvantages**:
- Requires 2x infrastructure capacity during deployment
- More complex setup
- Higher resource costs

**Implementation**:
```bash
# Deploy to green environment
kubectl apply -f k8s/green/

# Run smoke tests
./scripts/smoke-tests.sh --api-url https://green.hub.example.com

# Switch traffic (update load balancer)
kubectl patch service api-service -p '{"spec":{"selector":{"version":"green"}}}'

# Monitor for issues
# If problems detected, switch back to blue
```

#### 2. Rolling Deployment

**Best for**: Resource-constrained environments, gradual rollouts

**How it works**:
- Deploy new version to subset of pods
- Gradually replace old pods with new ones
- Monitor health at each step
- Roll back if issues detected

**Advantages**:
- Lower resource requirements
- Gradual rollout reduces risk
- Can pause and resume deployment

**Disadvantages**:
- Brief service degradation possible
- More complex rollback
- Requires careful health monitoring

**Implementation**:
```bash
# Update deployment with new image
kubectl set image deployment/api-service \
  api-service=ghcr.io/your-org/datainteroperabilityhub-api-service:v1.1.0

# Monitor rollout
kubectl rollout status deployment/api-service

# Pause rollout if needed
kubectl rollout pause deployment/api-service

# Resume rollout
kubectl rollout resume deployment/api-service
```

#### 3. Canary Deployment

**Best for**: High-risk changes, A/B testing, gradual feature rollouts

**How it works**:
- Deploy new version to small subset (e.g., 10% of traffic)
- Monitor metrics and errors
- Gradually increase traffic percentage
- Full rollout or rollback based on results

**Advantages**:
- Minimal impact if issues occur
- Real-world testing with production traffic
- Gradual risk reduction

**Disadvantages**:
- Requires traffic splitting infrastructure
- More complex monitoring
- Longer deployment process

**Implementation**:
```bash
# Deploy canary version
kubectl apply -f k8s/canary/

# Route 10% traffic to canary
kubectl patch service api-service -p '{"spec":{"traffic":{"canary":10}}}'

# Monitor metrics for 30 minutes
# If healthy, increase to 50%
kubectl patch service api-service -p '{"spec":{"traffic":{"canary":50}}}'

# If still healthy, route 100% and remove canary
kubectl patch service api-service -p '{"spec":{"traffic":{"canary":100}}}'
```

### Recommended Strategy

For the Data Interoperability Hub, we recommend **Blue-Green Deployment** for production because:

1. **Zero downtime**: Critical for SaaS platform
2. **Instant rollback**: Essential for production stability
3. **Full testing**: Verify new version before traffic switch
4. **Risk mitigation**: Isolated testing environment

---

## Pre-Deployment Checklist

### Code Quality

- [ ] All code reviews completed and approved
- [ ] All unit tests passing (100% pass rate)
- [ ] All integration tests passing
- [ ] All E2E tests passing against staging
- [ ] Code coverage meets requirements (80%+ overall, 90%+ critical paths)
- [ ] Linting and formatting checks passed
- [ ] Security scans completed (SAST, dependency scanning)
- [ ] No known critical or high-severity bugs

### Documentation

- [ ] API documentation updated (OpenAPI schema)
- [ ] Changelog updated with new features and breaking changes
- [ ] Deployment notes documented
- [ ] Runbooks updated if procedures changed
- [ ] User documentation updated if features changed

### Database

- [ ] All migrations tested in staging
- [ ] Migrations are backward-compatible
- [ ] Database backup created
- [ ] Migration rollback plan documented
- [ ] Database performance tested with production-like data volumes

### Infrastructure

- [ ] Infrastructure changes reviewed and approved
- [ ] Resource requirements verified (CPU, memory, storage)
- [ ] Scaling policies reviewed
- [ ] Network configuration verified
- [ ] SSL certificates valid and not expiring soon
- [ ] DNS records updated if needed

### Security

- [ ] Security review completed
- [ ] Secrets rotated if needed
- [ ] Access controls verified
- [ ] Rate limiting thresholds reviewed
- [ ] DDoS protection configured
- [ ] WAF rules updated if needed

### Performance

- [ ] Performance tests passed in staging
- [ ] Load tests completed with expected traffic
- [ ] Response time targets met (P95 < 500ms)
- [ ] Throughput targets met
- [ ] Resource utilization within limits

### Monitoring

- [ ] Monitoring dashboards updated
- [ ] Alerting rules reviewed and tested
- [ ] On-call rotation scheduled
- [ ] Incident response plan ready

### Communication

- [ ] Stakeholders notified of deployment window
- [ ] Maintenance window scheduled (if needed)
- [ ] Rollback plan communicated to team
- [ ] Support team briefed on changes

---

## Deployment Procedures

### Step 1: Prepare Deployment Artifacts

```bash
# Tag release
git tag -a v1.1.0 -m "Release version 1.1.0"
git push origin v1.1.0

# Build and push Docker images
docker build -t ghcr.io/your-org/datainteroperabilityhub-api-service:v1.1.0 -f services/api/Dockerfile .
docker push ghcr.io/your-org/datainteroperabilityhub-api-service:v1.1.0

# Build and push worker image
docker build -t ghcr.io/your-org/datainteroperabilityhub-worker-service:v1.1.0 -f services/worker/Dockerfile .
docker push ghcr.io/your-org/datainteroperabilityhub-worker-service:v1.1.0

# Build and push service images
# ... (repeat for all services)
```

### Step 2: Backup Database

```bash
# Create database backup
kubectl exec -it postgres-0 -- pg_dump -U hub hub > backup-$(date +%Y%m%d-%H%M%S).sql

# Verify backup
ls -lh backup-*.sql

# Store backup in secure location
# (e.g., S3, backup storage)
```

### Step 3: Run Database Migrations

```bash
# Create migration job
kubectl apply -f k8s/migrations/job.yaml

# Wait for completion
kubectl wait --for=condition=complete job/migrations --timeout=600s

# Verify migration success
kubectl logs job/migrations
```

### Step 4: Deploy Application (Blue-Green)

```bash
# Deploy to green environment
kubectl apply -f k8s/green/

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=api-service,version=green --timeout=300s

# Verify health
kubectl get pods -l app=api-service,version=green
```

### Step 5: Run Smoke Tests

```bash
# Run smoke tests against green environment
export API_URL=https://green.hub.example.com
./scripts/smoke-tests.sh

# Verify all tests pass
```

### Step 6: Switch Traffic

```bash
# Update service selector to point to green
kubectl patch service api-service -p '{"spec":{"selector":{"version":"green"}}}'

# Verify traffic is routing correctly
kubectl get endpoints api-service
```

### Step 7: Monitor Deployment

```bash
# Watch pod status
kubectl get pods -w

# Monitor logs
kubectl logs -f deployment/api-service

# Check metrics
# (Access Grafana dashboard)
```

---

## Post-Deployment Verification

### Health Checks

```bash
# Verify all health endpoints
curl https://api.hub.example.com/health/
curl https://api.hub.example.com/api/v1/health/semantic/
curl https://api.hub.example.com/api/v1/health/datacontract/
curl https://api.hub.example.com/api/v1/health/compliance/
curl https://api.hub.example.com/api/v1/health/dq/
```

### Functional Verification

```bash
# Run smoke tests
./scripts/smoke-tests.sh --api-url https://api.hub.example.com

# Run critical E2E tests
pytest tests/e2e/ -m "e2e_batch1" -v
```

### Monitoring Verification

- [ ] All services showing healthy in Grafana
- [ ] No critical alerts firing
- [ ] Error rates within normal range
- [ ] Response times within targets
- [ ] Job processing working correctly
- [ ] Email notifications working
- [ ] Rate limiting functioning

### Metrics Verification

- [ ] Request rate normal
- [ ] Error rate < 1%
- [ ] P95 latency < 500ms
- [ ] Job success rate > 99%
- [ ] Database connection pool healthy
- [ ] Redis connection healthy
- [ ] S3 operations successful

---

## Rollback Procedures

### Rollback Triggers

Rollback should be initiated immediately if:

1. **Critical errors**: Error rate > 5% for 5 minutes
2. **Service degradation**: P95 latency > 1s for 5 minutes
3. **Service unavailability**: Health checks failing
4. **Data corruption**: Database integrity issues detected
5. **Security issues**: Security vulnerabilities discovered
6. **Business impact**: User-reported critical issues

### Blue-Green Rollback

```bash
# Switch traffic back to blue
kubectl patch service api-service -p '{"spec":{"selector":{"version":"blue"}}}'

# Verify traffic switched
kubectl get endpoints api-service

# Monitor blue environment
kubectl logs -f deployment/api-service -l version=blue
```

### Rolling Deployment Rollback

```bash
# Rollback to previous revision
kubectl rollout undo deployment/api-service

# Rollback to specific revision
kubectl rollout undo deployment/api-service --to-revision=2

# Verify rollback
kubectl rollout status deployment/api-service
```

### Database Rollback

**⚠️ Warning**: Database rollbacks are complex and should be avoided. Always test migrations in staging first.

```bash
# List migration history
python manage.py showmigrations

# Rollback specific migration (if backward-compatible)
python manage.py migrate app_name previous_migration_name

# Restore from backup if needed
kubectl exec -it postgres-0 -- psql -U hub hub < backup-YYYYMMDD-HHMMSS.sql
```

### Rollback Verification

After rollback:

1. Verify all health endpoints
2. Run smoke tests
3. Monitor metrics for 30 minutes
4. Verify no data loss
5. Document rollback reason

---

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Service Health**
   - Service uptime
   - Health check status
   - Pod restarts

2. **Performance**
   - Request rate
   - Response time (P50, P95, P99)
   - Error rate
   - Throughput

3. **Resources**
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network I/O

4. **Business Metrics**
   - Active users
   - API requests
   - Job success rate
   - Data processing volume

### Alerting Rules

Critical alerts (immediate response):
- Service down
- Error rate > 5%
- Database connection failures
- High latency (P95 > 1s)

Warning alerts (investigate):
- Error rate > 1%
- High latency (P95 > 500ms)
- Job queue depth > 100
- Resource usage > 80%

### Monitoring Dashboards

Access monitoring dashboards:
- **Grafana**: https://grafana.hub.example.com
- **Prometheus**: https://prometheus.hub.example.com
- **Jaeger**: https://jaeger.hub.example.com

---

## Troubleshooting

### Common Issues

#### Services Not Starting

```bash
# Check pod status
kubectl get pods

# Check pod logs
kubectl logs <pod-name>

# Check events
kubectl describe pod <pod-name>

# Check resource limits
kubectl top pods
```

#### Database Connection Issues

```bash
# Test database connection
kubectl exec -it api-service-0 -- python manage.py dbshell

# Check database status
kubectl get pods -l app=postgres

# Check connection pool
# (View metrics in Grafana)
```

#### High Error Rates

```bash
# Check error logs
kubectl logs -f deployment/api-service | grep ERROR

# Check error metrics
# (View in Grafana dashboard)

# Check service dependencies
kubectl get endpoints
```

#### Performance Degradation

```bash
# Check resource usage
kubectl top pods
kubectl top nodes

# Check slow queries
# (View database performance dashboard)

# Check job queue depth
# (View worker metrics)
```

### Debugging Commands

```bash
# Access service shell
kubectl exec -it deployment/api-service -- bash

# Check environment variables
kubectl exec deployment/api-service -- env

# View service configuration
kubectl get configmap api-service-config -o yaml

# View secrets (base64 encoded)
kubectl get secret api-service-secrets -o yaml
```

---

## Support

For deployment support:

- **Documentation**: https://docs.hub.example.com/deployment
- **Issues**: https://github.com/your-org/datainteroperabilityhub/issues
- **On-Call**: Check PagerDuty rotation
- **Email**: devops@hub.example.com

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

