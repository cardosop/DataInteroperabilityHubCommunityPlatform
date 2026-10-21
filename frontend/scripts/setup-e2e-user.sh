#!/bin/bash
# Setup E2E Test User
# Creates a test user for frontend E2E tests

set -e

API_URL="${VITE_API_BASE_URL:-http://localhost:8000/api/v1}"

echo "Setting up E2E test user..."

# Try to register user
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/auth/register/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "e2e_test@example.com",
    "password": "testpass123",
    "name": "E2E Test User"
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 201 ]; then
  echo "✅ Test user created successfully"
  exit 0
elif [ "$HTTP_CODE" -eq 400 ]; then
  # User might already exist - try to login to verify
  LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/auth/login/" \
    -H "Content-Type: application/json" \
    -d '{
      "email": "e2e_test@example.com",
      "password": "testpass123"
    }')
  
  LOGIN_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
  if [ "$LOGIN_CODE" -eq 200 ]; then
    echo "✅ Test user already exists and can login"
    exit 0
  else
    echo "⚠️  Test user exists but login failed. You may need to reset the password."
    echo "   Response: $LOGIN_RESPONSE"
    exit 1
  fi
else
  echo "❌ Failed to create test user. HTTP $HTTP_CODE"
  echo "   Response: $BODY"
  exit 1
fi
