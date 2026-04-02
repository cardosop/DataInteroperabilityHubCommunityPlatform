# Operations Guide

**Document Version**: 1.0.0
**Last Updated**: 2026-03-26

---

## Overview

This is the central operations reference for Meshant. It links to detailed runbooks and guides for operating the platform in production.

## Key Documents

- [Capability Degradation Guide](capability-degradation.md) — how the system behaves when dependencies are unavailable
- [Operator External Setup Checklist](operator-external-setup-checklist.md) — provisioning external dependencies
- [BaaS Infrastructure Runbook](runbooks/BAAS_INFRASTRUCTURE.md) — BaaS service operations
- [Compliance Service Configuration](runbooks/COMPLIANCE_SERVICE_CONFIG.md) — compliance service setup

## Health Checks

```bash
# API health
curl -s https://<host>/api/v1/health/

# Database connectivity
kubectl exec -it <pod> -- python manage.py dbshell -c "SELECT 1;"

# Redis connectivity
kubectl exec -it <pod> -- python -c "from django.core.cache import cache; cache.set('health', 1)"
```

## Monitoring

- Prometheus metrics exposed at `/metrics/`
- Structured JSON logging via `django-structlog`
- Trace correlation via `X-Trace-ID` header

## Incident Response

1. Check health endpoint
2. Review structured logs for error patterns
3. Consult [capability-degradation.md](capability-degradation.md) for dependency failures
4. Rollback if needed: `helm rollback meshant <revision>`
