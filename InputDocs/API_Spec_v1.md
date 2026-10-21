# API Spec v1

This document defines the **external HTTP API (v1)** for the Interoperable Data Hub MVP.

It covers:

- Resource models (JSON representations) derived from the Domain Model.  
- Endpoints and methods.  
- Auth & tenant scoping.  
- Synchronous vs asynchronous behavior (Jobs).  
- Error format and basic security.

This spec is **implementation-agnostic** (no specific framework assumed).

---

## 1. General Conventions

### 1.1 Base URL & Versioning

- Base URL: `https://api.<hub-domain>/api/v1`  
- All endpoints described here are under `/api/v1`.  
- Future versions will live under `/api/v2`, etc.  
  v1 must remain stable for the MVP lifecycle.

### 1.2 Content Types

- Request/response body: `application/json; charset=utf-8`
- File uploads:
  - Preferred: upload via **pre-signed URLs** obtained from `/files/init`.
  - Optional future: `multipart/form-data` upload endpoints.

### 1.3 Authentication & Tenant Scoping

- Auth: **Bearer token** in `Authorization` header:

  ```http
  Authorization: Bearer <token>
  ```

- The token contains at least:
  - `tenant_id`
  - `user_id`
  - `roles[]` (e.g. `TENANT_ADMIN`, `DATA_PROVIDER`, `DATA_CONSUMER`, `AUDITOR`)

- Most endpoints are **tenant-scoped**:
  - They operate only on resources belonging to `tenant_id` in the token.
  - No explicit `tenant_id` parameter is needed for standard calls.
- Some endpoints (e.g. marketplace discovery, semantic URIs) can span multiple tenants (read-only).

Platform-admin / cross-tenant operations are out of scope for public v1.

### 1.4 Roles & Authorization

High-level roles:

- `TENANT_ADMIN`
  - Manage tenant-level configuration and users (see §12 User Management API).
- `DATA_PROVIDER`
  - Create/edit assets and contracts.
  - Upload data.
  - Trigger DQ and compliance checks for their tenant.
- `DATA_CONSUMER`
  - Browse internal catalog & public marketplace.
  - Request/purchase access.
  - Access assets they are entitled to.
- `AUDITOR`
  - View compliance/DQ reports and audit logs.

---

## 15. User Management API

### 15.1 POST /users

Create a new user in the current tenant.

- **Method & URL:** `POST /api/v1/users`
- **Roles:** `TENANT_ADMIN` only

**Request Body**

```json
{
  "email": "user@example.com",
  "display_name": "Jane Doe",
  "roles": ["DATA_PROVIDER", "DATA_CONSUMER"],
  "send_invitation": true
}
```

**Request Fields**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `email` | string | Yes | - | User email address. Must be unique within tenant. Valid email format required. |
| `display_name` | string | No | - | User's display name. Max 255 characters. |
| `roles` | array of strings | No | `[]` | Array of role keys (`TENANT_ADMIN`, `DATA_PROVIDER`, `DATA_CONSUMER`, `AUDITOR`). At least one role is required. |
| `send_invitation` | boolean | No | `true` | If `true`, sends invitation email to user. If `false`, user is created but must be activated manually. |

**Response (201 Created)**

```json
{
  "user": {
    "id": "uuid",
    "tenant_id": "uuid",
    "email": "user@example.com",
    "display_name": "Jane Doe",
    "status": "INVITED",
    "roles": ["DATA_PROVIDER", "DATA_CONSUMER"],
    "created_at": "2025-01-15T10:00:00Z",
    "created_by_user_id": "uuid"
  },
  "invitation_token": "550e8400-e29b-41d4-a716-446655440000" // Only if send_invitation = false
}
```

**Behavior**

- Creates user with `status = INVITED` (if `send_invitation = true`) or `status = ACTIVE` (if `send_invitation = false`).
- If `send_invitation = true`:
  - Sends invitation email with activation link.
  - User must click link and set password to activate account.
- If `send_invitation = false`:
  - User is created as `ACTIVE` (for programmatic user creation).
  - `invitation_token` is returned in response (can be sent separately).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid email format, empty roles array, or duplicate email within tenant. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `TENANT_ADMIN` role. |
| `409 Conflict` | `USER_ALREADY_EXISTS` | User with this email already exists in the tenant. |

---

### 15.2 GET /users

List users in the current tenant.

- **Method & URL:** `GET /api/v1/users?status=ACTIVE&limit=20&offset=0`
- **Roles:** `TENANT_ADMIN` only

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string (enum) | No | Filter by user status (`ACTIVE`, `INVITED`, `DISABLED`). |
| `role` | string | No | Filter by role key (e.g., `DATA_PROVIDER`). |
| `limit`, `offset` | integer | No | Pagination parameters. |

**Response**

```json
{
  "items": [
    {
      "id": "uuid",
      "tenant_id": "uuid",
      "email": "user@example.com",
      "display_name": "Jane Doe",
      "status": "ACTIVE",
      "roles": ["DATA_PROVIDER", "DATA_CONSUMER"],
      "created_at": "2025-01-15T10:00:00Z",
      "last_login_at": "2025-01-20T14:30:00Z"
    }
  ],
  "total": 25,
  "limit": 20,
  "offset": 0
}
```

---

### 15.3 GET /users/{id}

Get a single user by ID.

- **Method & URL:** `GET /api/v1/users/{id}`
- **Roles:** `TENANT_ADMIN` only (or users can view their own profile)

**Response**

Returns user JSON (same structure as list response item).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `USER_NOT_FOUND` | User with given ID does not exist or is not in the current tenant. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `TENANT_ADMIN` role and is not viewing their own profile. |

---

### 15.4 PATCH /users/{id}

Update a user (roles, display name, status).

- **Method & URL:** `PATCH /api/v1/users/{id}`
- **Roles:** `TENANT_ADMIN` only

**Request Body**

```json
{
  "display_name": "Jane Smith",
  "roles": ["DATA_PROVIDER"],
  "status": "ACTIVE"
}
```

All fields are optional; only provided fields are updated.

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `display_name` | string | No | New display name. Can be `null` to clear. |
| `roles` | array of strings | No | New roles array. Must include at least one role. |
| `status` | string (enum) | No | New status (`ACTIVE`, `INVITED`, `DISABLED`). |

**Status Transition Rules**

- `INVITED` → `ACTIVE`: User has accepted invitation.
- `ACTIVE` → `DISABLED`: User is deactivated (cannot log in, but data is preserved).
- `DISABLED` → `ACTIVE`: User is reactivated.
- `ACTIVE` → `INVITED`: Not allowed (cannot revert to invitation state).

#### 15.4.1 User Role Change Impact on Sessions

When a user's roles are changed via `PATCH /users/{id}`, the following rules apply to active sessions and permissions:

**Immediate Impact**

- **Role changes take effect immediately**:
  - New roles are applied to the user record in the database
  - Updated roles are reflected in the user's JWT token claims on next token refresh
  - **Active sessions are NOT automatically invalidated** (see below for details)

**Session Invalidation Behavior**

- **JWT access tokens**:
  - **Current tokens remain valid** until expiration (typically 15 minutes)
  - Users with revoked roles can continue to use current tokens until they expire
  - **Next token refresh** will include updated roles
  - **Recommendation**: For security-sensitive role changes (e.g., revoking `TENANT_ADMIN`), consider forcing token refresh or invalidating sessions
- **Refresh tokens**:
  - **Refresh tokens remain valid** until expiration or revocation
  - When refresh token is used to obtain a new access token, new token includes updated roles
- **API keys**:
  - **API keys are NOT affected** by user role changes
  - API keys have their own scopes and are independent of user roles

**Permission Enforcement**

- **Authorization checks**:
  - Authorization is checked on every API request using the current JWT token claims
  - If a user's roles are revoked, they will be denied access on their next request (after token refresh)
  - **In-flight operations**: Operations already in progress may complete if they started before role change
- **Immediate enforcement** (future enhancement):
  - Platform may support immediate session invalidation for critical role changes
  - This would require:
    - Maintaining a session blacklist (e.g., Redis)
    - Checking blacklist on every request
    - Invalidating tokens when roles are revoked

**Best Practices**

- **For security-sensitive role changes**:
  - Revoke refresh tokens: `POST /auth/revoke-refresh-tokens` (if available)
  - Force user to re-authenticate
  - Monitor for unauthorized access attempts
- **For non-critical role changes**:
  - Allow natural token expiration (15 minutes)
  - Updated roles will be applied on next token refresh

**Audit Trail**

- Role changes are logged in `audit_events` with:
  - Event type: `USER_ROLES_UPDATED`
  - Old and new roles in `details_json`
  - User ID and admin who made the change
  - Timestamp of change

**Response**

Returns updated user JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `USER_NOT_FOUND` | User with given ID does not exist or is not in the current tenant. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid status transition, empty roles array, or invalid role key. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `TENANT_ADMIN` role. |

---

### 15.5 DELETE /users/{id}

Delete or disable a user.

- **Method & URL:** `DELETE /api/v1/users/{id}`
- **Roles:** `TENANT_ADMIN` only

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `hard_delete` | boolean | No | `false` | If `true`, permanently deletes user (irreversible). If `false`, sets `status = DISABLED` (soft delete). |

**Behavior**

- **Soft delete** (default): Sets `users.status = DISABLED`. User data is preserved but user cannot log in.
- **Hard delete**: Permanently deletes user record (only if user has no associated resources, e.g., no assets created, no audit events).

#### 15.5.1 User Deletion and Resource Ownership

**Associated Resources Definition**

A user is considered to have "associated resources" if any of the following exist:

1. **Assets**: User is the `created_by_user_id` for any asset with `status != DELETED`
2. **Contracts**: User is the `created_by_user_id` for any contract with `status != DELETED`
3. **Datasets**: User is the `created_by_user_id` for any dataset
4. **Files**: User is the `created_by_user_id` for any file with `status != DELETED`
5. **Marketplace Listings**: User is the `created_by_user_id` for any listing with `status != DELETED`
6. **Marketplace Orders**: User is the `requested_by_user_id` for any order
7. **Active Jobs**: User is the `created_by_user_id` for any job with `status IN (PENDING, RUNNING)`
8. **Audit Events**: User is referenced in any `audit_events` record (as `actor_user_id` or `resource_id`)

#### 15.5.2 Running Jobs During User Deletion

**Behavior for PENDING Jobs**

- **Soft delete**: When a user is soft-deleted (`hard_delete = false`):
  - `PENDING` jobs remain in queue and can be processed normally
  - Jobs continue to reference the deleted user's ID in `created_by_user_id`
  - Jobs are not cancelled or modified
- **Hard delete**: When a user is hard-deleted (`hard_delete = true`):
  - Hard delete is **blocked** if user has any `PENDING` jobs (counted as "associated resources")
  - User must first wait for jobs to complete or manually cancel them before hard delete

**Behavior for RUNNING Jobs**

- **Soft delete**: When a user is soft-deleted (`hard_delete = false`):
  - **RUNNING jobs are NOT automatically cancelled**
  - Jobs continue to execute normally until completion
  - Jobs remain associated with the deleted user's ID in `created_by_user_id`
  - **Rationale**: Cancelling running jobs could cause data loss or incomplete operations (e.g., partial DQ/compliance results)
  - **Recommendation**: If immediate cancellation is needed, manually cancel jobs via `POST /jobs/{id}/cancel` before deleting user
- **Hard delete**: When a user is hard-deleted (`hard_delete = true`):
  - Hard delete is **blocked** if user has any `RUNNING` jobs (counted as "associated resources")
  - Error response includes job count:
    ```json
    {
      "error": {
        "code": "USER_HAS_RESOURCES",
        "details": {
          "resource_counts": {
            "active_jobs": 2,
            "running_jobs": 1,
            "pending_jobs": 1
          }
        }
      }
    }
    ```
  - User must wait for jobs to complete or manually cancel them before hard delete

**Job Completion After User Deletion**

- **After soft delete**: When a RUNNING job completes:
  - Job status is updated to `SUCCEEDED` or `FAILED` normally
  - Job results (DQ runs, compliance runs) are created normally
  - `created_by_user_id` remains set to the deleted user's ID (for audit trail)
  - Results are accessible to other tenant members
- **After hard delete**: Hard delete cannot proceed if RUNNING jobs exist, so this scenario does not occur

**Manual Job Cancellation Before User Deletion**

- **Best practice**: Before deleting a user, tenant admins should:
  1. Check for active jobs: `GET /jobs?created_by_user_id={user_id}&status=PENDING,RUNNING`
  2. Cancel jobs if needed: `POST /jobs/{id}/cancel` for each job
  3. Wait for cancellations to complete (jobs transition to `CANCELLED`)
  4. Then proceed with user deletion
- **Automatic cancellation** (future enhancement): Platform may support automatic cancellation of user's jobs during deletion, but this is not part of MVP

**Soft Delete Behavior**

When a user is soft-deleted (`hard_delete = false`):

- **User record**: `users.status = DISABLED`, `users.disabled_at = NOW()`
- **Login blocked**: User cannot log in or use API tokens
- **Resource access**: 
  - Resources created by the user remain accessible to other tenant members
  - Resources are not transferred; `created_by_user_id` remains unchanged
  - Other users in the tenant can continue to access assets, contracts, datasets created by the disabled user
- **Audit events**: User remains in audit logs (referenced by `actor_user_id`)
- **Reactivation**: User can be reactivated by setting `status = ACTIVE` (future enhancement)

**Hard Delete Behavior**

When a user is hard-deleted (`hard_delete = true`):

- **Pre-deletion check**: System verifies user has no associated resources (see list above)
- **If resources exist**: Returns `409 Conflict` with error code `USER_HAS_RESOURCES` and details:
  ```json
  {
    "error": {
      "code": "USER_HAS_RESOURCES",
      "message": "User cannot be hard-deleted because they have associated resources.",
      "details": {
        "resource_counts": {
          "assets": 5,
          "contracts": 2,
          "datasets": 10,
          "files": 15,
          "listings": 1,
          "orders": 3,
          "active_jobs": 0
        },
        "suggestion": "Use soft delete (hard_delete=false) to disable the user while preserving resources."
      }
    }
  }
  ```
- **If no resources exist**:
  - User record is permanently deleted from `users` table
  - User roles are deleted from `user_roles` join table
  - User's API keys are revoked (if any)
  - User's refresh tokens are revoked (if any)
  - **Audit events**: User references in audit logs are preserved (audit logs are append-only), but `actor_user_id` may become a dangling reference (acceptable for audit trail integrity)

**Resource Ownership Transfer (Future Enhancement)**

For MVP, resource ownership is **not transferred** when a user is deleted. Resources remain associated with the deleted user's ID.

**Post-MVP Enhancement** (not required for MVP):
- Option to transfer ownership to another user or tenant admin
- Bulk ownership transfer API: `POST /users/{id}/transfer-resources`
- Ownership transfer audit trail

**Response**

- `204 No Content` on success (both soft and hard delete).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `USER_NOT_FOUND` | User with given ID does not exist or is not in the current tenant. |
| `409 Conflict` | `USER_HAS_RESOURCES` | User cannot be hard-deleted because they have associated resources (assets, contracts, etc.). Use soft delete instead. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `TENANT_ADMIN` role. |

---

### 15.6 POST /users/invite

Resend invitation email to a user.

- **Method & URL:** `POST /api/v1/users/invite`
- **Roles:** `TENANT_ADMIN` only

**Request Body**

```json
{
  "user_id": "uuid"
}
```

**Response**

- `200 OK` with message: `{"message": "Invitation email sent"}`

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `USER_NOT_FOUND` | User with given ID does not exist or is not in the current tenant. |
| `400 Bad Request` | `USER_ALREADY_ACTIVE` | User is already `ACTIVE`; invitation not needed. |

Each endpoint below implies minimum required role(s).

### 1.5 Errors

All error responses use a common structure:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Contract validation failed.",
    "http_status": 400,
    "details": {
      "field_errors": [
        { "path": "info.name", "message": "Name is required" }
      ]
    },
    "request_id": "req-1234567890",
    "timestamp": "2025-01-01T12:34:56Z"
  }
}
```

**Error Response Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `error.code` | string | Yes | Machine-readable error code (uppercase with underscores, e.g. `VALIDATION_FAILED`). |
| `error.message` | string | Yes | Human-readable error message. Safe to display in UI (no stack traces, no secrets). |
| `error.http_status` | integer | Yes | HTTP status code (mirrors the actual HTTP status). |
| `error.details` | object | No | Structured error details. May include field-specific errors, limits, or context. **MUST NOT contain raw PII**. |
| `error.request_id` | string | Yes | Unique request ID for correlation with logs. |
| `error.timestamp` | string (ISO 8601) | Yes | UTC timestamp when error occurred. |

**Common Error Codes (non-exhaustive)**

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `AUTH_UNAUTHORIZED` | 401 | Missing or invalid bearer token. |
| `AUTH_FORBIDDEN` | 403 | Token valid but user lacks required role/permission. |
| `VALIDATION_ERROR` | 400 | Generic input validation error (missing/invalid parameters, bad payload). |
| `VALIDATION_FAILED` | 400 | Contract validation failed (CLI or schema validation). |
| `CONTRACT_VALIDATION_FAILED` | 400 | DataContract CLI validation failed. |
| `CONTRACT_NORMALIZATION_FAILED` | 400 | Contract is valid but normalization to HubContract failed. |
| `CONTRACT_CLI_ERROR` | 502/500 | CLI crashed, timed out, or returned unexpected output. |
| `NOT_FOUND` | 404 | Resource not found (generic). |
| `ASSET_NOT_FOUND` | 404 | Asset with given ID not found or not visible. |
| `FILE_NOT_FOUND` | 404 | File with given ID not found or not visible. |
| `JOB_NOT_FOUND` | 404 | Job with given ID not found or not visible. |
| `COMPLIANCE_BLOCKED` | 409 | Compliance check determined `allowed_to_store = false`. |
| `DQ_FAILED` | 400/500 | DQ run failed (validation or engine error). |
| `FILE_TOO_LARGE` | 413/400 | File exceeds configured maximum size. |
| `FILE_UNSUPPORTED_TYPE` | 400 | File type/extension not supported. |
| `UPLOAD_SESSION_EXPIRED` | 410 | Chunked upload session expired (24-hour TTL). |
| `RATE_LIMIT_EXCEEDED` | 429 | Tenant or user exceeded rate limit. |
| `INTERNAL_ERROR` | 500 | Generic unexpected server-side error. |
| `SYSTEM_UNAVAILABLE` | 503 | Temporary outage or maintenance. |

**Error Response Guidelines**

- The API does **not** return raw PII/sensitive sample data in errors.
- All error responses follow the standard envelope structure above.
- Error codes are stable and documented; clients should handle them programmatically.
- The `details` field structure varies by error code (see endpoint-specific documentation).
- When multiple validation errors occur, `details.field_errors` contains an array of all errors.

### 1.6 Pagination

List endpoints use standardized pagination.

- **Decision (v1):**
  - All list endpoints **MUST** support offset-based pagination.
  - Cursor-based pagination is an **optional extension**, recommended for high-volume endpoints (e.g. `/jobs`, `/audit-events`, `/marketplace/listings`).
  - Adding cursor support to an endpoint is considered a **non-breaking** change as long as existing offset behavior is preserved.

**Offset-based (default, required in v1)**

- Query params:
  - `limit` (int, default 20, max 100)
  - `offset` (int, default 0)
- Response:

  ```json
  {
    "items": [ ... ],
    "total": 123,
    "limit": 20,
    "offset": 0
  }
  ```

- Semantics & consistency:
  - Items are returned in a stable default order per endpoint (typically `created_at DESC, id DESC`, unless specified otherwise).
  - Each request is evaluated against the **current** state of the data store; there is **no cross-page snapshot** guarantee.
  - If data changes between pages (new rows, updates, deletes):
    - Items may shift between pages.
    - Clients **MUST** tolerate occasional duplicates or gaps when paginating with `offset`.
    - For strictly reproducible views, clients SHOULD combine pagination with additional filters (e.g. `created_from` / `created_to`) where available.

**Cursor-based (optional extension for high-volume endpoints)**

Some high-volume list endpoints (for example `/jobs`, `/audit-events`, `/marketplace/listings`) **MAY** also support cursor-based pagination.

- Query params:
  - `limit` (int, default 20, max 100)
  - `cursor` (string, optional)
- Behavior:
  - When `cursor` is present, the server **MUST ignore** `offset` and use cursor-based pagination.
  - When `cursor` is absent, the first page is returned starting from the most recent items.

- Response shape (adds `next_cursor`):

  ```json
  {
    "items": [ ... ],
    "total": 123,
    "limit": 20,
    "offset": 0,
    "next_cursor": "opaque-token-or-null"
  }
  ```

- Cursor format:
  - `next_cursor` is an **opaque, URL-safe string**. Clients **MUST NOT** parse or construct it manually.
  - Internally, the server SHOULD encode the last item’s sort key (e.g. `created_at`, `id`) using a URL-safe Base64 or similar encoding.
  - `next_cursor = null` indicates there are **no more pages**.

- Ordering & consistency guarantees:
  - Each cursor-enabled endpoint defines its ordering (by default: `created_at DESC, id DESC`).
  - Given a particular cursor chain:
    - The server **MUST NOT** return the same item twice in that chain.
    - Items that are created **after** the initial page may or may not appear in subsequent pages of the **same** chain; clients SHOULD restart from the beginning to see new items.
    - Deleting or modifying items between pages may cause some items to be skipped; the API does **not** guarantee full snapshot isolation across pages.
  - Endpoints that support cursor-based pagination will explicitly mention `cursor` and `next_cursor` in their section.


---

## 2. Resource Representations (Summary)

These shapes are **aligned with the Domain Model** but may omit some internals.

### 2.1 Contract

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "status": "DRAFT | VALID | INVALID | WARNING_ONLY",
  "original_spec_type": "ODCS | DATACONTRACT_COM",
  "original_spec_version": "3.0.2",
  "original_format": "JSON | YAML",
  "validation_status": "VALID | INVALID | WARNING_ONLY | ERROR",
  "validation_errors": [],
  "validation_warnings": [],
  "cli_version": "x.y.z",
  "last_validated_at": "2025-01-01T12:00:00Z",
  "hub_contract_version": 1,
  "hub_contract_json": { "...": "HubContract v1 JSON" },
  "normalization_status": "NOT_NORMALIZED | NORMALIZED_OK | NORMALIZED_WITH_WARNINGS | NORMALIZATION_FAILED",
  "normalization_errors": [],
  "normalization_warnings": [],
  "semantic_uri": "https://hub.example.com/id/contract/uuid",
  "created_by_user_id": "uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-02T09:00:00Z"
}
```

> `original_raw` is **not returned by default**; may be accessible via a dedicated endpoint/flag.

---

### 2.2 Asset

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "name": "Customer Orders",
  "slug": "customer-orders",
  "description": "Orders data product for analytics.",
  "domain": "sales",
  "status": "DRAFT | ACTIVE | PUBLIC | RETIRED",
  "primary_contract_id": "uuid",
  "latest_dataset_id": "uuid",
  "quality_status": "UNKNOWN | PASS | WARN | FAIL",
  "compliance_status": "UNKNOWN | PASS | WARN | FAIL",
  "semantic_status": "OK | DEGRADED",
  "semantic_uri": "https://hub.example.com/id/asset/uuid",
  "created_by_user_id": "uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-02T09:00:00Z"
}
```

---

### 2.3 Dataset

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "data_file_id": "uuid",
  "schema_json": {
    "fields": [
      {
        "name": "order_id",
        "data_type": "string",
        "nullable": false
      }
    ]
  },
  "row_count": 120000,
  "sample_json": [
    {
      "order_id": "O123",
      "customer_email": "masked@example.com"
    }
  ],
  "semantic_uri": "https://hub.example.com/id/dataset/uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "created_by_user_id": "uuid"
}
```

(Actual sample values can be masked/anonymized depending on policy.)

---

### 2.4 DQRun

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "data_file_id": null,
  "job_id": "uuid",
  "run_scope": "INTERNAL | EXTERNAL",
  "profile_key": "intake_basic",
  "status": "PENDING | RUNNING | SUCCEEDED | FAILED",
  "overall_status": "PASS | WARN | FAIL | UNKNOWN",
  "quality_score": 95.2,
  "checks_json": [],
  "details_json": {},
  "started_at": "2025-01-01T12:00:00Z",
  "completed_at": "2025-01-01T12:02:00Z",
  "requested_by_user_id": "uuid"
}
```

---

### 2.5 ComplianceRun

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "data_file_id": "uuid",
  "job_id": "uuid",
  "mode": "INTERNAL | EXTERNAL",
  "status": "PENDING | RUNNING | SUCCEEDED | FAILED",
  "overall_status": "PASS | WARN | FAIL | UNKNOWN",
  "risk_level": "LOW | MEDIUM | HIGH",
  "allowed_to_store": true,
  "applicable_regimes": ["GDPR", "LGPD"],
  "detected_categories": ["PII_DIRECT_EMAIL"],
  "column_findings_json": {},
  "details_json": {},
  "started_at": "2025-01-01T12:00:00Z",
  "completed_at": "2025-01-01T12:01:00Z",
  "requested_by_user_id": "uuid"
}
```

---

### 2.6 Job

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "type": "QUALITY_CHECK | COMPLIANCE_CHECK | CONTRACT_VALIDATION | SEMANTIC_MAPPING | CONTRACT_MIGRATION",
  "status": "PENDING | RUNNING | SUCCEEDED | FAILED | CANCELLED",
  "resource_type": "ASSET | CONTRACT | DATASET | DATAFILE | LISTING",
  "resource_id": "uuid",
  "requested_by_user_id": "uuid",
  "started_at": "2025-01-01T12:00:00Z",
  "finished_at": "2025-01-01T12:01:00Z",
  "error_code": null,
  "error_message": null,
  "cancellation_requested": false,
  "timeout_seconds": 1800,
  "percent_complete": 75.5,
  "estimated_remaining_seconds": 450,
  "details_json": {
    "profile_key": "intake_basic",
    "mode": "INTERNAL",
    "engine_version": "1.2.3",
    "partial_results": {}
  },
  "created_at": "2025-01-01T12:00:00Z"
}
```

**Job Response Fields**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique job identifier. |
| `tenant_id` | UUID | Tenant that owns the job. |
| `type` | string (enum) | Job type (see enum values below). |
| `status` | string (enum) | Current job status: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`. |
| `resource_type` | string | Type of resource the job operates on. |
| `resource_id` | UUID | ID of the resource the job operates on. |
| `requested_by_user_id` | UUID | User who requested the job. |
| `started_at` | timestamp (ISO 8601) | When job started execution (null if not started). |
| `finished_at` | timestamp (ISO 8601) | When job completed (null if not finished). |
| `error_code` | string (nullable) | Error code if job failed (e.g., `DQ_TIMEOUT`, `COMPLIANCE_ENGINE_ERROR`). |
| `error_message` | string (nullable) | Human-readable error message if job failed. |
| `cancellation_requested` | boolean | Whether cancellation has been requested (true if `POST /jobs/{id}/cancel` was called). |
| `timeout_seconds` | integer | Maximum runtime in seconds (configurable per job type). |
| `percent_complete` | numeric (nullable) | Progress percentage (0-100) if available. |
| `estimated_remaining_seconds` | integer (nullable) | Estimated time remaining in seconds if available. |
| `details_json` | object (nullable) | Job-specific metadata (engine versions, progress details, partial results). |
| `created_at` | timestamp (ISO 8601) | When job was created. |

**Job type enum**

The `type` field uses the shared job type enumeration defined in the Technical Design Document (`jobs.type`):

- `QUALITY_CHECK`
- `COMPLIANCE_CHECK`
- `CONTRACT_VALIDATION`
- `SEMANTIC_MAPPING`
- `CONTRACT_MIGRATION`

All API clients must use these exact values.
```

---

### 2.7 AuditEvent

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "actor_user_id": "uuid",
  "actor_tenant_id": "uuid",
  "event_type": "ASSET_CREATED",
  "resource_type": "ASSET",
  "resource_id": "uuid",
  "occurred_at": "2025-01-01T12:00:00Z",
  "request_id": "req-123456",
  "details_json": {
    "asset_name": "Customer Orders",
    "asset_status": "ACTIVE"
  }
}
```

---

### 2.8 Marketplace Listing

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "status": "DRAFT | PUBLISHED | SUSPENDED",
  "title": "Customer Orders (EU)",
  "short_description": "Daily snapshot of EU orders.",
  "long_description": "Markdown or text with more detail...",
  "price_model": "FREE | ONE_TIME | SUBSCRIPTION | CONTACT_SALES",
  "price_amount": 99.0,
  "currency": "USD",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-02T09:00:00Z"
}
```

---

### 2.9 Order / Entitlement (simplified)

```json
{
  "id": "uuid",
  "consumer_tenant_id": "uuid",
  "listing_id": "uuid",
  "status": "REQUESTED | APPROVED | REJECTED | CANCELLED",
  "requested_by_user_id": "uuid",
  "approved_by_user_id": "uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-02T09:00:00Z"
}
```

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "listing_id": "uuid",
  "order_id": "uuid",
  "status": "ACTIVE | EXPIRED | REVOKED",
  "granted_at": "2025-01-01T12:00:00Z",
  "expires_at": null
}
```

---

### 2.10 Tenant

```json
{
  "id": "uuid",
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "status": "ACTIVE | SUSPENDED | DELETED",
  "kyc_status": "VERIFIED | UNVERIFIED",
  "region": "us-east-1",
  "deleted_at": "2025-01-15T10:00:00Z | null",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

**Field Notes**:
- `deleted_at`: Only present when `status = DELETED`. Indicates when the tenant was marked for deletion. Used for retention period tracking (default: 30 days before physical deletion).

---

## 3. Contracts API

### 3.1 POST /contracts

Create a **contract** from an external spec file or JSON (contract-first or contract-only).

- **Method & URL:** `POST /api/v1/contracts`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Request body (two modes)**

1. File-mode:

```json
{
  "asset_id": "uuid-or-null",
  "original_spec_type": "ODCS",
  "original_spec_version": "3.0.2",
  "original_format": "YAML",
  "original_raw": "<full YAML string>",
  "validate": true
}
```

2. JSON-mode:

```json
{
  "asset_id": "uuid-or-null",
  "original_spec_type": "DATACONTRACT_COM",
  "original_spec_version": "0.4.0",
  "original_format": "JSON",
  "original_raw": "{ "name": "..." }",
  "validate": true
}
```

**Request Fields**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `asset_id` | string (UUID) or null | No | `null` | UUID of associated asset. `null` allowed for contract-only assets. |
| `original_spec_type` | string (enum) | Yes | - | Contract spec type: `ODCS` or `DATACONTRACT_COM` |
| `original_spec_version` | string | Yes | - | Version of the spec (e.g. `3.0.2`, `0.4.0`) |
| `original_format` | string (enum) | Yes | - | Format of original contract: `JSON` or `YAML` |
| `original_raw` | string | Yes | - | Full contract content as string (YAML or JSON) |
| `validate` | boolean | No | `true` | If `true` (default), triggers CLI validation + normalization synchronously. If `false`, contract is created with `status = DRAFT` and `validation_status = null` without running CLI. |

**Behavior**

- Creates Contract record with `status = DRAFT` (default).
- If `validate = true` (default when omitted):
  - Calls DataContract CLI synchronously (with timeout, typically 30-60 seconds).
  - On success:
    - Sets `validation_status` based on CLI results (`VALID`, `INVALID`, `WARNING_ONLY`, or `ERROR`).
    - Computes `hub_contract_json`, sets `normalization_status`.
    - Updates `status` to match validation result (`VALID`, `INVALID`, or `WARNING_ONLY`).
  - On CLI failure/timeout:
    - Sets `validation_status = ERROR`.
    - Sets `status = INVALID`.
    - Returns error response (see below).
- If `validate = false`:
  - Contract is created with `status = DRAFT`.
  - `validation_status = null`.
  - `hub_contract_json = null`.
  - Client must call `POST /contracts/{id}/validate` later to validate.

**Success Response (201 Created)**

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid-or-null",
  "status": "DRAFT | VALID | INVALID | WARNING_ONLY",
  "original_spec_type": "ODCS",
  "original_spec_version": "3.0.2",
  "original_format": "YAML",
  "validation_status": "VALID | INVALID | WARNING_ONLY | ERROR | null",
  "validation_errors": [],
  "validation_warnings": [],
  "cli_version": "x.y.z",
  "last_validated_at": "2025-01-01T12:00:00Z | null",
  "hub_contract_version": "1.0.0",
  "hub_contract_json": { "...": "HubContract v1 JSON" } | null,
  "normalization_status": "NOT_NORMALIZED | NORMALIZED_OK | NORMALIZED_WITH_WARNINGS | NORMALIZATION_FAILED | null",
  "normalization_errors": [],
  "normalization_warnings": [],
  "semantic_uri": "https://hub.example.com/id/contract/uuid",
  "created_by_user_id": "uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-02T09:00:00Z"
}
```

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Missing required fields, invalid enum values, or malformed request body. |
| `400 Bad Request` | `CONTRACT_VALIDATION_FAILED` | CLI validation failed (when `validate = true`). Response includes structured `errors` and `warnings` arrays in `error.details` (see §3.1.1 for format). |
| `400 Bad Request` | `CONTRACT_NORMALIZATION_FAILED` | Contract is valid but normalization to HubContract failed. Response includes `normalization_errors` in `error.details`. |
| `422 Unprocessable Entity` | `UNSUPPORTED_SPEC_VERSION` | `original_spec_version` is not supported for the given `original_spec_type`. |
| `422 Unprocessable Entity` | `INVALID_SPEC_FORMAT` | `original_format` does not match the actual content in `original_raw` (e.g., JSON format but content is YAML). |
| `500 Internal Server Error` | `CONTRACT_CLI_ERROR` | CLI crashed, timed out, or returned unexpected output (technical failure, not user fault). |
| `503 Service Unavailable` | `SYSTEM_UNAVAILABLE` | CLI service is temporarily unavailable. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `404 Not Found` | `ASSET_NOT_FOUND` | `asset_id` provided but asset does not exist or is not visible to tenant. |

#### 3.1.1 Contract Validation Error Response Format

When contract validation fails (`CONTRACT_VALIDATION_FAILED`), the API returns a structured error response with field-level errors and warnings.

**Error Response Structure**

```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "The data contract is not valid. Found 2 errors.",
    "http_status": 400,
    "request_id": "req-1234567890",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "validation_status": "INVALID",
      "cli_version": "0.9.0",
      "original_spec_type": "ODCS",
      "original_spec_version": "1.0.0",
      "errors": [
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.fields[0].name",
          "message": "Field name is required.",
          "rule_id": "field_name_required"
        },
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.fields[1].data_type",
          "message": "Invalid data type 'stringy'. Must be one of: string, integer, float, boolean, date, datetime, timestamp.",
          "rule_id": "data_type_enum",
          "suggestion": "Use 'string' instead of 'stringy'.",
          "line_number": 15,
          "column_number": 8
        }
      ],
      "warnings": [
        {
          "severity": "WARNING",
          "category": "METADATA",
          "path": "$.info.description",
          "message": "Description is missing. Consider adding a description for better discoverability.",
          "rule_id": "description_recommended"
        }
      ],
      "summary": {
        "total_errors": 2,
        "total_warnings": 1,
        "errors_by_category": {
          "SCHEMA": 2,
          "METADATA": 0
        }
      }
    }
  }
}
```

**Error Object Fields**

Each error in the `errors` array contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `severity` | string (enum) | Yes | `ERROR`, `WARNING`, `INFO` |
| `category` | string (enum) | Yes | `SCHEMA`, `METADATA`, `QUALITY`, `COMPLIANCE`, `SYNTAX`, `BUSINESS_RULE` |
| `path` | string (JSONPath) | Yes | JSONPath to the field/object with the error (e.g., `$.schema.fields[0].name`) |
| `message` | string | Yes | Human-readable error message (user-facing, no stack traces) |
| `rule_id` | string | No | Identifier of the validation rule that failed (for reference) |
| `suggestion` | string | No | Actionable suggestion for fixing the error |
| `line_number` | integer | No | Line number in source file (if applicable, for YAML/JSON files) |
| `column_number` | integer | No | Column number in source file (if applicable) |

**Error Categories**

| Category | Description | Examples |
|----------|-------------|----------|
| `SYNTAX` | JSON/YAML parsing errors | Invalid JSON, missing quotes, trailing commas |
| `SCHEMA` | Schema definition errors | Missing required fields, invalid field types, invalid enum values |
| `METADATA` | Metadata errors | Missing description, invalid version format, missing owners |
| `QUALITY` | Quality rule errors | Invalid quality rule expressions, unsupported dimensions |
| `COMPLIANCE` | Compliance configuration errors | Invalid jurisdiction codes, missing legal bases |
| `BUSINESS_RULE` | Business logic validation errors | Circular dependencies, invalid references |

**Severity Levels**

| Severity | Meaning | Impact on Contract Status |
|----------|---------|--------------------------|
| `ERROR` | Contract is invalid and cannot be activated | `validation_status = INVALID` |
| `WARNING` | Contract is valid but has issues | `validation_status = WARNING_ONLY` (if no errors) |
| `INFO` | Informational message (best practices) | `validation_status = VALID` (no impact) |

**Validation Status Determination**

The `validation_status` in the response is determined by error severity:

- **`VALID`**: No errors, only INFO messages (or no messages)
- **`WARNING_ONLY`**: Only WARNING and INFO messages, no ERROR messages
- **`INVALID`**: At least one ERROR message
- **`ERROR`**: CLI failed to execute (timeout, crash, unexpected output) - returns `CONTRACT_CLI_ERROR` instead

#### 3.1.2 Contract Normalization Error Examples

When contract normalization fails (`CONTRACT_NORMALIZATION_FAILED`), the API returns structured normalization errors in `error.details.normalization_errors`.

**Normalization Error Response Structure**

```json
{
  "error": {
    "code": "CONTRACT_NORMALIZATION_FAILED",
    "message": "Contract normalization to HubContract failed.",
    "http_status": 400,
    "details": {
      "normalization_errors": [
        {
          "severity": "ERROR",
          "category": "SCHEMA_MAPPING",
          "path": "$.schema.fields[0].type",
          "message": "Unsupported field type 'timestamp' in ODCS v3.0.2. Use 'datetime' instead.",
          "rule_id": "type_mapping_odcs_v3",
          "suggestion": "Update field type to 'datetime' or migrate to a supported spec version."
        },
        {
          "severity": "WARNING",
          "category": "METADATA_MAPPING",
          "path": "$.info.owners",
          "message": "Owner email format is invalid. Expected email address.",
          "rule_id": "owner_email_validation",
          "suggestion": "Update owner email to valid format (e.g., 'user@example.com')."
        }
      ],
      "normalization_warnings": [
        {
          "severity": "WARNING",
          "category": "FIELD_MAPPING",
          "path": "$.schema.fields[2]",
          "message": "Field 'custom_field' is not part of HubContract v1.0.0 schema. Stored in 'extensions'.",
          "rule_id": "extension_field_mapping"
        }
      ],
      "summary": {
        "total_errors": 1,
        "total_warnings": 2,
        "errors_by_category": {
          "SCHEMA_MAPPING": 1,
          "METADATA_MAPPING": 0
        }
      }
    }
  }
}
```

**Normalization Error Categories**

| Category | Description | Examples |
|----------|-------------|----------|
| `SCHEMA_MAPPING` | Errors mapping contract schema to HubContract schema | Unsupported field types, invalid constraints, missing required fields |
| `METADATA_MAPPING` | Errors mapping contract metadata to HubContract metadata | Invalid owner format, missing required metadata, invalid date formats |
| `FIELD_MAPPING` | Errors mapping individual fields | Field name conflicts, type mismatches, constraint violations |
| `QUALITY_RULE_MAPPING` | Errors mapping quality rules | Unsupported rule types, invalid rule expressions, missing rule dependencies |
| `COMPLIANCE_RULE_MAPPING` | Errors mapping compliance rules | Unsupported regime codes, invalid threshold values, missing required compliance fields |
| `VERSION_COMPATIBILITY` | Errors related to spec version compatibility | Unsupported spec version, breaking changes between versions |

**Example Normalization Error Scenarios**

**Scenario 1: Unsupported Field Type**

```json
{
  "severity": "ERROR",
  "category": "SCHEMA_MAPPING",
  "path": "$.schema.fields[0].type",
  "message": "Field type 'bigint' is not supported in HubContract v1.0.0. Supported types: string, integer, float, boolean, date, datetime.",
  "rule_id": "type_mapping_hubcontract_v1",
  "suggestion": "Use 'integer' type instead, or migrate contract to HubContract v2.0.0 which supports 'bigint'."
}
```

**Scenario 2: Missing Required Metadata**

```json
{
  "severity": "ERROR",
  "category": "METADATA_MAPPING",
  "path": "$.info",
  "message": "Required field 'title' is missing in contract metadata.",
  "rule_id": "required_metadata_hubcontract",
  "suggestion": "Add 'title' field to contract metadata (e.g., 'info.title: \"My Data Contract\"')."
}
```

**Scenario 3: Invalid Quality Rule Expression**

```json
{
  "severity": "ERROR",
  "category": "QUALITY_RULE_MAPPING",
  "path": "$.quality.expectations[0].expression",
  "message": "Quality rule expression 'column.not_null()' uses unsupported function 'not_null()'. Supported functions: expect_column_values_to_not_be_null, expect_column_values_to_be_unique.",
  "rule_id": "quality_rule_expression_validation",
  "suggestion": "Update expression to use supported function: 'expect_column_values_to_not_be_null(column=\"field_name\")'."
}
```

**Scenario 4: Extension Field Mapping (Warning)**

```json
{
  "severity": "WARNING",
  "category": "FIELD_MAPPING",
  "path": "$.schema.fields[5]",
  "message": "Field 'custom_metadata' is not part of HubContract v1.0.0 schema. Field will be stored in 'extensions.custom_metadata'.",
  "rule_id": "extension_field_mapping",
  "suggestion": "No action required. Field is preserved in extensions and will be available in HubContract JSON."
}
```

**Normalization Status Values**

- **`NOT_NORMALIZED`**: Contract has not been normalized yet (normalization not attempted)
- **`NORMALIZED_OK`**: Normalization succeeded with no errors or warnings
- **`NORMALIZED_WITH_WARNINGS`**: Normalization succeeded but with warnings (non-blocking issues)
- **`NORMALIZATION_FAILED`**: Normalization failed due to errors (blocking issues)

**Example Error Responses**

**Example 1: Invalid Contract (Multiple Errors)**
```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "The data contract is not valid. Found 3 errors.",
    "http_status": 400,
    "details": {
      "validation_status": "INVALID",
      "errors": [
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.fields[0].name",
          "message": "Field name is required.",
          "rule_id": "field_name_required"
        },
        {
          "severity": "ERROR",
          "category": "SCHEMA",
          "path": "$.schema.primary_key[0]",
          "message": "Primary key field 'order_id' does not exist in schema.fields.",
          "rule_id": "primary_key_reference"
        },
        {
          "severity": "ERROR",
          "category": "SYNTAX",
          "path": "$",
          "message": "Invalid JSON: Unexpected token ',' at line 42.",
          "line_number": 42
        }
      ],
      "summary": {
        "total_errors": 3,
        "total_warnings": 0
      }
    }
  }
}
```

**Example 2: Valid Contract with Warnings**
```json
{
  "error": {
    "code": "CONTRACT_VALIDATION_FAILED",
    "message": "The data contract is valid but has warnings.",
    "http_status": 400,
    "details": {
      "validation_status": "WARNING_ONLY",
      "errors": [],
      "warnings": [
        {
          "severity": "WARNING",
          "category": "METADATA",
          "path": "$.info.description",
          "message": "Description is missing. Consider adding a description for better discoverability.",
          "rule_id": "description_recommended"
        }
      ],
      "summary": {
        "total_errors": 0,
        "total_warnings": 1
      }
    }
  }
}
```

**Note**: Even when `validation_status = WARNING_ONLY`, the API returns HTTP 400 with `CONTRACT_VALIDATION_FAILED` to indicate validation issues. Clients should check `validation_status` to determine if contract can be activated.

---

### 3.2 GET /contracts

List contracts in the current tenant.

- **Method & URL:** `GET /api/v1/contracts?asset_id=<uuid>&status=VALID&limit=20&offset=0`

Query params:

- `asset_id` (optional).
- `status` (optional).
- Pagination.

**Response**

```json
{
  "items": [ { /* Contract */ } ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

---

### 3.3 GET /contracts/{id}

Get a single contract.

- **Method & URL:** `GET /api/v1/contracts/{id}`

Response: `200 OK` with Contract JSON.

---

### 3.4 PATCH /contracts/{id}

Update a contract (e.g., via UI editing of **HubContract JSON**).

- **Method & URL:** `PATCH /api/v1/contracts/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Body (example)**

```json
{
  "hub_contract_json": {
    "...": "updated HubContract v1 JSON"
  },
  "status": "DRAFT"
}
```

**Contract Versioning Behavior**

- **In-place update**: `PATCH /contracts/{id}` updates the existing contract record **in place** (does not create a new version).
- **Version increment**: The `contracts.version` field is **not automatically incremented** on update. It remains the same unless explicitly changed.
- **Version management**: 
  - If a new contract version is needed (e.g., breaking changes), users should create a new contract via `POST /contracts` and link it to the asset.
  - Alternatively, use `POST /contracts/{id}/migrate` to migrate to a new HubContract version (see §3.6).
- **Asset linkage**: 
  - Assets reference contracts via `assets.primary_contract_id`.
  - Updating a contract in place affects all assets that reference it.
  - If an asset needs a different contract version, update `assets.primary_contract_id` to point to the new contract.
- **Historical access**: 
  - Previous contract versions are **not automatically preserved** on update.
  - For audit purposes, contract changes are logged in `audit_events` with the old and new `hub_contract_json` in `details_json`.
  - If version history is required, create new contract records instead of updating in place.

**Update Rules**

- Editing `hub_contract_json` sets `status` back to `DRAFT` until re-validated.
- `validation_status` is reset to `null` when `hub_contract_json` is modified.
- `normalization_status` is reset to `null` when `hub_contract_json` is modified.
- Contract must be re-validated via `POST /contracts/{id}/validate` after update.

#### 3.4.1 Contract Update Impact on Assets

When a contract is updated via `PATCH /contracts/{id}`, the following rules apply to assets that reference the contract:

**Immediate Impact**

- **Contract status reset**: Contract `status` is set to `DRAFT` and `validation_status` is set to `null`
- **Asset status impact**: Assets referencing this contract (`assets.primary_contract_id = <contract_id>`) are **not automatically updated**
- **Asset validation**: Assets remain in their current status (`ACTIVE`, `DRAFT`, etc.) but may become invalid if contract validation fails

**After Re-Validation**

When the contract is re-validated via `POST /contracts/{id}/validate`:

1. **If validation succeeds** (`validation_status = VALID` or `WARNING_ONLY`):
   - Contract `status` can be set to `ACTIVE` (if user chooses)
   - **Assets are NOT automatically re-validated**
   - Assets continue to reference the updated contract
   - **No action required** for assets; they continue to function normally

2. **If validation fails** (`validation_status = INVALID` or `ERROR`):
   - Contract `status` remains `DRAFT` or becomes `INVALID`
   - **Assets referencing this contract may become invalid**:
     - Assets with `status = ACTIVE` remain `ACTIVE` but may show warnings in UI
     - Asset activation gates (DQ, compliance) continue to work
     - **Recommendation**: Users should fix the contract or create a new contract version

**Asset Re-Validation (Optional)**

- Assets are **not automatically re-validated** when their contract is updated
- Users can manually trigger asset re-validation if needed:
  - Re-run DQ/compliance checks: `POST /dq-runs` or `POST /compliance-runs`
  - Check asset status: `GET /assets/{id}`
- **Best practice**: After updating a contract, verify that assets using it are still valid

**Breaking Changes**

If a contract update introduces breaking changes (e.g., schema changes that invalidate existing datasets):

- **Existing datasets are NOT automatically invalidated**
- **Users should**:
  1. Review asset status and DQ/compliance results
  2. Update datasets if schema changes require it
  3. Create a new contract version if breaking changes are needed (instead of updating in place)

**Audit Trail**

- Contract updates are logged in `audit_events` with:
  - Event type: `CONTRACT_UPDATED`
  - Old and new `hub_contract_json` in `details_json` (for audit purposes)
  - Asset IDs that reference the contract (for traceability)

**Response**: `200 OK` with updated Contract JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `CONTRACT_NOT_FOUND` | Contract with given ID does not exist or is not visible to tenant. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid `hub_contract_json` structure or invalid field values. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `409 Conflict` | `CONTRACT_IN_USE` | Contract is referenced by assets and cannot be modified (implementation-specific; may allow updates with warnings). |

---

### 3.5 POST /contracts/{id}/validate

Run **DataContract CLI** validation & normalize into HubContract if needed.

- **Method & URL:** `POST /api/v1/contracts/{id}/validate`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Body** (optional):

```json
{
  "force_normalization": true
}
```

**Response (sync)**

```json
{
  "contract": { /* Contract JSON */ }
}
```

---

### 3.7 DELETE /contracts/{id}

Delete a contract.

- **Method & URL:** `DELETE /api/v1/contracts/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | `false` | If `true`, deletes contract even if it is referenced by assets. If `false`, returns error if contract is in use. |

**Behavior**

- **Soft delete** (default):
  - If contract is referenced by assets (`assets.primary_contract_id = <contract_id>`):
    - Returns `409 Conflict` with error code `CONTRACT_IN_USE` (unless `force = true`).
  - If `force = true`:
    - Deletes contract even if referenced.
    - Assets referencing the contract will have `primary_contract_id = NULL` (may cause asset status issues).
  - If contract is not referenced:
    - Permanently deletes contract record.
    - Emits audit event: `CONTRACT_DELETED`.

**Response**

- `204 No Content` on success.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `CONTRACT_NOT_FOUND` | Contract with given ID does not exist or is not visible to tenant. |
| `409 Conflict` | `CONTRACT_IN_USE` | Contract is referenced by assets (use `force = true` to delete anyway). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

### 3.6 POST /contracts/{id}/migrate

Migrate a contract to a new HubContract version.

- **Method & URL:** `POST /api/v1/contracts/{id}/migrate`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Request Body**

```json
{
  "target_hub_contract_version": "2.0.0",
  "migration_strategy": "ON_WRITE"
}
```

**Request Fields**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `target_hub_contract_version` | string | Yes | - | Target HubContract version (e.g., `"2.0.0"`). Must be a supported version. |
| `migration_strategy` | string (enum) | No | `ON_WRITE` | Migration strategy: `ON_WRITE` (migrate when contract is accessed), `ON_READ` (migrate immediately), `BACKGROUND` (queue background migration job). |

**Migration Strategies**

- **`ON_WRITE`** (default):
  - Contract is migrated when it is next accessed (read or write).
  - Migration happens synchronously during the request.
  - Original contract remains unchanged until migration.
- **`ON_READ`**:
  - Contract is migrated immediately (synchronously).
  - Original contract is updated in place.
  - Returns migrated contract in response.
- **`BACKGROUND`**:
  - Creates a `CONTRACT_MIGRATION` job.
  - Migration happens asynchronously.
  - Client should poll `GET /jobs/{id}` for completion.

**Response**

**Synchronous** (`ON_WRITE` or `ON_READ`):

```json
{
  "contract": { /* Migrated Contract JSON */ },
  "migration_applied": true,
  "migration_details": {
    "source_version": "1.0.0",
    "target_version": "2.0.0",
    "migration_strategy": "ON_READ",
    "warnings": []
  }
}
```

**Asynchronous** (`BACKGROUND`):

```json
{
  "job": {
    "id": "uuid",
    "type": "CONTRACT_MIGRATION",
    "status": "PENDING",
    "resource_type": "CONTRACT",
    "resource_id": "uuid"
  },
  "migration_details": {
    "source_version": "1.0.0",
    "target_version": "2.0.0",
    "migration_strategy": "BACKGROUND"
  }
}
```

#### 3.6.1 Contract Migration Impact on Assets

When a contract is migrated to a new HubContract version, the following rules apply to assets that reference the contract:

**Asset Status Impact**

- **Assets are NOT automatically updated** when their contract is migrated:
  - Assets continue to reference the migrated contract via `assets.primary_contract_id`
  - Asset status (`ACTIVE`, `DRAFT`, etc.) remains unchanged
  - Asset `dq_status` and `compliance_status` remain unchanged
- **Asset contract version awareness**:
  - Assets do not track which HubContract version their contract is using
  - Assets always reference the contract's current `hub_contract_version` (after migration)

**Asset Re-Validation Requirements**

- **After migration** (`ON_READ` or `BACKGROUND` strategy):
  - Assets referencing the migrated contract **do NOT require automatic re-validation**
  - Assets continue to function normally with the migrated contract
  - **Optional re-validation**: Users may choose to re-run DQ/compliance checks if migration introduces schema changes:
    - Re-run DQ: `POST /dq-runs` with `asset_id` or `dataset_id`
    - Re-run compliance: `POST /compliance-runs` with `asset_id` or `dataset_id`
- **Schema compatibility**:
  - If migration introduces breaking schema changes (e.g., removed fields, type changes):
    - Existing datasets may become incompatible with the new contract schema
    - Asset `dq_status` may need to be re-evaluated
    - **Recommendation**: Review asset status and DQ/compliance results after migration

**Migration Strategy Impact on Assets**

- **`ON_WRITE` strategy**:
  - Migration happens lazily when contract is accessed
  - Assets see the migrated contract on next read/write operation
  - No immediate impact on assets
- **`ON_READ` strategy**:
  - Contract is migrated immediately
  - Assets see the migrated contract immediately on next access
  - No immediate impact on assets (migration is transparent)
- **`BACKGROUND` strategy**:
  - Migration happens asynchronously
  - Assets continue to use the old contract version until migration completes
  - After migration completes, assets automatically use the new version
  - **Timing**: Migration typically completes within 5-10 minutes (depending on contract complexity)

**Dataset Compatibility After Migration**

- **Existing datasets**:
  - Datasets attached to assets are **not automatically re-validated** after contract migration
  - Dataset schemas remain unchanged
  - If migration introduces schema changes, datasets may become incompatible
  - **Detection**: Schema validation during dataset attachment will detect incompatibilities
- **New datasets**:
  - New datasets attached after migration use the migrated contract schema
  - Schema validation uses the new contract version

**DQ/Compliance Results After Migration**

- **Existing DQ/compliance runs**:
  - Results remain valid and are not invalidated by contract migration
  - Results reference the contract ID (not the version), so they remain linked
  - **Re-running recommended**: If migration introduces schema or rule changes, users should re-run DQ/compliance checks
- **New DQ/compliance runs**:
  - Use the migrated contract version for validation
  - Results are based on the new contract schema/rules

**Audit Trail**

- Contract migration is logged in `audit_events` with:
  - Event type: `CONTRACT_MIGRATED`
  - Old and new `hub_contract_version` in `details_json`
  - Asset IDs that reference the contract (for traceability)
  - Migration strategy used

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `CONTRACT_NOT_FOUND` | Contract with given ID does not exist or is not visible to tenant. |
| `400 Bad Request` | `UNSUPPORTED_VERSION` | Target HubContract version is not supported or is invalid. |
| `400 Bad Request` | `MIGRATION_NOT_NEEDED` | Contract is already at target version. |
| `400 Bad Request` | `MIGRATION_INCOMPATIBLE` | Migration from source to target version is not supported (breaking changes). |
| `409 Conflict` | `MIGRATION_IN_PROGRESS` | A migration job is already in progress for this contract. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |

---

## 4. Assets & Datasets API

### 4.1 POST /assets

Create a **draft asset** (start of data-first or contract-first flows).

- **Method & URL:** `POST /api/v1/assets`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Body**

```json
{
  "name": "Customer Orders",
  "slug": "customer-orders",
  "description": "Orders data product for analytics.",
  "domain": "sales"
}
```

Response: `201 Created` with Asset JSON.

---

### 4.2 GET /assets

List assets for the current tenant.

- **Method & URL:** `GET /api/v1/assets?status=ACTIVE&domain=sales&limit=20&offset=0`

Query params:

- `status` (optional).
- `domain` (optional).
- Pagination.

Response: list of Asset objects.

---

### 4.3 GET /assets/{id}

Get asset details.

- **Method & URL:** `GET /api/v1/assets/{id}`
- **Roles:** `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR`

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `include` | string (comma-separated) | No | - | Comma-separated list of related resources to include in response. Valid values: `contract`, `datasets`, `latest_dq`, `latest_compliance`. Multiple values can be combined: `?include=contract,latest_dq` |

**Include Parameter Values**

- `contract` - Include the primary (latest) contract associated with the asset.
- `datasets` - Include all datasets for this asset (paginated, see note below).
- `latest_dq` - Include the most recent DQ run for this asset.
- `latest_compliance` - Include the most recent compliance run for this asset.

**Note on `datasets` expansion:**
- When `include=datasets` is specified, the response includes a `datasets` array with all datasets for the asset.
- For assets with many datasets, consider using `GET /assets/{id}/datasets` with pagination instead.
- The `datasets` expansion does not support pagination; it returns all datasets (up to a reasonable limit, e.g., 100).

**Success Response (200 OK)**

**Base response (no `include` parameter):**

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "name": "Customer Orders",
  "slug": "customer-orders",
  "description": "Orders data product for analytics.",
  "domain": "sales",
  "status": "DRAFT | ACTIVE | PUBLIC | RETIRED",
  "primary_contract_id": "uuid",
  "latest_dataset_id": "uuid",
  "quality_status": "UNKNOWN | PASS | WARN | FAIL",
  "compliance_status": "UNKNOWN | PASS | WARN | FAIL",
  "semantic_status": "OK | DEGRADED",
  "semantic_uri": "https://hub.example.com/id/asset/uuid",
  "created_by_user_id": "uuid",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-02T09:00:00Z"
}
```

**Expanded response (with `include` parameter):**

```json
{
  "asset": {
    "id": "uuid",
    "tenant_id": "uuid",
    "name": "Customer Orders",
    "slug": "customer-orders",
    "description": "Orders data product for analytics.",
    "domain": "sales",
    "status": "DRAFT | ACTIVE | PUBLIC | RETIRED",
    "primary_contract_id": "uuid",
    "latest_dataset_id": "uuid",
    "quality_status": "UNKNOWN | PASS | WARN | FAIL",
    "compliance_status": "UNKNOWN | PASS | WARN | FAIL",
    "semantic_status": "OK | DEGRADED",
    "semantic_uri": "https://hub.example.com/id/asset/uuid",
    "created_by_user_id": "uuid",
    "created_at": "2025-01-01T12:00:00Z",
    "updated_at": "2025-01-02T09:00:00Z"
  },
  "contract": { /* Contract JSON (if include=contract) */ } | null,
  "datasets": [ /* Array of Dataset JSON (if include=datasets) */ ] | null,
  "latest_dq_run": { /* DQRun JSON (if include=latest_dq) */ } | null,
  "latest_compliance_run": { /* ComplianceRun JSON (if include=latest_compliance) */ } | null
}
```

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ASSET_NOT_FOUND` | Asset with the given ID does not exist or is not visible to the tenant. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid `include` parameter value (e.g., unknown expansion name). |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role to view this asset. |

---

### 4.4 PATCH /assets/{id}

Update asset metadata or status.

- **Method & URL:** `PATCH /api/v1/assets/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Request Body**

All fields are optional; only provided fields are updated.

```json
{
  "name": "string",
  "description": "string",
  "domain": "string",
  "status": "DRAFT | ACTIVE | PUBLIC | RETIRED",
  "visibility": "INTERNAL | PUBLIC",
  "version": 1
}
```

**Request Fields**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | No | - | Asset name. Must be non-empty if provided. |
| `description` | string | No | - | Asset description. Can be `null` to clear. |
| `domain` | string | No | - | Domain/category (e.g. `sales`, `finance`). Can be `null` to clear. |
| `status` | string (enum) | No | - | Asset status. See validation rules below. |
| `visibility` | string (enum) | No | - | Visibility level. See validation rules below. |
| `version` | integer | **Yes** | - | Current version of the asset (from `GET /assets/{id}` response). Used for optimistic locking. |

**Optimistic Locking**

- The `version` field is **required** in all `PATCH` requests to prevent concurrent modification conflicts.
- Clients MUST obtain the current `version` value from `GET /assets/{id}` before making an update.
- The server compares the provided `version` with the current database value:
  - If they match: Update proceeds and `version` is incremented.
  - If they don't match: Update is rejected with `409 Conflict` and error code `ASSET_CONCURRENT_MODIFICATION`.
- On successful update, the response includes the new `version` value.
- **Client retry behavior**: On `409 Conflict`, clients should:
  1. Fetch the latest asset data via `GET /assets/{id}`.
  2. Re-apply user's changes to the fresh data.
  3. Retry the `PATCH` request with the new `version` value.

**Asset Activation Requirements**

The following table defines the complete requirements for transitioning an asset to `ACTIVE` status:

| Requirement | Condition | Acceptable Values | Notes |
|-------------|-----------|-------------------|-------|
| **Primary Contract** | Required | Contract must exist with:<br>- `status = ACTIVE`<br>- `validation_status = VALID` OR `WARNING_ONLY` (per tenant policy)<br>- `normalization_status in { NORMALIZED_OK, NORMALIZED_WITH_WARNINGS }` | If contract is `WARNING_ONLY`, tenant policy determines if asset can be activated |
| **DQ Status** | If dataset exists | `PASS` OR `WARN` (not `FAIL` or `UNKNOWN`) | If asset has no dataset, this requirement is skipped |
| **Compliance Status** | If dataset exists | `PASS` OR `WARN` (not `FAIL` or `UNKNOWN`) | If asset has no dataset, this requirement is skipped |
| **Dataset** | Optional | Asset can be `ACTIVE` without a dataset | Contract-only assets are allowed |

**Status Transition Validation Rules**

The following rules apply when updating `status`:

| From Status | To Status | Requirements | Error Code if Invalid |
|-------------|-----------|--------------|----------------------|
| Any | `DRAFT` | No restrictions | - |
| `DRAFT` | `ACTIVE` | See **Asset Activation Requirements Table** below | `ASSET_ACTIVATION_BLOCKED` |
| `ACTIVE` | `PUBLIC` | 1. Must have an existing marketplace listing<br>2. Tenant must have `kyc_status = VERIFIED` | `ASSET_PUBLICATION_BLOCKED` |
| `ACTIVE` | `RETIRED` | No restrictions | - |
| `PUBLIC` | `RETIRED` | No restrictions | - |
| `PUBLIC` | `ACTIVE` | No restrictions (downgrade from public) | - |
| `RETIRED` | Any | Not allowed (retired assets cannot be reactivated) | `ASSET_RETIRED` |

**Visibility Validation Rules**

- `visibility = PUBLIC` can only be set when `status = PUBLIC`.
- `visibility = INTERNAL` can be set for any status.
- If `status` is changed to `PUBLIC`, `visibility` is automatically set to `PUBLIC` (even if not provided in request).
- If `status` is changed from `PUBLIC` to another status, `visibility` remains `PUBLIC` unless explicitly changed.

**Success Response (200 OK)**

Returns updated Asset JSON (same structure as `GET /assets/{id}`).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid field values (e.g., empty `name`, invalid enum values). |
| `400 Bad Request` | `ASSET_ACTIVATION_BLOCKED` | Cannot transition to `ACTIVE`: missing valid contract or failed DQ/compliance. Response includes `error.details` with specific blockers. |
| `400 Bad Request` | `ASSET_PUBLICATION_BLOCKED` | Cannot transition to `PUBLIC`: missing listing or tenant not verified. Response includes `error.details` with specific blockers. |
| `400 Bad Request` | `ASSET_RETIRED` | Cannot modify retired assets (status transitions from `RETIRED` are not allowed). |
| `404 Not Found` | `ASSET_NOT_FOUND` | Asset with the given ID does not exist or is not visible to the tenant. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `409 Conflict` | `ASSET_CONCURRENT_MODIFICATION` | Asset was modified by another request (optimistic locking conflict). Client should retry with fresh data. |

---

### 4.5 POST /assets/{id}/datasets

Attach a **dataset** to an asset using an existing DataFile.

- **Method & URL:** `POST /api/v1/assets/{id}/datasets`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Body**

```json
{
  "data_file_id": "uuid",
  "schema_json": {
    "fields": [
      { "name": "order_id", "data_type": "string", "nullable": false }
    ]
  },
  "row_count": 120000,
  "sample_json": [ { "order_id": "..." } ]
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data_file_id` | UUID | Yes | Existing file ID (must belong to tenant and have `status = COMPLETE`). |
| `schema_json` | object | No | Inferred schema (if omitted, schema is inferred from file). |
| `row_count` | integer | No | Number of rows (if omitted, counted from file). |
| `sample_json` | array | No | Sample data rows (if omitted, extracted from file). |

**Validation Rules**

1. **Asset Status**:
   - Asset must be `ACTIVE` or `DRAFT` (cannot attach to `RETIRED` assets).
   - Error code: `ASSET_RETIRED` if asset is `RETIRED`.

2. **Existing Dataset**:
   - If asset already has a dataset:
     - Creates a **new dataset version** (increments `datasets.version`).
     - Previous dataset versions remain accessible for audit/history.
     - **Previous dataset remains active** until new dataset passes all gates (DQ, compliance, schema validation).
     - **Asset `latest_dataset_id` is NOT updated** until new dataset reaches `INTAKE_READY` status (see `Architecture_API_Alignment.md` §5.7.2).
   - If asset has no dataset:
     - Creates first dataset with `version = 1`.

#### 4.5.1 Dataset Versioning Edge Cases

**Case 1: New Dataset Fails DQ/Compliance**

- **Behavior**:
  - New dataset is created with `version = N+1` (where N is the previous version)
  - DQ and compliance jobs are triggered automatically
  - **If DQ fails** (`dq_status = FAIL`):
    - New dataset is marked as `INTAKE_BLOCKED`
    - Asset `latest_dataset_id` remains pointing to previous dataset (or `NULL` if this is the first dataset)
    - Previous dataset remains active and accessible
    - Users can access previous dataset via `GET /datasets/{id}` or `GET /assets/{id}?include=datasets`
  - **If compliance fails** (`compliance_status = FAIL`, `allowed_to_store = false`):
    - New dataset is marked as `INTAKE_BLOCKED`
    - Asset `latest_dataset_id` remains pointing to previous dataset
    - Previous dataset remains active and accessible
  - **User action**: User must fix data issues and re-upload, or delete the failed dataset version

**Case 2: New Dataset Succeeds, Previous Dataset Access**

- **Behavior**:
  - When new dataset reaches `INTAKE_READY`:
    - Asset `latest_dataset_id` is updated to point to the new dataset
    - Previous dataset versions remain in database (not deleted)
    - Previous dataset versions are accessible via:
      - `GET /assets/{id}/datasets` (lists all versions)
      - `GET /datasets/{id}` (access specific version by ID)
  - **Previous dataset access**:
    - Previous datasets are **read-only** (cannot be modified or deleted if newer version exists)
    - Users can download files from previous datasets if they have access
    - Previous datasets are preserved for audit/history purposes

**Case 3: Multiple Concurrent Dataset Attachments**

- **Behavior**:
  - If multiple `POST /assets/{id}/datasets` requests are made concurrently:
    - Each request creates a new dataset version
    - Version numbers are assigned sequentially (no gaps)
    - All versions go through DQ/compliance gates independently
    - **Only the first version to reach `INTAKE_READY`** becomes the active dataset (`latest_dataset_id`)
    - Other versions remain in database but are not active
    - **Recommendation**: Users should wait for one dataset attachment to complete before attaching another

**Case 4: Dataset Deletion with Multiple Versions**

- **Behavior**:
  - If a dataset version is deleted via `DELETE /datasets/{id}`:
    - Dataset record is permanently deleted
    - **If deleted dataset was `latest_dataset_id`**:
      - Asset `latest_dataset_id` is set to the next most recent dataset version (if any)
      - If no other dataset versions exist, `latest_dataset_id` is set to `NULL`
    - **If deleted dataset was not the latest**:
      - Asset `latest_dataset_id` remains unchanged
      - Other dataset versions remain accessible

**Case 5: Asset Deletion with Multiple Dataset Versions**

- **Behavior**:
  - When an asset is deleted:
    - All dataset versions are deleted (cascade delete)
    - Files referenced by datasets are **not** deleted (may be reused by other datasets)
    - DQ/compliance runs for datasets are preserved (subject to retention policy)

3. **File Requirements**:
   - File must exist and belong to the same tenant.
   - File must have `status = COMPLETE` (upload must be finalized).
   - File format must be supported (CSV, JSON, Parquet).
   - Error code: `FILE_NOT_FOUND` if file doesn't exist.
   - Error code: `FILE_NOT_COMPLETE` if file upload is not complete.

4. **Schema Validation** (if contract exists):
   - If asset has a primary contract with schema:
     - System compares provided/inferred schema with contract schema.
     - Warnings are added to response if discrepancies are found.
     - Schema mismatches do **not** block dataset attachment (warnings only).
   - If no contract exists:
     - Schema is accepted as-is (no validation).

5. **Compliance Gate**:
   - After dataset attachment, compliance check is **automatically triggered** (if not already done for this file).
   - Dataset attachment completes even if compliance is pending (async job).
   - If compliance later fails, asset `compliance_status` is updated accordingly.

**Response (201 Created)**

Returns Dataset JSON (see §2.3 for schema):

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "version": 1,
  "data_file_id": "uuid",
  "schema_json": { /* ... */ },
  "row_count": 120000,
  "sample_json": [ /* ... */ ],
  "created_at": "2025-01-15T10:00:00Z",
  "created_by_user_id": "uuid"
}
```

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ASSET_NOT_FOUND` | Asset with given ID does not exist or is not visible to tenant. |
| `400 Bad Request` | `ASSET_RETIRED` | Cannot attach dataset to retired asset. |
| `404 Not Found` | `FILE_NOT_FOUND` | File with given ID does not exist or is not visible to tenant. |
| `400 Bad Request` | `FILE_NOT_COMPLETE` | File upload is not complete (`status != COMPLETE`). |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid schema JSON structure or unsupported file format. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |

---

### 4.6 GET /assets/{id}/datasets

List datasets for an asset.

- **Method & URL:** `GET /api/v1/assets/{id}/datasets?limit=20&offset=0`

Response: paginated list of Dataset objects.

---

### 4.7 GET /datasets/{dataset_id}

Get a single dataset.

- **Method & URL:** `GET /api/v1/datasets/{dataset_id}`
- **Roles:** `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR`

Response: Dataset JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `DATASET_NOT_FOUND` | Dataset with given ID does not exist or is not visible to tenant. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role or dataset is not visible to tenant. |

---

### 4.8 POST /assets/{id}/remap

Delete an asset.

- **Method & URL:** `DELETE /api/v1/assets/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | `false` | If `true`, deletes asset even if it has active listings or entitlements. If `false`, returns error if asset is in use. |

**Behavior**

- **Soft delete** (default):
  - Sets `assets.status = RETIRED` (does not physically delete).
  - If asset has active marketplace listings:
    - Automatically unpublishes all listings (`listings.status = UNPUBLISHED`).
    - Returns `409 Conflict` with error code `ASSET_HAS_LISTINGS` (unless `force = true`).
  - If asset has active entitlements:
    - Revokes all entitlements (`entitlements.status = REVOKED`).
    - Returns `409 Conflict` with error code `ASSET_HAS_ENTITLEMENTS` (unless `force = true`).
  - If `force = true`:
    - Deletes asset even if it has listings or entitlements.
    - Cascades to:
      - Unpublish all listings.
      - Revoke all entitlements.
      - Delete all datasets (and associated files).
      - Delete semantic mappings.
  - Emits audit event: `ASSET_DELETED`.

**Cascade Behavior**

- **Datasets**: All datasets attached to the asset are deleted (cascade).
- **Files**: Physical files are marked for deletion (background cleanup job).
- **Contracts**: Contracts are **not** deleted (may be referenced by other assets).
- **Listings**: Listings are automatically unpublished.
- **Entitlements**: Entitlements are automatically revoked.

**Response**

- `204 No Content` on success.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ASSET_NOT_FOUND` | Asset with given ID does not exist or is not visible to tenant. |
| `409 Conflict` | `ASSET_HAS_LISTINGS` | Asset has active marketplace listings (use `force = true` to delete anyway). |
| `409 Conflict` | `ASSET_HAS_ENTITLEMENTS` | Asset has active entitlements (use `force = true` to delete anyway). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

### 4.10 DELETE /datasets/{id}

Delete a dataset.

- **Method & URL:** `DELETE /api/v1/datasets/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Behavior**

- **Physical deletion**:
  - Permanently deletes dataset record.
  - **File is NOT deleted** (file may be referenced by other datasets or used for external scans).
  - If this is the only dataset for an asset:
    - Asset remains but has no dataset (contract-only asset).
  - Emits audit event: `DATASET_DELETED`.

**Cascade Behavior**

- **Files**: File record is **not** deleted (file may be reused).
- **Assets**: Asset record is **not** deleted (asset becomes contract-only).
- **DQ/Compliance runs**: Run records are **not** deleted (preserved for audit).

**Response**

- `204 No Content` on success.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `DATASET_NOT_FOUND` | Dataset with given ID does not exist or is not visible to tenant. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

Manually trigger semantic mapping for an asset.

- **Method & URL:** `POST /api/v1/assets/{id}/remap`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Behavior**

- Triggers a new semantic mapping job for the asset and its related entities (contract, datasets)
- Resets retry counter (allows retry after fixing data/contract issues)
- Updates `semantic_status` based on result:
  - `OK` if mapping succeeds
  - `DEGRADED` if mapping fails

**Response (202 Accepted)**

```json
{
  "job": {
    "id": "uuid",
    "type": "SEMANTIC_MAPPING",
    "status": "PENDING",
    "resource_type": "ASSET",
    "resource_id": "uuid",
    "created_at": "2025-01-15T10:00:00Z"
  }
}
```

Client should poll `/jobs/{id}` for completion.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ASSET_NOT_FOUND` | Asset with given ID does not exist or is not visible to tenant. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |

---

### 4.9 DELETE /assets/{id}

Delete an asset.

- **Method & URL:** `DELETE /api/v1/assets/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | `false` | If `true`, deletes asset even if it has active listings or entitlements. If `false`, returns error if asset is in use. |

**Behavior**

- **Soft delete** (default):
  - Sets `assets.status = RETIRED` (does not physically delete).
  - If asset has active marketplace listings:
    - Automatically unpublishes all listings (`listings.status = UNPUBLISHED`).
    - Returns `409 Conflict` with error code `ASSET_HAS_LISTINGS` (unless `force = true`).
  - If asset has active entitlements:
    - Revokes all entitlements (`entitlements.status = REVOKED`).
    - Returns `409 Conflict` with error code `ASSET_HAS_ENTITLEMENTS` (unless `force = true`).
  - If `force = true`:
    - Deletes asset even if it has listings or entitlements.
    - Cascades to:
      - Unpublish all listings.
      - Revoke all entitlements.
      - Delete all datasets (and associated files).
      - Delete semantic mappings.
  - Emits audit event: `ASSET_DELETED`.

**Cascade Behavior**

- **Datasets**: All datasets attached to the asset are deleted (cascade).
- **Files**: Physical files are marked for deletion (background cleanup job).
- **Contracts**: Contracts are **not** deleted (may be referenced by other assets).
- **Listings**: Listings are automatically unpublished.
- **Entitlements**: Entitlements are automatically revoked.

**Response**

- `204 No Content` on success.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ASSET_NOT_FOUND` | Asset with given ID does not exist or is not visible to tenant. |
| `409 Conflict` | `ASSET_HAS_LISTINGS` | Asset has active marketplace listings (use `force = true` to delete anyway). |
| `409 Conflict` | `ASSET_HAS_ENTITLEMENTS` | Asset has active entitlements (use `force = true` to delete anyway). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

### 4.10 DELETE /datasets/{id}

Delete a dataset.

- **Method & URL:** `DELETE /api/v1/datasets/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Behavior**

- **Physical deletion**:
  - Permanently deletes dataset record.
  - **File is NOT deleted** (file may be referenced by other datasets or used for external scans).
  - If this is the only dataset for an asset:
    - Asset remains but has no dataset (contract-only asset).
  - Emits audit event: `DATASET_DELETED`.

**Cascade Behavior**

- **Files**: File record is **not** deleted (file may be reused).
- **Assets**: Asset record is **not** deleted (asset becomes contract-only).
- **DQ/Compliance runs**: Run records are **not** deleted (preserved for audit).

**Response**

- `204 No Content` on success.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `DATASET_NOT_FOUND` | Dataset with given ID does not exist or is not visible to tenant. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

## 5. Files API (Upload & Intake)

The Files API handles ingestion of uploaded data files and associates them with assets/datasets.

Uploads can be:

- **SIMPLE**: single direct upload to a pre-signed URL (default / small files).
- **CHUNKED**: multi-part upload for **large or unreliable** connections (reserved / post-MVP feature flag, but protocol is stable).

### 5.1 POST /files/init

Initialize a file upload (data-first & contract-first).

- **Method & URL:** `POST /api/v1/files/init`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Request Body**

```json
{
  "file_name": "orders_2025_01.csv",
  "content_type": "text/csv",
  "expected_size_bytes": 10485760,
  "purpose": "DATASET | EXTERNAL_SCAN | SAMPLE | REPORT"
}
```

**Request Fields**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file_name` | string | Yes | - | Original filename. Must be non-empty, max 255 characters. |
| `content_type` | string | No | `application/octet-stream` | MIME type (e.g. `text/csv`, `application/parquet`). Used for validation and processing hints. |
| `expected_size_bytes` | integer | No | - | Client's best estimate of file size in bytes. Required for chunked mode decisions. If omitted, server assumes simple upload mode. |
| `purpose` | string (enum) | No | `DATASET` | Purpose of the upload: `DATASET` (intake), `EXTERNAL_SCAN` (scan-only), `SAMPLE`, or `REPORT`. |

**Note:** `expected_size_bytes` is used by the server to:
- Choose upload mode (SIMPLE vs CHUNKED).
- Validate against tenant/global size limits.
- Pre-allocate storage if needed.

##### 5.1.2 Content Type Validation

**Validation Timing**

Content type validation occurs at **two stages**:

1. **Initial validation** (during `POST /files/init`):
   - Validates declared `content_type` against **allowed MIME types** for the tenant/environment
   - Rejects unsupported types immediately (e.g., `application/x-executable`, `application/x-msdownload`)
   - Does **not** validate actual file content at this stage

2. **Content validation** (during `POST /files/{id}/complete`):
   - Server performs **content sniffing** on the uploaded file
   - Compares detected content type with declared `content_type`
   - Handles mismatches according to policy (see below)

**Supported Content Types**

The platform supports the following content types for data files:

| Content Type | File Extensions | Description |
|--------------|----------------|-------------|
| `text/csv` | `.csv` | Comma-separated values |
| `application/json` | `.json`, `.jsonl` | JSON or JSON Lines |
| `application/parquet` | `.parquet` | Apache Parquet format |
| `application/x-parquet` | `.parquet` | Alternative Parquet MIME type (accepted) |
| `text/plain` | `.txt`, `.tsv` | Plain text or tab-separated values |

**Content Type Detection**

During `POST /files/{id}/complete`, the server:

1. **Reads file header** (first 512 bytes) to detect actual content type
2. **Uses detection library** (e.g., `python-magic`, `file` command) to identify MIME type
3. **Falls back to file extension** if header detection fails
4. **Compares detected type with declared `content_type`**

**Mismatch Handling**

When a content type mismatch is detected:

**Policy: Strict Validation (Default)**

- **If declared `content_type` is `application/octet-stream`** (default):
  - Server accepts detected content type
  - Updates `files.content_type` to detected type
  - No error returned

- **If declared `content_type` is specific** (e.g., `text/csv`):
  - **Mismatch tolerance**: Server allows compatible types:
    - `text/csv` ↔ `text/plain` (if file extension is `.csv`)
    - `application/json` ↔ `application/jsonl` (if content is valid JSON Lines)
    - `application/parquet` ↔ `application/x-parquet`
  - **Incompatible mismatch** (e.g., declared `text/csv` but detected `application/json`):
    - Returns `400 Bad Request` with error code `FILE_CONTENT_TYPE_MISMATCH`:
      ```json
      {
        "error": {
          "code": "FILE_CONTENT_TYPE_MISMATCH",
          "message": "Declared content type does not match actual file content.",
          "details": {
            "declared_content_type": "text/csv",
            "detected_content_type": "application/json",
            "file_name": "data.csv",
            "suggestion": "Update content_type to 'application/json' or verify file content."
          }
        }
      }
      ```
    - Upload is **rejected**; file is not processed
    - Client must re-upload with correct `content_type` or fix file content

**Policy: Lenient Validation (Configurable)**

- Can be enabled per tenant via `tenant_config.content_type_validation_mode = "LENIENT"`
- In lenient mode:
  - Mismatches result in **warning** (not error)
  - Server updates `files.content_type` to detected type
  - Upload proceeds normally
  - Warning is logged in audit events

**Error Codes**

- `FILE_CONTENT_TYPE_MISMATCH` (HTTP 400): Declared content type does not match detected content type (strict mode only)
- `FILE_UNSUPPORTED_TYPE` (HTTP 400): Content type is not supported (regardless of declared type)
- `FILE_CONTENT_INVALID` (HTTP 400): File content is corrupted or cannot be parsed (detected during schema inference)

**Chunk Sizing & Upload Mode**

Server chooses upload mode and (for chunked uploads) chunk size based on `expected_size_bytes`.

**Configuration**:
- All file size limits and chunk configuration are defined in `SystemRequrements.md` §11.1.1.
- Default values:
  - `SIMPLE_UPLOAD_THRESHOLD_BYTES` = 67108864 (64 MiB)
  - `MIN_CHUNK_SIZE_BYTES` = 5242880 (5 MiB)
  - `MAX_CHUNK_SIZE_BYTES` = 67108864 (64 MiB)
  - `TARGET_CHUNK_COUNT` = 1000
  - `MAX_CHUNK_COUNT` = 10000
- Limits can be overridden per tenant via tenant configuration (see `API_Spec_v1.md` §13).

Algorithm:

If expected_size_bytes <= SIMPLE_UPLOAD_THRESHOLD (or missing):

upload_mode = "SIMPLE"

Else:

upload_mode = "CHUNKED"

Compute:

text
Copy code
base_chunk_size = ceil(expected_size_bytes / TARGET_CHUNK_COUNT)

chunk_size_bytes = clamp(
  base_chunk_size,
  MIN_CHUNK_SIZE,
  MAX_CHUNK_SIZE
)

total_chunks = ceil(expected_size_bytes / chunk_size_bytes)
If total_chunks > MAX_CHUNK_COUNT, server may:

Increase chunk_size_bytes to reduce total_chunks, or

Reject with 400 and an error (e.g. UPLOAD_TOO_LARGE).

Response (SIMPLE upload)

```json
{
  "file_id": "uuid",
  "upload_mode": "SIMPLE",
  "upload_url": "https://storage-provider/presigned-url",
  "upload_url_expires_at": "2025-01-15T10:15:00Z",
  "headers": {
    "Content-Type": "text/csv",
    "x-amz-server-side-encryption": "AES256"
  }
}
```

**Pre-signed URL Details**

- **Expiration**: Pre-signed URLs expire **15 minutes** after generation (configurable via `PRESIGNED_URL_TTL_SECONDS`, default: 900 seconds).
- **HTTP Method**: `PUT` (for SIMPLE uploads) or `POST` (for multipart uploads, if supported).
- **Required Headers**: 
  - `Content-Type`: Must match the `content_type` provided in the request (or `application/octet-stream` if not specified).
  - Additional headers may be required by the storage provider (e.g., `x-amz-server-side-encryption`).
- **Permissions Scope**:
  - Pre-signed URLs are scoped to:
    - **Single file**: Only the specific `file_id` can be uploaded to this URL.
    - **Tenant isolation**: URL includes tenant context; uploads are validated against `tenant_id` from the bearer token.
    - **Single use**: Each pre-signed URL is intended for a single upload operation (idempotent retries are allowed if the upload fails).
- **Security**:
  - URLs are cryptographically signed and cannot be modified without invalidating the signature.
  - URLs include expiration timestamp; expired URLs are rejected by the storage provider.
  - Backend validates `tenant_id` and `file_id` match before accepting the upload.

Client performs a single upload to `upload_url` with the provided headers.

After upload completes, client calls `POST /files/{id}/complete` (5.4).

Response (CHUNKED upload)

json
Copy code
{
  "file_id": "uuid",
  "upload_mode": "CHUNKED",
  "chunk_size_bytes": 8388608,
  "total_chunks": 125,
  "max_concurrent_chunks": 4
}
```

**Concurrent Chunk Upload Configuration**

- **Default `max_concurrent_chunks`**: `4` (configurable per tenant via `tenant_config.max_concurrent_chunks`, default: 4)
- **Server-side enforcement**:
  - Server tracks active chunk uploads per `file_id` (in-memory or database counter)
  - If client exceeds `max_concurrent_chunks`, server returns `429 Too Many Requests` with error code `RATE_LIMIT_EXCEEDED`
  - `Retry-After` header indicates when client can retry (typically immediate, but may be delayed if server is overloaded)
- **Per-tenant overrides**: Can be configured via `PATCH /tenants/{id}/config`:
  ```json
  {
    "max_concurrent_chunks": 8  // Allow up to 8 concurrent chunks for this tenant
  }
  ```
- **Client behavior**:
  - Clients MUST respect `max_concurrent_chunks` from the response
  - Clients SHOULD upload chunks in batches (e.g., upload 4 chunks, wait for all to complete, then upload next 4)
  - Clients MAY use a sliding window approach (maintain exactly `max_concurrent_chunks` in-flight uploads)

Client must:

Split the file into total_chunks pieces of size chunk_size_bytes (final chunk may be smaller).

Upload chunks via PUT /files/{id}/chunks/{chunk_number} (5.2), optionally in parallel up to max_concurrent_chunks.

Use GET /files/{id}/chunks (5.3) to resume interrupted uploads.

Call POST /files/{id}/complete (5.4) to finalize.

Clients must respect the server-selected upload_mode. Chunk endpoints are only valid when upload_mode = "CHUNKED".

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Missing required `file_name`, invalid enum values, or malformed request body. |
| `400 Bad Request` | `FILE_TOO_LARGE` | `expected_size_bytes` exceeds configured maximum (global or tenant-specific limit). Response includes `error.details.max_size_bytes`. |
| `400 Bad Request` | `FILE_UNSUPPORTED_TYPE` | `content_type` or file extension is not supported. Response includes `error.details.supported_types`. |
| `400 Bad Request` | `FILE_CONTENT_TYPE_MISMATCH` | Declared `content_type` does not match actual file content (strict validation mode). Response includes `error.details.declared_content_type` and `error.details.detected_content_type`. |
| `413 Payload Too Large` | `FILE_TOO_LARGE` | Alternative status code for size limit violations (server may use 400 or 413). |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | Tenant or user exceeded upload rate limit. Response includes `Retry-After` header. |
| `503 Service Unavailable` | `SYSTEM_UNAVAILABLE` | Object storage or upload service temporarily unavailable. |
| `500 Internal Server Error` | `INTERNAL_ERROR` | Unexpected server error during upload initialization. |

##### 5.1.1 Upload session expiration

   Chunked uploads are associated with an **upload session** identified by the `file_id` returned from `POST /files`.

   - **Session TTL**:  
     An upload session is valid for **24 hours** from creation. After 24 hours, the session expires.

   - **Behavior after expiration**:  
     Once expired:
     - The server **MUST** reject all subsequent calls to:
       - `PUT /files/{id}/chunks/{chunk_index}`
       - `POST /files/{id}/chunks/complete`
       - `GET /files/{id}/chunks`
     - These endpoints MUST return `410 Gone` with a body similar to:

       ```json
       {
         "error": "UPLOAD_SESSION_EXPIRED",
         "message": "This upload session has expired. Please start a new upload."
       }
       ```

     - The server **MUST** delete any partial chunks and mark the upload as expired. Deletion may be performed asynchronously by a background job.

   - **Client responsibilities**:  
     Clients **MUST** treat `UPLOAD_SESSION_EXPIRED` as non-recoverable for that `file_id`:
     - Do not retry further chunks for the same `file_id`.
     - Start a new upload session (`POST /files`) if the upload should be retried.

#### 5.2 PUT /files/{id}/chunks/{chunk_number}

Upload a single chunk of a file (chunked uploads only).

Method & URL: PUT /api/v1/files/{file_id}/chunks/{chunk_number}

Roles: DATA_PROVIDER, TENANT_ADMIN

Path parameters

file_id – UUID returned by POST /files/init.

chunk_number – 1-based integer in 1..total_chunks.

Headers

Content-Type: application/octet-stream

Content-Length: <bytes> – must be chunk_size_bytes for all non-final chunks; final chunk may be ≤ chunk_size_bytes.

X-Chunk-Checksum-Sha256: <hex> – SHA-256 checksum of this chunk’s bytes.

Body

Raw binary for the chunk.

Behavior

Valid only if upload_mode = "CHUNKED" for this file_id.

Server validates:

chunk_number ∈ [1, total_chunks].

Content-Length within allowed range.

Calculated SHA-256 of body matches X-Chunk-Checksum-Sha256.

On success, server records per-chunk metadata (implementation detail) and marks the chunk as UPLOADED.

Idempotency

Re-upload of the same chunk_number:

If checksum matches existing stored chunk → 200 OK (idempotent).

If checksum differs → 409 Conflict (CHUNK_CHECKSUM_MISMATCH).

Responses

200 OK – chunk accepted and stored.

400 Bad Request – e.g., invalid chunk_number, invalid Content-Length.

404 Not Found – unknown file_id or not visible to tenant.

409 Conflict – checksum mismatch, upload not in CHUNKED mode, or chunk out of range.

410 Gone – upload session expired or already finalized.

#### 5.3 GET /files/{id}/chunks
List uploaded and missing chunks for a CHUNKED upload (resume support).

Method & URL: GET /api/v1/files/{id}/chunks

Roles: DATA_PROVIDER, TENANT_ADMIN

Response

json
Copy code
{
  "file_id": "uuid",
  "upload_mode": "CHUNKED",
  "chunk_size_bytes": 8388608,
  "total_chunks": 125,
  "uploaded_chunks": [1, 2, 3, 10, 11, 12],
  "missing_chunks": [4, 5, 6, 7, 8, 9],
  "upload_status": "INIT | UPLOADING | PENDING_FINALIZE | COMPLETE | FAILED | EXPIRED"
}
uploaded_chunks – chunk numbers fully stored and verified.

missing_chunks – convenience field; server may compute as 1..total_chunks \ uploaded_chunks.

upload_status – current internal status of the upload.

#### 5.3.1 Chunked Upload Resume Flow (Detailed)

**Client-Side State Tracking**

Clients MUST maintain local state to track upload progress and enable resume:

**Recommended Client State Structure**:
```json
{
  "file_id": "uuid",
  "file_name": "data.csv",
  "total_size_bytes": 1048576000,
  "chunk_size_bytes": 8388608,
  "total_chunks": 125,
  "max_concurrent_chunks": 4,
  "uploaded_chunks": [1, 2, 3, 10, 11, 12],
  "failed_chunks": [4, 5],
  "last_updated": "2025-01-15T10:30:00Z"
}
```

**State Persistence**:
- Clients SHOULD persist upload state to:
  - **Browser**: `localStorage` or `sessionStorage` (key: `upload_state_{file_id}`)
  - **SDK/CLI**: Local file (e.g., `~/.datahub/uploads/{file_id}.json`) or in-memory cache
- State SHOULD be updated after each successful chunk upload.
- State SHOULD be cleared after successful `POST /files/{id}/complete`.

**Resume Flow (Step-by-Step)**

1. **Detect Interruption**:
   - Client detects upload interruption (network error, process crash, user cancellation).
   - Client checks if upload state exists locally.

2. **Query Server State**:
   - Client calls `GET /files/{id}/chunks` to retrieve server-side chunk status.
   - Server returns `uploaded_chunks` and `missing_chunks` arrays.

3. **Reconcile Client and Server State**:
   - Client compares local `uploaded_chunks` with server `uploaded_chunks`.
   - **If mismatch**: Trust server state (server is authoritative).
   - **If match**: Proceed with uploading `missing_chunks`.

4. **Resume Upload**:
   - For each chunk in `missing_chunks`:
     - **Retry Strategy**:
       - **Max retries**: 3 attempts per chunk
       - **Backoff**: Exponential backoff (1s, 2s, 4s)
       - **Timeout**: 60 seconds per chunk upload
     - **Concurrent Uploads**:
       - Upload up to `max_concurrent_chunks` chunks in parallel
       - Wait for all concurrent uploads to complete before starting next batch
     - **Chunk Upload**:
       - Call `PUT /files/{id}/chunks/{chunk_number}` with chunk data
       - On success: Add `chunk_number` to local `uploaded_chunks` and persist state
       - On failure: Add `chunk_number` to local `failed_chunks` for retry
     - **Partial Chunk Handling**:
       - If upload fails mid-chunk (network error during PUT):
         - Retry the entire chunk (do not attempt partial resume)
         - Server validates chunk integrity via checksum, so partial chunks are rejected

5. **Finalize Upload**:
   - Once `missing_chunks` is empty (all chunks uploaded):
     - Call `POST /files/{id}/complete` to finalize
     - Clear local upload state on success

**Error Handling During Resume**

- **Network Errors**:
  - Retry with exponential backoff (max 3 retries per chunk)
  - If all retries fail, mark chunk as failed and continue with other chunks
  - After all chunks attempted, retry failed chunks again (up to 3 overall attempts)

- **Server Errors (4xx/5xx)**:
  - **400 Bad Request**: Invalid chunk (checksum mismatch, out of range) → Skip chunk, log error
  - **410 Gone**: Upload session expired → Abort resume, start new upload
  - **429 Too Many Requests**: Rate limited → Wait for `Retry-After` header, then retry
  - **500/503**: Server error → Retry with exponential backoff

- **Session Expiration**:
  - If `GET /files/{id}/chunks` returns `410 Gone`:
    - Abort resume attempt
    - Clear local upload state
    - Start new upload session (`POST /files/init`)

**Client Implementation Recommendations**

**Browser/JavaScript**:
```javascript
class ChunkedUploader {
  async resumeUpload(fileId) {
    // 1. Load local state
    const localState = this.loadState(fileId);
    
    // 2. Query server state
    const serverState = await this.getChunks(fileId);
    
    // 3. Reconcile and determine missing chunks
    const missingChunks = serverState.missing_chunks;
    
    // 4. Upload missing chunks with retry
    for (const chunkNum of missingChunks) {
      await this.uploadChunkWithRetry(fileId, chunkNum, {
        maxRetries: 3,
        backoffMs: [1000, 2000, 4000]
      });
    }
    
    // 5. Finalize
    await this.completeUpload(fileId);
    this.clearState(fileId);
  }
}
```

**SDK/Python**:
```python
class ChunkedUploader:
    def resume_upload(self, file_id: str) -> None:
        # 1. Load local state
        local_state = self.load_state(file_id)
        
        # 2. Query server state
        server_state = self.client.get_chunks(file_id)
        
        # 3. Reconcile and upload missing chunks
        for chunk_num in server_state.missing_chunks:
            self.upload_chunk_with_retry(
                file_id, chunk_num,
                max_retries=3,
                backoff_seconds=[1, 2, 4]
            )
        
        # 4. Finalize
        self.client.complete_upload(file_id)
        self.clear_state(file_id)
```

**Typical resume flow**

Client calls `GET /files/{id}/chunks`.

For each chunk_number in missing_chunks, client re-issues PUT /files/{id}/chunks/{chunk_number} with retry logic.

Once missing_chunks is empty, client calls POST /files/{id}/complete (5.4).

Errors

400 Bad Request – upload is not in CHUNKED mode (UPLOAD_NOT_CHUNKED).

404 Not Found – no upload for this id or not visible to tenant.

410 Gone – upload expired/cleaned up (UPLOAD_SESSION_EXPIRED).

#### 5.4 POST /files/{id}/complete
Mark upload as complete and optionally trigger intake processing (schema inference, compliance & DQ).

Method & URL: POST /api/v1/files/{id}/complete

Roles: DATA_PROVIDER, TENANT_ADMIN

Body

json
Copy code
{
  "asset_id": "uuid",
  "ingestion_mode": "DATA_FIRST | CONTRACT_FIRST | CONTRACT_ONLY",
  "format": "CSV",
  "run_compliance": true,
  "run_dq": true,
  "expected_size_bytes": 10485760,
  "file_checksum_sha256": "deadbeef..."   // optional, full-file checksum
}
expected_size_bytes – optional; server may compare to actual size.

file_checksum_sha256 – optional; recommended for integrity; server may compute/compose full-file checksum and compare.

Behavior – SIMPLE uploads

Valid when upload_mode = "SIMPLE" for this file_id.

Server validates upload completed successfully at storage provider.

Optionally verifies expected_size_bytes and file_checksum_sha256 if provided.

Creates data_file record and triggers intake pipeline:

Schema inference.

DQ run (if run_dq = true).

Compliance run (if run_compliance = true).

Behavior – CHUNKED uploads

Additional steps when upload_mode = "CHUNKED":

Validate upload state:

upload_status must be UPLOADING or PENDING_FINALIZE.

Validate completeness:

Ensure all chunk numbers 1..total_chunks are present and marked UPLOADED.

If any missing → 409 Conflict:

json
Copy code
{
  "code": "UPLOAD_INCOMPLETE",
  "details": {
    "missing_chunks": [7, 8, 9]
  }
}
Optionally validate size and checksum:

Compute or compose final size from chunks.

If file_checksum_sha256 is provided, compute full-file checksum (implementation detail) and compare.

On mismatch → 409 Conflict (FILE_CHECKSUM_MISMATCH).

Compose/merge chunks into a single object in backing storage.

Mark upload as complete:

upload_status = "COMPLETE"

Persist final size and checksum in data_files metadata.

Trigger same intake pipeline as SIMPLE uploads (schema inference, DQ, compliance).

Response

json
Copy code
{
  "data_file_id": "uuid",
  "schema_json": { "fields": [ /* ... */ ] },
  "dq_run_id": "uuid",
  "compliance_run_id": "uuid",
  "dq_job_id": "uuid",
  "compliance_job_id": "uuid"
}
Client polls /jobs/{dq_job_id} and /jobs/{compliance_job_id} for completion, then calls /assets/{asset_id}/datasets when ready.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Missing required fields, invalid enum values, or malformed request body. |
| `404 Not Found` | `FILE_NOT_FOUND` | File with given ID does not exist or is not visible to tenant. |
| `409 Conflict` | `UPLOAD_INCOMPLETE` | Missing chunks for CHUNKED upload. Response includes `error.details.missing_chunks`. |
| `409 Conflict` | `FILE_CHECKSUM_MISMATCH` | Full-file checksum mismatch (provided checksum does not match computed value). |
| `410 Gone` | `UPLOAD_SESSION_EXPIRED` | Upload session expired (24-hour TTL exceeded). Client must start a new upload. |
| `410 Gone` | `UPLOAD_FAILED` | Upload failed before completion (network error, storage error, etc.). Partial objects are cleaned up after 24 hours. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `500 Internal Server Error` | `INTERNAL_ERROR` | Unexpected server error during finalization. |

**Partial Upload Cleanup Policy**

- **SIMPLE uploads**: If upload fails after partial upload to object storage:
  - Partial object is marked for cleanup
  - Cleanup occurs within 24 hours (same as chunked session TTL)
  - Calling `/complete` on a failed upload returns `410 Gone` with `UPLOAD_FAILED` error code

- **CHUNKED uploads**: If upload fails before completion:
  - Partial chunks are retained until session expiration (24 hours)
  - After expiration, all partial chunks are deleted
  - Calling `/complete` on an expired or failed upload returns `410 Gone` with `UPLOAD_SESSION_EXPIRED` or `UPLOAD_FAILED`

UPLOAD_TOO_LARGE – exceeds global or tenant-specific max size.

FILE_CHECKSUM_MISMATCH – full-file checksum mismatch.

---

## 6. Data Quality API

### 6.1 POST /dq-runs

Trigger a **Data Quality run** (intake + manual re-runs).

- **Method & URL:** `POST /api/v1/dq-runs`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN`

**Body**

```json
{
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "profile_key": "intake_basic"
}
```

For an **external/scan-only** run (optional):

```json
{
  "run_scope": "EXTERNAL",
  "data_file_id": "uuid",
  "profile_key": "intake_basic"
}
```

**Response**

```json
{
  "dq_run": { /* DQRun JSON */ },
  "job": { /* Job JSON */ }
}
```

---

### 6.2 GET /dq-runs/{id}

Get a Data Quality run result.

- **Method & URL:** `GET /api/v1/dq-runs/{id}`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN`, `AUDITOR`

**Response (200 OK)**

Returns complete DQRun JSON (see §2.4 for schema):

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "data_file_id": null,
  "job_id": "uuid",
  "run_scope": "INTERNAL",
  "profile_key": "intake_basic_gx",
  "status": "SUCCEEDED",
  "overall_status": "PASS",
  "quality_score": 95.2,
  "checks_json": [
    {
      "check_id": "not_null_customer_id",
      "name": "not_null_customer_id",
      "category": "COMPLETENESS",
      "status": "PASS",
      "severity": "HIGH",
      "target": {
        "level": "COLUMN",
        "column_name": "customer_id"
      },
      "metrics": {
        "observed_value": 0.0,
        "expected_min": 0.0,
        "expected_max": 0.01,
        "row_count": 120000,
        "observed_null_ratio": 0.0
      }
    }
  ],
  "details_json": {
    "engine_type": "GX",
    "engine_version": "0.18.0",
    "ruleset_version": "intake_basic_v1",
    "sample_size": 10000,
    "strategy": "first_n_rows"
  },
  "started_at": "2025-01-01T12:00:00Z",
  "completed_at": "2025-01-01T12:02:00Z",
  "requested_by_user_id": "uuid"
}
```

**Response Availability**

- **While job is running** (`status = PENDING` or `RUNNING`):
  - Returns DQRun with current status.
  - `checks_json` may be empty or contain partial results.
  - `overall_status` is `UNKNOWN` until completion.
- **After completion** (`status = SUCCEEDED` or `FAILED`):
  - Returns complete DQRun with all results.
  - `checks_json` contains all check results.
  - `overall_status` reflects final outcome.
- **If job was cancelled** (`status = FAILED`, `job.cancellation_requested = true`):
  - Returns DQRun with `status = FAILED`.
  - `details_json.partial = true` indicates incomplete results.
  - `checks_json` may contain partial results (if any were computed before cancellation).
  - `overall_status` remains `UNKNOWN` (partial results are not used for asset activation).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `DQ_RUN_NOT_FOUND` | DQ run with given ID does not exist or is not visible to tenant. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role to view DQ runs. |

---

### 6.3 GET /dq-runs

List DQ runs (for asset or dataset).

- **Method & URL:** `GET /api/v1/dq-runs?asset_id=uuid&dataset_id=uuid&limit=20&offset=0`

---

## 7. Compliance API

### 7.1 POST /compliance-runs

Trigger a **Compliance run**.

- **Method & URL:** `POST /api/v1/compliance-runs`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN`, `AUDITOR` (depending on mode)

**Internal / Intake mode**

```json
{
  "mode": "INTERNAL",
  "asset_id": "uuid",
  "dataset_id": "uuid-or-null",
  "data_file_id": "uuid",
  "applicable_regimes": ["GDPR", "LGPD"]
}
```

**External / Scan-only mode**

```json
{
  "mode": "EXTERNAL",
  "data_file_id": "uuid",
  "applicable_regimes": ["GDPR", "LGPD", "CCPA"]
}
```

**Response**

```json
{
  "compliance_run": { /* ComplianceRun JSON */ },
  "job": { /* Job JSON */ }
}
```

---

### 7.2 GET /compliance-runs/{id}

Get a Compliance run result.

- **Method & URL:** `GET /api/v1/compliance-runs/{id}`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN`, `AUDITOR`

**Response (200 OK)**

Returns complete ComplianceRun JSON (see §2.5 for schema):

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "asset_id": "uuid",
  "dataset_id": "uuid",
  "data_file_id": "uuid",
  "job_id": "uuid",
  "mode": "INTERNAL",
  "status": "SUCCEEDED",
  "overall_status": "PASS",
  "risk_level": "LOW",
  "allowed_to_store": true,
  "applicable_regimes": ["GDPR", "LGPD"],
  "detected_categories": ["PII_DIRECT_EMAIL"],
  "column_findings_json": {
    "customer_email": {
      "pii_category": "PII_DIRECT_EMAIL",
      "risk_score": 0.8,
      "regulations": ["GDPR", "LGPD"]
    }
  },
  "details_json": {
    "engine_version": "1.0.0",
    "scan_strategy": "full_scan",
    "row_count_scanned": 120000
  },
  "started_at": "2025-01-01T12:00:00Z",
  "completed_at": "2025-01-01T12:01:00Z",
  "requested_by_user_id": "uuid"
}
```

**Response Availability**

- **While job is running** (`status = PENDING` or `RUNNING`):
  - Returns ComplianceRun with current status.
  - `column_findings_json` may be empty or contain partial results.
  - `overall_status` is `UNKNOWN` until completion.
  - `allowed_to_store` is `null` until completion.
- **After completion** (`status = SUCCEEDED` or `FAILED`):
  - Returns complete ComplianceRun with all results.
  - `column_findings_json` contains all findings.
  - `overall_status` reflects final outcome.
  - `allowed_to_store` indicates whether data can be stored (fail-closed: `false` if incomplete).
- **If job was cancelled** (`status = FAILED`, `job.cancellation_requested = true`):
  - Returns ComplianceRun with `status = FAILED`.
  - `details_json.partial = true` indicates incomplete scan.
  - `allowed_to_store = false` (fail-closed: incomplete scan blocks storage).
  - `overall_status` remains `UNKNOWN` (partial results are not used for compliance gate).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `COMPLIANCE_RUN_NOT_FOUND` | Compliance run with given ID does not exist or is not visible to tenant. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role to view compliance runs. |

---

### 7.3 GET /compliance-runs

List compliance runs for an asset or dataset.

- **Method & URL:** `GET /api/v1/compliance-runs?asset_id=uuid&dataset_id=uuid&mode=INTERNAL&limit=20&offset=0`

---

## 8. Jobs API

### 8.1 GET /jobs/{id}

Check status of a Job.

- **Method & URL:** `GET /api/v1/jobs/{id}`

Response: Job JSON.

---

### 8.2 GET /jobs

List Jobs for the current tenant.

- **Method & URL:** `GET /api/v1/jobs?resource_type=ASSET&resource_id=uuid&type=QUALITY_CHECK&status=FAILED&limit=20&offset=0`

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `resource_type` | string | No | Filter by resource type (e.g., `ASSET`, `CONTRACT`, `DATASET`). |
| `resource_id` | UUID | No | Filter by resource ID. |
| `type` | string (enum) | No | Filter by job type (`QUALITY_CHECK`, `COMPLIANCE_CHECK`, `CONTRACT_VALIDATION`, `SEMANTIC_MAPPING`, `CONTRACT_MIGRATION`). |
| `status` | string (enum) | No | Filter by job status (`PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`). |
| `limit` | integer | No | Maximum number of results (default: 20, max: 100). |
| `offset` | integer | No | Pagination offset (default: 0). |

Response: paginated list of Jobs.

---

### 8.3 POST /jobs/{id}/cancel

Cancel a running or pending job.

- **Method & URL:** `POST /api/v1/jobs/{id}/cancel`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN` (must be owner of the job)

**Request Body**

```json
{
  "reason": "User requested cancellation"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reason` | string | No | Human-readable reason for cancellation. Max 500 characters. |

**Behavior**

- **If job is `PENDING`**:
  - Immediately sets `status = CANCELLED`, `cancellation_requested = true`, `cancel_requested_at = NOW()`, `cancel_reason = <provided reason>`.
  - Removes job from queue (if not yet picked up by worker).
  - Returns `202 Accepted`.

- **If job is `RUNNING`**:
  - Sets `cancellation_requested = true`, `cancel_requested_at = NOW()`, `cancel_reason = <provided reason>`.
  - **Does NOT change `status`** (remains `RUNNING`).
  - Publishes cancellation event to job queue control topic.
  - Worker observes cancellation flag and performs cleanup (see `System_Architecture.md` §2.4.3).
  - Returns `202 Accepted`.

- **If job is already in terminal state** (`SUCCEEDED`, `FAILED`, `CANCELLED`):
  - Returns `409 Conflict` with error code `JOB_ALREADY_COMPLETED`.

**Response (202 Accepted)**

```json
{
  "job": {
    "id": "uuid",
    "status": "CANCELLED" | "RUNNING",
    "cancellation_requested": true,
    "cancel_requested_at": "2025-01-15T10:00:00Z",
    "cancel_reason": "User requested cancellation"
  }
}
```

**Partial Results Handling**

- If job was cancelled after partial results were written:
  - Partial results are preserved in `dq_runs` or `compliance_runs` with `status = FAILED` and `details_json.partial = true`.
  - Partial results are **not used** for asset activation or compliance gate decisions.
  - User must create a new job to re-run the operation.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `JOB_NOT_FOUND` | Job with given ID does not exist or is not visible to tenant. |
| `409 Conflict` | `JOB_ALREADY_COMPLETED` | Job is already in terminal state (`SUCCEEDED`, `FAILED`, or `CANCELLED`). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role or is not the owner of the job. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

## 9. Audit API

### 9.1 GET /audit-events

Retrieve audit logs for the tenant.

- **Method & URL:**  
  `GET /api/v1/audit-events?asset_id=uuid&event_type=COMPLIANCE_CHECK_COMPLETED&from=2025-01-01T00:00:00Z&to=2025-01-31T23:59:59Z&limit=50&offset=0`
- **Roles:** `TENANT_ADMIN`, `AUDITOR`

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `asset_id` | UUID | No | Filter by asset ID. |
| `contract_id` | UUID | No | Filter by contract ID. |
| `dataset_id` | UUID | No | Filter by dataset ID. |
| `event_type` | string | No | Filter by event type (e.g., `COMPLIANCE_CHECK_COMPLETED`, `ASSET_CREATED`). |
| `entity_type` | string | No | Filter by entity type (e.g., `ASSET`, `CONTRACT`, `DATASET`, `JOB`). |
| `user_id` | UUID | No | Filter by user ID (actor). |
| `from` | timestamp (ISO 8601) | No | Start of time range (inclusive). |
| `to` | timestamp (ISO 8601) | No | End of time range (inclusive). |
| `sort_by` | string | No | Sort field: `timestamp` (default), `event_type`, `entity_type`. |
| `sort_order` | string | No | Sort direction: `desc` (default, newest first), `asc` (oldest first). |
| `format` | string | No | Response format: `json` (default), `csv` (for export). |
| `limit` | integer | No | Maximum number of results (default: 50, max: 1000). |
| `offset` | integer | No | Pagination offset (default: 0). |

**Date Range Validation**

- `from` and `to` must be valid ISO 8601 timestamps.
- If `from` is provided without `to`, `to` defaults to current time.
- If `to` is provided without `from`, `from` defaults to 30 days ago.
- Maximum time range: 1 year (if exceeded, returns `400 Bad Request` with `TIME_RANGE_TOO_LARGE`).

**Response (200 OK)**

**JSON Format** (default):

```json
{
  "items": [
    {
      "id": "uuid",
      "tenant_id": "uuid",
      "actor_user_id": "uuid",
      "actor_tenant_id": "uuid",
      "event_type": "COMPLIANCE_CHECK_COMPLETED",
      "resource_type": "ASSET",
      "resource_id": "uuid",
      "occurred_at": "2025-01-01T12:00:00Z",
      "request_id": "req-123456",
      "details_json": {
        "asset_name": "Customer Orders",
        "compliance_status": "PASS"
      }
    }
  ],
  "total": 1250,
  "limit": 50,
  "offset": 0
}
```

**CSV Format** (`format=csv`):

Returns CSV file with headers:
- `id`, `tenant_id`, `actor_user_id`, `actor_tenant_id`, `event_type`, `resource_type`, `resource_id`, `occurred_at`, `request_id`, `details_json`

#### 9.1.1 Audit Log CSV Export Format

**CSV Format Specification**

When `Accept: text/csv` is specified, the response is a CSV file with the following format:

**Headers** (first row):
```
id,tenant_id,actor_user_id,actor_tenant_id,event_type,resource_type,resource_id,occurred_at,request_id,details_json
```

**Data Rows**:
- **Field separator**: Comma (`,`)
- **Text qualifier**: Double quotes (`"`) for fields containing commas, newlines, or quotes
- **Quote escaping**: Double quotes within quoted fields are escaped as `""`
- **Encoding**: UTF-8
- **Line endings**: `\n` (Unix-style) or `\r\n` (Windows-style), depending on client

**Field Formatting**:

| Field | Format | Description |
|-------|--------|-------------|
| `id` | UUID string | Event ID (e.g., `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"`) |
| `tenant_id` | UUID string | Tenant ID |
| `actor_user_id` | UUID string or empty | User ID who performed the action (empty if `actor_type != USER`) |
| `actor_tenant_id` | UUID string or empty | Tenant ID of the actor (empty if actor is system) |
| `event_type` | String | Event type (e.g., `"ASSET_CREATED"`, `"QUALITY_CHECK_COMPLETED"`) |
| `resource_type` | String | Resource type (e.g., `"ASSET"`, `"CONTRACT"`, `"DATASET"`) |
| `resource_id` | UUID string or empty | Resource ID (empty if not applicable) |
| `occurred_at` | ISO 8601 timestamp | Event timestamp (e.g., `"2025-01-15T10:30:00Z"`) |
| `request_id` | String or empty | Request ID for tracing (empty if not available) |
| `details_json` | JSON string (escaped) | Event-specific details as JSON string (see below) |

**JSON Field Escaping**:

The `details_json` field contains a JSON object serialized as a string and properly escaped for CSV:

- **JSON serialization**: The JSON object is serialized to a compact string (no pretty-printing)
- **CSV escaping**: The JSON string is wrapped in double quotes and internal quotes are escaped
- **Example**:
  ```csv
  "{\"asset_id\":\"uuid\",\"asset_name\":\"Customer Orders\",\"status\":\"ACTIVE\"}"
  ```

**Nested JSON Handling**:

For complex nested JSON structures in `details_json`:

- **Full JSON preserved**: Entire JSON structure is included as a single CSV field
- **No flattening**: Nested objects and arrays are not flattened into separate columns
- **Parsing**: Clients must parse the JSON string to access nested fields

**Example CSV Row**:

```csv
a1b2c3d4-e5f6-7890-abcd-ef1234567890,tenant-uuid-123,user-uuid-456,tenant-uuid-123,ASSET_CREATED,ASSET,asset-uuid-789,2025-01-15T10:30:00Z,req-abc123,"{""asset_id"":""asset-uuid-789"",""asset_name"":""Customer Orders"",""status"":""ACTIVE""}"
```

**Array Fields in details_json**:

If `details_json` contains arrays, they are serialized as JSON arrays:

```csv
...,"{""detected_categories"":[""PII_DIRECT_EMAIL"",""PAYMENT_CARD""],""count"":1250}"
```

**Large details_json Handling**:

- **No truncation**: Full `details_json` is included (no size limits)
- **Performance**: Large exports may take longer to generate
- **Recommendation**: For very large exports (> 100,000 rows), use async export via job (future enhancement)

**CSV Export Limitations**:

- **Max rows per export**: 100,000 rows (configurable via `AUDIT_EXPORT_MAX_ROWS`)
- **Time range**: Maximum 1 year per export (enforced by API)
- **Pagination**: Large exports are not paginated (single CSV file)
- **Async export** (future enhancement): For very large exports, use `POST /audit-events/export` to create an async job

**Response Headers**:

- `Content-Type: text/csv; charset=utf-8`
- `Content-Disposition: attachment; filename="audit-events-2025-01-15.csv"`
- `Content-Length: <file-size-in-bytes>`

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid date format, invalid enum values, or malformed query parameters. |
| `400 Bad Request` | `TIME_RANGE_TOO_LARGE` | Time range exceeds 1 year. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `TENANT_ADMIN` or `AUDITOR` role. |

---

## 10. Marketplace API

### 10.1 POST /marketplace/listings

Create or update a listing for an Asset (provider side).

- **Method & URL:** `POST /api/v1/marketplace/listings`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN`

**Listing Creation Requirements**

Before a listing can be created, the following requirements MUST be met:

1. **Asset Status**:
   - Asset MUST be `ACTIVE` (cannot create listing for `DRAFT`, `RETIRED`, or assets without status).
   - Error code: `ASSET_NOT_ACTIVE` if asset is not `ACTIVE`.

2. **Tenant KYC Status**:
   - Tenant MUST have `kyc_status = VERIFIED` (only verified tenants can publish to marketplace).
   - Error code: `TENANT_NOT_VERIFIED` if tenant is not verified.

3. **Asset Ownership**:
   - Asset MUST belong to the requester's tenant (`assets.tenant_id = token.tenant_id`).
   - Error code: `ASSET_NOT_FOUND` if asset does not exist or belongs to a different tenant.

4. **Existing Listing**:
   - If a listing already exists for this asset (`listings.asset_id = <asset_id>` and `listings.tenant_id = <tenant_id>`):
     - Endpoint updates the existing listing (same as `PATCH /marketplace/listings/{id}`).
     - Returns `200 OK` with updated listing.
   - If no listing exists:
     - Creates new listing with `status = DRAFT`.
     - Returns `201 Created` with new listing.

**Asset Deletion After Listing Creation**

- If an asset is deleted (`status = RETIRED` or hard-deleted) after a listing is created:
  - Listing remains in database but is **automatically unpublished** (`status = UNPUBLISHED`).
  - Marketplace search excludes listings for deleted assets.
  - Existing entitlements remain active (for audit/compliance purposes).
  - Error code: `ASSET_DELETED` if attempting to update a listing for a deleted asset.

**Body**

```json
{
  "asset_id": "uuid",
  "title": "Customer Orders (EU)",
  "short_description": "Daily EU orders snapshot.",
  "long_description": "More details...",
  "price_model": "FREE | ONE_TIME | REQUEST_APPROVAL",
  "price_amount": 99.0,
  "currency": "USD"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `asset_id` | UUID | Yes | Asset to list. Must be `ACTIVE` and belong to requester's tenant. |
| `title` | string | Yes | Public title for the listing. Max 255 characters. |
| `short_description` | string | Yes | Brief description (1-2 sentences). Max 500 characters. |
| `long_description` | string | No | Detailed description. Max 10,000 characters. |
| `price_model` | string (enum) | Yes | Pricing model: `FREE`, `ONE_TIME`, or `REQUEST_APPROVAL` (for MVP). |
| `price_amount` | float | No | Price amount (required if `price_model != FREE`). Must be >= 0. |
| `currency` | string | No | Currency code (ISO 4217, e.g., `USD`, `EUR`). Required if `price_model != FREE`. |

**Response**

- `201 Created` (new listing) or `200 OK` (updated listing) with Listing JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Missing required fields, invalid enum values, or malformed request body. |
| `404 Not Found` | `ASSET_NOT_FOUND` | Asset with given ID does not exist or is not visible to tenant. |
| `400 Bad Request` | `ASSET_NOT_ACTIVE` | Asset is not `ACTIVE` (must be `ACTIVE` to create listing). |
| `403 Forbidden` | `TENANT_NOT_VERIFIED` | Tenant `kyc_status` is not `VERIFIED` (only verified tenants can publish). |
| `410 Gone` | `ASSET_DELETED` | Asset has been deleted; listing cannot be created or updated. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |

---

### 10.2 PATCH /marketplace/listings/{id}

Update a listing (including status).

- **Method & URL:** `PATCH /api/v1/marketplace/listings/{id}`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN` (must be owner of the listing)

**Body**

```json
{
  "title": "Updated Title",
  "short_description": "Updated description",
  "status": "PUBLISHED"
}
```

All fields are optional; only provided fields are updated.

**Listing Status Transition Rules**

| From Status | To Status | Requirements | Error Code if Invalid |
|-------------|-----------|--------------|----------------------|
| `DRAFT` | `PUBLISHED` | 1. Asset must be `ACTIVE`<br>2. Tenant must be `kyc_status = VERIFIED` | `ASSET_NOT_ACTIVE`, `TENANT_NOT_VERIFIED` |
| `PUBLISHED` | `UNPUBLISHED` | No restrictions | - |
| `PUBLISHED` | `DRAFT` | **Not allowed** (cannot revert published listing to draft) | `LISTING_ALREADY_PUBLISHED` |
| `UNPUBLISHED` | `PUBLISHED` | 1. Asset must be `ACTIVE`<br>2. Tenant must be `kyc_status = VERIFIED` | `ASSET_NOT_ACTIVE`, `TENANT_NOT_VERIFIED` |
| `UNPUBLISHED` | `DRAFT` | No restrictions | - |
| `DRAFT` | `UNPUBLISHED` | No restrictions | - |

**Status Meanings**:
- `DRAFT`: Listing is being created/edited, not visible in marketplace.
- `PUBLISHED`: Listing is visible in marketplace search and browse.
- `UNPUBLISHED`: Listing was published but is now hidden (e.g., asset was deleted, provider unpublished it).

**Automatic Unpublishing**:
- Listing is automatically set to `UNPUBLISHED` if:
  - Asset is deleted (`status = RETIRED` or hard-deleted).
  - Asset status changes from `ACTIVE` to `DRAFT` or `RETIRED`.
  - Tenant `kyc_status` changes from `VERIFIED` to `UNVERIFIED`.

#### 10.2.1 Listing Unpublishing and Active Entitlements

When a listing is unpublished (either manually via `PATCH /marketplace/listings/{id}` with `status = UNPUBLISHED` or automatically due to asset deletion/tenant suspension), the following rules apply to existing entitlements:

**Entitlement Behavior**

- **Existing entitlements are NOT automatically revoked**:
  - Entitlements with `status = ACTIVE` remain `ACTIVE`
  - Entitlements with `status = ACTIVE` and `expires_at IS NULL` remain active indefinitely
  - Entitlements with `expires_at` continue to be valid until expiration
- **Rationale**: Entitlements represent granted access rights that should not be retroactively revoked unless explicitly required by policy

**Access Control**

- **Active entitlements continue to grant access**:
  - Consumers with active entitlements can still download files via `GET /files/{id}/download`
  - Consumers can still access asset metadata via `GET /assets/{id}`
  - Marketplace search excludes unpublished listings, but direct asset access via entitlement remains valid
- **New entitlements cannot be created**:
  - New orders cannot be placed for unpublished listings
  - Existing `REQUESTED` orders cannot be approved (returns error `LISTING_UNPUBLISHED`)

**Notification**

- **Consumer notification** (optional, configurable):
  - Email notification may be sent to consumers with active entitlements when a listing is unpublished
  - Notification includes:
    - Listing title and asset name
    - Reason for unpublishing (if available)
    - Information about existing entitlements remaining active
- **Provider notification**:
  - Provider (listing owner) is notified when listing is automatically unpublished
  - Notification includes reason (asset deleted, tenant suspended, etc.)

**Re-publishing Impact**

- **If listing is re-published** (`status = PUBLISHED`):
  - Existing entitlements remain active (no change)
  - New orders can be placed
  - Existing `REQUESTED` orders can be approved

**Revocation (Manual)**

- **Manual entitlement revocation**:
  - Provider can manually revoke entitlements via `PATCH /entitlements/{id}` with `status = REVOKED`
  - Revocation is logged in audit events
  - Revoked entitlements no longer grant access

**Policy Considerations**

- **Audit compliance**: Entitlements are preserved for audit/compliance purposes even after listing unpublishing
- **Data access rights**: Consumers who have been granted access retain that access unless explicitly revoked
- **Provider control**: Providers can manually revoke entitlements if needed (e.g., for policy violations)

**Response**: Updated Listing JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `LISTING_NOT_FOUND` | Listing with given ID does not exist or is not visible to tenant. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid status transition or invalid field values. |
| `400 Bad Request` | `ASSET_NOT_ACTIVE` | Cannot publish listing: asset is not `ACTIVE`. |
| `403 Forbidden` | `TENANT_NOT_VERIFIED` | Cannot publish listing: tenant is not verified. |
| `409 Conflict` | `LISTING_ALREADY_PUBLISHED` | Cannot revert `PUBLISHED` listing to `DRAFT`. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not the owner of the listing or lacks required role. |

---

### 10.4 DELETE /marketplace/listings/{id}

Delete a listing permanently.

- **Method & URL:** `DELETE /api/v1/marketplace/listings/{id}`
- **Roles:** `DATA_PROVIDER`, `TENANT_ADMIN` (must be owner of the listing)

**Behavior**

- **Physical deletion**:
  - Permanently deletes listing record.
  - **Asset is NOT deleted** (asset remains, just not listed).
  - **Entitlements are NOT revoked** (existing entitlements remain active for audit/compliance).
  - **Orders are NOT deleted** (orders remain for audit).
  - Emits audit event: `LISTING_DELETED`.

**Cascade Behavior**

- **Orders**: Order records are **not** deleted (preserved for audit).
- **Entitlements**: Entitlement records are **not** deleted (preserved for audit).
- **Assets**: Asset record is **not** deleted (asset remains in provider's catalog).

**Response**

- `204 No Content` on success.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `LISTING_NOT_FOUND` | Listing with given ID does not exist or is not visible to tenant. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not the owner of the listing or lacks required role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

### 10.3 GET /marketplace/listings

Public marketplace search (cross-tenant).

- **Method & URL:**  
  `GET /api/v1/marketplace/listings?status=PUBLISHED&domain=sales&query=orders&limit=20&offset=0`
- **Roles:** `DATA_CONSUMER`, `DATA_PROVIDER`, `TENANT_ADMIN`, `AUDITOR` (or public if deployment allows)

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string (enum) | No | Filter by listing status: `PUBLISHED` (default), `DRAFT`, `UNPUBLISHED`. Only `PUBLISHED` listings are visible to non-owners. |
| `domain` | string | No | Filter by asset domain (e.g., `sales`, `finance`, `marketing`). |
| `query` | string | No | Full-text search query. Searches in `title`, `short_description`, `long_description`, and asset `name`. |
| `price_model` | string (enum) | No | Filter by pricing model: `FREE`, `ONE_TIME`, `REQUEST_APPROVAL`. |
| `min_price` | float | No | Minimum price (requires `max_price` or `price_model`). |
| `max_price` | float | No | Maximum price (requires `min_price` or `price_model`). |
| `quality_status` | string (enum) | No | Filter by asset DQ status: `PASS`, `WARN`, `FAIL`, `UNKNOWN`. |
| `compliance_status` | string (enum) | No | Filter by asset compliance status: `PASS`, `WARN`, `FAIL`, `UNKNOWN`. |
| `sort_by` | string | No | Sort field: `relevance` (default), `title`, `created_at`, `updated_at`, `price_amount`. |
| `sort_order` | string | No | Sort direction: `asc` (default), `desc`. |
| `limit` | integer | No | Maximum number of results (default: 20, max: 100). |
| `offset` | integer | No | Pagination offset (default: 0). |

**Search Algorithm**

- **Full-text search** (`query` parameter):
  - Searches across listing `title`, `short_description`, `long_description`, and asset `name`.
  - Uses case-insensitive matching.
  - Supports partial word matching (e.g., "order" matches "orders", "ordering").
  - Results are ranked by relevance (exact matches first, then partial matches).

#### 10.3.1 Marketplace Search Ranking Algorithm

When `sort_by = relevance` (default when `query` is provided), results are ranked using a relevance scoring algorithm.

**Relevance Score Calculation**

The relevance score is calculated as a weighted sum of multiple factors:

```python
relevance_score = (
    title_match_score * 3.0 +
    name_match_score * 2.5 +
    description_match_score * 1.0 +
    quality_boost * 0.5 +
    compliance_boost * 0.5 +
    recency_boost * 0.3
)
```

**Match Scoring**

- **Title match** (`title_match_score`):
  - **Exact match** (query matches entire title): Score = 10.0
  - **Prefix match** (query matches start of title): Score = 8.0
  - **Word match** (query matches word in title): Score = 6.0
  - **Partial match** (query matches substring in title): Score = 4.0
  - **No match**: Score = 0.0
- **Asset name match** (`name_match_score`):
  - Same scoring as title match (exact = 10.0, prefix = 8.0, word = 6.0, partial = 4.0)
- **Description match** (`description_match_score`):
  - **Word match** (query matches word in description): Score = 3.0
  - **Partial match** (query matches substring in description): Score = 1.0
  - **No match**: Score = 0.0

**Quality and Compliance Boosts**

- **Quality boost** (`quality_boost`):
  - `quality_status = PASS`: +2.0
  - `quality_status = WARN`: +1.0
  - `quality_status = FAIL` or `UNKNOWN`: +0.0
- **Compliance boost** (`compliance_boost`):
  - `compliance_status = PASS`: +2.0
  - `compliance_status = WARN`: +1.0
  - `compliance_status = FAIL` or `UNKNOWN`: +0.0

**Recency Boost**

- **Recency boost** (`recency_boost`):
  - Created within last 7 days: +2.0
  - Created within last 30 days: +1.0
  - Created within last 90 days: +0.5
  - Older than 90 days: +0.0

**Final Ranking**

- Results are sorted by `relevance_score` in descending order (highest score first)
- If `relevance_score` is equal, secondary sort by `created_at DESC` (newest first)
- If no `query` is provided, `sort_by = relevance` is ignored and results are sorted by `created_at DESC` (or specified `sort_by` field)

**Example Scoring**

Listing A:
- Query: "customer orders"
- Title: "Customer Orders Dataset" (exact match in title: 10.0)
- Asset name: "customer-orders" (exact match: 10.0)
- Quality: PASS (+2.0)
- Compliance: PASS (+2.0)
- Created: 5 days ago (+2.0)
- **Relevance score**: (10.0 * 3.0) + (10.0 * 2.5) + (0 * 1.0) + (2.0 * 0.5) + (2.0 * 0.5) + (2.0 * 0.3) = **58.1**

Listing B:
- Query: "customer orders"
- Title: "Order Data" (word match in title: 6.0)
- Asset name: "orders" (word match: 6.0)
- Description: "Customer order data" (word match: 3.0)
- Quality: WARN (+1.0)
- Compliance: PASS (+2.0)
- Created: 60 days ago (+0.5)
- **Relevance score**: (6.0 * 3.0) + (6.0 * 2.5) + (3.0 * 1.0) + (1.0 * 0.5) + (2.0 * 0.5) + (0.5 * 0.3) = **33.65**

Result: Listing A appears before Listing B (higher relevance score).

**Filtering**:
  - All filters are applied as `AND` conditions.
  - Price filters require both `min_price` and `max_price`, or use `price_model` alone.
- **Sorting**:
  - `relevance`: Only applicable when `query` is provided; ranks by search relevance (see algorithm above).
  - Other sort fields: Standard ascending/descending order.
- **Response ordering**: Results are returned in the order specified by `sort_by` and `sort_order`.

**Response**:

```json
{
  "items": [
    {
      "listing": { /* Listing JSON */ },
      "asset": {
        "id": "uuid",
        "name": "Customer Orders",
        "domain": "sales",
        "quality_status": "PASS",
        "compliance_status": "PASS"
      },
      "provider": {
        "tenant_id": "uuid",
        "name": "Provider Corp"
      }
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### 10.5 POST /marketplace/orders

Consumer creates an **order / access request** for a listing.

- **Method & URL:** `POST /api/v1/marketplace/orders`
- **Roles:** `DATA_CONSUMER`, `TENANT_ADMIN`

**Body**

```json
{
  "listing_id": "uuid"
}
```

**Behavior**

- Creates an `Order` record with `status = REQUESTED`
- **Price locking**: Order captures the listing's current price at creation time:
  - `order.price_amount = listing.price_amount` (snapshot at order creation)
  - `order.price_model = listing.price_model` (snapshot at order creation)
  - `order.currency = listing.currency` (snapshot at order creation)
  - **Price changes after order creation**: If listing price changes after order is created, the order's price remains locked to the original value
- **Auto-approval**: If listing has `price_model = FREE`:
  - Order is automatically approved (`status = APPROVED`)
  - `Entitlement` record is created automatically (`status = ACTIVE`)
  - Response includes both `order` and `entitlement`
- **Manual approval required**: If listing has `price_model != FREE`:
  - Order remains `status = REQUESTED`
  - Provider tenant admin must approve via `PATCH /marketplace/orders/{id}`
  - Response includes only `order` (no `entitlement` yet)

#### 10.5.1 Marketplace Order Price Change Handling

**Price Locking at Order Creation**

When an order is created via `POST /marketplace/orders`, the order captures a **snapshot** of the listing's pricing at that moment:

- **Fields captured**:
  - `order.price_amount`: Snapshot of `listing.price_amount` at order creation
  - `order.price_model`: Snapshot of `listing.price_model` at order creation
  - `order.currency`: Snapshot of `listing.currency` at order creation
- **Rationale**: Prevents price changes from affecting pending orders, ensuring fair pricing for consumers

**Price Changes After Order Creation**

- **Listing price changes**: If a provider changes the listing price after an order is created:
  - **Pending orders** (`status = REQUESTED`): Order price remains locked to original value
  - **Approved orders** (`status = APPROVED`): Order price remains locked (already approved)
  - **Rejected orders** (`status = REJECTED`): Order price remains locked (for audit trail)
  - **Cancelled orders** (`status = CANCELLED`): Order price remains locked (for audit trail)
- **No price mismatch errors**: The system does not reject orders or approvals due to price mismatches
  - Orders are always processed with their locked price
  - Listing price changes do not affect existing orders

**Price Display**

- **Order details**: When viewing an order (`GET /marketplace/orders/{id}`):
  - Response includes the locked price (`order.price_amount`, `order.price_model`, `order.currency`)
  - Response may optionally include current listing price for comparison (future enhancement)
- **Listing details**: When viewing a listing (`GET /marketplace/listings/{id}`):
  - Response shows current listing price (may differ from order prices if listing was updated)

**Price Change Notification** (Future Enhancement)

- **Provider notification**: When listing price changes, providers may be notified of pending orders with different prices
- **Consumer notification**: Consumers may be notified if listing price decreases significantly after order creation (optional, configurable)

**Billing Integration** (Post-MVP)

- **Future billing**: When billing is integrated, orders will be billed at the locked price (`order.price_amount`)
- **Price history**: Order price snapshots provide audit trail for billing disputes

**Response**

**Auto-approved (FREE listings):**
```json
{
  "order": {
    "id": "uuid",
    "consumer_tenant_id": "uuid",
    "listing_id": "uuid",
    "status": "APPROVED",
    "requested_by_user_id": "uuid",
    "approved_by_user_id": "system",
    "created_at": "2025-01-01T12:00:00Z",
    "updated_at": "2025-01-01T12:00:00Z"
  },
  "entitlement": {
    "id": "uuid",
    "tenant_id": "uuid",
    "asset_id": "uuid",
    "listing_id": "uuid",
    "order_id": "uuid",
    "status": "ACTIVE",
    "granted_at": "2025-01-01T12:00:00Z",
    "expires_at": null
  }
}
```

**Manual approval required (paid listings):**
```json
{
  "order": {
    "id": "uuid",
    "consumer_tenant_id": "uuid",
    "listing_id": "uuid",
    "status": "REQUESTED",
    "requested_by_user_id": "uuid",
    "approved_by_user_id": null,
    "created_at": "2025-01-01T12:00:00Z",
    "updated_at": "2025-01-01T12:00:00Z"
  }
}
```

---

### 10.6 PATCH /marketplace/orders/{id}

Approve or reject an order (provider side).

- **Method & URL:** `PATCH /api/v1/marketplace/orders/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN` of the **provider tenant** (owner of the listing)

**Body**

```json
{
  "status": "APPROVED" | "REJECTED"
}
```

**Behavior**

- **On approval** (`status = APPROVED`):
  - Updates order: `status = APPROVED`, `approved_by_user_id = <current_user>`, `updated_at = NOW()`
  - Creates `Entitlement` record:
    - `tenant_id = <consumer_tenant_id>` (from order)
    - `asset_id = <asset_id>` (from listing)
    - `listing_id = <listing_id>`
    - `order_id = <order_id>`
    - `status = ACTIVE`
    - `granted_at = NOW()`
    - `expires_at = null` (or set based on listing/tenant policy)
  - Emits audit event: `MARKETPLACE_ORDER_APPROVED`
  - Consumer tenant can now access the asset

- **On rejection** (`status = REJECTED`):
  - Updates order: `status = REJECTED`, `approved_by_user_id = <current_user>`, `updated_at = NOW()`
  - No entitlement is created
  - Emits audit event: `MARKETPLACE_ORDER_REJECTED`

#### 10.6.1 Marketplace Order Fulfillment Flow

**Fulfillment Process After Approval**

When an order is approved (`PATCH /marketplace/orders/{id}` with `status = APPROVED`), the following fulfillment process is executed:

**Step 1: Order Approval (Synchronous)**

- **Transaction**: Order update and entitlement creation occur in a **single database transaction**
- **Atomicity**: If entitlement creation fails, order approval is rolled back
- **Timing**: Entitlement is created **immediately** (not queued for background processing)
- **Response**: API returns updated order and created entitlement in response body

**Step 2: Entitlement Activation (Immediate)**

- **Entitlement Status**: Set to `ACTIVE` immediately upon creation
- **Access Granted**: Consumer tenant can access the asset **immediately** after approval
- **No Delay**: No background job or queue processing required for entitlement activation

**Step 3: Notification (Asynchronous)**

- **Consumer Notification**:
  - **Email notification** sent to order requester (user who created the order)
  - **Email content**:
    - Subject: "Your data access request has been approved"
    - Body includes:
      - Asset name and description
      - Listing title
      - Access instructions (how to download/access data)
      - Entitlement expiration date (if applicable)
  - **Notification timing**: Sent asynchronously (within 1 minute of approval)
  - **Notification failure**: If email fails, error is logged but does not affect entitlement creation

- **Provider Notification** (optional, configurable):
  - **Email notification** sent to listing owner (provider tenant admin)
  - **Email content**:
    - Subject: "New order approved for your listing"
    - Body includes:
      - Consumer tenant name
      - Order details
      - Asset name

**Step 4: Entitlement Usage Tracking**

- **Access Logging**: All data access (downloads, API calls) is logged in audit events
- **Usage Metrics**: Entitlement usage is tracked for reporting and analytics
- **Monitoring**: Entitlement activation and usage are monitored via metrics

**Order Status Transitions**

| From Status | To Status | Who Can Perform | Notes |
|-------------|-----------|-----------------|-------|
| `REQUESTED` | `APPROVED` | Provider (DATA_PROVIDER, TENANT_ADMIN) | Creates entitlement |
| `REQUESTED` | `REJECTED` | Provider (DATA_PROVIDER, TENANT_ADMIN) | No entitlement created |
| `REQUESTED` | `CANCELLED` | Consumer (DATA_CONSUMER, TENANT_ADMIN) | Consumer cancels before approval |
| `APPROVED` | `CANCELLED` | Not allowed | Cannot cancel approved orders (use entitlement revocation) |
| `REJECTED` | `CANCELLED` | Not allowed | Cannot cancel rejected orders |
| `CANCELLED` | Any | Not allowed | Terminal state |

**Fulfillment Failure Handling**

**If Entitlement Creation Fails**:

- **Transaction Rollback**: Order approval is rolled back (order remains `REQUESTED`)
- **Error Response**: API returns `500 Internal Server Error` with error code `INTERNAL_ERROR`
- **Error Details**: Response includes:
  ```json
  {
    "error": {
      "code": "INTERNAL_ERROR",
      "message": "Failed to create entitlement after order approval.",
      "details": {
        "order_id": "uuid",
        "failure_reason": "Database constraint violation",
        "retry_recommended": true
      }
    }
  }
  ```
- **Retry**: Provider can retry approval (idempotent operation)
- **Audit Event**: `MARKETPLACE_ORDER_APPROVAL_FAILED` audit event is emitted

**If Notification Fails**:

- **Entitlement Still Created**: Notification failure does not affect entitlement creation
- **Error Logged**: Notification failure is logged for monitoring
- **Retry**: Notification service retries failed notifications (up to 3 attempts)
- **Manual Notification**: Provider can manually notify consumer if needed

**Entitlement Expiration Notification**

When an entitlement is about to expire or has expired:

- **Pre-Expiration Notification** (7 days before expiration):
  - Email sent to consumer tenant admin
  - Subject: "Your data access will expire soon"
  - Body includes expiration date and renewal instructions

- **Expiration Notification** (on expiration):
  - Email sent to consumer tenant admin
  - Subject: "Your data access has expired"
  - Body includes renewal instructions

**Notification Configuration**

- **Email Templates**: Stored in configuration and can be customized per tenant
- **Notification Channels**: Currently email only (future: webhooks, Slack, etc.)
- **Notification Preferences**: Can be configured per tenant (opt-in/opt-out)

**Fulfillment Metrics**

The following metrics are tracked for order fulfillment:

- `marketplace_order_approval_duration_seconds` (histogram): Time from approval request to entitlement creation
- `marketplace_entitlement_creation_success_total` (counter): Successful entitlement creations
- `marketplace_entitlement_creation_failures_total` (counter): Failed entitlement creations
- `marketplace_notification_sent_total{type}` (counter): Notifications sent by type (approval, expiration, etc.)
- `marketplace_notification_failures_total{type}` (counter): Notification failures by type

**Response**

Returns updated `Order` JSON. If approved, response may optionally include the created `Entitlement`:

```json
{
  "order": { /* Updated Order JSON */ },
  "entitlement": { /* Entitlement JSON, if approved */ }
}
```

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ORDER_NOT_FOUND` | Order with given ID does not exist or is not visible to provider tenant. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid status value (must be `APPROVED` or `REJECTED`). |
| `409 Conflict` | `ORDER_ALREADY_PROCESSED` | Order is already `APPROVED` or `REJECTED` (cannot change status). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not a member of the provider tenant or lacks required role. |

---

### 10.7 GET /marketplace/orders/{id}

- **Method & URL:** `GET /api/v1/marketplace/orders/{id}`
- **Roles:** `DATA_CONSUMER` or `TENANT_ADMIN` (consumer tenant) OR `DATA_PROVIDER` or `TENANT_ADMIN` (provider tenant)

Returns Order JSON. Consumer tenants can view their own orders; provider tenants can view orders for their listings.

---

### 10.8 GET /entitlements

List **assets** the current tenant is entitled to access.

- **Method & URL:** `GET /api/v1/entitlements?status=ACTIVE&limit=20&offset=0`
- **Roles:** `DATA_CONSUMER`, `DATA_PROVIDER`, `TENANT_ADMIN`, `AUDITOR`

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string (enum) | No | Filter by entitlement status: `ACTIVE` (default), `REVOKED`, `EXPIRED`. |
| `asset_id` | UUID | No | Filter by asset ID. |
| `listing_id` | UUID | No | Filter by listing ID. |
| `limit` | integer | No | Maximum number of results (default: 20, max: 100). |
| `offset` | integer | No | Pagination offset (default: 0). |

**Response**

```json
{
  "items": [
    {
      "entitlement": {
        "id": "uuid",
        "tenant_id": "uuid",
        "asset_id": "uuid",
        "listing_id": "uuid",
        "order_id": "uuid",
        "status": "ACTIVE",
        "granted_at": "2025-01-01T12:00:00Z",
        "expires_at": null
      },
      "asset": {
        "id": "uuid",
        "name": "Customer Orders",
        "domain": "sales"
      },
      "listing": {
        "id": "uuid",
        "title": "Customer Orders (EU)"
      }
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

---

### 10.6.2 POST /marketplace/orders/{id}/cancel

Cancel a marketplace order (consumer side).

- **Method & URL:** `POST /api/v1/marketplace/orders/{id}/cancel`
- **Roles:** `DATA_CONSUMER` or `TENANT_ADMIN` of the **consumer tenant** (requester of the order)

**Request Body** (optional)

```json
{
  "reason": "No longer needed"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reason` | string | No | Optional cancellation reason (max 500 characters). |

**Behavior**

- **Cancellation Rules**:
  - Only orders with `status = REQUESTED` can be cancelled
  - Orders with `status = APPROVED` cannot be cancelled (use entitlement revocation instead)
  - Orders with `status = REJECTED` or `CANCELLED` cannot be cancelled (already terminal)
- **On cancellation**:
  - Updates order: `status = CANCELLED`, `cancelled_at = NOW()`, `cancelled_by_user_id = <current_user>`, `cancellation_reason = <reason>`
  - **No entitlement is created** (order was not approved)
  - Emits audit event: `MARKETPLACE_ORDER_CANCELLED`
  - Provider is notified (optional, configurable)

**Response (200 OK)**

```json
{
  "order": {
    "id": "uuid",
    "consumer_tenant_id": "uuid",
    "listing_id": "uuid",
    "status": "CANCELLED",
    "cancelled_at": "2025-01-15T10:30:00Z",
    "cancelled_by_user_id": "uuid",
    "cancellation_reason": "No longer needed",
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
}
```

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ORDER_NOT_FOUND` | Order with given ID does not exist or is not visible to tenant. |
| `400 Bad Request` | `ORDER_ALREADY_PROCESSED` | Order is already `APPROVED` or `REJECTED` (cannot cancel). |
| `409 Conflict` | `ORDER_ALREADY_CANCELLED` | Order is already `CANCELLED`. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not a member of the consumer tenant or lacks required role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

**Notification**

- **Provider Notification** (optional, configurable):
  - Email notification may be sent to listing owner when consumer cancels order
  - Email includes:
    - Order ID and listing title
    - Consumer tenant name
    - Cancellation reason (if provided)
    - Timestamp of cancellation

---

### 10.7 GET /entitlements/{id}

Get a single entitlement by ID.

- **Method & URL:** `GET /api/v1/entitlements/{id}`
- **Roles:** `DATA_CONSUMER`, `DATA_PROVIDER`, `TENANT_ADMIN`, `AUDITOR`

**Response (200 OK)**

Returns complete Entitlement JSON (see §2.9 for schema) plus minimal Asset and Listing info.

**Authorization**

- Consumer tenants can view entitlements where `entitlements.tenant_id = <consumer_tenant_id>`.
- Provider tenants can view entitlements where `entitlements.asset_id` belongs to their tenant.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ENTITLEMENT_NOT_FOUND` | Entitlement with given ID does not exist or is not visible to tenant. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role or entitlement is not visible to tenant. |

---

### 10.8 PATCH /entitlements/{id}

Revoke or update an entitlement (provider side).

- **Method & URL:** `PATCH /api/v1/entitlements/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN` of the **provider tenant** (owner of the asset)

**Request Body**

```json
{
  "status": "REVOKED",
  "revoke_reason": "Policy violation"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string (enum) | No | New status: `REVOKED` (to revoke), `ACTIVE` (to reactivate if previously revoked). |
| `revoke_reason` | string | No | Human-readable reason for revocation. Max 500 characters. Required if `status = REVOKED`. |

**Status Transition Rules**

| From Status | To Status | Requirements | Error Code if Invalid |
|-------------|-----------|--------------|----------------------|
| `ACTIVE` | `REVOKED` | No restrictions | - |
| `REVOKED` | `ACTIVE` | No restrictions (reactivation) | - |
| `EXPIRED` | `ACTIVE` | **Not allowed** (expired entitlements cannot be reactivated) | `ENTITLEMENT_EXPIRED` |
| `EXPIRED` | `REVOKED` | No restrictions | - |

**Behavior**

- **On revocation** (`status = REVOKED`):
  - Sets `entitlements.status = REVOKED`, `entitlements.revoked_at = NOW()`, `entitlements.revoked_reason = <revoke_reason>`.
  - Invalidates any cached entitlement checks (cache invalidation).
  - Emits audit event: `ENTITLEMENT_REVOKED`.
  - Consumer tenant immediately loses access to the asset.

- **On reactivation** (`status = ACTIVE` from `REVOKED`):
  - Sets `entitlements.status = ACTIVE`, `entitlements.revoked_at = NULL`, `entitlements.revoked_reason = NULL`.
  - Emits audit event: `ENTITLEMENT_REACTIVATED`.
  - Consumer tenant regains access to the asset.

**Response (200 OK)**

Returns updated Entitlement JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `ENTITLEMENT_NOT_FOUND` | Entitlement with given ID does not exist or is not visible to provider tenant. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid status transition or missing `revoke_reason` when revoking. |
| `400 Bad Request` | `ENTITLEMENT_EXPIRED` | Cannot reactivate expired entitlement (must create new entitlement). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not a member of the provider tenant or lacks required role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

## 11. Authentication & API Key Management

### 11.1 POST /auth/api-keys

Create a new API key for programmatic access.

- **Method & URL:** `POST /api/v1/auth/api-keys`
- **Roles:** `TENANT_ADMIN` or `DATA_PROVIDER`

**Request Body**

```json
{
  "name": "Production CI/CD Key",
  "scopes": ["assets:read", "assets:write", "jobs:read"],
  "expires_in_days": 365
}
```

**Request Fields**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | User-provided label for the API key (e.g., "Production CI/CD Key"). Max 255 characters. |
| `scopes` | array of strings | No | All scopes for user's roles | Fine-grained permissions (e.g., `assets:read`, `jobs:write`). If omitted, key inherits all scopes from user's roles. |
| `expires_in_days` | integer | No | No expiration | Number of days until key expires. Must be between 1 and 3650 (10 years). |

**Response (201 Created)**

```json
{
  "api_key": {
    "id": "uuid",
    "name": "Production CI/CD Key",
    "prefix": "idh_live_",
    "key": "idh_live_aB3dEf9GhIjKlMnOpQrStUvWxYz1234",
    "scopes": ["assets:read", "assets:write", "jobs:read"],
    "created_at": "2025-01-15T10:00:00Z",
    "expires_at": "2026-01-15T10:00:00Z"
  }
}
```

**Important**: The full API key (`key` field) is shown **only once** during creation. It cannot be retrieved later. Store it securely.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid `name` (empty or too long), invalid `scopes`, or `expires_in_days` out of range. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `TENANT_ADMIN` or `DATA_PROVIDER` role. |

---

### 11.2 GET /auth/api-keys

List API keys for the current tenant.

- **Method & URL:** `GET /api/v1/auth/api-keys?limit=20&offset=0`
- **Roles:** `TENANT_ADMIN` or `DATA_PROVIDER`

**Query Parameters**

- `limit`, `offset` (pagination, standard)

**Response**

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Production CI/CD Key",
      "prefix": "idh_live_",
      "scopes": ["assets:read", "assets:write", "jobs:read"],
      "created_at": "2025-01-15T10:00:00Z",
      "last_used_at": "2025-01-20T14:30:00Z",
      "expires_at": "2026-01-15T10:00:00Z",
      "revoked_at": null
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

**Note**: The full API key value is **never** returned in list responses (only `prefix` is shown).

---

### 11.3 DELETE /auth/api-keys/{id}

Revoke an API key.

- **Method & URL:** `DELETE /api/v1/auth/api-keys/{id}`
- **Roles:** `TENANT_ADMIN` or `DATA_PROVIDER` (must be creator or tenant admin)

**Response**

- `204 No Content` on success

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `API_KEY_NOT_FOUND` | API key with given ID does not exist or is not visible to tenant. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not the creator of the key and lacks `TENANT_ADMIN` role. |

**Behavior**: Revoked keys are immediately invalid; no grace period.

---

### 11.4 POST /auth/login

Authenticate a user and obtain access and refresh tokens.

- **Method & URL:** `POST /api/v1/auth/login`
- **Roles:** None (public endpoint)

**Request Body**

```json
{
  "email": "user@example.com",
  "password": "secure-password"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User email address. Must be valid email format. |
| `password` | string | Yes | User password. Plain text (transmitted over HTTPS). |

**Response (200 OK)**

```json
{
  "access_token": "<jwt>",
  "expires_in": 900,
  "refresh_token": "<opaque-token-or-jwt>",
  "token_type": "Bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "Jane Doe",
    "tenant_id": "uuid",
    "roles": ["DATA_PROVIDER", "DATA_CONSUMER"]
  }
}
```

**Response Fields**

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | string | JWT access token (valid for 15 minutes by default). |
| `expires_in` | integer | Access token lifetime in seconds (default: 900). |
| `refresh_token` | string | Opaque refresh token (valid for 14 days by default). |
| `token_type` | string | Always `"Bearer"` for access tokens. |
| `user` | object | User information including tenant and roles. |

**Behavior**

- Validates email and password against stored credentials (hashed passwords).
- Checks user status (`ACTIVE`, `INVITED`, `DISABLED`).
- Checks tenant status (`ACTIVE`, `SUSPENDED`, `DELETED`).
- Issues new access token and refresh token.
- Records login event in audit log.
- Updates `users.last_login_at` timestamp.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `401 Unauthorized` | `INVALID_CREDENTIALS` | Email or password is incorrect. |
| `401 Unauthorized` | `USER_DISABLED` | User account is disabled (`status = DISABLED`). |
| `401 Unauthorized` | `USER_NOT_ACTIVE` | User account is not active (`status = INVITED`; user must accept invitation first). |
| `403 Forbidden` | `TENANT_SUSPENDED` | Tenant is suspended (`status = SUSPENDED`). |
| `403 Forbidden` | `TENANT_DELETED` | Tenant is deleted (`status = DELETED`). |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | Too many failed login attempts (rate limiting applies). |
| `400 Bad Request` | `VALIDATION_ERROR` | Missing or invalid email/password format. |

**Security Notes**

- Failed login attempts are rate-limited (e.g., 5 attempts per 15 minutes per email).
- After multiple failed attempts, account may be temporarily locked (implementation-specific).
- Passwords are never returned in responses.
- Refresh tokens should be stored securely (HTTP-only cookies recommended for web apps).

---

### 11.5 POST /auth/logout

Logout a user and revoke refresh tokens.

- **Method & URL:** `POST /api/v1/auth/logout`
- **Roles:** None (requires valid access token)

**Request Body**

```json
{
  "revoke_all_sessions": false
}
```

**Request Fields**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `revoke_all_sessions` | boolean | No | `false` | If `true`, revokes all refresh tokens for the user across all devices. If `false`, revokes only the current session's refresh token. |

**Behavior**

- **Current session revocation** (`revoke_all_sessions = false`):
  - Marks the current refresh token as revoked (`revoked_at = NOW()`, `revoked_reason = "LOGOUT"`).
  - Increments user's `token_version` (invalidates all access tokens issued before logout).
  - Emits audit event: `AUTH_LOGOUT`.

- **All sessions revocation** (`revoke_all_sessions = true`):
  - Marks all refresh tokens for the user as revoked.
  - Increments user's `token_version`.
  - Emits audit event: `AUTH_LOGOUT_ALL_SESSIONS`.

- **Access tokens**: Short-lived access tokens remain valid until expiration (no immediate revocation, but new tokens cannot be issued after `token_version` increment).

**Response (200 OK)**

```json
{
  "message": "Logged out successfully",
  "revoked_sessions": 1
}
```

**Response Fields**

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Success message. |
| `revoked_sessions` | integer | Number of refresh tokens revoked (1 for current session, or total count for all sessions). |

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| `500 Internal Server Error` | `INTERNAL_ERROR` | Unexpected error during logout. |

---

### 11.6 POST /auth/refresh

Refresh an access token using a refresh token.

- **Method & URL:** `POST /api/v1/auth/refresh`
- **Roles:** None (public endpoint, but requires valid refresh token)

**Request Body**

```json
{
  "refresh_token": "<opaque-token-or-jwt>"
}
```

**Response (200 OK)**

```json
{
  "access_token": "<jwt>",
  "expires_in": 900,
  "refresh_token": "<new-refresh-token>",
  "token_type": "Bearer"
}
```

**Behavior**

- Validates refresh token (not expired, not revoked)
- Issues new access token and new refresh token (refresh token rotation)
- Old refresh token is marked as revoked

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `REFRESH_TOKEN_INVALID` | Invalid refresh token format. |
| `401 Unauthorized` | `REFRESH_TOKEN_EXPIRED` | Refresh token has expired. |
| `401 Unauthorized` | `REFRESH_TOKEN_REVOKED` | Refresh token has been revoked. |

---

### 11.7 POST /auth/password-reset

Initiate password reset flow.

- **Method & URL:** `POST /api/v1/auth/password-reset`
- **Roles:** None (public endpoint)

**Request Body**

```json
{
  "email": "user@example.com"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | string | Yes | User email address. Must be valid email format. |

**Behavior**

- Validates email exists in system.
- Generates password reset token (opaque, cryptographically secure).
- Stores token with expiration (default: 1 hour, configurable via `PASSWORD_RESET_TOKEN_TTL_SECONDS`).
- Sends password reset email with reset link containing token.
- **Security**: Always returns success (200 OK) even if email doesn't exist (prevents email enumeration).

**Response (200 OK)**

```json
{
  "message": "If the email exists, a password reset link has been sent."
}
```

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid email format. |
| `429 Too Many Requests` | `RATE_LIMIT_EXCEEDED` | Too many password reset requests (rate limited to prevent abuse). |

**Security Notes**

- Rate limiting: Maximum 3 requests per email per hour.
- Token expiration: 1 hour (configurable).
- Token is single-use (invalidated after successful reset).
- Failed attempts are logged for security monitoring.

---

### 11.8 POST /auth/password-reset/confirm

Confirm password reset and set new password.

- **Method & URL:** `POST /api/v1/auth/password-reset/confirm`
- **Roles:** None (public endpoint, but requires valid reset token)

**Request Body**

```json
{
  "token": "550e8400-e29b-41d4-a716-446655440000",
  "new_password": "secure-new-password"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string (UUID) | Yes | Password reset token from email link. Format: UUID v4 (36 characters, e.g., `550e8400-e29b-41d4-a716-446655440000`). See `Security_Design_and_Threat_Model.md` §5.11.8 for details. |
| `new_password` | string | Yes | New password. Must meet password policy (min length, complexity). |

**Password Policy**

- Minimum length: 12 characters (configurable via `PASSWORD_MIN_LENGTH`).
- Must contain: uppercase, lowercase, number, special character.
- Cannot be common password (checked against common password list).

**Behavior**

- Validates reset token (exists, not expired, not already used).
- Validates new password meets policy.
- Updates user password (hashed and stored).
- Invalidates reset token (single-use).
- Revokes all refresh tokens for the user (security measure).
- Increments user's `token_version` (invalidates all access tokens).
- Emits audit event: `PASSWORD_RESET_COMPLETED`.

**Response (200 OK)**

```json
{
  "message": "Password has been reset successfully. Please log in with your new password."
}
```

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid password format or password does not meet policy. |
| `400 Bad Request` | `PASSWORD_RESET_TOKEN_INVALID` | Invalid or malformed reset token. |
| `401 Unauthorized` | `PASSWORD_RESET_TOKEN_EXPIRED` | Reset token has expired (1 hour TTL). |
| `401 Unauthorized` | `PASSWORD_RESET_TOKEN_USED` | Reset token has already been used. |
| `404 Not Found` | `USER_NOT_FOUND` | User associated with token does not exist. |

---

### 11.9 POST /auth/accept-invitation

Accept user invitation and set password.

- **Method & URL:** `POST /api/v1/auth/accept-invitation`
- **Roles:** None (public endpoint, but requires valid invitation token)

**Request Body**

```json
{
  "invitation_token": "550e8400-e29b-41d4-a716-446655440000",
  "password": "secure-password",
  "display_name": "Jane Doe"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `invitation_token` | string (UUID) | Yes | Invitation token from invitation email or API response. Format: UUID v4 (36 characters, e.g., `550e8400-e29b-41d4-a716-446655440000`). See `Security_Design_and_Threat_Model.md` §5.11.7 for details. |
| `password` | string | Yes | User's chosen password. Must meet password policy (same as password reset). |
| `display_name` | string | No | User's display name (can be set during acceptance or later). |

**Behavior**

- Validates invitation token (exists, not expired, user status is `INVITED`).
- Validates password meets policy.
- Sets user password (hashed and stored).
- Updates user: `status = ACTIVE`, `display_name = <provided or existing>`.
- Invalidates invitation token (single-use).
- Emits audit event: `USER_INVITATION_ACCEPTED`.
- Optionally sends welcome email.

**Response (200 OK)**

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "Jane Doe",
    "status": "ACTIVE",
    "tenant_id": "uuid",
    "roles": ["DATA_PROVIDER"]
  },
  "access_token": "<jwt>",
  "expires_in": 900,
  "refresh_token": "<opaque-token>",
  "token_type": "Bearer"
}
```

**Note**: User is automatically logged in after accepting invitation (tokens are returned).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid password format or password does not meet policy. |
| `400 Bad Request` | `INVITATION_TOKEN_INVALID` | Invalid or malformed invitation token. |
| `401 Unauthorized` | `INVITATION_TOKEN_EXPIRED` | Invitation token has expired (default: 7 days, configurable via `INVITATION_TOKEN_TTL_DAYS`). |
| `401 Unauthorized` | `INVITATION_TOKEN_USED` | Invitation token has already been used (user already accepted). |
| `404 Not Found` | `USER_NOT_FOUND` | User associated with token does not exist. |
| `409 Conflict` | `USER_ALREADY_ACTIVE` | User is already `ACTIVE` (invitation already accepted). |

---

## 12. Tenant Management API (Platform Admin Only)

### 12.1 POST /tenants

Create a new tenant (platform admin only).

- **Method & URL:** `POST /api/v1/tenants`
- **Roles:** Platform Admin only (special role, not tenant-scoped)

**Request Body**

```json
{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "region": "us-east-1",
  "initial_admin_email": "admin@acme.com",
  "initial_admin_display_name": "Admin User",
  "kyc_status": "UNVERIFIED",
  "send_invitation": true
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Tenant organization name. Max 255 characters. Must be unique within environment. |
| `slug` | string | Yes | URL-friendly identifier. Must be unique, lowercase alphanumeric with hyphens. Regex: `^[a-z0-9-]+$`. Must start and end with alphanumeric character. Max 100 characters. |
| `region` | string | No | Data region (e.g., `us-east-1`, `eu-central-1`). Defaults to platform default region. |
| `initial_admin_email` | string | Yes | Email for the initial tenant admin user. |
| `initial_admin_display_name` | string | No | Display name for initial admin. |
| `kyc_status` | string (enum) | No | `UNVERIFIED` (default) or `VERIFIED`. Only `VERIFIED` tenants can publish to marketplace. |
| `send_invitation` | boolean | No | `true` (default) | If `true`, sends invitation email to `initial_admin_email`. If `false`, user is created but invitation must be sent separately. |

**Response (201 Created)**

```json
{
  "tenant": {
    "id": "uuid",
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "status": "ACTIVE",
    "kyc_status": "UNVERIFIED",
    "region": "us-east-1",
    "created_at": "2025-01-15T10:00:00Z"
  },
  "admin_user": {
    "id": "uuid",
    "email": "admin@acme.com",
    "status": "INVITED",
    "invitation_token": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Behavior**

- **Transaction 1** (atomic): Creates tenant record with `status = ACTIVE`, `kyc_status = UNVERIFIED` (unless specified).
- **Transaction 2** (atomic): Creates default roles for the tenant (`TENANT_ADMIN`, `DATA_PROVIDER`, `DATA_CONSUMER`, `AUDITOR`) if they don't exist (idempotent).
- **Transaction 3** (atomic): Creates initial admin user with `status = INVITED` (if `send_invitation = true`) or `status = ACTIVE` (if `send_invitation = false`), and assigns `TENANT_ADMIN` role via `user_roles` join table.
- **Asynchronous**: If `send_invitation = true`, sends invitation email to `initial_admin_email` (within 1 minute). Email failures are logged but do not affect tenant creation.
- Returns `invitation_token` in response (for programmatic invitation handling if `send_invitation = false`).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid name, slug format, or duplicate name/slug. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not a platform admin. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

### 12.2 GET /tenants

List tenants (platform admin only).

- **Method & URL:** `GET /api/v1/tenants?status=ACTIVE&kyc_status=VERIFIED&limit=20&offset=0`
- **Roles:** Platform Admin only

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string (enum) | No | Filter by tenant status: `ACTIVE`, `SUSPENDED`, `DELETED`. |
| `kyc_status` | string (enum) | No | Filter by KYC status: `VERIFIED`, `UNVERIFIED`. |
| `region` | string | No | Filter by region. |
| `limit` | integer | No | Maximum number of results (default: 20, max: 100). |
| `offset` | integer | No | Pagination offset (default: 0). |

**Response**

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Acme Corporation",
      "slug": "acme-corp",
      "status": "ACTIVE",
      "kyc_status": "VERIFIED",
      "region": "us-east-1",
      "created_at": "2025-01-15T10:00:00Z"
    }
  ],
  "total": 50,
  "limit": 20,
  "offset": 0
}
```

---

### 12.3 GET /tenants/{id}

Get a single tenant (platform admin only).

- **Method & URL:** `GET /api/v1/tenants/{id}`
- **Roles:** Platform Admin only

**Response (200 OK)**

Returns complete Tenant JSON (see §2.10 for schema).

---

### 12.4 PATCH /tenants/{id}

Update tenant (platform admin only).

- **Method & URL:** `PATCH /api/v1/tenants/{id}`
- **Roles:** Platform Admin only

**Request Body**

```json
{
  "name": "Updated Name",
  "status": "SUSPENDED",
  "kyc_status": "VERIFIED",
  "region": "eu-central-1"
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Updated tenant name. |
| `status` | string (enum) | No | Tenant status: `ACTIVE`, `SUSPENDED`, `DELETED`. |
| `kyc_status` | string (enum) | No | KYC status: `VERIFIED`, `UNVERIFIED`. |
| `region` | string | No | Data region. |

**Status Transition Rules**

| From Status | To Status | Requirements | Impact |
|-------------|-----------|-------------|--------|
| `ACTIVE` | `SUSPENDED` | No restrictions | Blocks write operations, allows read. |
| `SUSPENDED` | `ACTIVE` | No restrictions | Restores full access. |
| `ACTIVE` | `DELETED` | No restrictions | Initiates soft delete process. |
| `SUSPENDED` | `DELETED` | No restrictions | Initiates soft delete process. |
| `DELETED` | `ACTIVE` | **Not allowed** | Deletion is permanent. |

**KYC Status Impact**

- Setting `kyc_status = VERIFIED`:
  - Allows tenant to publish assets to marketplace.
  - Existing `PUBLISHED` listings remain published.
- Setting `kyc_status = UNVERIFIED`:
  - Automatically unpublishes all `PUBLISHED` listings (`status = UNPUBLISHED`).
  - Prevents new listings from being published.

**Response (200 OK)**

Returns updated Tenant JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `TENANT_NOT_FOUND` | Tenant with given ID does not exist. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid status transition or invalid field values. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not a platform admin. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

## 13. Tenant Configuration API

### 13.1 GET /tenants/{id}/config

Get tenant configuration.

- **Method & URL:** `GET /api/v1/tenants/{id}/config`
- **Roles:** `TENANT_ADMIN` (for own tenant) or Platform Admin (for any tenant)

**Response (200 OK)**

```json
{
  "tenant_id": "uuid",
  "default_dq_profile": "intake_basic_gx",
  "allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA"],
  "default_compliance_regimes": ["GDPR", "LGPD"],
  "data_retention_days": 2555,
  "rate_limits": {
    "dq_runs": {
      "burst_per_10s": 20,
      "sustained_per_min": 60,
      "daily_cap": 10000
    },
    "compliance_runs": {
      "burst_per_10s": 20,
      "sustained_per_min": 60,
      "daily_cap": 10000
    },
    "file_uploads": {
      "burst_per_10s": 10,
      "sustained_per_min": 30
    }
  },
  "max_file_size_bytes": 10737418240,
  "max_job_concurrency": 5,
  "max_queued_jobs": 50,
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

**TenantConfig Schema**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tenant_id` | UUID | Yes | - | Tenant ID (read-only). |
| `default_dq_profile` | string | No | `intake_basic_gx` | Default DQ profile key for intake flows. Must be a valid profile key. |
| `allowed_compliance_regimes` | array of strings | No | `["GDPR", "LGPD", "CCPA", "HIPAA", "SOX"]` | List of compliance regimes available to this tenant. |
| `default_compliance_regimes` | array of strings | No | `["GDPR", "LGPD"]` | Default compliance regimes applied to intake flows. Must be subset of `allowed_compliance_regimes`. |
| `data_retention_days` | integer | No | `2555` (7 years) | Data retention period in days. Applies to audit logs, files, and other tenant data. |
| `rate_limits` | object | No | Platform defaults | Per-endpoint category rate limits. See rate limit structure below. |
| `max_file_size_bytes` | integer | No | `10737418240` (10 GB) | Maximum file size for uploads (global or tenant-specific override). |
| `max_job_concurrency` | integer | No | `5` | Maximum concurrent running jobs for this tenant. |
| `max_queued_jobs` | integer | No | `50` | Maximum queued jobs for this tenant. |
| `created_at` | timestamp | Yes | - | When configuration was created (read-only). |
| `updated_at` | timestamp | Yes | - | When configuration was last updated (read-only). |

**Rate Limit Structure**

```json
{
  "dq_runs": {
    "burst_per_10s": 20,
    "sustained_per_min": 60,
    "daily_cap": 10000
  },
  "compliance_runs": {
    "burst_per_10s": 20,
    "sustained_per_min": 60,
    "daily_cap": 10000
  },
  "file_uploads": {
    "burst_per_10s": 10,
    "sustained_per_min": 30
  },
  "contract_validation": {
    "burst_per_10s": 20,
    "sustained_per_min": 60
  },
  "catalog_reads": {
    "burst_per_10s": 50,
    "sustained_per_min": 200
  }
}
```

---

### 13.2 PATCH /tenants/{id}/config

Update tenant configuration.

- **Method & URL:** `PATCH /api/v1/tenants/{id}/config`
- **Roles:** `TENANT_ADMIN` (for own tenant) or Platform Admin (for any tenant)

**Request Body**

```json
{
  "default_dq_profile": "intake_basic_soda",
  "default_compliance_regimes": ["GDPR", "LGPD", "CCPA"],
  "data_retention_days": 1825,
  "rate_limits": {
    "dq_runs": {
      "daily_cap": 20000
    }
  }
}
```

All fields are optional; only provided fields are updated.

**Validation Rules**

- `default_dq_profile`: Must be a valid profile key (e.g., `intake_basic_gx`, `intake_basic_soda`).
- `allowed_compliance_regimes`: Must be subset of platform-supported regimes: `["GDPR", "LGPD", "CCPA", "HIPAA", "SOX"]`.
- `default_compliance_regimes`: Must be subset of `allowed_compliance_regimes`.
- `data_retention_days`: Must be between 90 and 3650 (3 months to 10 years).
- `rate_limits`: Each category can override platform defaults, but cannot exceed platform maximums.

**Response (200 OK)**

Returns updated TenantConfig JSON.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `TENANT_NOT_FOUND` | Tenant with given ID does not exist. |
| `400 Bad Request` | `VALIDATION_ERROR` | Invalid configuration values (e.g., invalid profile key, invalid regime, retention days out of range). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User is not `TENANT_ADMIN` for this tenant or platform admin. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

---

## 14. Semantic API

### 14.1 GET /context.jsonld

Get the JSON-LD context document.

- **Method & URL:** `GET /context.jsonld`
- **Roles:** None (public endpoint)

**Response (200 OK)**

Returns JSON-LD context document:

```json
{
  "@context": {
    "@version": 1.1,
    "dcat": "http://www.w3.org/ns/dcat#",
    "dct": "http://purl.org/dc/terms/",
    "hub": "https://hub.example.com/ontology#",
    "hub:DataAsset": {
      "@id": "hub:DataAsset",
      "@type": "@id"
    },
    "hub:hasContract": {
      "@id": "hub:hasContract",
      "@type": "@id"
    },
    "hub:hasDataset": {
      "@id": "hub:hasDataset",
      "@type": "@id"
    },
    "dct:title": "http://purl.org/dc/terms/title",
    "dct:description": "http://purl.org/dc/terms/description",
    "dcat:theme": "http://www.w3.org/ns/dcat#theme",
    "dcat:keyword": "http://www.w3.org/ns/dcat#keyword"
  }
}
```

**Response Headers**

- `Content-Type`: `application/ld+json`
- `Cache-Control`: `public, max-age=3600` (1 hour cache)
- `ETag`: Context version hash (for cache validation)

**Versioning**

- Context document is versioned via `@version` field.
- Changes to context are backward-compatible when possible.
- Breaking changes increment the version number.
- Clients should cache the context document and re-fetch periodically.

**Error Responses**

- `200 OK` is always returned (context is always available).

---

### 14.2 JSON-LD Resolution

Resolve URIs to JSON-LD for contracts, assets, datasets.

- `GET /id/contract/{contract_id}`
- `GET /id/asset/{asset_id}`
- `GET /id/dataset/{dataset_id}`

These are **publicly accessible** endpoints (for interoperability), but may omit sensitive internal fields.

Example response (simplified):

```json
{
  "@context": "https://hub.example.com/context.jsonld",
  "@id": "https://hub.example.com/id/asset/uuid",
  "@type": "dcat:Dataset",
  "dct:title": "Customer Orders",
  "dct:description": "Orders data product for analytics.",
  "dcat:theme": ["sales"],
  "dcat:keyword": ["orders", "ecommerce"],
  "dcat:distribution": [
    {
      "@type": "dcat:Distribution",
      "dct:title": "Parquet snapshot",
      "dcat:accessURL": "https://api.hub.example.com/...",
      "odcs:contract": "https://hub.example.com/id/contract/uuid"
    }
  ]
}
```

---

### 14.3 SPARQL Endpoint

For semantic queries (primarily for developers/integrators).

- **Method & URL:** `GET /sparql` or `POST /sparql`
- **Roles:** `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR` (or public if deployment allows)

**GET /sparql**

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | SPARQL query string (URL-encoded). |
| `format` | string | No | Response format: `json` (default), `xml`, `csv`, `tsv`. |
| `default-graph-uri` | string | No | Default graph URI (for multi-graph stores). Can be repeated for multiple graphs. |
| `named-graph-uri` | string | No | Named graph URI. Can be repeated for multiple graphs. |

**POST /sparql**

**Request Body**

```json
{
  "query": "PREFIX dcat: <http://www.w3.org/ns/dcat#> SELECT ?dataset ?title WHERE { ?dataset a dcat:Dataset . ?dataset dct:title ?title }",
  "format": "json",
  "default-graph-uri": ["https://hub.example.com/graph/public"]
}
```

**Request Fields**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | SPARQL query string. |
| `format` | string | No | Response format: `json` (default), `xml`, `csv`, `tsv`. |
| `default-graph-uri` | array of strings | No | Default graph URIs. |
| `named-graph-uri` | array of strings | No | Named graph URIs. |

**Query Restrictions**

- **Read-only**: Only `SELECT` and `CONSTRUCT` queries are allowed (no `INSERT`, `DELETE`, `UPDATE`).
- **Timeout**: Queries are limited to **30 seconds** (configurable via `SPARQL_QUERY_TIMEOUT_SECONDS`).
- **Result size**: Maximum **10,000 results** per query (configurable via `SPARQL_MAX_RESULTS`).
- **Tenant scoping**: Authenticated queries are automatically scoped to the tenant's named graph(s).

**Response (200 OK)**

**JSON Format** (default):

```json
{
  "head": {
    "vars": ["dataset", "title"]
  },
  "results": {
    "bindings": [
      {
        "dataset": {
          "type": "uri",
          "value": "https://hub.example.com/id/asset/uuid"
        },
        "title": {
          "type": "literal",
          "value": "Customer Orders"
        }
      }
    ]
  }
}
```

**XML Format** (`format=xml`):

Returns standard SPARQL XML results format.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `400 Bad Request` | `SPARQL_PARSE_ERROR` | SPARQL query syntax error. |
| `400 Bad Request` | `SPARQL_QUERY_INVALID` | Query contains unsupported operations (e.g., `INSERT`, `DELETE`). |
| `400 Bad Request` | `SPARQL_QUERY_TOO_LARGE` | Query string exceeds maximum length (configurable, default: 10,000 characters). |
| `504 Gateway Timeout` | `SPARQL_QUERY_TIMEOUT` | Query exceeded timeout limit (30 seconds). |
| `413 Payload Too Large` | `SPARQL_RESULT_TOO_LARGE` | Query result exceeds maximum size (10,000 results). |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token (if authentication is required). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role or query attempts to access restricted graphs. |

**Response Headers**

- `Content-Type`: `application/sparql-results+json` (for JSON), `application/sparql-results+xml` (for XML)
- `X-SPARQL-Query-Time`: Query execution time in milliseconds

**Authentication & Authorization**

- **Public queries** (if deployment allows):
  - Only access public named graph (public DCAT/asset metadata).
  - No cross-tenant data exposure.
- **Authenticated queries**:
  - Access tenant-specific named graph(s).
  - Queries are automatically filtered by `tenant_id` from bearer token.
  - Cross-tenant queries are **not allowed** (unless user has platform admin role).

**Rate Limiting**

- Per-tenant limits: 50 requests per 10s (burst), 200 requests per minute (sustained).
- See `Security_Design_and_Threat_Model.md` §5.12.3 for details.

---

## 16. Security & Rate Limiting (API-Level)

- All `/api/v1` endpoints require a valid bearer token, except:
  - `/id/...` JSON-LD endpoints (may be open).
  - `/sparql` may require token depending on deployment.
- Rate limits:
  - Per-tenant and per-user limits on:
    - DQ runs (`/dq-runs`)
    - Compliance runs (`/compliance-runs`)
    - Jobs polling (`/jobs`)
- Sensitive rules:
  - No raw PII/sensitive data in error responses or audit JSON.
  - Download endpoints (detailed in §5.5) must check **Entitlements** before giving access.

---

### 5.6 DELETE /files/{id}

Delete a file.

- **Method & URL:** `DELETE /api/v1/files/{id}`
- **Roles:** `DATA_PROVIDER` or `TENANT_ADMIN`

**Behavior**

- **Physical deletion**:
  - Sets `files.status = DELETED`.
  - **Physical file deletion**: File is marked for deletion in object storage (background cleanup job deletes physical object).
  - **Dataset cascade**: If file is attached to a dataset:
    - Dataset record is **not** automatically deleted.
    - Dataset's `file_id` is set to `NULL` (dataset becomes orphaned).
    - Asset remains but dataset has no file reference.
  - **Audit**: Emits audit event: `FILE_DELETED`.

**Cascade Behavior**

- **Datasets**: Dataset records are **not** deleted, but `datasets.file_id` is set to `NULL`.
- **DQ/Compliance runs**: Run records are **not** deleted (preserved for audit).
- **Jobs**: Job records are **not** deleted (preserved for audit).

**Response**

- `204 No Content` on success.

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `FILE_NOT_FOUND` | File with given ID does not exist or is not visible to tenant. |
| `409 Conflict` | `FILE_IN_USE` | File is attached to a dataset and cannot be deleted (must delete dataset first, or use `force = true`). |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks `DATA_PROVIDER` or `TENANT_ADMIN` role. |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | `false` | If `true`, deletes file even if attached to dataset (orphans the dataset). If `false`, returns error if file is in use. |

---

### 5.5 GET /files/{id}/download

Download a file (requires entitlement for cross-tenant access).

- **Method & URL:** `GET /api/v1/files/{id}/download`
- **Roles:** `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR`

**Authorization**

- **Same-tenant access**: If the file belongs to the requester's tenant (`files.tenant_id = token.tenant_id`):
  - Access is granted if user has appropriate role (`DATA_PROVIDER`, `TENANT_ADMIN`, or `AUDITOR`).
  - No entitlement check required.
- **Cross-tenant access**: If the file belongs to a different tenant:
  - Requires an active `Entitlement` record:
    - `entitlements.tenant_id = <requester_tenant_id>`
    - `entitlements.asset_id = <asset_id>` (where `datasets.file_id = <file_id>`)
    - `entitlements.status = 'ACTIVE'`
    - `entitlements.expires_at IS NULL OR entitlements.expires_at > NOW()`
  - If no active entitlement exists, returns `403 Forbidden` with error code `ENTITLEMENT_REQUIRED`.

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `range` | string | No | HTTP Range header value (e.g., `bytes=0-1023`). Supports partial content downloads. |

**Rate Limiting**

File download endpoints are subject to rate limiting to prevent abuse and ensure fair resource usage:

- **Per-tenant limits** (default):
  - Burst: **20** requests per 10 seconds
  - Sustained: **100** requests per minute
  - Daily cap: **10,000** downloads per day
- **Per-user limits** (within tenant):
  - Burst: **10** requests per 10 seconds (50% of tenant limit)
  - Sustained: **50** requests per minute (50% of tenant limit)
- **Per-API-key limits**:
  - Same as per-user limits (if using API key authentication)
- **Rate limit headers**:
  - `X-RateLimit-Limit`: Maximum requests allowed in the current window
  - `X-RateLimit-Remaining`: Remaining requests in the current window
  - `X-RateLimit-Reset`: Unix timestamp when the rate limit resets
  - `Retry-After`: Seconds to wait before retrying (if rate limit exceeded)
- **Rate limit errors**:
  - Returns `429 Too Many Requests` with error code `RATE_LIMIT_EXCEEDED`
  - Error response includes `retry_after_seconds` in `error.details`
- **Configuration**:
  - Limits can be overridden per tenant via `tenant_config.rate_limits.file_downloads`
  - Enterprise tenants may have higher limits

**Response**

**Success (200 OK or 206 Partial Content)**

- **Response Type**: Redirect to pre-signed download URL (HTTP 302 Found) or direct download (HTTP 200 OK).
- **Implementation**: Backend generates a short-lived pre-signed download URL (expires in 5 minutes) and either:
  - Returns `302 Found` with `Location` header pointing to the pre-signed URL (preferred for large files).
  - Or streams the file directly (for small files or when range requests are used).

**Pre-signed Download URL Details**

- **Expiration**: 5 minutes (300 seconds), shorter than upload URLs to minimize exposure.
- **HTTP Method**: `GET`.
- **Permissions**: `GetObject` permission for the specific object key.
- **Range Requests**: Supported if storage provider supports it (e.g., S3 supports Range requests).

**Response Headers**

- `Content-Type`: From `files.content_type` or inferred from file extension.
- `Content-Length`: File size in bytes (from `files.size_bytes`).
- `Content-Disposition`: `attachment; filename="<original_filename>"` (for downloads) or `inline` (for previews).
- `Accept-Ranges`: `bytes` (if range requests are supported).
- `ETag`: File checksum (from `files.content_sha256` if available).

**Error Responses**

| Status | Error Code | Description |
|--------|------------|-------------|
| `404 Not Found` | `FILE_NOT_FOUND` | File with given ID does not exist or is not visible to tenant. |
| `403 Forbidden` | `ENTITLEMENT_REQUIRED` | Cross-tenant access requires an active entitlement. |
| `403 Forbidden` | `ENTITLEMENT_EXPIRED` | Entitlement exists but has expired. |
| `403 Forbidden` | `AUTH_FORBIDDEN` | User lacks required role to access files. |
| `410 Gone` | `FILE_DELETED` | File has been deleted (`files.status = DELETED`). |
| `416 Range Not Satisfiable` | `RANGE_NOT_SATISFIABLE` | Range request is invalid (e.g., start > file size). |
| `401 Unauthorized` | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |

**Range Request Support**

- If `Range` header is provided:
  - Backend validates the range (start, end, length).
  - Returns `206 Partial Content` with:
    - `Content-Range`: `bytes <start>-<end>/<total>`
    - `Content-Length`: Length of the requested range.
  - Pre-signed URL includes range parameters if redirecting.

**Example Request**

```http
GET /api/v1/files/7c1eaa0f-1234-5678-9abc-def012345678/download
Authorization: Bearer <token>
Range: bytes=0-1023
```

**Example Response (Redirect)**

```http
HTTP/1.1 302 Found
Location: https://storage-provider/presigned-download-url?expires=1234567890&signature=...
Content-Type: application/json

{
  "download_url": "https://storage-provider/presigned-download-url?expires=1234567890&signature=...",
  "expires_at": "2025-01-15T10:20:00Z",
  "file_id": "uuid",
  "size_bytes": 10485760
}
```

**Example Response (Direct Download)**

```http
HTTP/1.1 200 OK
Content-Type: text/csv
Content-Length: 10485760
Content-Disposition: attachment; filename="orders_2025_01.csv"
Accept-Ranges: bytes
ETag: "deadbeef..."

<file content>
```

---

This **API v1 spec** is the contract that SDKs (JS/Python) should implement and that the UI will call for the MVP flows:

- Data-first, contract-first, contract-only onboarding.  
- DQ & compliance as services.  
- Catalog & asset detail views.  
- Marketplace listing, discovery, and access.  
- Semantic discovery and integration.  

Any endpoint/shape changes must be updated here first, then rolled out to the implementation and SDKs.

## 15. GraphQL API (Read-only, MVP)

The platform exposes a **GraphQL endpoint** at `/graphql` (not under `/api/v1`) behind the same public API Gateway that fronts `/api/v1` REST endpoints.

**Endpoint Details**

- **URL**: `POST /graphql` (base URL: `https://api.<hub-domain>/graphql`)
- **Content-Type**: `application/json`
- **Authentication**: Same bearer token as REST API (`Authorization: Bearer <token>`)
  - Supports both JWT tokens and API keys
  - Token must include `tenant_id`, `user_id` (or API key context), and `roles[]`
- **Rate Limiting**: Uses same rate limit buckets as REST catalog endpoints:
  - Per-tenant: 50 requests/10s burst, 200 requests/min sustained
  - Per-user/API-key: Same limits as REST catalog endpoints
- **Error Format**: Standard GraphQL error format with `extensions.code` mapping to API error codes:

**GraphQL Query Complexity Limits**

To prevent resource exhaustion and ensure fair usage, GraphQL queries are subject to complexity limits:

- **Maximum query depth**: **10 levels** (e.g., `query { assets { datasets { files { ... } } } }` is limited to 10 nested levels)
- **Maximum fields per query**: **100 fields** (counted across all selections, including nested fields)
- **Maximum aliases**: **50 aliases** per query
- **Query timeout**: **30 seconds** (configurable via `GRAPHQL_QUERY_TIMEOUT_SECONDS`)
- **Result size limit**: **10,000 items** per list field (e.g., `assets { items { ... } }` returns max 10,000 items)
- **Complexity scoring**: Queries are scored using a complexity algorithm:
  - Base complexity: 1 point per field
  - Nested fields: Complexity multiplies by depth (e.g., depth 2 = 2x, depth 3 = 3x)
  - List fields: Complexity multiplies by estimated result size (capped at 100x)
  - **Maximum complexity score**: **1,000 points** per query
- **Error responses**:
  - If query exceeds complexity limits, returns `400 Bad Request` with error code `GRAPHQL_QUERY_TOO_COMPLEX`
  - Error response includes:
    ```json
    {
      "errors": [
        {
          "message": "Query complexity exceeds maximum allowed (1000). Current complexity: 1250.",
          "extensions": {
            "code": "GRAPHQL_QUERY_TOO_COMPLEX",
            "complexity": 1250,
            "max_complexity": 1000,
            "suggestion": "Reduce query depth or limit result sets using pagination."
          }
        }
      ]
    }
    ```
  - If query exceeds timeout, returns error code `GRAPHQL_QUERY_TIMEOUT`
  - If query exceeds result size limit, returns error code `GRAPHQL_RESULT_TOO_LARGE`

**Rate Limiting**

GraphQL queries are subject to the same rate limiting as REST endpoints (see `Security_Design_and_Threat_Model.md` §5.12.3):
- Per-tenant: Burst 50 requests per 10s, sustained 200 requests per minute
- Rate limits are applied **per query**, not per field resolved
- Rate limit headers are included in GraphQL responses (same format as REST)

- **Error Format**: Standard GraphQL error format with `extensions.code` mapping to API error codes:
  ```json
  {
    "errors": [
      {
        "message": "Asset not found",
        "extensions": {
          "code": "ASSET_NOT_FOUND",
          "http_status": 404,
          "request_id": "req-1234567890"
        }
      }
    ]
  }
  ```

This section defines:

- The MVP **scope / deferral decision** for GraphQL.
- A **minimal schema** for the main read flows.
- **Usage guidelines** relative to REST.
- **AuthN/AuthZ** rules for GraphQL.

### 13.1 Scope and deferral decision

- GraphQL is **in scope for MVP** but **limited to read-only queries** used primarily by the **first-party web UI**.
- For external integrators and SDKs:
  - **REST remains the canonical, fully supported contract** for v1.
  - GraphQL is exposed as **optional / beta** for read use cases; only the queries documented below are considered stable.
- **No GraphQL mutations** are part of v1:
  - All writes (create/update/delete assets, datasets, contracts, jobs, files, etc.) use the REST endpoints described in sections 3–11.
- Advanced GraphQL features (subscriptions, custom directives, schema stitching with external systems, etc.) are **explicitly deferred** to post-MVP.

In short: **GraphQL is a read-only aggregation layer for the UI**, and **REST is the primary public API**.

---

### 13.2 Schema overview (SDL)

The MVP schema is intentionally small and maps directly to existing REST resources.

```graphql
schema {
  query: Query
}

"""
Root read-only entry point.
"""
type Query {
  """
  Current authenticated user (based on bearer token).
  """
  me: User!

  """
  List assets for the current tenant with basic filters.
  Mirrors GET /api/v1/assets.
  """
  assets(
    status: AssetStatus
    domain: String
    search: String
    page: PageInput
  ): AssetConnection!

  """
  Fetch a single asset by ID.
  Mirrors GET /api/v1/assets/{id}.
  """
  asset(id: ID!): Asset

  """
  Datasets for a given asset.
  Mirrors GET /api/v1/assets/{id}/datasets.
  """
  assetDatasets(
    assetId: ID!
    page: PageInput
  ): DatasetConnection!

  """
  Jobs for the current tenant (DQ, compliance, etc.).
  Mirrors GET /api/v1/jobs.
  """
  jobs(
    status: JobStatus
    type: JobType
    page: PageInput
  ): JobConnection!

  """
  Single job by ID.
  Mirrors GET /api/v1/jobs/{id}.
  """
  job(id: ID!): Job
}

"""
Pagination input, similar to limit/offset.
"""
input PageInput {
  limit: Int = 20
  offset: Int = 0
}

"""
Connection wrapper for paginated results.
"""
type AssetConnection {
  items: [Asset!]!
  totalCount: Int!
}

type DatasetConnection {
  items: [Dataset!]!
  totalCount: Int!
}

type JobConnection {
  items: [Job!]!
  totalCount: Int!
}

"""
Simplified user view from the current tenant.
"""
type User {
  id: ID!
  tenantId: ID!
  email: String!
  displayName: String
  roles: [RoleKey!]!
}

enum RoleKey {
  TENANT_ADMIN
  DATA_PROVIDER
  DATA_CONSUMER
  AUDITOR
}

"""
Subset of Asset JSON from section 2.2.
"""
type Asset {
  id: ID!
  tenantId: ID!
  name: String!
  slug: String!
  description: String
  domain: String
  status: AssetStatus!
  primaryContractId: ID
  latestDatasetId: ID
  qualityStatus: QualityStatus!
  complianceStatus: ComplianceStatus!
  semanticStatus: SemanticStatus!
  createdAt: String!
}

enum AssetStatus {
  DRAFT
  ACTIVE
  PUBLIC
  RETIRED
}

enum QualityStatus {
  UNKNOWN
  PASS
  WARN
  FAIL
}

enum ComplianceStatus {
  UNKNOWN
  PASS
  WARN
  FAIL
}

enum SemanticStatus {
  OK
  DEGRADED
}

"""
Subset of Dataset JSON from section 2.3.
"""
type Dataset {
  id: ID!
  assetId: ID!
  version: Int!
  status: String!
  format: String
  rowCount: Int
  createdAt: String!
}

"""
Job view aligned with Jobs API.
"""
type Job {
  id: ID!
  tenantId: ID!
  type: JobType!
  status: JobStatus!
  createdAt: String!
  startedAt: String
  finishedAt: String
  errorCode: String
}

enum JobType {
  DQ_RUN
  COMPLIANCE_RUN
  CONTRACT_VALIDATION
  SEMANTIC_MAPPING
}

enum JobStatus {
  PENDING
  RUNNING
  SUCCEEDED
  FAILED
  CANCELLED
}
Notes:

This schema is non-exhaustive; it exposes the minimum needed for:

Asset list & detail pages.

Dataset and job views in the UI.

Any additional fields/types must be added using normal change control and deprecation rules, not breaking changes.

13.3 GraphQL vs. REST usage guidelines
When to use REST

External integrators must rely on REST for:

Creating/updating/deleting assets, datasets, contracts, listings, files.

Upload flows (/files, chunked upload).

Long-running operations setup (/dq-runs, /compliance-runs, /jobs).

SDKs (JS/Python) should treat REST as the source of truth for all write flows and for any functionality not yet exposed via GraphQL.

When to use GraphQL

The first-party web UI should favor GraphQL for:

Screens that need to join multiple resources (asset + listing + latest DQ/compliance & jobs).

Flexible filtering / search within a tenant where combining several REST calls would be chatty.

External integrators may use the documented GraphQL queries for read flows if they accept:

That only the documented parts of the schema are stable.

That REST remains the compatibility baseline and may be more conservative in its evolution.

General guidance

GraphQL does not replace the REST APIs; it is a read optimization layer over them.

New capabilities must be added to REST first; GraphQL then composes or mirrors them as needed.

Introspection is enabled, but only documented types/fields are considered stable for v1.

### 13.4 GraphQL Resolver Implementation

**Implementation**: GraphQL resolvers are implemented using **Strawberry GraphQL** with `strawberry-django` for Django integration. See `Technology_Stack_Decisions.md` for version and configuration details.

**Resolver Architecture**

GraphQL resolvers are implemented as thin wrappers around REST API service methods:

- **Data fetching**: Resolvers call the same service methods used by REST endpoints
- **Authorization**: Resolvers apply the same authorization checks as REST endpoints
- **Tenant scoping**: All resolvers automatically scope queries to `context.tenant_id`
- **Error handling**: Resolvers map service errors to GraphQL error format

**Resolver Implementation Pattern**

Each resolver follows this pattern using Strawberry GraphQL:

```python
# Example: Asset resolver (Strawberry GraphQL with Django)
import strawberry
from strawberry.django import auth
from typing import Optional

@strawberry.django.type(models.Asset)
class Asset:
    id: strawberry.ID
    name: str
    status: str
    # ... other fields

@strawberry.type
class Query:
    @strawberry.field
    @auth.login_required  # Django authentication
    async def asset(self, info: Info, id: strawberry.ID) -> Optional[Asset]:
        # 1. Extract context (from Django request)
        request = info.context.request
        tenant_id = request.user.tenant_id
        user_id = request.user.id
        roles = [role.name for role in request.user.roles.all()]
        
        # 2. Authorization check
        if not any(role in ['DATA_PROVIDER', 'DATA_CONSUMER', 'TENANT_ADMIN', 'AUDITOR'] for role in roles):
            raise GraphQLError("Unauthorized", extensions={"code": "AUTH_FORBIDDEN"})
        
        # 3. Call service method (same as REST endpoint)
        asset = await asset_service.get_asset_by_id(
            asset_id=id,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        # 4. Handle not found
        if not asset:
            return None  # GraphQL returns null for not found
        
        # 5. Return mapped data (Strawberry auto-maps Django models)
        return asset
```

**N+1 Query Prevention**

To prevent N+1 query problems, resolvers use **DataLoader pattern**:

- **DataLoader**: Batches and caches database queries within a single GraphQL request
- **Implementation**: Using Strawberry GraphQL with `strawberry-django` DataLoader support
- **Library**: `strawberry-django` provides built-in DataLoader utilities
- **Example**:
  ```python
  # Asset resolver with DataLoader (Strawberry GraphQL)
  from strawberry.django import DataLoader
  
  class AssetLoader(DataLoader):
      async def batch_load(self, keys):
          # Batch load all assets in one query
          assets = await models.Asset.objects.filter(id__in=keys).all()
          return [assets.get(id=key) for key in keys]
  
  @strawberry.field
  async def asset(self, info: Info, id: strawberry.ID) -> Optional[Asset]:
      loader = info.context.asset_loader  # DataLoader instance
      return await loader.load(id)  # Batched with other asset loads in same request
  ```
- See `Technology_Stack_Decisions.md` for GraphQL library details.

**Field-Level Authorization**

Some fields require additional authorization checks:

- **Internal fields** (e.g., `dq_runs`, `compliance_runs`):
  - Only visible to `TENANT_ADMIN`, `DATA_PROVIDER`, or `AUDITOR` roles
  - Resolver returns `null` if user lacks required role (does not fail entire query)
- **Sensitive fields** (e.g., `sample_json` with PII):
  - Only visible to authorized users
  - Resolver returns `null` or masked data if user lacks access
- **Cross-tenant fields** (e.g., `provider_tenant_id`):
  - Only visible to platform admins or users with explicit cross-tenant permissions
  - Resolver returns `null` for regular users

**Nested Query Resolution**

For nested queries (e.g., `assets { datasets { files { ... } } }`):

- **Depth limit**: Maximum 10 levels (enforced by complexity analyzer)
- **Authorization**: Each nested level applies authorization checks
- **Performance**: DataLoader batches queries at each level
- **Example**: `assets.datasets.files`:
  1. Resolve `assets` (batched query for all assets)
  2. For each asset, resolve `datasets` (batched query for all datasets)
  3. For each dataset, resolve `files` (batched query for all files)

**Error Handling**

- **Service errors**: Mapped to GraphQL error format:
  ```json
  {
    "errors": [
      {
        "message": "Asset not found",
        "extensions": {
          "code": "ASSET_NOT_FOUND",
          "http_status": 404
        }
      }
    ]
  }
  ```
- **Field errors**: If a field resolver fails:
  - **Non-critical fields**: Field resolves to `null`, query continues
  - **Critical fields**: Entire query fails with error
- **Partial results**: GraphQL may return partial results if some fields fail (per GraphQL spec)

**Caching Strategy**

- **Request-level caching**: DataLoader caches results within a single request
- **No cross-request caching**: Each GraphQL request starts with a fresh cache
- **Future enhancement**: May add Redis-based caching for frequently accessed data

### 13.5 Authentication & authorization for GraphQL
Authentication

GraphQL endpoint: POST /graphql

Body: standard GraphQL JSON ({ "query": "...", "variables": { ... } }).

Auth is identical to REST:

Authorization: Bearer <access-token> header (JWT or opaque token).

Optional API keys may be supported via the same mechanisms as /api/v1.

The gateway extracts:

tenant_id, user_id, and roles from the token.

Populates the GraphQL execution context with this identity.

Authorization

All resolvers enforce the same tenant scoping rules as REST:

Every query is implicitly scoped to context.tenant_id.

Cross-tenant reads are only allowed for MPA / platform-admin roles, and only where explicitly implemented.

Field- and type-level rules:

Some fields or object types may be restricted to certain roles:

e.g., internal compliance or DQ diagnostics only visible to TENANT_ADMIN, DATA_PROVIDER, or AUDITOR.

If a user is not authorized:

Either the field resolves to null, or the entire query fails with a standard error, depending on sensitivity.

GraphQL uses the same rate limiting buckets as REST:

Per-tenant and per-user rate limits applied to /graphql, aligned with /api/v1 thresholds for read-heavy operations.

Security considerations

No raw PII/sensitive sample data should be exposed via GraphQL, consistent with REST rules.

Persisted queries and/or operation whitelisting may be used for the first-party UI to:

Improve cacheability.

Reduce risk from arbitrarily expensive queries.

---

### 13.6 GraphQL Query Examples

#### Example 1: List Assets with Filters

```graphql
query ListAssets($status: AssetStatus, $domain: String) {
  assets(status: $status, domain: $domain, page: { limit: 20, offset: 0 }) {
    items {
      id
      name
      slug
      description
      domain
      status
      qualityStatus
      complianceStatus
      createdAt
    }
    totalCount
  }
}
```

**Variables:**
```json
{
  "status": "ACTIVE",
  "domain": "sales"
}
```

#### Example 2: Get Asset with Datasets

```graphql
query GetAssetWithDatasets($assetId: ID!) {
  asset(id: $assetId) {
    id
    name
    description
    status
    primaryContractId
    latestDatasetId
    qualityStatus
    complianceStatus
  }
  assetDatasets(assetId: $assetId, page: { limit: 10, offset: 0 }) {
    items {
      id
      version
      status
      format
      rowCount
      createdAt
    }
    totalCount
  }
}
```

**Variables:**
```json
{
  "assetId": "uuid-here"
}
```

#### Example 3: Query Jobs with Filters

```graphql
query GetJobs($status: JobStatus, $type: JobType) {
  jobs(status: $status, type: $type, page: { limit: 50, offset: 0 }) {
    items {
      id
      type
      status
      createdAt
      startedAt
      finishedAt
      errorCode
    }
    totalCount
  }
}
```

**Variables:**
```json
{
  "status": "RUNNING",
  "type": "QUALITY_CHECK"
}
```

#### Example 4: Get Current User

```graphql
query GetMe {
  me {
    id
    email
    displayName
    tenantId
    roles
  }
}
```

---

## 17. API versioning & evolution

The platform exposes a versioned REST API under the base path:

```text
/ api / v1 / ...
```

This section defines:

- How versioning works for `/api/v1`.
- The deprecation and removal policy.
- How (and when) the `Accept` header is used.
- Backward-compatibility guarantees and what counts as a breaking change.

### 14.1 Versioning model

**Major version in the URL path**

- The **major API version** is encoded in the URL path:
  - `/api/v1/...`
  - Future major versions will use `/api/v2/...`, `/api/v3/...`, etc.
- `/api/v1` is the **only supported major version** at MVP launch.

**Minor / additive changes**

- Within a major version (e.g., `v1`), we allow **non-breaking, additive** changes:
  - Adding new endpoints.
  - Adding optional request fields.
  - Adding optional response fields.
  - Adding new error codes (that are backward-compatible with existing semantics).
- These changes are documented in the changelog and do **not** change the `/api/v1` path.

**GraphQL alignment**

- The GraphQL endpoint `/graphql` is considered part of the **v1 surface**:
  - It is read-only and maps to the `/api/v1` REST resources.
  - When a new major version of the REST API is introduced, GraphQL will either:
    - add a versioned endpoint (e.g., `/graphql/v2`), or
    - version the schema with standard GraphQL deprecation semantics and clear documentation.

### 14.2 Version negotiation & `Accept` header

**REST**

- REST APIs use **path-based versioning** exclusively for major versions.
- Clients SHOULD send:

  ```http
  Accept: application/json
  ```

- The server may also accept vendor-style media types as aliases, e.g.:

  ```http
  Accept: application/vnd.idh.v1+json
  ```

  but for v1:
  - The **path** (`/api/v1`) is the source of truth for the version.
  - The version inside the media type is **ignored** for negotiation purposes; it must match the path if present.

- If `Accept` does not include a compatible JSON type (`application/json`, `application/*`, or `*/*`), the server may return `406 Not Acceptable`.

**GraphQL**

- GraphQL endpoint uses standard content type:

  ```http
  Content-Type: application/json
  Accept: application/json
  ```

- There is **no header-based API version negotiation** for GraphQL in v1. The schema is tied to the v1 REST API and evolved via:
  - additive fields,
  - deprecation markers,
  - and documented changes.

### 14.3 Backward compatibility guarantees

For `/api/v1`, the platform makes the following guarantees:

**We will NOT:**

- Change HTTP methods (e.g., `POST` → `PUT`) for existing endpoints.
- Change endpoint paths.
- Remove required request parameters or headers.
- Change the type or meaning of required fields in request/response payloads.
- Remove existing success status codes (e.g., turning a `201` into a `200` or `400`).
- Remove endpoints without going through the deprecation process described below.

**We MAY (considered non-breaking):**

- Add **new endpoints**.
- Add **optional** request fields with sensible defaults.
- Add **optional** response fields.
- Add **new error codes** in the existing error envelope.
- Add **new enum values** for some fields **only when documented** as “open-ended”; clients are expected to:
  - Ignore unknown enum values where possible, or
  - Treat them as “OTHER” in UI.

Any change that does not fit into the “non-breaking” bucket is treated as a **breaking change** and must be delivered via a new major version (`/api/v2`).

### 14.4 What counts as a breaking change

Examples of **breaking changes**:

- Removing an endpoint or changing its path.
- Changing an HTTP method (e.g., `POST` → `PATCH`).
- Making a previously optional field **required**.
- Removing a field that clients may reasonably rely on.
- Changing the type of a field (e.g., `string` → `number`, or scalar → object).
- Narrowing validation rules so that previously valid payloads become invalid, without an alternate migration path.
- Changing business semantics in a way that would violate documented behavior (e.g., silently changing what `status = ACTIVE` means).

These **must not** be rolled out under `/api/v1`. Instead:

- Introduce `/api/v2/...` with the new behavior.
- Maintain `/api/v1` according to the deprecation timeline below.

### 14.5 Deprecation timeline & policy

When we need to introduce a new version or remove/change behavior in a way that affects clients:

**Deprecation states**

- **Active**: fully supported; receives bug fixes and new backward-compatible features.
- **Deprecated**: still functional, but:
  - No new features.
  - Only critical bug fixes.
  - A published end-of-support date.
- **Sunset**: endpoint is removed or returns errors.

**Timeline**

- Minimum **6 months notice** between:
  - The first public deprecation announcement and documentation update, and
  - The final removal (sunset) of an endpoint or behavior.
- When introducing `/api/v2`:
  - `/api/v1` remains **supported** for at least **12 months** after `v2` becomes generally available.
  - Within those 12 months:
    - At least the last 6 months are in **Deprecated** state with a clear sunset date.

**Communication channels**

- Deprecations are communicated via:
  - API documentation (mark endpoints/fields as **DEPRECATED**).
  - Release notes / changelog.
  - Optional HTTP headers on deprecated endpoints, e.g.:

    ```http
    Deprecation: true
    Sunset: 2027-01-01T00:00:00Z
    Link: </docs/api/v1/deprecations#endpoint-x>; rel="deprecation"
    ```

Clients are expected to monitor these channels and migrate before the sunset date.

#### 14.5.1 Deprecation Communication Templates

**Email Notification Template** (sent to registered API key owners and tenant admins):

```
Subject: [ACTION REQUIRED] API Endpoint Deprecation Notice: {endpoint_path}

Dear {tenant_name} API User,

We are deprecating the following API endpoint as part of our platform evolution:

Endpoint: {method} {endpoint_path}
Deprecation Date: {deprecation_date}
Sunset Date: {sunset_date}
Reason: {reason}

What you need to do:
1. Review the migration guide: {migration_guide_url}
2. Update your integration to use the new endpoint: {new_endpoint_path}
3. Test your changes in the staging environment
4. Complete migration before {sunset_date}

If you have questions or need assistance, please contact support at {support_email}.

Thank you for your understanding.

-- The Data Interoperability Hub Team
```

**API Documentation Deprecation Notice Template**:

```markdown
## ⚠️ DEPRECATED

**This endpoint is deprecated and will be removed on {sunset_date}.**

**Deprecation Date**: {deprecation_date}  
**Sunset Date**: {sunset_date}  
**Replacement**: {new_endpoint_path}  
**Migration Guide**: {migration_guide_url}

**Reason**: {reason}

**What to do**:
1. Migrate to the new endpoint: {new_endpoint_path}
2. Review the migration guide for breaking changes
3. Update your integration before {sunset_date}

After {sunset_date}, this endpoint will return `410 Gone` with error code `ENDPOINT_DEPRECATED`.
```

**HTTP Response Header Template** (for deprecated endpoints):

```http
Deprecation: true
Sunset: {sunset_date_iso8601}
Link: <{deprecation_docs_url}>; rel="deprecation"
Link: <{migration_guide_url}>; rel="alternate"
X-Deprecation-Reason: {reason}
X-Replacement-Endpoint: {new_endpoint_path}
```

**Changelog Entry Template**:

```markdown
## Deprecation Notice - {date}

### Deprecated: {method} {endpoint_path}

- **Deprecation Date**: {deprecation_date}
- **Sunset Date**: {sunset_date}
- **Replacement**: {new_endpoint_path}
- **Reason**: {reason}
- **Migration Guide**: {migration_guide_url}

**Breaking Changes** (if applicable):
- {breaking_change_1}
- {breaking_change_2}

**Action Required**: Migrate to {new_endpoint_path} before {sunset_date}.
```

**Automated Deprecation Notifications**

- Deprecation notices are automatically sent:
  - **Email**: To all registered API key owners and tenant admins 6 months before sunset.
  - **Reminder**: 3 months before sunset.
  - **Final warning**: 1 month before sunset.
- Notifications include:
  - Deprecated endpoint details.
  - Replacement endpoint information.
  - Migration guide link.
  - Support contact information.
- Notifications are tracked:
  - Platform tracks which tenants have acknowledged deprecation notices.
  - Follow-up notifications are sent to tenants that haven't migrated.

### 14.6 Coexistence of multiple versions

When a new major version (e.g., `/api/v2`) is introduced:

- `/api/v1` and `/api/v2` may run in parallel for a period of time.
- They are treated as **independent surfaces**:
  - Tokens and auth rules are shared.
  - Rate limits may be separate per version (implementation detail), but the **documented limits** apply per tenant across all versions overall.
- New functionality is typically added only to the latest major version:
  - `/api/v1` receives bug fixes and security patches.
  - `/api/v2` receives both fixes and new features.

### 14.7 GraphQL & versioning

- For v1, GraphQL is **read-only** and aligned with `/api/v1` semantics.
- GraphQL schema evolution follows standard GraphQL best practices:
  - Additive fields and types are allowed.
  - Fields can be marked `@deprecated(reason: "…")`.
  - Deprecated fields remain available for at least **12 months** from deprecation announcement before removal.
- When a new major REST version is introduced:
  - Either a new GraphQL endpoint (e.g., `/graphql/v2`) is provided, or
  - The existing schema is versioned and clearly documented with migration paths.

Together, these rules ensure:

- `/api/v1` is stable and safe to integrate with.
- Breaking changes are introduced only with new major versions.
- Deprecations come with **clear timelines** and **at least 6 months notice**.
- Both REST and GraphQL surfaces share consistent expectations about evolution and support.
