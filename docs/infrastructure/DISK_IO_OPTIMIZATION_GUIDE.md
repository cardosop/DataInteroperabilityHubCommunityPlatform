# Disk I/O Optimization Guide for PostgreSQL

## Current Situation

Based on the disk I/O diagnosis:

### Findings
- **Docker Volume Location**: `/var/lib/docker/volumes/datainteroperabilityhub_pgdata/_data`
- **Storage Device**: `/dev/sda4` (root filesystem)
- **Disk Utilization**: High (110.90% during I/O operations - indicates saturation)
- **Mount Options**: Using `relatime` (not optimized for database workloads)
- **Recovery Time**: 55+ minutes for 1.8GB WAL files (extremely slow)

### Root Cause
The slow recovery is primarily due to:
1. **Slow disk I/O**: The disk is saturated during fsync operations
2. **Suboptimal mount options**: Using `relatime` instead of `noatime`
3. **Large WAL files**: 1.8GB of WAL requiring extensive fsync operations

## Optimization Options

### Option 1: Optimize Mount Options (Quick Fix)

**Current**: Using `relatime`
**Recommended**: Use `noatime` to reduce write operations

**Steps**:
1. Edit `/etc/fstab`:
   ```bash
   sudo nano /etc/fstab
   ```
2. Find the line for `/` (root filesystem) and add `noatime`:
   ```
   UUID=... / ext4 defaults,noatime 0 1
   ```
3. Remount (without reboot):
   ```bash
   sudo mount -o remount,noatime /
   ```

**Note**: This requires root access and may require a reboot for permanent changes.

### Option 2: Move Docker Volume to Faster Storage (Best Performance)

If you have an SSD available (like `/dev/nvme0n1`), move the Docker volume there.

**Steps**:

1. **Stop PostgreSQL**:
   ```bash
   docker compose stop postgres
   ```

2. **Backup current volume**:
   ```bash
   docker run --rm \
     -v datainteroperabilityhub_pgdata:/data \
     -v $(pwd):/backup \
     alpine tar czf /backup/pgdata-backup-$(date +%Y%m%d).tar.gz -C /data .
   ```

3. **Create new directory on SSD** (if available):
   ```bash
   sudo mkdir -p /mnt/ssd/postgres-data
   sudo chown -R 999:999 /mnt/ssd/postgres-data  # PostgreSQL UID/GID
   ```

4. **Update docker-compose.yml** to use bind mount:
   ```yaml
   volumes:
     - /mnt/ssd/postgres-data:/var/lib/postgresql/data
   ```

5. **Restore data**:
   ```bash
   docker run --rm \
     -v /mnt/ssd/postgres-data:/data \
     -v $(pwd):/backup \
     alpine sh -c "cd /data && tar xzf /backup/pgdata-backup-YYYYMMDD.tar.gz"
   ```

6. **Start PostgreSQL**:
   ```bash
   docker compose up -d postgres
   ```

### Option 3: Configure Docker to Use Different Storage Location

**Steps**:

1. **Stop Docker**:
   ```bash
   sudo systemctl stop docker
   ```

2. **Edit Docker daemon configuration** (`/etc/docker/daemon.json`):
   ```json
   {
     "data-root": "/mnt/ssd/docker"
   }
   ```

3. **Move existing Docker data** (if needed):
   ```bash
   sudo mv /var/lib/docker /mnt/ssd/docker
   ```

4. **Start Docker**:
   ```bash
   sudo systemctl start docker
   ```

**Warning**: This affects all Docker containers, not just PostgreSQL.

### Option 4: Optimize PostgreSQL Configuration (Already Applied)

The following optimizations are already in `docker-compose.yml`:
- `checkpoint_timeout=15min`: Longer checkpoint intervals
- `checkpoint_completion_target=0.9`: Spreads checkpoint I/O
- `wal_compression=on`: Reduces WAL size
- `checkpoint_flush_after=256kB`: Optimizes flush behavior

### Option 5: Add `noatime` to Docker Volume Mount (Recommended)

If you can't modify the root filesystem, you can optimize the Docker volume mount.

**Update docker-compose.yml**:
```yaml
postgres:
  volumes:
    - pgdata:/var/lib/postgresql/data:noatime
```

**Note**: This requires Docker to support mount options, which may need additional configuration.

## Performance Impact Estimates

### Current Performance
- **Recovery Time**: 55+ minutes for 1.8GB WAL
- **Disk I/O**: Saturated (110% utilization)
- **Expected**: 15-30 minutes for similar WAL size

### After Optimization (Expected)
- **With `noatime`**: 20-30% faster recovery
- **On SSD**: 5-10x faster recovery (5-10 minutes for 1.8GB WAL)
- **Combined optimizations**: 10-15x faster recovery

## Monitoring

Use the diagnostic script to monitor improvements:
```bash
./scripts/diagnose_disk_io.sh
```

## Recommendations Priority

1. **Immediate** (Quick wins):
   - Add `noatime` mount option (if possible)
   - Monitor current recovery completion

2. **Short-term** (This week):
   - Move Docker volume to SSD if available
   - Optimize root filesystem mount options

3. **Long-term** (This month):
   - Set up WAL archiving to prevent large WAL accumulation
   - Implement regular backups
   - Consider dedicated database storage

## Related Documentation

- [Database Recovery Troubleshooting](./DATABASE_RECOVERY_TROUBLESHOOTING.md)
- [Database Recovery Status](./DATABASE_RECOVERY_STATUS.md)
- `scripts/diagnose_disk_io.sh` - Disk I/O diagnostic script
