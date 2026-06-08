# Troubleshooting Guide

## API Endpoint Troubleshooting

### Compliance endpoints return 404
Verify that you are using the standardized pattern: `/api/v1/compliance/runs/`. The legacy `/compliance-runs/` pattern is no longer supported.

### DQ endpoints return 404
Verify that you are using the standardized pattern: `/api/v1/dq/runs/`. The legacy `/dq-runs/` pattern is no longer supported.

### Authentication errors
Ensure your JWT is valid and not expired. Check the `exp` claim in the token payload.

### Rate limiting (HTTP 429)
Reduce request frequency or contact support to increase your tenant's rate limit.

## Common issues

### Database connectivity
Check that PostgreSQL is running and `POSTGRES_HOST` is correctly set.

### Redis connectivity
Check that Redis is running and `REDIS_URL` is correctly set.
