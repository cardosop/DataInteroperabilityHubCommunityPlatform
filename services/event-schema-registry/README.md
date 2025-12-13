# Event Schema Registry Service

The Event Schema Registry Service provides a REST API for managing and querying event schemas, including schema retrieval, event type discovery, and event data validation.

## Overview

The event schema registry service:
- Exposes REST API endpoints for event schema operations
- Provides schema retrieval for all event types
- Enables event data validation against schemas
- Supports event type discovery and categorization
- Manages schema version information

## Architecture

```
┌─────────────────────────────────────┐
│   Event Schema Registry Service     │
│   (FastAPI + Django)                │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  REST API Endpoints         │   │
│  │  - GET /event-types         │   │
│  │  - GET /event-types/{type}  │   │
│  │  - POST /validate           │   │
│  │  - GET /base-schema         │   │
│  │  - GET /categories          │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Event Schema System        │   │
│  │  - BASE_EVENT_SCHEMA        │   │
│  │  - EVENT_TYPE_SCHEMAS       │   │
│  │  - EventSchema validator    │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## API Endpoints

### Health Check

**GET /health**
- Returns service health status
- Response: `{"status": "healthy", "service": "event-schema-registry-service", "version": "...", "total_event_types": ...}`

**GET /metrics**
- Prometheus metrics endpoint
- Returns metrics in Prometheus format

### Event Type Discovery

**GET /event-types**
- List all registered event types
- Query parameters:
  - `category` (optional): Filter by category (e.g., 'contract', 'asset')
- Response: `EventTypesListResponse`

**GET /event-types/{event_type}**
- Get schema for a specific event type
- Response: `SchemaResponse` (404 if not found)

**GET /categories**
- Get list of all event categories
- Response: `{"categories": [...], "total": N}`

**GET /categories/{category}/event-types**
- Get all event types for a specific category
- Response: `EventTypesListResponse` (404 if category not found)

### Schema Retrieval

**GET /base-schema**
- Get base event schema
- Returns the base schema that all events must conform to
- Response: Base schema JSON

**GET /version**
- Get current event schema version
- Response: `{"version": "...", "total_event_types": N, "total_categories": N}`

**GET /version/{event_type}**
- Get schema version for a specific event type
- Response: `{"event_type": "...", "version": "...", "has_schema": true}`

### Event Validation

**POST /validate**
- Validate event data against event type schema
- Request body:
  ```json
  {
    "event_type": "contract.created",
    "data": {
      "contract_id": "uuid"
    },
    "event_version": "1.0.0"  // optional
  }
  ```
- Response: `ValidateEventResponse`

**POST /validate-full**
- Validate a complete event (including base fields)
- Request body: Complete event JSON
- Response: `ValidateEventResponse`

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EVENT_SCHEMA_REGISTRY_PORT` | `8091` | Service port |
| `DATABASE_URL` | - | PostgreSQL connection URL (for future schema persistence) |
| `DJANGO_SETTINGS_MODULE` | `hub.settings` | Django settings module |
| `SECRET_KEY` | - | Django secret key |
| `DEBUG` | `False` | Django debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ENVIRONMENT` | `development` | Environment name |

## Usage

### Running Locally

```bash
# Set environment variables
export DJANGO_SETTINGS_MODULE=hub.settings
export SECRET_KEY=dev-secret-key

# Run the service
uvicorn services.event-schema-registry.main:app --host 0.0.0.0 --port 8091
```

### Running with Docker Compose

The service is configured in `docker-compose.yml`:

```yaml
event-schema-registry-service:
  build:
    context: .
    dockerfile: services/event-schema-registry/Dockerfile
  ports:
    - "8091:8091"
  depends_on:
    - postgres
```

Start the service:

```bash
docker compose up event-schema-registry-service
```

### Example API Calls

**List all event types:**
```bash
curl http://localhost:8091/event-types
```

**Get schema for specific event type:**
```bash
curl http://localhost:8091/event-types/contract.created
```

**Validate event data:**
```bash
curl -X POST http://localhost:8091/validate \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "contract.created",
    "data": {
      "contract_id": "123e4567-e89b-12d3-a456-426614174000"
    }
  }'
```

**Get event categories:**
```bash
curl http://localhost:8091/categories
```

**Get event types for category:**
```bash
curl http://localhost:8091/categories/contract/event-types
```

**Get base schema:**
```bash
curl http://localhost:8091/base-schema
```

**Validate complete event:**
```bash
curl -X POST http://localhost:8091/validate-full \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "123e4567-e89b-12d3-a456-426614174000",
    "event_type": "contract.created",
    "event_version": "1.0.0",
    "timestamp": "2025-01-15T10:00:00Z",
    "source": {
      "service": "hub",
      "tenant_id": null
    },
    "data": {
      "contract_id": "123e4567-e89b-12d3-a456-426614174000"
    }
  }'
```

## Event Schema Structure

### Base Schema

All events must conform to the base schema:

```json
{
  "event_id": "uuid",
  "event_type": "domain.entity.action",
  "event_version": "1.0.0",
  "timestamp": "ISO 8601 datetime",
  "source": {
    "service": "string",
    "tenant_id": "uuid or null",
    "user_id": "uuid (optional)",
    "request_id": "string (optional)"
  },
  "data": {
    // Event-specific data
  },
  "metadata": {
    "correlation_id": "string (optional)",
    "causation_id": "uuid (optional)",
    "tags": ["string"] (optional)
  }
}
```

### Event Type Schemas

Event type schemas extend the base schema by defining the structure of the `data` field:

```json
{
  "data": {
    "type": "object",
    "required": ["field1", "field2"],
    "properties": {
      "field1": {"type": "string", "format": "uuid"},
      "field2": {"type": "string"}
    }
  }
}
```

## Event Categories

Events are organized into categories based on their domain:

- **contract**: Contract-related events
- **asset**: Asset-related events
- **dataset**: Dataset-related events
- **ingestion**: Ingestion-related events
- **quality**: Data quality events
- **compliance**: Compliance-related events
- **version**: Versioning events
- **access**: Access control events
- **marketplace**: Marketplace events
- **workflow**: Workflow orchestration events

## Development

### Running Tests

```bash
# Integration tests
pytest services/event-schema-registry/tests/
```

### Adding New Event Types

1. Add event type schema to `hub/apps/core/events/event_types.py`
2. Add schema definition to `EVENT_TYPE_SCHEMAS` dictionary
3. Schema will be automatically available via the registry service

## Troubleshooting

### Service Not Starting

1. Check health:
   ```bash
   curl http://localhost:8091/health
   ```

2. Check logs:
   ```bash
   docker compose logs event-schema-registry-service
   ```

3. Verify dependencies:
   ```bash
   docker compose ps postgres
   ```

### Schema Not Found

1. Verify event type exists:
   ```bash
   curl http://localhost:8091/event-types
   ```

2. Check event type format:
   - Must match pattern: `domain.entity.action`
   - Use lowercase with dots as separators

### Validation Failures

1. Check required fields:
   - Review schema for required fields
   - Ensure all required fields are provided

2. Check field types:
   - Verify UUIDs are valid UUID strings
   - Verify types match schema definitions

3. Check validation response:
   ```bash
   curl -X POST http://localhost:8091/validate \
     -H "Content-Type: application/json" \
     -d '{"event_type": "...", "data": {...}}'
   ```

## Related Documentation

- [Event Bus Documentation](../../docs/EVENT_BUS.md)
- [Event Types Reference](../../docs/EVENT_TYPES_REFERENCE.md)
- [Event Types Implementation Summary](../../docs/EVENT_TYPES_IMPLEMENTATION_SUMMARY.md)
- [Docker Compose Deployment](../../docs/DOCKER_COMPOSE_DEPLOYMENT.md)

