# API Gateway Service

FastAPI service that provides API Gateway functionality for the Data Interoperability Hub.

## Features

- **Request Routing**: Routes requests to backend services
- **API Key Authentication**: Validates API keys using Django ORM
- **Rate Limiting**: Redis-based rate limiting with sliding window algorithm
  - Per-tier limits (Free: 1000 req/hour, Pro: 10000 req/hour, Enterprise: unlimited)
  - Per-tenant limits (configurable)
  - Per-user/API-key limits (configurable)
- **Request/Response Logging**: Structured logging with request IDs
- **Distributed Tracing**: OpenTelemetry integration for request tracing
- **Error Handling**: Proper error responses with request IDs
- **Metrics**: Prometheus metrics endpoint

## Architecture

The API Gateway sits between clients and backend services, handling:
1. API key authentication
2. Rate limiting checks
3. Request forwarding to backend services
4. Response transformation with rate limit headers
5. Error handling and logging

## Configuration

Environment variables:

- `REDIS_CACHE_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `BACKEND_SERVICE_URL`: Backend service URL (default: `http://api-service:8000`)
- `PORT`: Service port (default: `8088`)
- `OPENTELEMETRY_ENABLED`: Enable OpenTelemetry tracing (default: `false`)
- `JAEGER_AGENT_HOST`: Jaeger agent host (default: `jaeger`)
- `JAEGER_AGENT_PORT`: Jaeger agent port (default: `6831`)

## API Key Authentication

API keys can be provided in two ways:

1. **Authorization Header**: `Authorization: ApiKey <key>`
2. **X-API-Key Header**: `X-API-Key: <key>`

## Rate Limiting

Rate limits are enforced at three levels (all must pass):

1. **Tier Limit**: Based on API tier (FREE, PRO, ENTERPRISE)
2. **Tenant Limit**: Configurable per tenant (optional)
3. **API Key Limit**: Configurable per API key (optional)

Rate limit information is returned in response headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in window
- `X-RateLimit-Reset`: Unix timestamp when limit resets
- `Retry-After`: Seconds until retry is allowed

## Running the Service

### Development

```bash
cd services/api-gateway
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8088 --reload
```

### Docker

```bash
docker build -t api-gateway -f services/api-gateway/Dockerfile .
docker run -p 8088:8088 api-gateway
```

### Docker Compose

The service is included in `docker-compose.yml`:

```bash
docker-compose up api-gateway
```

## Testing

### Unit Tests

```bash
pytest tests/ -m unit
```

### Integration Tests

```bash
pytest tests/ -m integration
```

### E2E Tests

```bash
pytest tests/ -m e2e
```

### All Tests

```bash
pytest tests/
```

## Endpoints

- `GET /health`: Health check endpoint
- `GET /metrics`: Prometheus metrics endpoint
- `GET /`: Service information
- `* /api/v1/*`: Proxied to backend service

## Dependencies

- FastAPI: Web framework
- Redis: Rate limiting storage
- Django ORM: Database access for API key validation
- OpenTelemetry: Distributed tracing
- Prometheus: Metrics collection

## Error Responses

All error responses include:
- `error`: Error message
- `request_id`: Unique request ID for tracing

Common error codes:
- `401 Unauthorized`: Invalid or missing API key
- `429 Too Many Requests`: Rate limit exceeded
- `502 Bad Gateway`: Backend service error
- `504 Gateway Timeout`: Backend service timeout
- `500 Internal Server Error`: Gateway error
