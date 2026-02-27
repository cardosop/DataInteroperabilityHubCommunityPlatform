#!/usr/bin/env bash
# Reset postgres-test volume (removes old data, fresh start)
# Use when postgres-test is slow to start due to old/corrupt data restoration.
# Uses .env.test so postgres initializes with hub_test/hub_test (avoids .env's hub/hub).
set -e
cd "$(dirname "$0")/.."
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
ENV_FILE="${ENV_FILE:-.env.test}"

echo "Stopping test stack..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop

echo "Removing postgres-test container (if exists)..."
docker rm -f hub-test-postgres 2>/dev/null || true

echo "Removing postgres-test-data volume..."
docker volume rm datainteroperabilityhub_postgres-test-data

echo "Starting postgres-test (with $ENV_FILE for hub_test credentials)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d postgres-test

echo "Waiting for postgres-test to be healthy..."
until docker compose -f "$COMPOSE_FILE" exec -T postgres-test pg_isready -U hub_test -d hub_test -t 5 2>/dev/null; do
  echo "  Waiting for postgres..."
  sleep 3
done

echo "Starting rest of test stack..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

echo "Done. Postgres-test volume reset and stack restarted."
