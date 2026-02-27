#!/usr/bin/env bash
# Verify test stack is up and reachable.
# Use after: docker compose -f docker-compose.test.yml --env-file .env.test up -d
# Exit 0 if API and MailHog respond; exit 1 otherwise.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8001}"
MAILHOG_URL="${MAILHOG_URL:-http://localhost:8025}"

echo "Verifying test stack..."
echo "  API:      ${API_URL}"
echo "  MailHog:  ${MAILHOG_URL}"

if curl -sf "${API_URL}/health/" > /dev/null; then
  echo "  ✓ API health OK"
else
  echo "  ✗ API health failed"
  exit 1
fi

if curl -sf "${MAILHOG_URL}/" > /dev/null; then
  echo "  ✓ MailHog OK"
else
  echo "  ✗ MailHog failed"
  exit 1
fi

echo "Test stack verified."
