# Docker Performance Optimization Guide

This guide provides recommendations and scripts for optimizing Docker performance, particularly for Prefect flow runs that use Docker workers.

## Quick Start

Run the optimization script regularly:

```bash
# Standard cleanup (safe, doesn't remove volumes)
./scripts/optimize-docker-performance.sh

# Aggressive cleanup (removes unused volumes - use with caution)
./scripts/optimize-docker-performance.sh --aggressive

# Dry run (preview what would be cleaned)
./scripts/optimize-docker-performance.sh --dry-run
```

## Common Performance Issues

### Issue: Prefect Flow Runs Timing Out

**Symptoms:**
- Prefect flow runs fail with `ReadTimeout` errors
- Docker container creation takes >60 seconds
- E2E tests timeout waiting for flow runs to complete

**Root Causes:**
1. Docker daemon is slow or overloaded
2. Too many concurrent Docker operations
3. Unused Docker resources consuming disk space
4. Docker socket timeout too low

**Solutions:**

1. **Run Docker cleanup:**
   ```bash
   ./scripts/optimize-docker-performance.sh
   ```

2. **Restart Docker daemon** (if you have sudo access):
   ```bash
   sudo systemctl restart docker
   ```

3. **Monitor Docker performance:**
   ```bash
   docker stats --no-stream
   docker system df
   ```

## Docker Daemon Configuration

### Optimize `/etc/docker/daemon.json`

Create or update `/etc/docker/daemon.json` with the following configuration:

```json
{
  "max-concurrent-downloads": 10,
  "max-concurrent-uploads": 10,
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-ulimits": {
    "nofile": {
      "Hard": 64000,
      "Name": "nofile",
      "Soft": 64000
    }
  }
}
```

**Apply changes:**
```bash
sudo systemctl restart docker
```

**Note:** Requires sudo/root access. If you don't have access, ask your system administrator.

## Docker Compose Configuration

### Prefect Worker Docker Configuration

The `prefect-worker-docker` service in `docker-compose.yml` is configured with:

1. **Docker socket timeouts:**
   - `DOCKER_CLIENT_TIMEOUT`: 120 seconds (default)
   - `DOCKER_READ_TIMEOUT`: 120 seconds (default)

2. **Concurrent flow run limit:**
   - `PREFECT_WORKER_LIMIT`: 2 (default) - limits concurrent flow runs to reduce Docker daemon load

**Customize timeouts:**
```bash
# In .env.dev or docker-compose.yml
DOCKER_CLIENT_TIMEOUT=180
DOCKER_READ_TIMEOUT=180
PREFECT_WORKER_LIMIT=1  # Reduce to 1 for slower systems
```

## Regular Maintenance

### Daily/Weekly Cleanup

Run the optimization script regularly:

```bash
# Weekly standard cleanup
./scripts/optimize-docker-performance.sh

# Monthly aggressive cleanup (removes unused volumes)
./scripts/optimize-docker-performance.sh --aggressive
```

### Manual Cleanup Commands

If you prefer manual cleanup:

```bash
# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -af

# Remove unused volumes (be careful!)
docker volume prune -f

# System-wide prune
docker system prune -af
```

## Monitoring Docker Performance

### Check Disk Usage

```bash
docker system df
```

**Output shows:**
- Images disk usage
- Containers disk usage
- Volumes disk usage
- Build cache disk usage

### Monitor Resource Usage

```bash
# Real-time stats
docker stats

# One-time snapshot
docker stats --no-stream
```

### Check Docker Daemon Health

```bash
docker info | grep -E "Server Version|Storage Driver|Logging Driver"
```

## E2E Test Timeouts

### Scheduled Export E2E Tests

The scheduled export E2E tests have been configured with increased timeouts to handle Docker daemon slowness:

- **Run completion timeout:** 3 minutes (was 2 minutes)
- **Test timeout:** 4 minutes (was 3 minutes)

**Location:** `frontend/e2e/journeys/scheduled-export/scheduled-export-journey.spec.ts`

If tests still timeout, consider:

1. Running Docker cleanup before tests
2. Reducing `PREFECT_WORKER_LIMIT` to 1
3. Increasing test timeouts further (if needed)

## Troubleshooting

### Docker Daemon Not Responding

**Symptoms:**
- `docker ps` hangs
- `docker info` times out
- Prefect flow runs fail immediately

**Solutions:**

1. **Check Docker daemon status:**
   ```bash
   sudo systemctl status docker
   ```

2. **Restart Docker daemon:**
   ```bash
   sudo systemctl restart docker
   ```

3. **Check Docker logs:**
   ```bash
   sudo journalctl -u docker.service -n 100
   ```

### Prefect Flow Runs Failing with Timeout

**Symptoms:**
- Flow runs fail with `ReadTimeout: UnixHTTPConnectionPool(...) Read timed out`
- Container creation takes >60 seconds

**Solutions:**

1. **Increase Docker socket timeouts** (already configured in docker-compose.yml)
2. **Reduce concurrent flow runs** by setting `PREFECT_WORKER_LIMIT=1`
3. **Run Docker cleanup** to free resources
4. **Restart Docker daemon** if it's unresponsive

### High Disk Usage

**Symptoms:**
- `docker system df` shows high disk usage
- System running out of disk space

**Solutions:**

1. **Run aggressive cleanup:**
   ```bash
   ./scripts/optimize-docker-performance.sh --aggressive
   ```

2. **Remove specific unused resources:**
   ```bash
   # Remove unused images
   docker image prune -af
   
   # Remove unused volumes (be careful!)
   docker volume prune -f
   ```

3. **Check what's using space:**
   ```bash
   docker system df -v
   ```

## Best Practices

1. **Regular Cleanup:** Run `./scripts/optimize-docker-performance.sh` weekly
2. **Monitor Performance:** Check `docker stats` and `docker system df` regularly
3. **Limit Concurrency:** Use `PREFECT_WORKER_LIMIT` to prevent Docker daemon overload
4. **Increase Timeouts:** Configure appropriate timeouts for slow Docker daemons
5. **Restart When Needed:** Restart Docker daemon if it becomes unresponsive

## Related Documentation

- [Docker Compose Deployment Guide](DOCKER_COMPOSE_DEPLOYMENT.md)
- [Prefect Integration Service README](../services/prefect-integration/README.md)
- [E2E Testing Guide](../frontend/e2e/README.md)

## Scripts

- `scripts/optimize-docker-performance.sh` - Docker performance optimization script
- `scripts/cleanup-docker-compose.sh` - Docker Compose cleanup script
