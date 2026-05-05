# API Idempotency Contract

**Phase 250.1.D / D250.8** — every write endpoint that opts into the idempotency contract requires an `Idempotency-Key` header on every request, validates it against the request body, and returns the cached response for any duplicate retry within a 24-hour window.

---

## Endpoints that enforce the contract

| Endpoint | Status |
|---|---|
| `POST /api/v1/assets/data-first/` | **Required** since 250.1.D (P1 deploy) |

Other write endpoints will be migrated incrementally; the cutover requires both the server-side enforcement (this doc) and an updated SDK release.

---

## Header format

```
Idempotency-Key: <tenant_uuid>:<sha256(canonical_body)>
```

Both fields MUST be lowercase. The two fields are joined by exactly one colon. Examples:

```
Idempotency-Key: 6f1d9c8a-2b3a-4f5e-9c7d-1234567890ab:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### Field definitions

| Field | Encoding |
|---|---|
| `tenant_uuid` | The authenticated tenant's UUID, in canonical lowercase hyphenated form (e.g., `01234567-89ab-cdef-0123-456789abcdef`). Uppercase or non-canonical forms are rejected with `IDEMPOTENCY_KEY_MALFORMED`. |
| `sha256(canonical_body)` | The lowercase hex SHA-256 of the **canonical body bytes**. See the canonicalisation rules below. |

### Canonical body bytes

For `application/json` requests, the canonical bytes are the JSON serialisation of the body with:

* `sort_keys=True` — object members sorted lexicographically by key
* `separators=(",", ":")` — most compact form (no whitespace)
* UTF-8 encoding

Example: the body `{"file_id": "f", "key": "k", "name": "n"}` canonicalises to the bytes `b'{"file_id":"f","key":"k","name":"n"}'`.

The server validates the body hash by recomputing the SHA-256 over the actual request body bytes. Clients that send a body whose canonical form doesn't match the key suffix will receive a `409 IDEMPOTENCY_KEY_MISMATCH` response.

---

## Server behaviour

### Validation order

1. **Missing header** → `400 IDEMPOTENCY_KEY_REQUIRED`
2. **Malformed key** (wrong shape, non-UUID prefix, non-hex suffix) → `400 IDEMPOTENCY_KEY_MALFORMED`
3. **Tenant mismatch** (key prefix ≠ authenticated tenant) → `400 IDEMPOTENCY_KEY_TENANT_MISMATCH`
4. **Body hash mismatch** (key suffix ≠ SHA-256 of received body) → `409 IDEMPOTENCY_KEY_MISMATCH`
5. **Cache hit** → return the cached response with `Idempotent-Replay: true` header
6. **Cache miss** → run the request normally; cache deterministic responses (see below)

### Which responses are cached

Cached for 24 hours per the spec:

* `200 OK`, `201 Created`, `202 Accepted`
* `400 Bad Request`, `403 Forbidden`, `404 Not Found`, `409 Conflict`, `413 Payload Too Large`, `422 Unprocessable Entity`

**NOT** cached (the next call should see fresh server state):

* `5xx` Server Errors — transient by definition
* `429 Too Many Requests` — rate limits expire
* `503 Service Unavailable` — circuit-breaker / degraded-mode (state changes when the breaker recovers)

### Replay header

A response served from the idempotency cache MUST carry the header `Idempotent-Replay: true`. Fresh executions either omit the header or set it to `false`. This lets clients distinguish a real execution from a deduplicated replay (useful for telemetry + retry decisions).

### Degraded-mode behaviour

If the cache backend (Redis) is unreachable:

* The server **degrades gracefully** — the request executes normally without idempotency caching.
* An ops-visible warning is logged (`idempotency_cache_get_failed` / `idempotency_cache_set_failed`).
* The user receives the response from the executed workflow, NOT a 5xx.

The reasoning: locking out every write request because Redis is down is worse for tenants than losing the deduplication property for a few minutes. Operators can monitor the warning rate via Prometheus + page on sustained loss.

---

## Client guidance

### Python SDK

The DataHub Python SDK ships a deterministic key composer in [`datahub_interoperability.idempotency`](../../sdk/python/datahub_interoperability/idempotency.py). The high-level `AssetsAPI.create_data_first()` method composes the key automatically:

```python
from datahub_interoperability import DataHubClient, DataHubClientConfig

client = DataHubClient(DataHubClientConfig(
    base_url="https://api.stagingmeshant-internal.example.com/api/v1",
    api_token="...",
))

result = await client.assets.create_data_first(
    tenant_uuid=my_tenant_uuid,
    file_id="01234567-89ab-cdef-0123-456789abcdef",
    key="my-asset",
    name="My Asset",
)
# Subsequent identical calls within 24 h return the same response
# without re-running the workflow.
```

### Compose the key manually (any language)

```python
from datahub_interoperability.idempotency import compose_idempotency_key, IDEMPOTENCY_HEADER

body = {"file_id": "...", "key": "my-asset", "name": "My Asset"}
key = compose_idempotency_key(my_tenant_uuid, body)
# Send as: Idempotency-Key: <key>
```

Equivalent in any language — the server only cares about the wire format:

```
canonical = json.dumps(body, sort_keys=True, separators=(',', ':')).encode('utf-8')
sha = hashlib.sha256(canonical).hexdigest()
key = f"{tenant_uuid_lowercase}:{sha}"
```

---

## Error codes

| Code | HTTP | Meaning |
|---|---|---|
| `IDEMPOTENCY_KEY_REQUIRED` | 400 | Header is missing |
| `IDEMPOTENCY_KEY_MALFORMED` | 400 | Header doesn't match `<uuid>:<sha256>` shape |
| `IDEMPOTENCY_KEY_TENANT_MISMATCH` | 400 | Key prefix is a different tenant's UUID |
| `IDEMPOTENCY_KEY_MISMATCH` | 409 | Key suffix doesn't match the actual body hash |

---

## Implementation references

* Server: [`hub/apps/core/idempotency.py`](../../hub/apps/core/idempotency.py)
* Server tests: [`hub/apps/assets/tests/test_data_first_idempotency.py`](../../hub/apps/assets/tests/test_data_first_idempotency.py)
* SDK: [`sdk/python/datahub_interoperability/idempotency.py`](../../sdk/python/datahub_interoperability/idempotency.py)
* SDK tests: [`sdk/python/tests/test_idempotency.py`](../../sdk/python/tests/test_idempotency.py)
* View wiring: [`hub/apps/assets/views.py::AssetViewSet.data_first`](../../hub/apps/assets/views.py)
