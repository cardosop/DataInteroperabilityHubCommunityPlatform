# Database Recovery Troubleshooting Guide

## Overview

This document describes common database startup issues related to PostgreSQL crash recovery and how to resolve them.

## Problem: Database Container Stuck in "Starting Up" State

### Symptoms

- Database container is running but marked as "unhealthy"
- Health checks are failing with "rejecting connections"
- Logs show: `FATAL: the database system is starting up`
- Logs show: `LOG: syncing data directory (fsync), elapsed time: XXX s`
- Recovery process taking an extremely long time (10+ minutes)

### Root Causes

1. **Unclean Shutdown**: Database was not shut down cleanly (crash, power loss, forced stop)
2. **Large WAL Files**: Significant amount of Write-Ahead Log (WAL) files need to be replayed
3. **Slow Disk I/O**: Disk performance issues causing slow fsync operations
4. **Insufficient Resources**: Container resource constraints

### Diagnosis

#### Check Container Status
```bash
docker ps -a | grep postgres
docker inspect hub-postgres --format='{{json .State.Health}}' | python3 -m json.tool
```

#### Check Database Logs
```bash
docker logs hub-postgres --tail 100
```

Look for:
- `database system was interrupted; last known up at [timestamp]`
- `syncing data directory (fsync), elapsed time: XXX s`
- Recovery progress messages

#### Check WAL Directory Size
```bash
docker exec hub-postgres ls -lh /var/lib/postgresql/data/pg_wal/
docker exec hub-postgres du -sh /var/lib/postgresql/data/pg_wal/
```

#### Use Monitoring Script
```bash
./scripts/monitor_database_recovery.sh hub-postgres
./scripts/monitor_database_recovery.sh hub-postgres --watch  # Continuous monitoring
```

### Solutions

#### Solution 1: Wait for Recovery to Complete (Recommended)

If the database is actively recovering, the best approach is to wait for it to complete. The recovery process is necessary to ensure data consistency.

**Optimized Configuration** (Already Applied):
- Increased health check timeout to 30 minutes (`start_period: 1800s`)
- Increased health check retries to 30
- Optimized PostgreSQL settings for faster recovery:
  - `max_wal_size=4GB`: Allows larger WAL before checkpoint
  - `checkpoint_timeout=15min`: Longer checkpoint intervals
  - `checkpoint_completion_target=0.9`: Spreads checkpoint I/O
  - `wal_compression=on`: Reduces WAL size
  - `checkpoint_flush_after=256kB`: Optimizes flush behavior

**Monitor Progress**:
```bash
# Single check
./scripts/monitor_database_recovery.sh hub-postgres

# Continuous monitoring
./scripts/monitor_database_recovery.sh hub-postgres --watch
```

#### Solution 2: Check Disk I/O Performance

If recovery is taking unusually long, check disk performance:

```bash
# Check disk I/O stats
iostat -x 1 5

# Check disk space
df -h

# Check Docker volume location
docker volume inspect datainteroperabilityhub_pgdata
```

If disk I/O is the bottleneck:
- Consider moving database volume to faster storage (SSD)
- Check for other processes consuming disk I/O
- Review Docker volume driver settings

#### Solution 3: Restart with Optimized Settings

If the current recovery is taking too long and you need immediate access:

1. **Stop the container**:
   ```bash
   docker stop hub-postgres
   ```

2. **Restart with optimized configuration** (already in docker-compose.yml):
   ```bash
   docker compose up -d postgres
   ```

3. **Monitor recovery**:
   ```bash
   ./scripts/monitor_database_recovery.sh hub-postgres --watch
   ```

#### Solution 4: Prevent Future Issues

**Proper Shutdown Procedures**:
- Always use `docker compose down` or `docker stop` (not `docker kill`)
- Allow services to shut down gracefully
- Use health checks to ensure services are ready before stopping

**WAL Management**:
- Configure WAL archiving for production environments
- Set up regular backups to reduce recovery time
- Monitor WAL directory size

**Configuration** (Already Applied):
The `docker-compose.yml` now includes optimized PostgreSQL settings for faster recovery and better performance.

### Prevention

1. **Regular Backups**: Ensure regular database backups are taken
2. **Graceful Shutdowns**: Always shut down containers gracefully
3. **Monitoring**: Set up alerts for database health issues
4. **Resource Allocation**: Ensure adequate resources (CPU, memory, disk I/O) for database container
5. **WAL Archiving**: Configure WAL archiving in production to prevent large WAL accumulation

### Configuration Details

The optimized PostgreSQL configuration in `docker-compose.yml` includes:

```yaml
command: >
  postgres
  -c max_wal_size=4GB
  -c checkpoint_timeout=15min
  -c checkpoint_completion_target=0.9
  -c wal_buffers=16MB
  -c shared_buffers=256MB
  -c maintenance_work_mem=256MB
  -c checkpoint_flush_after=256kB
  -c wal_compression=on
  -c max_connections=200
```

**Health Check Configuration**:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-hub}"]
  interval: 30s
  timeout: 10s
  retries: 30
  start_period: 1800s  # 30 minutes to allow for recovery
```

### Recovery Time Estimates

Recovery time depends on:
- **WAL Size**: Larger WAL files = longer recovery
- **Disk I/O**: Faster disks = faster recovery
- **Database Size**: Larger databases may take longer
- **System Load**: Other processes can slow recovery

**Typical Recovery Times**:
- Small WAL (< 100MB): 1-5 minutes
- Medium WAL (100MB - 1GB): 5-15 minutes
- Large WAL (1GB - 5GB): 15-60 minutes
- Very Large WAL (> 5GB): 1+ hours

### Troubleshooting Commands

```bash
# Check container status
docker ps -a | grep postgres

# Check health status
docker inspect hub-postgres --format='{{json .State.Health}}' | python3 -m json.tool

# View logs
docker logs hub-postgres --tail 100 -f

# Check recovery progress
./scripts/monitor_database_recovery.sh hub-postgres

# Check WAL files
docker exec hub-postgres ls -lh /var/lib/postgresql/data/pg_wal/

# Check disk space
df -h
docker system df

# Check container resources
docker stats hub-postgres --no-stream

# Test database connection
docker exec hub-postgres pg_isready -U hub

# Check if database is in recovery
docker exec hub-postgres psql -U hub -d hub -c "SELECT pg_is_in_recovery();"
```

### Related Files

- `docker-compose.yml`: Main database configuration
- `scripts/monitor_database_recovery.sh`: Recovery monitoring script
- `scripts/init-db.sql`: Database initialization script

### Additional Resources

- [PostgreSQL Recovery Documentation](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [PostgreSQL WAL Configuration](https://www.postgresql.org/docs/current/wal-configuration.html)
- [Docker Health Checks](https://docs.docker.com/engine/reference/builder/#healthcheck)
