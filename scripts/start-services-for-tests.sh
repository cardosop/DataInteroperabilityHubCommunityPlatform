#!/bin/bash
# Script to start all services required for integration tests

set -e

echo "Starting services for integration tests..."

# Start infrastructure services
echo "Starting infrastructure services (postgres, redis, minio, fuseki)..."
docker-compose up -d postgres redis minio fuseki

# Wait for infrastructure to be ready
echo "Waiting for infrastructure services to be ready..."
sleep 5

# Start microservices
echo "Starting microservices..."
docker-compose up -d datacontract-service dq-service compliance-service semantic-service

# Wait for services to be healthy
echo "Waiting for services to become healthy..."
timeout=60

for service in datacontract-service:8080 dq-service:8083 compliance-service:8082 semantic-service:8081; do
    name=${service%%:*}
    port=${service##*:}
    echo "Waiting for $name..."
    
    for i in $(seq 1 $timeout); do
        if docker-compose exec -T $name curl -f http://localhost:$port/health > /dev/null 2>&1 || \
           curl -f http://localhost:$port/health > /dev/null 2>&1; then
            echo "✅ $name is healthy"
            break
        fi
        if [ $i -eq $timeout ]; then
            echo "❌ $name failed to become healthy after $timeout seconds"
            docker-compose logs $name
            exit 1
        fi
        sleep 1
    done
done

echo "✅ All services are healthy and ready for testing"

