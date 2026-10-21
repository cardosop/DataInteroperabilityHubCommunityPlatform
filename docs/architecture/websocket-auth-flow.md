# WebSocket Authentication Flow & Reconnection Architecture (280.C.6.4)

**Date:** 2026-05-15  
**Scope:** Production WebSocket auth, reconnection, and resilience

## 1. Connection Establishment

```
Client                          Traefik/ALB                   Django ASGI
  |                                 |                              |
  |-- HTTP/1.1 Upgrade: ws -------->|                              |
  |                                 |-- Upgrade: ws -------------->|
  |                                 |                              |-- WebSocketAuthMiddleware
  |                                 |                              |   validates JWT token
  |                                 |                              |   from query param or
  |                                 |                              |   sec-websocket-protocol
  |                                 |                              |
  |                                 |                              |-- URLRouter matches path
  |                                 |                              |   to EventConsumer
  |                                 |                              |
  |<-------- 101 Switching Protocols ------------------------------|
  |                                 |                              |
  |<============= WSS (TLS) connection established ===============>|
```

### 1.1 — Authentication

Authentication is handled by `WebSocketAuthMiddleware` (`hub/apps/websocket/middleware/auth.py`).

**Token delivery:** The client passes the JWT in one of two ways:
1. **Query parameter:** `wss://meshant-internal.example.com/ws/events/?token=<jwt>`
2. **Sec-WebSocket-Protocol header:** The JWT is base64-encoded and passed as a subprotocol value. The middleware extracts it from `scope['subprotocols']`.

**Validation steps:**
1. Extract token from query string or subprotocols
2. Decode JWT using `django.contrib.auth` token backend
3. Validate tenant scoping (tenant_id in JWT must match the tenant context)
4. On success: populate `scope['user']` and `scope['tenant']`
5. On failure: close connection with code 4001 (auth failed)

**Token lifetime:** JWT tokens used for WebSocket connections have a 30-minute lifetime. The client must re-authenticate before expiry.

### 1.2 — Protocol Routing

After auth, the connection is routed by `URLRouter` (`hub/apps/websocket/routing.py`):

```
ws/events/           → EventConsumer      (real-time lineage + audit events)
ws/notifications/    → NotificationConsumer (toast + inbox updates)
ws/heartbeat/        → HeartbeatConsumer   (connection health monitoring)
```

## 2. Reconnection Architecture

### 2.1 — Client-Side Reconnection

The frontend WebSocket client (`frontend/src/shared/websocket/`) implements exponential backoff reconnection:

| Attempt | Delay | Jitter |
|---|---|---|
| 1 | 1s | ±0.5s |
| 2 | 2s | ±0.5s |
| 3 | 4s | ±1s |
| 4 | 8s | ±1s |
| 5 | 16s | ±2s |
| 6+ | 30s (cap) | ±5s |

**Backoff reset:** After a successful connection lasting >60s, the backoff counter resets to attempt 1.

**Token refresh:** Before each reconnection attempt, the client checks if the JWT has <5 minutes remaining. If so, it performs a token refresh via `POST /api/v1/auth/refresh/` before reconnecting.

### 2.2 — Server-Side Connection Tracking

- Each connection is tracked in Redis (`redis-channels`) with a TTL of 60s
- The `EventConsumer` sends a `ping` frame every 30s (Django Channels `--websocket-ping-interval`)
- If no `pong` is received within 10s, the server closes the connection
- On disconnect, the consumer cleans up subscription state from Redis

### 2.3 — Message Delivery Guarantees

| Scenario | Behavior |
|---|---|
| Client disconnects during message send | Message is queued in Redis for up to 5 min |
| Client reconnects within 5 min | Queued messages are replayed in order |
| Client disconnected >5 min | Messages are discarded; client must re-fetch via REST API |
| Server restart | All connections drop; clients reconnect with backoff |
| Redis failover | Channels layer reconnects; in-flight messages may be lost (at-most-once) |

## 3. Resilience

### 3.1 — Backend

- Django Channels runs on the same ASGI server as the HTTP API (Daphne / Uvicorn)
- Channel layer: Redis (`redis-channels`) with `channels_redis` backend
- Connection pooling: shared Redis connection via `hub.apps.core.redis_pools`
- Graceful shutdown: Daphne drains in-flight messages before exiting (SIGTERM → 10s drain → SIGKILL)

### 3.2 — Load Balancing

- Traefik/ALB distributes WebSocket connections across API pods
- Sticky sessions: ALB uses `awsalb` cookie for WebSocket target group (same pod for connection lifetime)
- Pod termination: `preStop` hook waits for existing WebSocket connections to drain before SIGTERM

### 3.3 — Monitoring

| Metric | Source | Alert |
|---|---|---|
| WebSocket connection count | `channels_connected_total` (Prometheus) | Drop >50% in 1m |
| Message delivery latency | Custom metric in EventConsumer | p95 >500ms for 5m |
| Reconnection rate | Client-side telemetry | Rate >10/min = server issue |
| Auth failure rate | `WebSocketAuthMiddleware` counter | >5% of connection attempts |

## 4. Security

- WSS only (TLS 1.2+) — plain WS connections are rejected at the load balancer
- JWT validation uses the same key as the REST API (`JWT_SECRET_KEY`)
- Tenant isolation: `scope['tenant']` is validated against the JWT's `tenant_id` claim
- Origin validation: `AllowedHostsOriginValidator` rejects connections from non-approved origins
- Rate limiting: maximum 5 connection attempts per IP per minute (429 on exceed)

## 5. Debugging

```bash
# Check active WebSocket connections
kubectl logs -n hub-production -l app=api-service | grep "WebSocket CONNECT"

# Test connection (wscat)
wscat -c "wss://meshant-internal.example.com/ws/events/?token=<jwt>"

# Check Redis channels state
redis-cli -a $REDIS_CHANNELS_PASSWORD PUBSUB channels "asgi:*"

# Monitor reconnection logs
kubectl logs -n hub-production -l app=api-service | grep "reconnect"
```
