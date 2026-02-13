#!/bin/bash
# Script to start all Docker Compose services and monitor their status

set -e

cd "$(dirname "$0")/.."

echo "========================================="
echo "Starting all Docker Compose services..."
echo "========================================="

# Start all services in detached mode
echo "Starting services (this may take several minutes for first-time builds)..."
docker compose up -d --remove-orphans

echo ""
echo "Waiting for services to start..."
sleep 10

echo ""
echo "========================================="
echo "Service Status:"
echo "========================================="
docker compose ps

echo ""
echo "========================================="
echo "Services by Status:"
echo "========================================="
echo ""
echo "Healthy services:"
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(healthy|Up.*healthy)" || echo "None yet"

echo ""
echo "Starting services:"
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(starting|Up.*starting)" || echo "None"

echo ""
echo "Unhealthy/Exited services:"
docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(unhealthy|Exited|Restarting)" || echo "None"

echo ""
echo "========================================="
echo "To monitor logs: docker compose logs -f [service-name]"
echo "To check status: docker compose ps"
echo "To view all services: docker compose ps -a"
echo "========================================="
