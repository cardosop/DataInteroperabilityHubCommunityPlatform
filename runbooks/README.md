# Operational Runbooks

This directory contains operational runbooks for the Interoperable Data Hub MVP.

## Runbook Index

### Deployment

- **RB-DEPLOY-001**: Standard Deployment Procedure
  - Routine application releases
  - Database migrations
  - Rollback procedures

### Database

- **RB-DB-001**: Database Outage / Degradation
  - Database connectivity issues
  - Connection pool exhaustion
  - High query latency

- **RB-DB-002**: Database Migration Rollback
  - Rolling back failed migrations
  - Schema restoration

- **RB-DB-003**: Database Restore from Backup
  - Full database restore
  - Point-in-time recovery
  - Partial restore

### Disaster Recovery

- **RB-DR-001**: Disaster Recovery Plan
  - Complete infrastructure failure
  - Regional outages
  - Multi-service failures

### Queue & Jobs

- **RB-QUEUE-001**: Queue Backlog / Throttling
  - High queue depth
  - Job lag
  - Worker failures

### Service Operations

- **RB-SVC-001**: Service Crash / High Error Rate
  - Service crashes
  - High error rates
  - Resource exhaustion

### Security

- **RB-SEC-001**: Security Incident Response
  - Account compromise
  - Unauthorized access
  - Data exfiltration

## Runbook Structure

All runbooks follow this structure:

1. **Title & ID** - Unique identifier
2. **Scope** - What's covered and what's not
3. **Audience & Roles** - Who should use this
4. **Prerequisites** - Tools and access needed
5. **Symptoms** - How to detect the issue
6. **Impact** - User-visible impact and severity
7. **Detection & Diagnosis** - Step-by-step diagnosis
8. **Immediate Actions** - First 10 minutes
9. **Remediation Procedures** - Detailed fix steps
10. **Validation & Recovery** - How to verify success
11. **Communication** - Who to notify
12. **Post-Incident Actions** - Follow-up tasks

## Using Runbooks

### During an Incident

1. Identify the issue type
2. Find the appropriate runbook
3. Follow the "Immediate Actions" section first
4. Proceed with diagnosis and remediation
5. Document the incident

### Keeping Runbooks Updated

- Update runbooks after each incident
- Review runbooks quarterly
- Test procedures in staging when possible
- Update based on infrastructure changes

## Related Documentation

- `InputDocs/Runbooks_and_Operational_Procedures.md` - Runbook specifications
- `monitoring/prometheus/alerts.yml` - Alerting rules
- `monitoring/grafana/dashboards/` - Monitoring dashboards

## Quick Reference

### Common Commands

```bash
# Check service status
kubectl get pods -l app=api-service -n production

# Check database connectivity
psql -h <db-host> -U <user> -d hub -c "SELECT 1;"

# Check queue depth
redis-cli LLEN rq:queue:default

# Rollback deployment
kubectl rollout undo deployment/api-service -n production

# Scale services
kubectl scale deployment/api-service --replicas=3 -n production
```

### Emergency Contacts

- **On-Call SRE**: [Contact Info]
- **Database Team**: [Contact Info]
- **Security Team**: [Contact Info]
- **Management Escalation**: [Contact Info]

