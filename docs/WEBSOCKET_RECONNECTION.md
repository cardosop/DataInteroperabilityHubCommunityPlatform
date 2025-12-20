# WebSocket Reconnection Logic Documentation

## Overview

This document describes the WebSocket reconnection logic for both client-side and server-side implementations. The system provides robust connection management with automatic reconnection, health checks, and connection cleanup.

## Server-Side Implementation

### Ping/Pong Heartbeat Mechanism

The server implements a periodic ping/pong heartbeat mechanism to keep connections alive and detect stale connections.

**Features:**
- **Periodic Server Pings**: Server sends ping messages at configurable intervals (default: 30 seconds)
- **Pong Response Tracking**: Server tracks pong responses to detect unresponsive clients
- **Automatic Cleanup**: Connections that don't respond to pings are automatically closed

**Configuration:**
```python
# settings.py
WEBSOCKET_PING_INTERVAL = 30  # seconds between pings
WEBSOCKET_PONG_TIMEOUT = 10   # seconds to wait for pong response
WEBSOCKET_CONNECTION_TIMEOUT = 300  # seconds of inactivity before timeout
```

**How It Works:**
1. When a WebSocket connection is established, the server starts two background tasks:
   - `_ping_loop()`: Sends periodic ping messages
   - `_health_check_loop()`: Monitors connection health

2. The server sends ping messages at the configured interval
3. Clients should respond with pong messages
4. If no pong is received within `WEBSOCKET_PONG_TIMEOUT`, the connection is closed
5. If no activity occurs within `WEBSOCKET_CONNECTION_TIMEOUT`, the connection is closed

### Connection Timeout Detection

The server tracks connection activity and automatically closes stale connections:

- **Last Activity Tracking**: Every message sent or received updates the `last_activity` timestamp
- **Inactivity Timeout**: Connections inactive for more than `WEBSOCKET_CONNECTION_TIMEOUT` are closed
- **Pong Timeout**: Connections that don't respond to pings within `WEBSOCKET_PONG_TIMEOUT` are closed

### Automatic Connection Cleanup

The server automatically cleans up connections in the following scenarios:

1. **Pong Timeout**: Client doesn't respond to ping within timeout period
2. **Inactivity Timeout**: No activity for configured timeout period
3. **Connection Errors**: Errors during ping/health check operations

When a connection is closed due to timeout, the server sends a close code `4000` (Normal Closure).

## Client-Side Reconnection Logic

### Exponential Backoff for Reconnection Attempts

The client implements exponential backoff to prevent overwhelming the server during reconnection attempts.

**Algorithm:**
```typescript
// Base delay: 1 second
// Max delay: 30 seconds
// Backoff multiplier: 2

delay = min(baseDelay * (2 ^ attemptNumber), maxDelay)
```

**Example:**
- Attempt 1: 1 second delay
- Attempt 2: 2 seconds delay
- Attempt 3: 4 seconds delay
- Attempt 4: 8 seconds delay
- Attempt 5: 16 seconds delay
- Attempt 6+: 30 seconds delay (capped)

### Max Reconnection Attempts

The client limits the number of reconnection attempts to prevent infinite reconnection loops.

**Configuration:**
```typescript
maxReconnectAttempts: 10  // Default: 10 attempts
```

**Behavior:**
- After `maxReconnectAttempts` failed attempts, reconnection stops
- Client enters `DISCONNECTED` state
- Manual reconnection required via `connect()` method

### Reconnection State Management

The client manages reconnection state through the following states:

1. **CONNECTING**: Initial connection attempt
2. **CONNECTED**: Successfully connected
3. **RECONNECTING**: Attempting to reconnect after disconnection
4. **DISCONNECTED**: Connection closed, not attempting to reconnect

**State Transitions:**
```
DISCONNECTED → CONNECTING → CONNECTED
CONNECTED → RECONNECTING (on disconnect)
RECONNECTING → CONNECTED (on successful reconnect)
RECONNECTING → DISCONNECTED (after max attempts)
```

### Implementation Example

```typescript
import { WebSocketClient } from '@/lib/api/websocket'

const client = new WebSocketClient({
  url: 'ws://localhost:8000/ws/events/',
  reconnectDelay: 1000,           // Base delay: 1 second
  maxReconnectAttempts: 10,       // Max 10 attempts
  pingInterval: 30000,             // Send ping every 30 seconds
  connectionTimeout: 10000,       // Connection timeout: 10 seconds
  autoReconnect: true              // Enable automatic reconnection
})

// Connect
client.connect()

// Listen for state changes
client.on('state_change', ({ newState }) => {
  console.log('Connection state:', newState)
})

// Listen for reconnection events
client.on('reconnecting', ({ attemptNumber, delay }) => {
  console.log(`Reconnecting (attempt ${attemptNumber}) in ${delay}ms`)
})
```

### Best Practices

1. **Handle Reconnection Events**: Listen for `state_change` events to update UI
2. **Resubscribe on Reconnect**: Re-subscribe to event types after reconnection
3. **Exponential Backoff**: Use exponential backoff to prevent server overload
4. **Max Attempts**: Set reasonable max attempts to prevent infinite loops
5. **User Feedback**: Inform users when connection is lost and when reconnecting

### Error Handling

The client handles various error scenarios:

- **Connection Errors**: Automatically attempts reconnection
- **Network Errors**: Uses exponential backoff for retries
- **Authentication Errors**: Stops reconnection (requires user action)
- **Server Errors**: Attempts reconnection with backoff

### Configuration Options

```typescript
interface WebSocketClientOptions {
  url?: string                    // WebSocket URL
  reconnectDelay?: number         // Base reconnection delay (ms)
  maxReconnectAttempts?: number  // Maximum reconnection attempts
  pingInterval?: number          // Ping interval (ms)
  connectionTimeout?: number     // Connection timeout (ms)
  autoReconnect?: boolean        // Enable automatic reconnection
}
```

## Testing

### Server-Side Tests

Test cases cover:
- Ping/pong heartbeat mechanism
- Connection timeout detection
- Automatic connection cleanup
- Health check loop functionality
- Background task cancellation

### Client-Side Tests

Test cases cover:
- Exponential backoff calculation
- Max reconnection attempts
- State management
- Reconnection event handling
- Error scenarios

## Monitoring

### Metrics

The following metrics are logged for monitoring:

- `websocket_ping_sent`: Server ping sent
- `websocket_pong_received`: Client pong received
- `websocket_pong_timeout`: Pong timeout detected
- `websocket_connection_timeout`: Connection timeout detected
- `websocket_connection_inactive_timeout`: Inactivity timeout detected

### Logging

All connection health events are logged with structured logging:
- Connection state changes
- Ping/pong events
- Timeout events
- Cleanup events

## Troubleshooting

### Common Issues

1. **Frequent Disconnections**
   - Check network stability
   - Verify ping/pong intervals are appropriate
   - Review connection timeout settings

2. **Reconnection Loops**
   - Check max reconnection attempts
   - Verify exponential backoff is working
   - Review server logs for errors

3. **Connection Timeouts**
   - Increase `WEBSOCKET_CONNECTION_TIMEOUT` if needed
   - Check for network issues
   - Verify client is responding to pings

## References

- [WebSocket API Documentation](WEBSOCKET_API.md)
- [Django Channels Documentation](https://channels.readthedocs.io/)
- [WebSocket Protocol RFC 6455](https://tools.ietf.org/html/rfc6455)

