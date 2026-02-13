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

### ODPS Events

#### Lifecycle Events
- `odps.created` - ODPS contract created
- `odps.updated` - ODPS contract updated
- `odps.deleted` - ODPS contract deleted
- `odps.normalized` - ODPS contract normalized
- `odps.linked` - ODPS contract linked to ODCS
- `odps.unlinked` - ODPS contract unlinked from ODCS

#### Processing Events
- `odps.ref.resolved` - ODPS $ref resolution completed
- `odps.ref.failed` - ODPS $ref resolution failed
- `odps.export.started` - ODPS export started
- `odps.export.completed` - ODPS export completed
- `odps.export.failed` - ODPS export failed

#### Workflow Events
- `odps.workflow.started` - ODPS workflow started
- `odps.workflow.completed` - ODPS workflow completed
- `odps.workflow.failed` - ODPS workflow failed
- `odps.workflow.step.completed` - ODPS workflow step completed
- `odps.workflow.step.failed` - ODPS workflow step failed

#### Progress Events
- `odps.creation.progress` - ODPS creation progress update
- `odps.normalization.progress` - ODPS normalization progress update
- `odps.ref.progress` - ODPS $ref resolution progress update
- `odps.export.progress` - ODPS export progress update
- `odps.workflow.progress` - ODPS workflow progress update

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

### JavaScript Example - ODPS Events

```javascript
const ws = new WebSocket('ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
  // Subscribe to ODPS events
  ws.send(JSON.stringify({
    type: 'subscribe',
    data: {
      event_types: [
        'odps.created',
        'odps.normalized',
        'odps.export.completed',
        'odps.creation.progress',
        'odps.normalization.progress',
        'odps.export.progress'
      ]
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'event') {
    const eventData = message.data;
    const eventType = eventData.event_type;

    switch (eventType) {
      case 'odps.created':
        console.log('ODPS contract created:', eventData.data.contract_id);
        break;

      case 'odps.normalized':
        console.log('ODPS contract normalized:', {
          contract_id: eventData.data.contract_id,
          status: eventData.data.normalization_status
        });
        break;

      case 'odps.export.completed':
        console.log('ODPS export completed:', {
          contract_id: eventData.data.contract_id,
          format: eventData.data.export_format,
          size: eventData.data.export_size
        });
        break;

      case 'odps.creation.progress':
        console.log('ODPS creation progress:', {
          contract_id: eventData.data.contract_id,
          progress: eventData.data.progress_percent + '%',
          step: eventData.data.current_step
        });
        updateProgressBar(eventData.data.progress_percent);
        break;

      case 'odps.normalization.progress':
        console.log('ODPS normalization progress:', {
          contract_id: eventData.data.contract_id,
          progress: eventData.data.progress_percent + '%'
        });
        updateNormalizationProgress(eventData.data.progress_percent);
        break;

      case 'odps.export.progress':
        console.log('ODPS export progress:', {
          contract_id: eventData.data.contract_id,
          progress: eventData.data.progress_percent + '%'
        });
        updateExportProgress(eventData.data.progress_percent);
        break;

      default:
        console.log('Received ODPS event:', eventType);
    }
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

### Python Example - ODPS Events

```python
import asyncio
import websockets
import json

async def handle_odps_event(event_data):
    """Handle ODPS events."""
    event_type = event_data.get("event_type")
    data = event_data.get("data", {})

    if event_type == "odps.created":
        print(f"ODPS contract created: {data.get('contract_id')}")

    elif event_type == "odps.normalized":
        print(f"ODPS contract normalized: {data.get('contract_id')} - {data.get('normalization_status')}")

    elif event_type == "odps.export.completed":
        print(f"ODPS export completed: {data.get('contract_id')} - {data.get('export_format')}")

    elif event_type == "odps.creation.progress":
        progress = data.get("progress_percent", 0)
        step = data.get("current_step", "unknown")
        print(f"ODPS creation progress: {progress}% - {step}")

    elif event_type == "odps.normalization.progress":
        progress = data.get("progress_percent", 0)
        print(f"ODPS normalization progress: {progress}%")

    elif event_type == "odps.export.progress":
        progress = data.get("progress_percent", 0)
        print(f"ODPS export progress: {progress}%")

async def connect_odps_websocket():
    """Connect to WebSocket and subscribe to ODPS events."""
    uri = "ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN"

    async with websockets.connect(uri) as websocket:
        # Subscribe to ODPS events
        subscribe_message = {
            "type": "subscribe",
            "data": {
                "event_types": [
                    "odps.created",
                    "odps.normalized",
                    "odps.export.completed",
                    "odps.creation.progress",
                    "odps.normalization.progress",
                    "odps.export.progress",
                    "odps.ref.progress"
                ]
            }
        }
        await websocket.send(json.dumps(subscribe_message))

        # Listen for events
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "event":
                handle_odps_event(data["data"])

asyncio.run(connect_odps_websocket())
```

### Real-Time ODPS Workflow Progress Example

```javascript
// Subscribe to ODPS workflow progress events
const ws = new WebSocket('ws://api.example.com/ws/events/?token=YOUR_JWT_TOKEN');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    data: {
      event_types: [
        'odps.workflow.started',
        'odps.workflow.progress',
        'odps.workflow.completed',
        'odps.workflow.failed',
        'odps.creation.progress',
        'odps.normalization.progress',
        'odps.ref.progress'
      ],
      filters: {
        contract_id: '550e8400-e29b-41d4-a716-446655440000'  // Filter by specific contract
      }
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'event') {
    const eventData = message.data;
    const eventType = eventData.event_type;
    const data = eventData.data;

    // Update UI based on event type
    switch (eventType) {
      case 'odps.workflow.started':
        showWorkflowStatus('ODPS workflow started');
        break;

      case 'odps.creation.progress':
        updateProgressBar('Creation', data.progress_percent);
        updateStatusText(data.current_step);
        break;

      case 'odps.normalization.progress':
        updateProgressBar('Normalization', data.progress_percent);
        break;

      case 'odps.ref.progress':
        updateProgressBar('Reference Resolution', data.progress_percent);
        updateRefCount(data.resolved_refs_count, data.total_refs_count);
        break;

      case 'odps.workflow.completed':
        showWorkflowStatus('ODPS workflow completed successfully');
        hideProgressBars();
        break;

      case 'odps.workflow.failed':
        showWorkflowStatus(`ODPS workflow failed: ${data.error_message}`);
        hideProgressBars();
        break;
    }
  }
};
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

