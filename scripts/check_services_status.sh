#!/bin/bash
# Quick script to check Docker Compose services status

cd "$(dirname "$0")/.."

echo "========================================="
echo "Docker Compose Services Status"
echo "========================================="
echo ""

echo "Total services defined: $(docker compose config --services | wc -l)"
echo "Services running: $(docker compose ps --format '{{.Status}}' | grep -c 'Up')"
echo ""

echo "Healthy services:"
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep "healthy" || echo "None"

echo ""
echo "Starting/Unhealthy services:"
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(starting|unhealthy)" || echo "None"

echo ""
echo "Stopped/Exited services:"
docker compose ps -a --format "table {{.Name}}\t{{.Status}}" | grep -E "(Exited|Stopped|Created)" | head -10 || echo "None"

echo ""
echo "========================================="
echo "Key Infrastructure Services:"
echo "========================================="
docker compose ps postgres redis-cache redis-queue redis-events redis-channels minio fuseki jaeger --format "table {{.Name}}\t{{.Status}}"

echo ""
echo "========================================="
echo "Application Services:"
echo "========================================="
docker compose ps api-service worker-service semantic-service workflow-engine-service --format "table {{.Name}}\t{{.Status}}"
