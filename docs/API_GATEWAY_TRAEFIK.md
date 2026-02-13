# API Paths: Default vs Optional Traefik Entrypoint

**Last Updated**: 2026-01-28

This document describes how the frontend and API can be reached: the **default path** (direct to api-service) and the **optional path** via Traefik as a single entrypoint.

---

## Overview

| Path | Traffic flow | When to use |
|------|--------------|-------------|
| **Default** | Frontend → api-service directly | Default; no Traefik/API Gateway in path |
| **Optional (via Traefik)** | Browser → Traefik → (Frontend or API Gateway → api-service) | Single entrypoint, TLS, API key at gateway |

---

## 1. Default path (no Traefik)

**Behaviour**: The frontend is built with `VITE_API_BASE_URL` pointing at the api-service (Django). All API and WebSocket traffic goes directly from the browser to api-service; it does **not** go through Traefik or the FastAPI API Gateway.

### Configuration

- **Frontend**: Set `VITE_API_BASE_URL` to the api-service base URL including `/api/v1`.
  - In Docker Compose (default): `VITE_API_BASE_URL=http://api-service:8000/api/v1` (for in-cluster) or for browser e.g. `http://localhost:8000/api/v1`.
  - Do **not** set `VITE_USE_TRAEFIK_ENTRYPOINT` (or set it to `false`).
- **Auth**: Session/cookie and Bearer token auth are handled by Django (api-service). No API key is required at the edge.

### Example (Docker Compose)

```bash
# .env or docker-compose environment
VITE_API_BASE_URL=http://api-service:8000/api/v1
VITE_WS_BASE_URL=ws://api-service:8000
# Leave unset or false for default path
# VITE_USE_TRAEFIK_ENTRYPOINT=false
```

When the app is served from the same host as the user (e.g. frontend at `http://localhost:3000` and API at `http://localhost:8000`), use:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 2. Optional path: via Traefik (single entrypoint)

**Behaviour**: All traffic enters through Traefik. Traefik routes:

- `GET /` (and other non-API paths) → **frontend** service (static/app).
- `GET /api/v1/...` → **API Gateway** (FastAPI) → api-service (Django).

So the browser talks only to one origin (e.g. `https://hub.example.com`); TLS and routing are handled by Traefik.

### Configuration

1. **Traefik**
   Use the dynamic routes in `infrastructure/traefik/dynamic/routes.yml`, which include:
   - A router for `/api/v1` → api-gateway (and optionally host-based API router).
   - A router for `/` (catch-all) → frontend service (when “single entrypoint” is enabled).

2. **Frontend**
   - Set `VITE_USE_TRAEFIK_ENTRYPOINT=true`.
   - Set `VITE_API_BASE_URL` to the **Traefik** API base URL (same origin as the app), e.g. `https://api.hub.local/api/v1` or `https://hub.example.com/api/v1` so that API calls go through Traefik → API Gateway.
   - If you use a dedicated API host (e.g. `api.hub.local`), set `VITE_API_BASE_URL=https://api.hub.local/api/v1` and ensure CORS and cookies are configured for that origin.

3. **Auth**
   - **Via API Gateway (Traefik → api-gateway)**: API key (e.g. `X-API-Key` or `Authorization`) is validated by the FastAPI API Gateway. Session/cookie auth may still be used if the gateway forwards cookies to api-service and the frontend uses the same origin or allowed CORS.
   - **Direct api-service (default path)**: Session/cookie and Bearer token only; no gateway API key.

### Example (Traefik as entrypoint)

```bash
# Frontend build/runtime (same origin for app and API)
VITE_USE_TRAEFIK_ENTRYPOINT=true
VITE_API_BASE_URL=https://hub.example.com/api/v1
VITE_WS_BASE_URL=wss://hub.example.com

# Or API on a separate host
VITE_USE_TRAEFIK_ENTRYPOINT=true
VITE_API_BASE_URL=https://api.hub.local/api/v1
VITE_WS_BASE_URL=wss://api.hub.local
```

---

## 3. Gateway-originated headers

When a request reaches api-service **via the API Gateway** (Traefik → API Gateway → api-service), the gateway sets the following headers on the request to the backend:

| Header | Set by gateway | Description |
|--------|----------------|-------------|
| `X-Gateway-Tenant-ID` | Yes | Tenant ID associated with the validated API key |
| `X-Gateway-User-ID` | Yes (if user-scoped key) | User ID associated with the API key |
| `X-Gateway-Request-ID` | Yes | Request ID for tracing/correlation |

**api-service behavior (ignore, do not trust for auth)**
api-service **ignores** these headers for authentication and authorization. Tenant and user are derived **only** from api-service’s own auth:

- **JWT** (Bearer token): tenant/user from token payload and DB lookup
- **API key** (ApiKey / X-API-Key): tenant/user from API key lookup in the hub DB
- **Session/cookie**: tenant/user from Django session

The gateway sets `X-Gateway-*` for logging and correlation; the backend does **not** use them to set `request.tenant_id`, `request.tenant`, or `request.user`. So:

- **(a) api-service ignores** gateway-originated headers and derives tenant/user from its own auth.
- **(b) Trust is not used** — there is no “trust when request is from gateway” path. If trust were introduced later, it would require verifying that the request actually came from the gateway (e.g. shared secret or network isolation) and must be documented and tested.

**Security (forged headers)**
Because api-service does not read `X-Gateway-Tenant-ID` or `X-Gateway-User-ID` for auth, a direct request to api-service with forged `X-Gateway-Tenant-ID` / `X-Gateway-User-ID` **cannot** override the authenticated tenant or user. Cross-tenant escalation via these headers is not possible. A regression test in `tests/security/test_gateway_headers_forged.py` asserts that forged gateway headers do not change tenant/user context (no mocks).

---

## 4. Auth model per path

| Path | Auth at edge | Notes |
|------|----------------|-------|
| **(1) Frontend → api-service direct** | Session/cookie or JWT (Django) | No API key required. Same as when not using Traefik. |
| **(2) Client → Traefik → API Gateway → api-service** | API key required | Session/cookie is **not** supported on this path; API key (e.g. `X-API-Key` or `Authorization: ApiKey <key>`) is required. Gateway validates the key and forwards the request; api-service validates the key again and derives tenant/user from it. |

When using the gateway path, configure API keys in the hub (tenant/developer) and pass the key in requests as documented in the API Gateway (e.g. `X-API-Key` or `Authorization: ApiKey <key>`).

---

## 5. Rate limiting

Rate limiting depends on the path; limits and response headers may differ.

| Path | Rate limiting | Notes |
|------|----------------|-------|
| **Traefik → API Gateway → api-service** | **API Gateway** (FastAPI, `services/api-gateway/`): tier-based (FREE, PRO, ENTERPRISE), per-tenant and per-API-key when configured. Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After` on 429. |
| **Frontend → api-service direct** | **Django** `hub.apps.rate_limiting.middleware.RateLimitMiddleware`: per-tenant and per-user limits. Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and optionally `X-RateLimit-User-Limit`, `X-RateLimit-User-Remaining`. |

When traffic goes through the API Gateway, rate limiting is applied at the gateway first; api-service may apply its own limits on the forwarded request. When traffic hits api-service directly, only Django rate limiting applies. See `docs/ARCHITECTURE.md` (BaaS / API Gateway) and `hub/apps/rate_limiting/` for implementation details.

---

## 6. Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | Yes (for API calls) | Base URL for the REST API including `/api/v1`. Default path: api-service URL. Traefik path: Traefik entrypoint URL (e.g. `https://api.hub.local/api/v1`). |
| `VITE_USE_TRAEFIK_ENTRYPOINT` | No | Set to `true` when the app is served and the API is reached via Traefik (single entrypoint). When `true`, the frontend uses `VITE_API_BASE_URL` as the Traefik API base. Default: unset/false (direct api-service). |
| `VITE_WS_BASE_URL` | No (optional) | WebSocket base URL (e.g. `ws://api-service:8000` or `wss://api.hub.local`). |

Build-time note: Vite embeds these at build time. Rebuild the frontend after changing `VITE_*` values.

---

## 7. Integration test (no mocks)

When Traefik is used as the single entrypoint, an integration test verifies routing with real services:

- **Location**: `tests/integration/test_traefik_routing.py`
- **Run (recommended)**: `./scripts/run_phase10_traefik_routing_tests.sh` — starts required services and runs tests inside api-service, hitting Traefik at `https://traefik:443`.
- **Run manually**: Start Traefik, frontend, api-gateway, api-service (and dependencies) with Docker Compose, then:
  ```bash
  docker compose exec -e PYTEST_DOCKER_COMPOSE_RUNTIME=1 -e TRAEFIK_BASE_URL=https://traefik:443 api-service \
    python -m pytest tests/integration/test_traefik_routing.py -v -m 'integration and docker_compose_runtime'
  ```
- **Assertions**:
  - `GET /` via Traefik returns 200 and HTML from the frontend.
  - `GET /api/v1/health` via Traefik returns 200 and JSON from the API Gateway (aggregate health with `status` and `backend_services`).

No mocks; real Traefik, frontend, api-gateway, and api-service are used.

---

## 8. URLs and health checks when Traefik is the entrypoint

- **Frontend**: Served at the Traefik host/port and path `/` (e.g. `https://hub.example.com/`). Health: Traefik routes `/` to the frontend service; the frontend container’s own health check remains on the service (e.g. `http://frontend:80/`).
- **API**: `https://<traefik-host>/api/v1/...` or `https://api.hub.local/api/v1/...` (if using the host-based API router). Health: e.g. `GET /api/v1/health` or the gateway’s `/health` behind Traefik; Traefik forwards to the API Gateway, which then talks to backends.
- **Traefik**: Dashboard and internal APIs are configured separately (e.g. `traefik.hub.local`); see `infrastructure/traefik/` and docker-compose.

---

## 9. Summary

- **Default**: Set `VITE_API_BASE_URL` to api-service (e.g. `http://api-service:8000/api/v1`). Do not set `VITE_USE_TRAEFIK_ENTRYPOINT`. Auth is session/Bearer on api-service.
- **Optional (Traefik)**: Set `VITE_USE_TRAEFIK_ENTRYPOINT=true` and `VITE_API_BASE_URL` to the Traefik API base (e.g. `https://api.hub.local/api/v1`). Auth at the edge is API key at the gateway; document session/Bearer if used end-to-end.
