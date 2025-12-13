# WebSocket API Documentation

## Overview

The WebSocket API provides real-time event updates for the Data Interoperability Hub. It enables clients to subscribe to event streams and receive real-time notifications for jobs, workflows, assets, contracts, datasets, and other system events.

## Features

- **Real-time Event Delivery**: Receive events as they occur in the system
- **Selective Subscription**: Subscribe to specific event types or patterns
- **Authentication**: JWT token or API key authentication
- **Tenant Isolation**: Automatic tenant scoping for all events
- **Filtering**: Filter events by tenant, resource type, and other criteria

## Connection

### Endpoint

```
ws://api.example.com/ws/events/
```

### Authentication

WebSocket connections support two authentication methods:

#### JWT Token Authentication

```
ws://api.example.com/ws/events/?token=<jwt_token>
```

or

```
ws://api.example.com/ws/events/?access_token=<jwt_token>
```

#### API Key Authentication

```
ws://api.example.com/ws/events/?api_key=<api_key>
```

or

```
ws://api.example.com/ws/events/?X-API-Key=<api_key>
```

### Connection Flow

1. Client initiates WebSocket connection with authentication
2. Server validates authentication and tenant membership
3. Server accepts connection and sends confirmation
4. Client subscribes to event types
5. Server sends events as they occur

## Message Protocol

### Message Format

All messages follow a standard JSON format:

```json
{
  "type": "message_type",
  "data": {},
  "error": "error_message",
  "request_id": "uuid",
  "timestamp": "2025-01-15T10:00:00Z"
}
```

### Message Types

#### Client to Server

- `subscribe`: Subscribe to event types
- `unsubscribe`: Unsubscribe from event types
- `ping`: Keep-alive ping

#### Server to Client

- `event`: Event notification
- `subscription_confirmed`: Subscription confirmation
- `subscription_error`: Subscription error
- `error`: Error message
- `pong`: Ping response

## Subscribing to Events

### Subscribe Message

```json
{
  "type": "subscribe",
  "data": {
    "event_types": [
      "contract.created",
      "asset.activated",
      "job.completed"
    ],
    "filters": {
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

### Subscribe Response

```json
{
  "type": "subscription_confirmed",
  "data": {
    "event_types": [
      "contract.created",
      "asset.activated",
      "job.completed"
    ],
    "filters": {
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

## Event Messages

### Event Format

```json
{
  "type": "event",
  "data": {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "event_type": "contract.created",
    "event_version": "1.0.0",
    "timestamp": "2025-01-15T10:00:00Z",
    "source": {
      "service": "hub",
      "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "550e8400-e29b-41d4-a716-446655440001",
      "request_id": "req-1234567890"
    },
    "data": {
      "contract_id": "550e8400-e29b-41d4-a716-446655440002"
    },
    "metadata": {
      "correlation_id": "corr-1234567890",
      "tags": ["contract", "creation"]
    }
  }
}
```

## Available Event Types

### Contract Events

- `contract.created`
- `contract.updated`
- `contract.deleted`
- `contract.validated`
- `contract.normalized`

### Asset Events

- `asset.created`
- `asset.updated`
- `asset.activated`
- `asset.published`
- `asset.retired`

### Dataset Events

- `dataset.created`
- `dataset.updated`
- `dataset.deleted`
- `dataset.uploaded`

### Job Events

- `job.started`
- `job.completed`
- `job.failed`
- `job.cancelled`

### Workflow Events

- `workflow.started`
- `workflow.completed`
- `workflow.failed`
- `workflow.cancelled`
- `workflow.step.completed`
- `workflow.step.failed`

### Quality Events

- `quality.check.started`
- `quality.check.completed`
- `quality.check.failed`
- `quality.anomaly.detected`

### Compliance Events

- `compliance.check.started`
- `compliance.check.completed`
- `compliance.check.failed`
- `compliance.report.generated`

## Error Handling

### Error Message Format

```json
{
  "type": "error",
  "error": "Error message",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Common Errors

- **4001**: Unauthorized - Invalid or missing authentication
- **4003**: Forbidden - User does not belong to a tenant
- **4000**: Bad Request - Invalid message format

## Usage Examples

### JavaScript Example

```javascript
const ws = new WebSocket('ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
  // Subscribe to events
  ws.send(JSON.stringify({
    type: 'subscribe',
    data: {
      event_types: ['contract.created', 'asset.activated']
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'event') {
    console.log('Received event:', message.data);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

### Python Example

```python
import asyncio
import websockets
import json

async def connect_websocket():
    uri = "ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN"
    
    async with websockets.connect(uri) as websocket:
        # Subscribe to events
        subscribe_message = {
            "type": "subscribe",
            "data": {
                "event_types": ["contract.created", "asset.activated"]
            }
        }
        await websocket.send(json.dumps(subscribe_message))
        
        # Listen for events
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "event":
                print(f"Received event: {data['data']}")

asyncio.run(connect_websocket())
```

## Best Practices

1. **Reconnection**: Implement automatic reconnection with exponential backoff
2. **Heartbeat**: Send ping messages periodically to keep connection alive
3. **Error Handling**: Handle all error types and implement appropriate recovery
4. **Subscription Management**: Unsubscribe from unused event types to reduce load
5. **Rate Limiting**: Be mindful of message rate limits

## Security

- All connections require authentication
- Events are automatically filtered by tenant
- Connections are validated against allowed hosts
- Messages are validated for format and content

## Limitations

- Maximum message size: 1MB
- Maximum concurrent connections per user: 10
- Message buffer capacity: 1000 messages
- Message expiry: 10 seconds

## Troubleshooting

### Connection Refused

- Verify authentication token is valid
- Check user belongs to a tenant
- Ensure WebSocket endpoint is accessible

### No Events Received

- Verify subscription message was sent correctly
- Check event types are valid
- Ensure filters match your tenant

### Connection Drops

- Implement reconnection logic
- Check network stability
- Verify server is not overloaded

