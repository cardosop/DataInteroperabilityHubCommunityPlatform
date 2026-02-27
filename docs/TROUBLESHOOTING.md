# Troubleshooting Guide

Common issues and solutions for the Data Interoperability Hub.

## Quick Diagnostics

### Check Service Health

```bash
# Check all services
docker compose ps

# Check specific service
docker compose logs api-service

# Check health endpoint
curl http://localhost:8000/health
```

### Check Database Connection

```bash
# Test PostgreSQL connection
docker compose exec postgres psql -U hub -d hub -c "SELECT 1;"

# Check database size
docker compose exec postgres psql -U hub -d hub -c "SELECT pg_size_pretty(pg_database_size('hub'));"
```

### Check Redis Connection

```bash
# Test Redis connection
docker compose exec redis redis-cli ping

# Check Redis info
docker compose exec redis redis-cli info
```

## Common Issues

### Services Won't Start

**Symptoms**: Services fail to start or crash immediately

**Solutions**:
```bash
# Check logs
docker compose logs <service-name>

# Check port conflicts
netstat -tulpn | grep -E '8000|5432|6379|9000'

# Restart services
docker compose restart <service-name>

# Rebuild services
docker compose build <service-name>
docker compose up -d <service-name>
```

### Database Connection Errors

**Symptoms**: `django.db.utils.OperationalError: could not connect to server`

**Solutions**:
```bash
# Ensure PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Restart PostgreSQL
docker compose restart postgres

# Check connection string
echo $DATABASE_URL
```

### Migration Errors

**Symptoms**: `django.db.migrations.exceptions.MigrationError`

**Solutions**:
```bash
# Show migration status
python manage.py showmigrations

# Fake migration (if needed)
python manage.py migrate --fake <app> <migration>

# Rollback migration
python manage.py migrate <app> <previous_migration>
```

### Redis Connection Errors

**Symptoms**: `redis.exceptions.ConnectionError`

**Solutions**:
```bash
# Ensure Redis is running
docker compose ps redis

# Check Redis logs
docker compose logs redis

# Restart Redis
docker compose restart redis

# Clear Redis cache
docker compose exec redis redis-cli FLUSHALL
```

### MinIO Connection Errors

**Symptoms**: `botocore.exceptions.ClientError: Unable to locate credentials`

**Solutions**:
```bash
# Ensure MinIO is running
docker compose ps minio

# Check MinIO logs
docker compose logs minio

# Verify credentials
echo $MINIO_ACCESS_KEY
echo $MINIO_SECRET_KEY

# Test MinIO connection
curl http://localhost:9000/minio/health/live
```

### Worker Not Processing Jobs

**Symptoms**: Jobs stuck in queue

**Solutions**:
```bash
# Check worker is running
docker compose ps worker-service

# Check worker logs
docker compose logs worker-service

# Restart worker
docker compose restart worker-service

# Check queue status
docker compose exec api-service python manage.py rqstats
```

### Workflow Engine Not Processing

**Symptoms**: Workflows stuck in DRAFT or RUNNING

**Solutions**:
```bash
# Check workflow engine is running
docker compose ps workflow-engine-service

# Check workflow engine logs
docker compose logs workflow-engine-service

# Restart workflow engine
docker compose restart workflow-engine-service

# Check workflow status
docker compose exec api-service python manage.py shell
>>> from hub.apps.orchestration.models import WorkflowInstance
>>> WorkflowInstance.objects.filter(status='RUNNING').count()
```

### API 500 Errors

**Symptoms**: Internal server errors

**Solutions**:
```bash
# Check API logs
docker compose logs api-service

# Check Django logs
docker compose exec api-service tail -f /var/log/django.log

# Enable debug mode (development only)
export DEBUG=True
docker compose restart api-service

# Check database integrity
python manage.py check --deploy
```

### Authentication Errors

**Symptoms**: `401 Unauthorized` or `403 Forbidden`

**Solutions**:
```bash
# Check JWT secret key
echo $SECRET_KEY

# Verify token
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/auth/me/

# Check user permissions
docker compose exec api-service python manage.py shell
>>> from hub.apps.users.models import User
>>> user = User.objects.get(email='user@example.com')
>>> user.is_active
>>> user.roles.all()
```

### CORS Errors

**Symptoms**: `Access-Control-Allow-Origin` errors in browser

**Solutions**:
```bash
# Check CORS settings
grep CORS_ALLOWED_ORIGINS hub/settings.py

# Add origin to CORS_ALLOWED_ORIGINS
export CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
docker compose restart api-service
```

### Performance Issues

**Symptoms**: Slow API responses, timeouts

**Solutions**:
```bash
# Check database queries
python manage.py shell
>>> from django.db import connection
>>> len(connection.queries)

# Check Redis cache hit rate
docker compose exec redis redis-cli info stats | grep keyspace

# Check service resource usage
docker stats

# Check database connections
docker compose exec postgres psql -U hub -d hub -c "SELECT count(*) FROM pg_stat_activity;"
```

## Log Analysis

### View Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs api-service

# Follow logs
docker compose logs -f api-service

# Last 100 lines
docker compose logs --tail=100 api-service

# Since timestamp
docker compose logs --since 2025-01-15T10:00:00 api-service
```

### Log Locations

- **Django**: `/var/log/django.log` (if configured)
- **Application**: `docker compose logs`
- **System**: `/var/log/syslog` (Linux)

### Common Log Patterns

```bash
# Errors
docker compose logs | grep -i error

# Warnings
docker compose logs | grep -i warning

# Database queries
docker compose logs api-service | grep "SELECT\|INSERT\|UPDATE\|DELETE"
```

## Database Issues

### Database Locked

```bash
# Check for locks
docker compose exec postgres psql -U hub -d hub -c "SELECT * FROM pg_locks WHERE NOT granted;"

# Kill blocking queries
docker compose exec postgres psql -U hub -d hub -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';"
```

### Database Corruption

```bash
# Check database integrity
docker compose exec postgres psql -U hub -d hub -c "VACUUM ANALYZE;"

# Reindex database
docker compose exec postgres psql -U hub -d hub -c "REINDEX DATABASE hub;"
```

### Database Size

```bash
# Check database size
docker compose exec postgres psql -U hub -d hub -c "SELECT pg_size_pretty(pg_database_size('hub'));"

# Check table sizes
docker compose exec postgres psql -U hub -d hub -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

## Network Issues

### Service Communication

```bash
# Test service connectivity
docker compose exec api-service curl http://semantic-service:8081/health
docker compose exec api-service curl http://dq-service:8083/health
docker compose exec api-service curl http://compliance-service:8082/health
```

### DNS Resolution

```bash
# Test DNS
docker compose exec api-service nslookup semantic-service
docker compose exec api-service nslookup postgres
```

## API Endpoint Troubleshooting

### Compliance Endpoints

**Symptoms**: Compliance run endpoints returning errors or not responding

**Solutions**:
```bash
# Check compliance service health
docker compose exec api-service curl http://compliance-service:8082/health

# Test compliance runs endpoint
curl -X GET http://localhost:8000/api/v1/compliance/runs/ \
  -H "Authorization: Bearer <token>"

# Check compliance run status
curl -X GET http://localhost:8000/api/v1/compliance/runs/{run-id}/ \
  -H "Authorization: Bearer <token>"

# Check compliance run results
curl -X GET http://localhost:8000/api/v1/compliance/runs/{run-id}/results/ \
  -H "Authorization: Bearer <token>"

# Check compliance service logs
docker compose logs compliance-service

# Verify compliance service connectivity
docker compose exec api-service curl -v http://compliance-service:8082/health
```

**Common Issues**:
- **404 Not Found**: Verify endpoint uses `/api/v1/compliance/runs/` (not `/compliance-runs/`)
- **500 Internal Server Error**: Check compliance service logs
- **Timeout**: Verify compliance service is running and accessible
- **401 Unauthorized**: Check authentication token

### Data Quality Endpoints

**Symptoms**: DQ run endpoints returning errors or not responding

**Solutions**:
```bash
# Check DQ service health
docker compose exec api-service curl http://dq-service:8083/health

# Test DQ runs endpoint
curl -X GET http://localhost:8000/api/v1/dq/runs/ \
  -H "Authorization: Bearer <token>"

# Check DQ run status
curl -X GET http://localhost:8000/api/v1/dq/runs/{run-id}/ \
  -H "Authorization: Bearer <token>"

# Check DQ run results
curl -X GET http://localhost:8000/api/v1/dq/runs/{run-id}/results/ \
  -H "Authorization: Bearer <token>"

# Check DQ service logs
docker compose logs dq-service

# Verify DQ service connectivity
docker compose exec api-service curl -v http://dq-service:8083/health
```

**Common Issues**:
- **404 Not Found**: Verify endpoint uses `/api/v1/dq/runs/` (not `/dq-runs/`)
- **500 Internal Server Error**: Check DQ service logs
- **Timeout**: Verify DQ service is running and accessible
- **401 Unauthorized**: Check authentication token

### Endpoint Pattern Verification

**Verify Standardized Endpoints**:
```bash
# Compliance endpoints (correct pattern)
curl http://localhost:8000/api/v1/compliance/runs/
curl http://localhost:8000/api/v1/compliance/runs/{id}/
curl http://localhost:8000/api/v1/compliance/runs/{id}/results/

# DQ endpoints (correct pattern)
curl http://localhost:8000/api/v1/dq/runs/
curl http://localhost:8000/api/v1/dq/runs/{id}/
curl http://localhost:8000/api/v1/dq/runs/{id}/results/
```

**Note**: Old endpoint patterns (e.g. paths containing `compliance-runs` or `dq-runs`) are deprecated and return `404 Not Found`. Always use the standardized patterns (`/runs/`).

---

## Resource Issues

### Memory Issues

```bash
# Check memory usage
docker stats

# Check system memory
free -h

# Restart services to free memory
docker compose restart
```

### Disk Space

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up Docker
docker system prune -a
```

## Recovery Procedures

### Service Recovery

```bash
# Restart all services
docker compose restart

# Rebuild and restart
docker compose build
docker compose up -d
```

### Database Recovery

```bash
# Backup database
docker compose exec postgres pg_dump -U hub hub > backup.sql

# Restore database
docker compose exec -T postgres psql -U hub hub < backup.sql
```

### Data Recovery

```bash
# List backups
ls -lh backups/

# Restore from backup
./scripts/restore_backup.sh <backup-file>
```

## Getting Help

### Debug Information

When reporting issues, include:

1. **Service logs**: `docker compose logs <service>`
2. **Service status**: `docker compose ps`
3. **Environment**: `docker compose config`
4. **Error messages**: Full error traceback
5. **Steps to reproduce**: Detailed steps

### Support Channels

- **Documentation**: Check relevant documentation
- **Runbooks**: See [Runbooks](runbooks/README.md)
- **Issue Tracker**: Report bugs and issues

## Related Documentation

- [Runbooks](runbooks/README.md) - Operational runbooks
- [Monitoring Guide](MONITORING.md) - Monitoring and observability
- [Deployment Guide](DOCKER_COMPOSE_DEPLOYMENT.md) - Deployment procedures

