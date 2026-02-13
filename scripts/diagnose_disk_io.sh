#!/bin/bash
# Script to diagnose disk I/O performance for PostgreSQL database
# Usage: ./scripts/diagnose_disk_io.sh

set -e

echo "=========================================="
echo "Disk I/O Performance Diagnosis"
echo "=========================================="
echo ""

# Check if iostat is available
if ! command -v iostat &> /dev/null; then
    echo "⚠️  iostat not found. Installing sysstat package..."
    echo "   Run: sudo apt-get install sysstat"
    echo ""
fi

# 1. Check disk space
echo "=== 1. Disk Space ==="
df -h | grep -E "(Filesystem|/dev/)" | head -5
echo ""

# 2. Check Docker volume location
echo "=== 2. Docker Volume Location ==="
VOLUME_NAME="datainteroperabilityhub_pgdata"
if docker volume inspect "$VOLUME_NAME" &>/dev/null; then
    VOLUME_INFO=$(docker volume inspect "$VOLUME_NAME" 2>/dev/null)
    MOUNTPOINT=$(echo "$VOLUME_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin)[0]['Mountpoint'])" 2>/dev/null || echo "unknown")
    echo "Volume: $VOLUME_NAME"
    echo "Mountpoint: $MOUNTPOINT"

    if [ "$MOUNTPOINT" != "unknown" ]; then
        # Find which device this is on
        DEVICE=$(df "$MOUNTPOINT" 2>/dev/null | tail -1 | awk '{print $1}' || echo "unknown")
        echo "Device: $DEVICE"

        # Check if it's on SSD or HDD
        if [ -e "/sys/block/$(basename "$DEVICE" | sed 's/[0-9]*$//')/queue/rotational" ]; then
            ROTATIONAL=$(cat "/sys/block/$(basename "$DEVICE" | sed 's/[0-9]*$//')/queue/rotational" 2>/dev/null || echo "unknown")
            if [ "$ROTATIONAL" = "0" ]; then
                echo "Storage Type: ✅ SSD"
            elif [ "$ROTATIONAL" = "1" ]; then
                echo "Storage Type: ⚠️  HDD (consider moving to SSD)"
            else
                echo "Storage Type: unknown"
            fi
        fi
    fi
else
    echo "⚠️  Volume '$VOLUME_NAME' not found"
fi
echo ""

# 3. Check current disk I/O stats
echo "=== 3. Current Disk I/O Statistics ==="
if command -v iostat &> /dev/null; then
    echo "Collecting I/O stats (5 seconds)..."
    iostat -x 1 5 2>/dev/null | tail -20 || echo "iostat not available"
else
    echo "⚠️  iostat not available. Install with: sudo apt-get install sysstat"
fi
echo ""

# 4. Check for processes consuming disk I/O
echo "=== 4. Top Disk I/O Consuming Processes ==="
if command -v iotop &> /dev/null; then
    echo "Running iotop (requires sudo)..."
    sudo iotop -b -n 1 -o -d 1 2>/dev/null | head -15 || echo "iotop not available or requires sudo"
elif command -v pidstat &> /dev/null; then
    echo "Checking process I/O with pidstat..."
    pidstat -d 1 1 2>/dev/null | head -20 || echo "pidstat not available"
else
    echo "⚠️  Install iotop or sysstat for process-level I/O monitoring"
    echo "   Run: sudo apt-get install iotop sysstat"
fi
echo ""

# 5. Check filesystem mount options
echo "=== 5. Filesystem Mount Options ==="
if [ -n "$MOUNTPOINT" ] && [ "$MOUNTPOINT" != "unknown" ]; then
    MOUNT_INFO=$(mount | grep "$(df "$MOUNTPOINT" 2>/dev/null | tail -1 | awk '{print $1}')" || echo "")
    if [ -n "$MOUNT_INFO" ]; then
        echo "Mount options:"
        echo "$MOUNT_INFO" | awk '{for(i=1;i<=NF;i++) if($i ~ /^\(/) print $i}'
        echo ""
        echo "Recommendations:"
        echo "  - Consider 'noatime' option to reduce write operations"
        echo "  - Consider 'nodiratime' option for directories"
        echo "  - For SSDs: 'discard' option for TRIM support"
    fi
fi
echo ""

# 6. Check Docker container I/O stats
echo "=== 6. PostgreSQL Container I/O Statistics ==="
CONTAINER_NAME="hub-postgres"
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container: $CONTAINER_NAME"
    docker stats "$CONTAINER_NAME" --no-stream --format "Block I/O: {{.BlockIO}}"
    echo ""

    # Check container resource limits
    MEM_LIMIT=$(docker inspect "$CONTAINER_NAME" --format='{{.HostConfig.Memory}}' 2>/dev/null || echo "unlimited")
    CPU_LIMIT=$(docker inspect "$CONTAINER_NAME" --format='{{.HostConfig.CpuQuota}}' 2>/dev/null || echo "unlimited")
    echo "Memory Limit: $MEM_LIMIT"
    echo "CPU Limit: $CPU_LIMIT"
else
    echo "⚠️  Container '$CONTAINER_NAME' is not running"
fi
echo ""

# 7. Check PostgreSQL I/O configuration
echo "=== 7. PostgreSQL I/O Configuration ==="
if docker exec "$CONTAINER_NAME" pg_isready -U hub >/dev/null 2>&1; then
    echo "PostgreSQL I/O settings:"
    docker exec "$CONTAINER_NAME" psql -U hub -d hub -c "
        SELECT name, setting, unit
        FROM pg_settings
        WHERE name IN (
            'checkpoint_timeout',
            'max_wal_size',
            'checkpoint_completion_target',
            'wal_buffers',
            'shared_buffers',
            'checkpoint_flush_after',
            'wal_compression'
        )
        ORDER BY name;
    " 2>/dev/null || echo "Cannot query PostgreSQL (still in recovery)"
else
    echo "⚠️  PostgreSQL is not accepting connections (still in recovery)"
    echo "Current configuration from docker-compose.yml:"
    echo "  - checkpoint_timeout: 15min"
    echo "  - max_wal_size: 4GB"
    echo "  - checkpoint_completion_target: 0.9"
    echo "  - wal_buffers: 16MB"
    echo "  - shared_buffers: 256MB"
    echo "  - checkpoint_flush_after: 256kB"
    echo "  - wal_compression: on"
fi
echo ""

# 8. Recommendations
echo "=== 8. Recommendations ==="
echo ""
echo "If disk I/O is slow:"
echo "  1. ✅ Move Docker volume to SSD storage"
echo "  2. ✅ Add 'noatime' mount option to reduce writes"
echo "  3. ✅ Ensure adequate memory for PostgreSQL buffers"
echo "  4. ✅ Consider increasing checkpoint_timeout if recovery is slow"
echo "  5. ✅ Monitor other processes consuming disk I/O"
echo ""
echo "To move Docker volume to different location:"
echo "  1. Stop PostgreSQL: docker compose stop postgres"
echo "  2. Backup volume: docker run --rm -v datainteroperabilityhub_pgdata:/data -v \$(pwd):/backup alpine tar czf /backup/pgdata-backup.tar.gz -C /data ."
echo "  3. Update docker-compose.yml to use bind mount to SSD location"
echo "  4. Restore data to new location"
echo ""
echo "To check current recovery progress:"
echo "  ./scripts/check_database_status.sh hub-postgres"
echo "  ./scripts/monitor_database_recovery.sh hub-postgres"
echo ""
