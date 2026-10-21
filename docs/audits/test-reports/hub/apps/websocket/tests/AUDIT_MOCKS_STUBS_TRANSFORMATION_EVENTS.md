# Audit: Mocks/Stubs in `test_transformation_events.py`

## Overview

This document audits all mocks and stubs used in `hub/apps/websocket/tests/test_transformation_events.py` and provides a replacement plan using real implementations.

**File:** `hub/apps/websocket/tests/test_transformation_events.py`
**Date:** 2026-01-03
**Status:** ✅ Audit Complete and Validated

**Validation:** All 9 tests pass. See `AUDIT_VALIDATION_REPORT.md` for validation details.

---

## Summary

**Total Mocks/Stubs Found:** 10 instances across 3 categories

1. **WebSocket Consumer Methods:** 4 mocks
2. **Redis Client:** 2 mocks
3. **Event Deduplication Functions:** 3 patches

---

## Detailed Audit

### 1. WebSocket Consumer Method Mocks

#### 1.1 `consumer.send_json_message = AsyncMock()` (Line 93)

**What it replaces:**
- Real method: `EventConsumer.send_json_message()` (line 1519 in `event_consumer.py`)
- Purpose: Sends JSON messages to WebSocket client
- Real implementation: Serializes `WebSocketMessage` to JSON and calls `self.send()`

**Why it's mocked:**
- Avoids actual WebSocket connection overhead in unit tests
- Allows verification of message sending without real WebSocket infrastructure

**Replacement Plan:**
- Use `WebsocketCommunicator` from `channels.testing` (as shown in `test_consumer.py`)
- Use `communicator.receive_json_from()` to capture actual messages
- Verify messages by receiving them through the communicator

**Real Implementation Example:**
```python
from channels.testing import WebsocketCommunicator
communicator = WebsocketCommunicator(EventConsumer.as_asgi(), "/ws/events/")
communicator.scope["user"] = self.user
communicator.scope["tenant"] = self.tenant
await communicator.connect()
# Messages can be received with:
response = await communicator.receive_json_from()
```

---

#### 1.2 `consumer.send = AsyncMock()` (Line 94)

**What it replaces:**
- Real method: Inherited from `AsyncWebsocketConsumer.send()` (Channels framework)
- Purpose: Low-level WebSocket send operation
- Real implementation: Sends raw text/binary data over WebSocket connection

**Why it's mocked:**
- Avoids actual WebSocket connection overhead
- Allows verification without network layer

**Replacement Plan:**
- Use `WebsocketCommunicator` which handles real WebSocket communication
- Messages sent via `send_json_message()` will be captured by `communicator.receive_json_from()`
- No need to mock `send()` directly when using `WebsocketCommunicator`

---

#### 1.3 `consumer.close = AsyncMock()` (Line 95)

**What it replaces:**
- Real method: Inherited from `AsyncWebsocketConsumer.close()` (Channels framework)
- Purpose: Closes WebSocket connection
- Real implementation: Closes the WebSocket connection with optional close code

**Why it's mocked:**
- Avoids actual connection closure overhead
- Allows testing without real connection lifecycle

**Replacement Plan:**
- Use `communicator.disconnect()` from `WebsocketCommunicator`
- This properly closes the connection and cleans up resources
- Verify connection closure by checking `communicator.disconnect()` return value

---

#### 1.4 `consumer.send_event = AsyncMock()` (Line 302)

**What it replaces:**
- Real method: `EventConsumer.send_event()` (line 1110 in `event_consumer.py`)
- Purpose: Sends event to WebSocket client with deduplication and filtering
- Real implementation:
  - Checks subscription
  - Applies filters
  - Performs deduplication
  - Sends via `send_json_message()`

**Why it's mocked:**
- In `test_event_replay_on_reconnection()`: To verify replay logic without sending actual messages
- Allows testing replay mechanism in isolation

**Replacement Plan:**
- Use `WebsocketCommunicator` to receive actual events
- Call `_replay_missed_transformation_events()` directly (it's a real method)
- Verify events are received via `communicator.receive_json_from()`
- Test deduplication by sending duplicate events and verifying only one is received

---

### 2. Redis Client Mocks

#### 2.1 `consumer._get_deduplication_redis_client = MagicMock(return_value=None)` (Line 305)

**What it replaces:**
- Real method: `EventConsumer._get_deduplication_redis_client()` (line 81 in `event_consumer.py`)
- Purpose: Gets Redis client for event deduplication (lazy initialization)
- Real implementation: Returns `get_deduplication_redis_client()` from `hub.apps.core.events.deduplication`

**Why it's mocked:**
- In `test_event_replay_on_reconnection()`: To disable deduplication for replay test
- Avoids Redis dependency in unit tests

**Replacement Plan:**
- Use real Redis client from `hub.apps.core.events.deduplication.get_redis_client()`
- Configure test settings to use test Redis instance or InMemoryRedis
- For tests that need deduplication disabled, use Django `override_settings` to disable it
- Alternative: Use real Redis in Docker Compose test environment

**Real Implementation:**
```python
from hub.apps.core.events.deduplication import get_redis_client
redis_client = get_redis_client()  # Returns None if Redis unavailable (graceful degradation)
```

---

#### 2.2 `mock_redis = MagicMock()` and `consumer._get_deduplication_redis_client = MagicMock(return_value=mock_redis)` (Lines 326-327)

**What it replaces:**
- Real Redis client instance
- Purpose: Mock Redis for deduplication testing
- Real implementation: `redis.Redis` client from `hub.apps.core.events.deduplication.get_redis_client()`

**Why it's mocked:**
- In `test_event_deduplication()`: To control deduplication behavior
- Avoids Redis dependency and allows deterministic test behavior

**Replacement Plan:**
- Use real Redis client with test Redis instance
- Use `fakeredis` library for in-memory Redis simulation (if available)
- Or use real Redis in Docker Compose test environment
- For deterministic behavior, use Redis transactions or test-specific keys with cleanup

**Real Implementation Options:**
1. **Use fakeredis (recommended for unit tests):**
   ```python
   import fakeredis
   redis_client = fakeredis.FakeStrictRedis()
   ```

2. **Use real Redis in Docker Compose:**
   ```python
   from hub.apps.core.events.deduplication import get_redis_client
   redis_client = get_redis_client()  # Uses settings.REDIS_URL
   ```

---

### 3. Event Deduplication Function Patches

#### 3.1 `patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate')` (Line 348)

**What it replaces:**
- Real function: `check_event_duplicate()` from `hub.apps.core.events.deduplication`
- Purpose: Checks if an event is a duplicate by querying Redis
- Real implementation: Queries Redis for deduplication key, returns `(is_duplicate: bool, existing_event_id: Optional[str])`

**Why it's patched:**
- In `test_event_deduplication()`: To control deduplication check results
- Allows testing both duplicate and non-duplicate scenarios

**Replacement Plan:**
- Use real `check_event_duplicate()` function
- Use real Redis client (fakeredis or Docker Compose Redis)
- Test duplicate scenario by:
  1. Sending first event (should pass)
  2. Storing event ID in Redis via `store_event_id()`
  3. Sending duplicate event (should be filtered)
- Test non-duplicate scenario by sending different events

**Real Implementation:**
```python
from hub.apps.core.events.deduplication import check_event_duplicate, store_event_id, generate_deduplication_key

redis_client = get_redis_client()
deduplication_key = generate_deduplication_key(event_type, event_data)
is_duplicate, existing_id = check_event_duplicate(deduplication_key, redis_client=redis_client)
```

---

#### 3.2 `patch('hub.apps.websocket.consumers.event_consumer.store_event_id')` (Line 349)

**What it replaces:**
- Real function: `store_event_id()` from `hub.apps.core.events.deduplication`
- Purpose: Stores event ID in Redis for deduplication
- Real implementation: Stores event ID with TTL in Redis

**Why it's patched:**
- In `test_event_deduplication()`: To control storage behavior
- Allows testing without actual Redis writes

**Replacement Plan:**
- Use real `store_event_id()` function
- Use real Redis client (fakeredis or Docker Compose Redis)
- Verify storage by checking Redis after storing
- Clean up stored keys in test teardown

**Real Implementation:**
```python
from hub.apps.core.events.deduplication import store_event_id, generate_deduplication_key

redis_client = get_redis_client()
deduplication_key = generate_deduplication_key(event_type, event_data)
store_event_id(deduplication_key, event_id, redis_client=redis_client, ttl=86400)
```

---

#### 3.3 `patch('hub.apps.websocket.consumers.event_consumer.generate_deduplication_key')` (Line 350)

**What it replaces:**
- Real function: `generate_deduplication_key()` from `hub.apps.core.events.deduplication`
- Purpose: Generates Redis key for event deduplication
- Real implementation: Creates SHA256 hash of event type + normalized event data

**Why it's patched:**
- In `test_event_deduplication()`: To control key generation
- Allows deterministic key values for testing

**Replacement Plan:**
- Use real `generate_deduplication_key()` function
- No need to patch - it's a pure function with deterministic output
- Verify key generation by comparing expected vs actual keys
- Test with different event types and data to verify uniqueness

**Real Implementation:**
```python
from hub.apps.core.events.deduplication import generate_deduplication_key

key = generate_deduplication_key("transformation.pipeline.execution.progress", {
    "pipeline_id": "123",
    "execution_id": "456",
    "progress_percent": 0.5
})
# Returns: "event:dedup:transformation.pipeline.execution.progress:{hash}"
```

---

## Replacement Plan Summary

### Phase 1: Replace WebSocket Consumer Mocks

**Action Items:**
1. Replace `_create_consumer()` helper to use `WebsocketCommunicator`
2. Update all tests to use `communicator.connect()` and `communicator.disconnect()`
3. Replace `consumer.send_json_message.called` assertions with `communicator.receive_json_from()`
4. Remove `AsyncMock()` assignments for `send`, `send_json_message`, `close`

**Example Migration:**
```python
# OLD:
consumer = self._create_consumer()
consumer.send_json_message = AsyncMock()
# ... test logic ...
self.assertTrue(consumer.send_json_message.called)

# NEW:
communicator = WebsocketCommunicator(EventConsumer.as_asgi(), "/ws/events/")
communicator.scope["user"] = self.user
communicator.scope["tenant"] = self.tenant
await communicator.connect()
# ... test logic ...
response = await communicator.receive_json_from()
self.assertIsNotNone(response)
```

---

### Phase 2: Replace Redis Mocks

**Action Items:**
1. Add `fakeredis` to test dependencies OR use Docker Compose Redis
2. Replace `MagicMock()` Redis with real Redis client
3. Use `override_settings` for tests that need deduplication disabled
4. Add Redis cleanup in test teardown

**Example Migration:**
```python
# OLD:
mock_redis = MagicMock()
consumer._get_deduplication_redis_client = MagicMock(return_value=mock_redis)

# NEW:
from hub.apps.core.events.deduplication import get_redis_client
import fakeredis

redis_client = fakeredis.FakeStrictRedis()
# Or use real Redis:
# redis_client = get_redis_client()
```

---

### Phase 3: Replace Deduplication Function Patches

**Action Items:**
1. Remove all `patch()` decorators for deduplication functions
2. Use real `check_event_duplicate()`, `store_event_id()`, `generate_deduplication_key()`
3. Test deduplication by actually storing and checking events
4. Add proper test data setup and cleanup

**Example Migration:**
```python
# OLD:
with patch('hub.apps.websocket.consumers.event_consumer.check_event_duplicate') as mock_check:
    mock_check.return_value = (False, None)
    await consumer.send_event(event)

# NEW:
from hub.apps.core.events.deduplication import (
    check_event_duplicate,
    store_event_id,
    generate_deduplication_key,
    get_redis_client
)

redis_client = get_redis_client()
# First event - not duplicate
is_duplicate, _ = check_event_duplicate(
    generate_deduplication_key(event_type, event_data),
    redis_client=redis_client
)
self.assertFalse(is_duplicate)

# Store event
store_event_id(
    generate_deduplication_key(event_type, event_data),
    event_id,
    redis_client=redis_client
)

# Second event - should be duplicate
is_duplicate, existing_id = check_event_duplicate(
    generate_deduplication_key(event_type, event_data),
    redis_client=redis_client
)
self.assertTrue(is_duplicate)
```

---

## Testing Strategy

### Test Isolation

- Each test should use a fresh `WebsocketCommunicator` instance
- Use unique Redis keys per test (include test name in key prefix)
- Clean up Redis keys in `tearDown()`
- Use separate test database transactions

### Test Data Setup

- Create real `Tenant`, `User`, `TransformationPipeline`, `PipelineExecution` instances
- Create real `Event` instances in database for replay tests
- Use `sync_to_async()` for database operations in async tests

### Verification Methods

- Use `communicator.receive_json_from()` to verify messages
- Use `communicator.receive_nothing()` to verify no messages
- Check Redis directly for deduplication state
- Query database for event persistence

---

## Dependencies

### Required Packages

- `channels` - Already installed (WebsocketCommunicator)
- `channels.testing` - Already installed (WebsocketCommunicator)
- `fakeredis` - Recommended for unit tests (optional, can use Docker Compose Redis)

### Configuration

- Ensure `REDIS_URL` is configured in test settings
- Use `InMemoryChannelLayer` for channel layer in tests
- Configure `WEBSOCKET_EVENT_REPLAY_ENABLED` in test settings

---

## Risk Assessment

### Low Risk
- Replacing `send_json_message`, `send`, `close` mocks with `WebsocketCommunicator`
- Using real `generate_deduplication_key()` (pure function)

### Medium Risk
- Replacing Redis mocks with real Redis (requires Redis availability)
- Replacing deduplication function patches (requires proper test data setup)

### Mitigation
- Use `fakeredis` for unit tests (no external dependency)
- Use Docker Compose Redis for integration tests
- Add proper error handling for Redis unavailability
- Add comprehensive test cleanup

---

## Implementation Checklist

- [ ] Phase 1: Replace WebSocket consumer mocks
  - [ ] Update `_create_consumer()` to use `WebsocketCommunicator`
  - [ ] Replace all `send_json_message` assertions
  - [ ] Replace all `send` assertions
  - [ ] Replace all `close` assertions
  - [ ] Update `test_event_replay_on_reconnection()` to use real `send_event()`

- [ ] Phase 2: Replace Redis mocks
  - [ ] Add `fakeredis` dependency OR configure Docker Compose Redis
  - [ ] Replace `_get_deduplication_redis_client` mocks
  - [ ] Add Redis cleanup in `tearDown()`
  - [ ] Update tests to handle Redis unavailability gracefully

- [ ] Phase 3: Replace deduplication function patches
  - [ ] Remove `patch()` decorators
  - [ ] Use real `check_event_duplicate()`
  - [ ] Use real `store_event_id()`
  - [ ] Use real `generate_deduplication_key()`
  - [ ] Update `test_event_deduplication()` with real deduplication flow

- [ ] Testing
  - [ ] Run all tests and verify they pass
  - [ ] Verify no mocks/stubs remain
  - [ ] Verify tests use real implementations
  - [ ] Verify test isolation and cleanup

---

## Notes

- All replacements use real implementations from the codebase
- Tests will be more integration-like but still fast with `fakeredis`
- Tests will better reflect real system behavior
- Better test coverage of actual WebSocket and Redis interactions
- Tests will catch integration issues that mocks would miss

---

## References

- `hub/apps/websocket/tests/test_consumer.py` - Example of using `WebsocketCommunicator`
- `hub/apps/websocket/consumers/event_consumer.py` - Real consumer implementation
- `hub/apps/core/events/deduplication.py` - Real deduplication implementation
- Channels Testing Documentation: https://channels.readthedocs.io/en/stable/testing.html

