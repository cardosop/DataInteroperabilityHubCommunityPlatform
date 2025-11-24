# Security Design and Threat Model

This document describes the **security and privacy design** for the Interoperable Data Hub MVP and provides a high‑level **threat model**.

It is intended for:

- Architects and engineers implementing backend, frontend, and infrastructure.
- Security and privacy stakeholders reviewing the platform.
- Future evolution of security controls as the product grows.

It is aligned with:

- `SystemRequirements.md`
- `Domain_Model.md`
- `API_Spec_v1.md`
- `UX_MVP_Flows.md`

---

## 1. Scope & Assumptions

### 1.1 In Scope (MVP)

- All `/api/v1` HTTP APIs.
- Web UI for:
  - Asset onboarding (data-first, contract-first, contract-only).
  - Data Quality (DQ) and Compliance runs and reports.
  - Marketplace browse and access.
  - Audit log views.
- Backend services:
  - API Gateway / Web app.
  - Core service (Assets, Contracts, Datasets, Jobs).
  - DQ service (Great Expectations / Soda).
  - Compliance service.
  - File intake / storage abstraction.
  - Semantic layer (RDF/JSON-LD and SPARQL).
- Datastores:
  - Primary application database.
  - Object storage for data files.
  - Audit log store.
  - Semantic store / triple store.

### 1.2 Out of Scope (for MVP, but relevant later)

- Detailed KYC / identity verification for marketplace participants.
- Full billing/payment processing security (PCI-DSS etc.).
- Hardware-level security (HSMs, host OS hardening specifics).
- Very large-scale multi-region DR strategy.

### 1.3 Threat Model Assumptions

- The platform runs in a **major cloud provider** (e.g., AWS, GCP, Azure).
- Network segments and security groups are available to restrict access.
- TLS termination is under our control (no insecure middleboxes we don’t configure).
- Users are authenticated via a central IdP or managed identity system (to be detailed in a separate IAM design).

---

## 2. Security Objectives

1. **Tenant Isolation**  
   Ensure that one tenant’s data (metadata, contracts, datasets, marketplace info) cannot be accessed by another tenant, except for intentionally public marketplace metadata and semantic identifiers.

2. **Protection of Sensitive Data**  
   - Enforce **encryption in transit** and **encryption at rest** for all data stores and object storage.
   - Avoid storing raw personal data where not necessary (e.g., in logs, semantic layer).

3. **Compliance-Focused Intake**  
   - Do not persist non-compliant data:  
     If Compliance checks indicate `allowed_to_store = false`, the data file is not persisted as a dataset, and any temporary storage is promptly deleted.
   - In case of internal errors or timeouts, **fail closed**:
     - Default: do **not** persist data (conservative behavior).

4. **Auditability**  
   - Maintain an immutable, tenant-scoped audit trail for key actions for at least 3 years.
   - Provide filtering and export to support internal / external audits.

5. **API & Marketplace Safety**  
   - Prevent unauthorized access to APIs and internal resources.
   - Ensure that marketplace access is tied to entitlements and does not leak data to non-entitled parties.

6. **Least Privilege & Defense in Depth**  
   - Isolate services with minimal permissions.
   - Apply multiple layers of controls (auth, authorization, network, data-level checks).

---

## 3. Assets & Data Classification

### 3.1 Primary Asset Types

- **Contracts & HubContract JSON**  
  - May contain schema, descriptions, legal and operational metadata, but **should not contain raw data**.
  - Classification: **Confidential (tenant)**.

- **Data Files / Datasets**  
  - May contain PII/PHI or other regulated data.
  - Classification: **Highly sensitive**; subject to regulatory controls per tenant (GDPR, LGPD, etc.).

- **Audit Logs**  
  - Must record events but **must not store raw PII**.
  - Classification: **Confidential**.

- **DQ & Compliance Results**  
  - Derived metrics and classifications; may indicate presence of PII but not store raw values.
  - Classification: **Confidential**, but less sensitive than raw data.

- **Semantic / RDF representations**  
  - Mostly structural and descriptive metadata; may reference domains, categories, and high-level legal constraints.
  - Classification: **Mixed**:
    - Public URIs and basic DCAT-like descriptors may be **Public**.
    - Detailed internal metadata is **Confidential**.

- **Marketplace listings & orders**  
  - Listing metadata is often semi-public (title, description, quality & compliance badges).
  - Order and entitlement details are **Confidential (consumer + provider tenants)**.

### 3.2 Classification Principles

- Raw data (rows from datasets) is always treated as **most sensitive** and is never logged in plaintext.
- Logs, audit events, and semantic graphs only include:
  - Derived statistics.
  - Non-reversible identifiers (IDs, hashes, pseudonyms).
  - High-level categories (e.g., "contains email addresses") instead of actual values.

---

## 4. Trust Model & Actors

### 4.1 Actors

- **Tenant Users**
  - Data Product Owner / Data Engineer / Data Consumer / Auditor / Tenant Admin.
  - Trusted only within the scope of their tenant and assigned roles.
- **Platform Admins**
  - Operate management plane.
  - Must be carefully controlled and audited.
- **External Buyers**
  - May be users of other tenants or external organizations.
- **Attacker Types**
  - Malicious tenant user (insider).
  - Compromised account (stolen credentials).
  - External attacker without valid credentials.
  - Supply-chain attacker abusing third-party components (DataContract CLI, GX, Soda, etc.).

### 4.2 Trust Boundaries

- Between **public internet** and **API gateway / frontend**.
- Between **API gateway** and internal microservices.
- Between services and **datastores** (DB, object store, semantic store).
- Between **marketplace** and core asset/datastore APIs.

---

## 5. Security Controls by Layer

### 5.1 Identity & Access Management

- All `/api/v1` endpoints require **Bearer token authentication** (except limited public semantic endpoints).
- Tokens carry:
  - `tenant_id`
  - `user_id`
  - `roles[]`
- Authorization checks:
  - Every tenant-scoped resource (Asset, Contract, Dataset, DQRun, ComplianceRun, Job, AuditEvent, Entitlement) includes a `tenant_id`.
  - All queries include `WHERE tenant_id = <token.tenant_id>` filters.
  - For cross-tenant marketplace views, only **published listing metadata** is readable.

Role-level restrictions (examples):

- `DATA_PROVIDER`
  - Create/edit Assets, Contracts, trigger DQ/Compliance for their tenant.
- `DATA_CONSUMER`
  - Read Marketplace, request access, read only entitlements & assets they are entitled to.
- `AUDITOR`
  - Read DQ/Compliance results, AuditEvents for their tenant.
- `TENANT_ADMIN`
  - Configure tenant defaults, manage users (not fully detailed here).

### 5.2 Tenant Isolation & Multi-Tenancy

- Logical isolation:
  - All tenant-specific tables contain a `tenant_id` column.
  - Every query uses `tenant_id` from the token as part of the filter.
- Optional physical isolation (future):
  - Some high-value tenants might use dedicated databases or schemas.
- Backups & exports:
  - Must preserve `tenant_id` and not mix data in cross-tenant operations without explicit design.

### 5.3 Data Protection – In Transit

- All external traffic:
  - HTTPS (TLS 1.2+ or higher).
  - HSTS enabled on the main domain.
- Internal service-to-service communication:
  - Encrypted (e.g., TLS or secure service mesh).
- No support for unencrypted HTTP outside of controlled local dev environments.

#### 5.3.1 Service-to-Service Authentication

Internal services authenticate to each other using one of the following mechanisms, depending on deployment architecture:

**Option A: Service Mesh with mTLS (Recommended for Production)**

- **Mechanism**: Mutual TLS (mTLS) via service mesh (e.g., Istio, Linkerd, Consul Connect).
- **Implementation**:
  - Each service has a unique certificate issued by the mesh's certificate authority (CA).
  - Certificates are automatically rotated by the mesh.
  - Services authenticate using their service identity (e.g., `api-service`, `dq-service`).
- **Authorization**: Service mesh policies control which services can call which endpoints.
- **Benefits**: Automatic certificate management, transparent encryption, fine-grained access control.

**Option B: Internal API Keys (Alternative for MVP)**

- **Mechanism**: Service-specific API keys stored as secrets (e.g., Kubernetes secrets, environment variables).
- **Implementation**:
  - Each service has a unique internal API key (format: `svc_<service-name>_<random-32-chars>`).
  - Keys are stored in secure secret management (e.g., Kubernetes secrets, HashiCorp Vault).
  - Services include the key in `Authorization: Bearer <internal-api-key>` header for internal calls.
- **Authorization**: Service identity is derived from the API key; access control via service registry or configuration.
- **Benefits**: Simpler setup for MVP, no mesh infrastructure required.

**Option C: JWT Service Tokens (Alternative)**

- **Mechanism**: Short-lived JWT tokens issued by `auth-service` for service-to-service calls.
- **Implementation**:
  - Services request tokens from `auth-service` using service credentials.
  - Tokens include `service_name`, `tenant_id` (if applicable), and expiration (default: 1 hour).
  - Tokens are included in `Authorization: Bearer <jwt>` header.
- **Authorization**: Token claims include service identity and scopes.
- **Benefits**: Centralized token management, audit trail of service calls.

**MVP Recommendation**

- For **MVP**: Use **Option B (Internal API Keys)** for simplicity.
- For **Production**: Migrate to **Option A (Service Mesh with mTLS)** for enhanced security and automatic certificate management.

**Implementation Details**

- **Service Identity**: Each service is identified by its deployment identifier (e.g., `api-service`, `dq-service`, `compliance-service`).
- **Secret Storage**: Internal API keys are stored in:
  - Kubernetes: `Secret` resources with type `Opaque`.
  - Docker Compose: Environment variables in `.env` files (not committed to version control).
- **Key Rotation**: Internal API keys are rotated:
  - Manually during security reviews (quarterly minimum).
  - Automatically if compromised (immediate revocation and re-issue).
- **Access Control**: Services can only call endpoints they are authorized for:
  - Defined in service registry or configuration files.
  - Enforced at API gateway or service level.

### 5.4 Data Protection – At Rest

- All databases and object storage buckets:
  - Encrypted at rest using cloud-native encryption (e.g., KMS-managed keys).
- Separate keys for:
  - Application DB.
  - Object storage for data files.
  - Semantic store (if separate).
  - Audit log store (optionally).

### 5.5 PII Handling & Logs

- **No PII in logs**:
  - Application, service, and audit logs must not record:
    - Raw values for emails, phone numbers, credit card numbers, IDs.
  - Instead, store:
    - Column names.
    - Categories detected (e.g., PII_EMAIL).
    - Counts / percentages.
- Request/Response logging:
  - Avoid logging full request bodies for endpoints handling data files or sample data.
  - Editable allowlists for which fields are safe to log (e.g., asset name, domain, status).
- DQ/Compliance reports:
  - Only derived metrics and classification results, not raw cell values.

### 5.6 Compliance Service – Storage & Failure Modes

- **Internal (intake) mode:**
  - Data is temporarily read for analysis.
  - If `allowed_to_store = true`:
    - ComplianceRun and Dataset are persisted.
  - If `allowed_to_store = false`:
    - Fail the intake.
    - Temporarily stored data is deleted as soon as processing completes.
- **External (scan-only) mode:**
  - Data is only stored in **ephemeral** storage (e.g., short-lived object with TTL).
  - Once checks complete:
    - Only ComplianceRun & derived results persist.
    - Raw file is deleted (or EOL’d) as soon as possible.
- **Error handling:**
  - If compliance service fails unexpectedly (timeout, crash):
    - The platform treats this as `allowed_to_store = false` (fail-closed).
    - Inform the user that “Compliance check failed; data was not persisted.”

### 5.7 DQ Service – Data Handling

- DQ service uses **read-only** access to the data file/table in object storage.
- Only aggregated metrics and test results are persisted (DQRun, checks JSON).
- No raw data values should be persisted in DQ-specific tables; sample data for UI should be:
  - Minimal.
  - Masked/anonymized if potentially sensitive.

### 5.8 File Upload & Intake Security

- Uploads use **pre-signed URLs** for direct-to-storage uploads.
- Validation:
  - File type and size checked against safe limits (configurable per tenant / globally).
  - Malicious files (e.g., extremely large, wrong content-type) are rejected at intake.
- After `/files/{id}/complete`:
  - Schema inference, DQ, and Compliance jobs run in an isolated environment.
- No direct execution of uploaded content.
- Virus/malware scanning: future enhancement.

### 5.9 Marketplace & Entitlements

- Marketplace listing pages:
  - Only show **metadata** and aggregated metrics.
  - Never expose full data, sample rows, or schema-level details that could leak proprietary secrets without permission.
- Download/API access:
  - Always check entitlements:
    - `Entitlement.status = ACTIVE`.
    - Consumer's tenant matches `Entitlement.tenant_id`.
- Order & entitlement changes are logged in AuditEvents.

**Entitlement Checking Implementation**

Entitlement checks are implemented as **middleware** in the API gateway (`api-service`), not as a dedicated endpoint. The middleware:

1. **Intercepts data access requests**:
   - Endpoints: `GET /files/{id}/download`, `GET /datasets/{id}/data`, any endpoint that accesses cross-tenant data.
   - Extracts `tenant_id` from bearer token and `asset_id` from request.

2. **Performs entitlement lookup**:
   - Same-tenant: No entitlement check (fast path).
   - Cross-tenant: Queries `entitlements` table for active entitlement matching `(consumer_tenant_id, asset_id)`.

3. **Returns appropriate error codes**:
   - `ENTITLEMENT_REQUIRED`: No entitlement exists.
   - `ENTITLEMENT_EXPIRED`: Entitlement expired.
   - `ENTITLEMENT_REVOKED`: Entitlement revoked.

4. **Caches results** (5-minute TTL) for performance.

See `SystemRequrements.md` §9.5.3 for detailed flow and query specifications.

### 5.10 Semantic Layer & SPARQL

- Semantic graph contains:
  - Structural & descriptive metadata.
  - References to contracts and assets via URIs.
- To avoid leaking sensitive data:
  - URIs and RDF describe **structure and classification**, not actual values.
  - PII/PHI fields are indicated only by type/category, not raw examples.
- SPARQL endpoint:
  - Read-only.
  - Rate-limited.
  - For public queries: only public DCAT/asset metadata.
  - For authenticated queries: tenant-specific views / controlled exposure.

### 5.11 JWT token structure and validation

The platform uses **JWT access tokens** for authenticating API and GraphQL calls, plus **longer-lived refresh tokens** for session continuity.

This section defines:

- JWT claim set (standard vs custom).
- Access vs refresh token lifetimes.
- Token refresh endpoint.
- Revocation strategy.
- Key management and rotation.

#### 5.11.1 Token types

We distinguish two token types:

1. **Access tokens (JWT)**
   - Format: signed JWT (`RS256` or `ES256`) with standard + custom claims.
   - Audience: `/api/v1` REST endpoints and `/graphql`.
   - Delivered to clients:
     - As a bearer token: `Authorization: Bearer <access_jwt>`.
   - Lifetime: **short** (default: 15 minutes).

2. **Refresh tokens (opaque or JWT-with-jti)**
   - Format: opaque random string **or** JWT containing a unique `jti`.
   - Never used as `Authorization` bearer tokens.
   - Stored by clients:
     - Prefer **HTTP-only, secure cookies** for browser-based flows.
   - Tracked server-side in a DB table for revocation.
   - Lifetime: **longer** (default: 7–30 days; configurable, e.g. 14 days).

Only **access tokens** are accepted by `/api/v1` and `/graphql`.

---

#### 5.11.2 JWT claims structure

Access tokens carry a minimal, multi-tenant-aware claim set.

**Standard claims (registered)**

```json
{
  "iss": "https://auth.idh.example.com",  // issuer
  "sub": "user-uuid",                     // user id
  "aud": ["idh-api-v1"],                  // audiences
  "exp": 1710000000,                      // expiry (seconds since epoch)
  "iat": 1709996400,                      // issued at
  "nbf": 1709996400,                      // not before
  "jti": "uuid-or-random-token-id"        // token id
}
```

- `iss` – fixed per environment (dev/stg/prod).
- `aud` – at minimum includes `"idh-api-v1"`; used to distinguish tokens for this API from others.
- `jti` – globally unique per token; used for security auditing and emergency revocation.

**Custom claims**

```json
{
  "tenant_id": "tenant-uuid",
  "tenant_slug": "acme-corp",        // optional, convenience
  "roles": ["TENANT_ADMIN", "DATA_PROVIDER"],
  "email": "user@example.com",
  "name": "Jane Doe",
  "scopes": ["assets:read", "assets:write", "jobs:read"],
  "authz_version": 3
}
```

- `tenant_id` (required)
  - Used for multi-tenant scoping. All access is implicitly restricted to this tenant unless the caller is a platform admin.
- `roles` (required)
  - Array of high-level role keys (e.g. `TENANT_ADMIN`, `DATA_PROVIDER`, `DATA_CONSUMER`, `AUDITOR`).
  - Used for coarse-grained authorization.
- `scopes` (optional but recommended)
  - Fine-grained permissions (e.g. `assets:read`, `jobs:read`, `jobs:cancel`).
  - Enables least-privilege API tokens beyond simple roles.
- `authz_version` (optional)
  - Bumped when a tenant’s or user’s permissions model changes.
  - Can be used to invalidate older tokens after major role or policy changes.

**PII minimization**

- Only non-sensitive identifiers (user id, email, display name) are allowed in tokens.
- No raw PII (e.g. government IDs, phone numbers, addresses) is placed in JWT claims.

---

#### 5.11.3 Token expiration & lifetime

**Access tokens**

- Default lifetime: **15 minutes** (`ACCESS_TOKEN_TTL = 900s`).
- Hard limit: they are considered invalid after `exp` regardless of any server-side changes.
- Short lifetime + key rotation provides a primary revocation mechanism.

**Refresh tokens**

- Default lifetime: **14 days** (`REFRESH_TOKEN_TTL = 14d`), configurable (7–30 days).
- Stored and tracked in DB with:
  - `id` (refresh token id / jti)
  - `user_id`, `tenant_id`
  - `issued_at`, `expires_at`
  - `revoked_at`, `revoked_reason`
  - `client_id` / device info (optional, for per-device sessions)

Refresh tokens can be rotated on each use (“**refresh token rotation**”):

- On successful refresh:
  - Old refresh token is marked `revoked`.
  - A new refresh token is issued and persisted.
- This limits damage if a refresh token is exfiltrated.

---

#### 5.11.4 Token refresh endpoint

Refresh is handled via a dedicated endpoint (see API_Spec_v1).

**Endpoint**

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "<opaque-token-or-jwt>"
}
```

**Behavior**

1. Validate refresh token:
   - Exists in DB and belongs to the current tenant/user (derived from the token or cookie).
   - Not expired (`now < expires_at`).
   - Not revoked (`revoked_at IS NULL`).
2. Optionally check **device/client binding** (e.g. user agent / fingerprint).
3. If valid:
   - Issue a new access token **and** a new refresh token.
   - Persist new refresh token row; mark old one as `revoked` with `revoked_reason = "ROTATED"`.
4. If invalid:
   - Return `401 Unauthorized` or `400 Bad Request` with appropriate error code:
     - `refresh_token_expired`
     - `refresh_token_revoked`
     - `refresh_token_invalid`

#### 5.11.4.1 Refresh Token Rotation Failure Handling

**Transaction Atomicity**

Refresh token rotation is performed in a **single database transaction** to ensure atomicity:

1. **Begin transaction**
2. **Validate old refresh token** (exists, not expired, not revoked)
3. **Create new refresh token record** (insert into `refresh_tokens` table)
4. **Revoke old refresh token** (update `refresh_tokens.revoked_at = NOW()`, `revoked_reason = "ROTATED"`)
5. **Generate new access token** (JWT)
6. **Generate new refresh token** (opaque token)
7. **Commit transaction**

**Failure Scenarios**

**Scenario 1: New Refresh Token Creation Fails**

- **Failure point**: Step 3 (insert new refresh token record fails)
- **Behavior**:
  - Transaction is rolled back automatically
  - Old refresh token remains **active** (not revoked)
  - No new tokens are issued
  - **Error response**: `500 Internal Server Error` with error code `INTERNAL_ERROR`
  - **Client action**: Client can retry the refresh request (idempotent operation)
- **Recovery**: System retries automatically (up to 3 times with exponential backoff)

**Scenario 2: Old Token Revocation Fails**

- **Failure point**: Step 4 (update old refresh token fails)
- **Behavior**:
  - Transaction is rolled back automatically
  - Old refresh token remains **active** (not revoked)
  - New refresh token is **not created**
  - **Error response**: `500 Internal Server Error` with error code `INTERNAL_ERROR`
  - **Client action**: Client can retry the refresh request
- **Recovery**: System retries automatically (up to 3 times with exponential backoff)

**Scenario 3: Token Generation Fails**

- **Failure point**: Step 5 or 6 (JWT or opaque token generation fails)
- **Behavior**:
  - Transaction is rolled back automatically
  - Old refresh token remains **active**
  - New tokens are **not issued**
  - **Error response**: `500 Internal Server Error` with error code `INTERNAL_ERROR`
  - **Client action**: Client can retry the refresh request
- **Recovery**: System retries automatically (up to 3 times with exponential backoff)

**Scenario 4: Partial Transaction Failure (Database Error)**

- **Failure point**: Any step after transaction begins
- **Behavior**:
  - Database transaction is rolled back automatically (ACID guarantee)
  - Old refresh token remains **active** (no state change)
  - No partial state is persisted
  - **Error response**: `500 Internal Server Error` with error code `INTERNAL_ERROR`
  - **Client action**: Client can retry the refresh request

**Idempotency Guarantees**

- **Retry safety**: Refresh token rotation is **idempotent**:
  - If client retries after a failure, the same old refresh token is used
  - Old token remains valid until rotation succeeds
  - Multiple retry attempts do not create duplicate refresh tokens
- **Concurrent refresh prevention**: 
  - Database-level locking prevents concurrent refresh attempts for the same token
  - If two refresh requests arrive simultaneously:
    - First request proceeds normally
    - Second request waits for first to complete
    - Second request sees old token as revoked and returns `REFRESH_TOKEN_REVOKED`

**Error Response Details**

When refresh token rotation fails, the error response includes:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Token refresh failed due to internal error. Please retry.",
    "http_status": 500,
    "details": {
      "failure_step": "refresh_token_creation",
      "retry_recommended": true,
      "retry_after_seconds": 1
    }
  }
}
```

**Monitoring and Alerting**

- **Metrics**:
  - `refresh_token_rotation_failures_total` (counter): Number of failed rotation attempts
  - `refresh_token_rotation_duration_seconds` (histogram): Time taken for rotation
  - `refresh_token_rotation_retries_total` (counter): Number of retry attempts
- **Alerts**:
  - **Warning**: Rotation failure rate > 1% over 5 minutes
  - **Critical**: Rotation failure rate > 5% over 5 minutes
  - **Critical**: Consecutive rotation failures > 10

**Client Retry Strategy**

- **Automatic retry**: SDKs should retry failed refresh requests automatically:
  - **Max retries**: 3 attempts
  - **Backoff**: Exponential backoff (1s, 2s, 4s)
  - **Timeout**: 30 seconds total (including retries)
- **After max retries**: SDK should prompt user to re-authenticate (login again)

**Response**

```json
{
  "access_token": "<jwt>",
  "expires_in": 900,
  "refresh_token": "<new-refresh-token>",
  "token_type": "Bearer"
}
```

Browser-based flows should prefer storing the refresh token in an **HTTP-only, Secure, SameSite cookie** and omit it from the JSON body, but the wire contract remains as above.

---

#### 5.11.5 Token revocation strategy

JWT access tokens are **stateless**, so we rely on:

1. **Short access token lifetime**.
2. **Server-tracked refresh tokens**.
3. Optional **blocklists** for high-risk scenarios.

**Access token revocation**

- Primary mechanism: let short-lived access tokens **expire naturally**.
- For high-risk events (compromise, account closure) we support:

  1. **User-level token versioning**
     - Store `token_version` on the user row.
     - Include the current `authz_version` / `token_version` in the JWT.
     - On login/logout or password reset, bump `token_version`.
     - Validation rejects any token whose `authz_version` or `token_version` is **less** than the current value.

  2. **Optional access-token blocklist**
     - For emergency revocation, `jti` values can be placed into a short-lived in-memory/Redis blocklist.
     - Validation checks `jti` against this list for a configured window (e.g. remaining TTL + small buffer).

**Refresh token revocation**

- Controlled fully via DB:

  - On logout:
    - Mark the user’s refresh token(s) `revoked_at = now()` and `revoked_reason = "LOGOUT"`.
  - On password reset or role change:
    - Optionally revoke all refresh tokens for the user/tenant.
  - On security incident:
    - Revoke all refresh tokens for the affected users and/or tenant.

- Once revoked, a refresh token **cannot** be used to obtain new access tokens.

**Revocation events & audit**

- Every explicit revocation (logout, admin revoke, incident response) writes an audit event:
  - `auth.token_revoked` with `tenant_id`, `user_id`, `reason`, `initiated_by`.

---

#### 5.11.6 Key management & rotation

Access tokens are signed with asymmetric keys (recommended: `RS256` or `ES256`).

**Key storage**

- Private keys:
  - Stored in a secure secrets manager (e.g., KMS/HSM integrated).
  - Never checked into code or config.
- Public keys:
  - Exposed via a JWKS endpoint, e.g.:
    - `GET /.well-known/jwks.json`
  - Used by API gateway and services to verify token signatures.

**Key IDs (`kid`)**

- Each token header includes:

  ```json
  {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-identifier-uuid"
  }
  ```

- `kid` identifies the signing key; verification looks up the right public key.

**Rotation schedule**

- Regular rotation:
  - Generate a new keypair every **90 days** (configurable).
  - Add new public key to JWKS.
  - Start issuing tokens with the new `kid`.
  - Keep old keys in JWKS until **all tokens** signed with them have expired (access + a small buffer).
- Emergency rotation:
  - Immediately mark a key as compromised.
  - Stop using it for signing.
  - Optionally:
    - Remove it from JWKS (forces all tokens with that `kid` to fail verification), **or**
    - Keep it for a grace period but block associated `jti` values via a blocklist.

**Verification in services**

For each incoming request:

1. Extract bearer token from `Authorization` header.
2. Decode header and payload **without trusting** the content yet.
3. Fetch public key by `kid` from JWKS (prefer cached, respect TTL).
4. Verify:
   - Signature (using `alg` and public key).
   - `iss` matches expected issuer.
   - `aud` contains required audience (e.g. `idh-api-v1`).
   - `exp` and `nbf` (no clock skew beyond configured tolerance, e.g. ±60s).
   - Optional: check `jti` against blocklist (if enabled) and `token_version` / `authz_version`.
5. Attach `tenant_id`, `user_id`, `roles`, and `scopes` from claims to the request context for downstream authorization.

This scheme provides:

- A precise, documented JWT structure.
- Short-lived, stateless access tokens plus controlled refresh tokens.
- Clear refresh and revocation flows.
- Robust key rotation with JWKS and `kid`-based lookup.

#### 5.11.7 Invitation Tokens

Invitation tokens are used to invite new users to join a tenant and set up their account. They are single-use, time-limited tokens that allow users to accept invitations and set their passwords.

**Invitation Token Format**

Invitation tokens follow a simple, secure format:
- **Format**: UUID v4 (36 characters including hyphens)
- **Example**: `550e8400-e29b-41d4-a716-446655440000`
- **Total length**: 36 characters
- **Character set**: Hexadecimal (0-9, a-f) with hyphens in standard UUID format

**Rationale for UUID v4**:
- Cryptographically secure (random generation)
- Globally unique (extremely low collision probability)
- URL-safe (no special encoding needed)
- Simple to implement and validate
- Standard format that's easy to work with in databases and APIs

**Invitation Token Storage**

Invitation tokens are stored in the `users` table with the following fields:
- `invitation_token` (UUID, nullable): The invitation token value
- `invitation_token_expires_at` (timestamp, nullable): Token expiration time (default: 7 days from creation, configurable via `INVITATION_TOKEN_TTL_DAYS`)
- `invitation_token_used_at` (timestamp, nullable): Timestamp when token was used (null until accepted)

**Invitation Token Lifecycle**

1. **Generation**: When a user is created with `status = INVITED`:
   - Generate a new UUID v4 token
   - Store token in `users.invitation_token`
   - Set `invitation_token_expires_at = NOW() + 7 days` (configurable)
   - Send invitation email with token embedded in acceptance URL

2. **Validation**: When user accepts invitation (`POST /auth/accept-invitation`):
   - Check token exists and matches `users.invitation_token`
   - Verify `invitation_token_expires_at > NOW()`
   - Verify `invitation_token_used_at IS NULL` (not already used)
   - Verify `users.status = 'INVITED'`

3. **Usage**: After successful acceptance:
   - Set `invitation_token_used_at = NOW()`
   - Clear `invitation_token` (set to NULL) for security
   - Update `users.status = 'ACTIVE'`

**Security Properties**

- **Single-use**: Token is invalidated immediately after acceptance
- **Time-limited**: Default 7-day expiration (configurable)
- **Cryptographically secure**: UUID v4 uses secure random number generation
- **No plaintext storage**: Token is stored directly (not hashed) but cleared after use
- **Audit trail**: Token usage is tracked via `invitation_token_used_at` timestamp

**Configuration**

- `INVITATION_TOKEN_TTL_DAYS` (default: 7): Number of days before invitation token expires
- Environment variable: `INVITATION_TOKEN_TTL_DAYS=7`

**Error Codes**

- `INVITATION_TOKEN_INVALID`: Token format is invalid (not a valid UUID)
- `INVITATION_TOKEN_EXPIRED`: Token has expired (`invitation_token_expires_at < NOW()`)
- `INVITATION_TOKEN_USED`: Token has already been used (`invitation_token_used_at IS NOT NULL`)

---

#### 5.11.8 Password Reset Tokens

Password reset tokens are used to allow users to reset forgotten passwords. They follow the same format and security properties as invitation tokens.

**Password Reset Token Format**

- **Format**: UUID v4 (36 characters including hyphens)
- **Example**: `550e8400-e29b-41d4-a716-446655440000`
- **Total length**: 36 characters
- **Character set**: Hexadecimal (0-9, a-f) with hyphens in standard UUID format

**Password Reset Token Storage**

Password reset tokens are stored in the `users` table with the following fields:
- `password_reset_token` (UUID, nullable): The reset token value
- `password_reset_token_expires_at` (timestamp, nullable): Token expiration time (default: 1 hour from creation, configurable via `PASSWORD_RESET_TOKEN_TTL_SECONDS`)
- `password_reset_token_used_at` (timestamp, nullable): Timestamp when token was used (null until reset is completed)

**Password Reset Token Lifecycle**

1. **Generation**: When password reset is requested (`POST /auth/password-reset`):
   - Generate a new UUID v4 token
   - Store token in `users.password_reset_token`
   - Set `password_reset_token_expires_at = NOW() + 1 hour` (configurable)
   - Send reset email with token embedded in reset URL

2. **Validation**: When user confirms reset (`POST /auth/password-reset/confirm`):
   - Check token exists and matches `users.password_reset_token`
   - Verify `password_reset_token_expires_at > NOW()`
   - Verify `password_reset_token_used_at IS NULL` (not already used)

3. **Usage**: After successful password reset:
   - Set `password_reset_token_used_at = NOW()`
   - Clear `password_reset_token` (set to NULL) for security
   - Update user password (hashed)
   - Revoke all refresh tokens for the user
   - Increment `users.token_version` (invalidates all access tokens)

**Security Properties**

- **Single-use**: Token is invalidated immediately after use
- **Short-lived**: Default 1-hour expiration (configurable)
- **Cryptographically secure**: UUID v4 uses secure random number generation
- **No plaintext storage**: Token is stored directly (not hashed) but cleared after use
- **Rate limited**: Maximum 3 reset requests per email per hour

**Configuration**

- `PASSWORD_RESET_TOKEN_TTL_SECONDS` (default: 3600): Number of seconds before reset token expires
- Environment variable: `PASSWORD_RESET_TOKEN_TTL_SECONDS=3600`

**Error Codes**

- `PASSWORD_RESET_TOKEN_INVALID`: Token format is invalid (not a valid UUID)
- `PASSWORD_RESET_TOKEN_EXPIRED`: Token has expired (`password_reset_token_expires_at < NOW()`)
- `PASSWORD_RESET_TOKEN_USED`: Token has already been used (`password_reset_token_used_at IS NOT NULL`)

---

#### 5.11.9 API Keys

API keys provide an alternative authentication mechanism for programmatic access, particularly suited for:
- Server-to-server integrations
- CI/CD pipelines
- Long-running automated processes
- Service accounts that don't require user context

**API Key Format**

API keys follow a structured format:
- Prefix: `idh_live_` (production) or `idh_test_` (non-production)
- Secret: 32-character random string (Base62: alphanumeric)
- Full format: `idh_live_<32-char-secret>` (e.g., `idh_live_aB3dEf9GhIjKlMnOpQrStUvWxYz1234`)
- Total length: ~40 characters

**API Key Storage**

- API keys are stored in the `api_keys` table with:
  - `id` (UUID, primary key)
  - `tenant_id` (UUID, FK)
  - `name` (string, user-provided label)
  - `key_hash` (string, bcrypt/argon2 hash of the full key)
  - `prefix` (string, `idh_live_` or `idh_test_`)
  - `scopes` (JSON array, e.g., `["assets:read", "assets:write", "jobs:read"]`)
  - `created_by_user_id` (UUID, FK)
  - `created_at` (timestamp)
  - `last_used_at` (timestamp, nullable)
  - `expires_at` (timestamp, nullable)
  - `revoked_at` (timestamp, nullable)
  - `revoked_reason` (string, nullable)

- **Never store the plaintext key**; only the hash is persisted.
- The full key is shown **once** during creation and cannot be retrieved later.

**API Key Creation**

**Endpoint:** `POST /api/v1/auth/api-keys`

**Request:**
```json
{
  "name": "Production CI/CD Key",
  "scopes": ["assets:read", "assets:write", "jobs:read"],
  "expires_in_days": 365
}
```

**Response:**
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

**Authorization:** Requires `TENANT_ADMIN` or `DATA_PROVIDER` role.

**API Key Usage**

- API keys are used as bearer tokens:
  ```http
  Authorization: Bearer idh_live_aB3dEf9GhIjKlMnOpQrStUvWxYz1234
  ```
- The API gateway:
  1. Extracts the key from the `Authorization` header
  2. Looks up the key by prefix + hash lookup
  3. Validates: not expired, not revoked, scopes match request
  4. Extracts `tenant_id` and `scopes` from the key record
  5. Creates a request context similar to JWT validation (but without `user_id`)

**API Key vs JWT Token: When to Use Each**

| Use Case | Recommended Method | Rationale |
|----------|-------------------|-----------|
| User-facing web UI | JWT (access + refresh tokens) | Short-lived, user context, automatic refresh |
| Mobile apps | JWT (access + refresh tokens) | User context, secure storage in keychain |
| Server-to-server | API keys | Long-lived, no user context needed |
| CI/CD pipelines | API keys | Automated, no user interaction |
| Service accounts | API keys | Persistent, scoped permissions |
| Temporary scripts | JWT (if user-initiated) or API keys | Depends on context |

**API Key Scopes**

Scopes follow the format: `<resource>:<action>` (e.g., `assets:read`, `jobs:write`).

Common scopes:
- `assets:read`, `assets:write`
- `contracts:read`, `contracts:write`
- `datasets:read`, `datasets:write`
- `jobs:read`, `jobs:write`, `jobs:cancel`
- `dq-runs:read`, `dq-runs:write`
- `compliance-runs:read`, `compliance-runs:write`
- `marketplace:read`, `marketplace:write`
- `audit:read`

#### 5.11.9.1 API Key Scopes vs User Role Permissions

**Relationship Model**

API key scopes and user role permissions are **independent** but **complementary**:

- **API keys have scopes**: Fine-grained permissions (e.g., `assets:read`, `assets:write`)
- **Users have roles**: Coarse-grained permissions (e.g., `DATA_PROVIDER`, `TENANT_ADMIN`)
- **Authorization check**: Both scopes (for API keys) and roles (for JWT tokens) are checked during authorization

**Scope-to-Role Mapping**

The following table maps common API key scopes to equivalent user roles:

| API Key Scope | Equivalent User Role(s) | Notes |
|---------------|------------------------|-------|
| `assets:read` | `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR` | Read access to assets |
| `assets:write` | `DATA_PROVIDER`, `TENANT_ADMIN` | Write access to assets |
| `contracts:read` | `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR` | Read access to contracts |
| `contracts:write` | `DATA_PROVIDER`, `TENANT_ADMIN` | Write access to contracts |
| `datasets:read` | `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR` | Read access to datasets |
| `datasets:write` | `DATA_PROVIDER`, `TENANT_ADMIN` | Write access to datasets |
| `jobs:read` | `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR` | Read access to jobs |
| `jobs:write` | `DATA_PROVIDER`, `TENANT_ADMIN` | Write access to jobs |
| `dq-runs:read` | `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR` | Read access to DQ runs |
| `dq-runs:write` | `DATA_PROVIDER`, `TENANT_ADMIN` | Write access to DQ runs |
| `compliance-runs:read` | `DATA_PROVIDER`, `TENANT_ADMIN`, `AUDITOR` | Read access to compliance runs |
| `compliance-runs:write` | `DATA_PROVIDER`, `TENANT_ADMIN` | Write access to compliance runs |
| `marketplace:read` | `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, `AUDITOR` | Read access to marketplace |
| `marketplace:write` | `DATA_PROVIDER`, `TENANT_ADMIN` | Write access to marketplace |
| `audit:read` | `TENANT_ADMIN`, `AUDITOR` | Read access to audit logs |

**Permission Model**

- **API keys are additive**: API keys can have multiple scopes, and all scopes are checked
- **Roles are additive**: Users can have multiple roles, and all roles are checked
- **Scope restrictions**: API keys **cannot exceed** the permissions of the creating user's roles:
  - If a user with `DATA_PROVIDER` role creates an API key, the key cannot have `audit:read` scope (requires `TENANT_ADMIN` or `AUDITOR` role)
  - If a user with `TENANT_ADMIN` role creates an API key, the key can have any scope
- **Scope validation**: When creating an API key, the system validates that the requested scopes are allowed for the creating user's roles
  - Returns `403 Forbidden` with error code `SCOPE_NOT_ALLOWED` if scope exceeds user's role permissions

**Authorization Decision**

For API key requests:
1. **Extract API key** from `Authorization` header
2. **Validate API key**: Check expiration, revocation, tenant membership
3. **Check scopes**: Verify that API key has required scope for the requested operation
4. **Check tenant context**: Verify that API key belongs to the correct tenant
5. **Grant or deny**: If all checks pass, grant access; otherwise, deny with appropriate error code

For JWT token requests:
1. **Extract JWT token** from `Authorization` header
2. **Validate JWT**: Check signature, expiration, tenant membership
3. **Check roles**: Verify that user has required role for the requested operation
4. **Check tenant context**: Verify that user belongs to the correct tenant
5. **Grant or deny**: If all checks pass, grant access; otherwise, deny with appropriate error code

**Example Scenarios**

**Scenario 1: API Key with Limited Scopes**
- User with `TENANT_ADMIN` role creates API key with scopes: `["assets:read", "assets:write"]`
- API key can read and write assets (scopes allow it)
- API key **cannot** read audit logs (no `audit:read` scope)
- Even though the creating user has `TENANT_ADMIN` role, the API key is restricted to its scopes

**Scenario 2: API Key Scope Validation**
- User with `DATA_PROVIDER` role attempts to create API key with scopes: `["assets:read", "audit:read"]`
- System validates: `audit:read` requires `TENANT_ADMIN` or `AUDITOR` role
- User only has `DATA_PROVIDER` role
- **Result**: `403 Forbidden` with error code `SCOPE_NOT_ALLOWED`
- **Error details**: `{"invalid_scopes": ["audit:read"], "required_roles": ["TENANT_ADMIN", "AUDITOR"]}`

**Scenario 3: User Role Change Impact on API Keys**
- User's roles are changed (e.g., `TENANT_ADMIN` → `DATA_PROVIDER`)
- **Existing API keys are NOT automatically revoked**
- **Existing API keys retain their scopes** (scopes are not changed)
- **New API keys** created by the user are restricted to scopes allowed by new roles
- **Recommendation**: Review and revoke API keys if role changes reduce permissions

**API Key Lifecycle**

**Rotation:**
- API keys can be rotated by:
  1. Creating a new key with the same scopes
  2. Updating integrations to use the new key
  3. Revoking the old key
- No automatic rotation; manual process only

**Revocation:**
- **Endpoint:** `DELETE /api/v1/auth/api-keys/{id}` or `PATCH /api/v1/auth/api-keys/{id}` with `{ "revoked": true }`
- Sets `revoked_at = NOW()` and `revoked_reason = "USER_REVOKED"` or `"ADMIN_REVOKED"`
- Revoked keys are immediately invalid; no grace period

**Expiration:**
- API keys can have an optional `expires_at` timestamp
- Expired keys are rejected with `AUTH_UNAUTHORIZED` error
- Keys without `expires_at` do not expire (until manually revoked)

**Rate Limiting for API Keys**

- API keys are subject to the same rate limiting as JWT tokens
- Rate limit buckets use `api_key_id` instead of `user_id`
- Per-API-key limits are typically higher than per-user limits (e.g., 2x tenant limits)

**Security Considerations**

- API keys are **long-lived** and must be protected:
  - Store in secure secrets managers (not in code)
  - Rotate regularly (recommended: annually or on security incident)
  - Monitor usage via `last_used_at`; revoke unused keys
  - Use least-privilege scopes (grant only necessary permissions)
- API keys do **not** support refresh; if compromised, revoke immediately

### 5.12 Rate limiting specification

This section expands on the high-level API rate limiting rules and defines:

- How limits are computed (sliding window vs fixed window).
- Limits per endpoint category and role.
- Response headers for limits.
- Error response format.
- Per-tenant vs global limits.

#### 5.12.1 Model & windows

The platform uses a **token bucket / sliding-window hybrid** for rate limiting:

- Each key (tenant, user, API key, IP) has one or more **buckets** per endpoint category.
- Every request:
  - Consumes **1 token** (or more for expensive operations, see below).
  - Is allowed if tokens remain, otherwise is rejected with HTTP `429 Too Many Requests`.
- Tokens are replenished over time (**sliding window**) instead of in discrete, fixed windows, which avoids traffic spikes at window boundaries.

Conceptually for a bucket:

- Capacity: `max_tokens` (burst size).
- Refill rate: `tokens_per_second` = `max_requests_per_min / 60`.

This behaves like a **sliding window**: the effective limit is enforced continuously rather than in strict 1-minute blocks.

#### 5.12.2 Keys & scoping (per-tenant vs global)

Limits are enforced at multiple levels, in the following order:

1. **Per-tenant buckets** (primary)
   - Key: `tenant_id + endpoint_category`
   - Ensures a single tenant cannot overload shared services.

2. **Per-user/API key buckets** (secondary)
   - Key: `tenant_id + user_id` or `tenant_id + api_key_id`
   - Prevents a single user from exhausting the tenant budget.

3. **Per-IP buckets** (optional, mostly for public/unauthenticated endpoints)
   - Key: `ip_address`
   - Mitigates basic abuse from unauthenticated clients.

4. **Global emergency caps** (rare, operational control)
   - Cluster-wide caps per endpoint category (e.g., DQ runs per second).
   - Only engaged in incident scenarios.

A request is **allowed** only if **all applicable buckets** (tenant, user/API key, and IP where relevant) have available tokens.

#### 5.12.3 Endpoint categories & default limits

Rather than defining limits per-URL only, we group endpoints into **rate limit categories**. Each category has per-tenant and per-user defaults, which can be tuned per plan or environment.

Defaults below are illustrative MVP values.

**(a) Job-creating endpoints (DQ / compliance / semantic)**

Includes:

- `POST /api/v1/dq-runs`
- `POST /api/v1/compliance-runs`
- `POST /api/v1/semantic-runs`
- Any other `POST /.../jobs` that creates background work.

Per-tenant defaults:

| Plan / tenant tier | Burst (per 10s) | Sustained (per min) | Daily cap      |
|--------------------|-----------------|----------------------|----------------|
| Free / Trial       | 10              | 30                   | 1,000 jobs/day |
| Standard           | 20              | 60                   | 10,000 jobs/day|
| Enterprise         | 50              | 150                  | 100,000 jobs/day|

- Model:
  - Burst limit → bucket capacity.
  - Sustained limit → refill rate.
- Daily cap enforced via counters (DB/Redis) and returns 429 when exceeded.

Per-user defaults (within tenant):

- Hard cap of 50% of tenant’s current burst/sustained limit (rounded up).
- Example (Standard plan):
  - Tenant: 20/60.
  - Per-user: 10/30.

**(b) Polling endpoints (jobs, runs)**

Includes:

- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{id}`
- `GET /api/v1/dq-runs/{id}`
- `GET /api/v1/compliance-runs/{id}`

Per-user per-tenant defaults:

- Burst: **30** requests per 10s.
- Sustained: **60** requests per minute.
- Intended to support dashboards and short polling loops without abuse.

**(c) Catalog / read-heavy endpoints**

Includes:

- `GET /api/v1/assets`
- `GET /api/v1/assets/{id}`
- `GET /api/v1/listings`
- `GET /api/v1/listings/{id}`
- Other low-cost reads.

Per-user per-tenant defaults:

- Burst: **50** requests per 10s.
- Sustained: **200** requests per minute.

These are higher because they are relatively cheap and may be used heavily by UI.

**(d) Admin / configuration endpoints**

Includes:

- Asset/contract creation and updates.
- Policy, role, and configuration changes.

Per-user per-tenant defaults:

- Burst: **10** requests per 10s.
- Sustained: **30** requests per minute.

Additionally, these endpoints may enforce stricter IP and device checks.

**(e) File upload endpoints**

Includes:

- `POST /api/v1/files/init` (upload initialization)
- `PUT /api/v1/files/{id}/chunks/{chunk_number}` (chunked uploads)
- `POST /api/v1/files/{id}/complete` (upload finalization)

Per-tenant defaults:

- Burst: **10** requests per 10s.
- Sustained: **30** requests per minute.

**Rationale**: Uploads are resource-intensive; limits prevent abuse while allowing reasonable concurrent uploads.

**(f) Contract validation endpoints**

Includes:

- `POST /api/v1/contracts` (create contract with validation)
- `POST /api/v1/contracts/{id}/validate` (re-validate contract)

Per-tenant defaults:

- Burst: **20** requests per 10s.
- Sustained: **60** requests per minute.

**Rationale**: Contract validation is relatively fast (sync operations), but should be rate-limited to prevent CLI service overload.

**(g) Semantic endpoints**

Includes:

- `GET /id/contract/{id}` (JSON-LD resolution)
- `GET /id/asset/{id}` (JSON-LD resolution)
- `GET /id/dataset/{id}` (JSON-LD resolution)
- `GET /sparql` (SPARQL queries)
- `POST /sparql` (SPARQL queries)

Per-tenant defaults:

- Burst: **50** requests per 10s (same as catalog endpoints).
- Sustained: **200** requests per minute (same as catalog endpoints).

**Rationale**: Semantic endpoints are read-heavy and similar in cost to catalog endpoints.

**(h) GraphQL endpoint**

Includes:

- `POST /graphql` (all GraphQL queries)

Per-tenant defaults:

- Burst: **50** requests per 10s (same as catalog endpoints).
- Sustained: **200** requests per minute (same as catalog endpoints).

**Rationale**: GraphQL is read-only in MVP and similar in cost to catalog endpoints. Rate limits are applied per query, not per field resolved.

**Notes:**

- Limits are **configurable by environment** (dev/stg/prod) and can be overridden per-tenant for enterprise contracts.
- Rate-limiting is applied **per HTTP method + path category**:
  - `POST /dq-runs` (job create)
  - `GET /dq-runs/{id}` (polling)

#### 5.12.4 Rate limit headers

For rate-limited endpoints, the API returns standard headers describing the **tenant-level** limit. User-level and IP-level limits may be stricter, but are not currently surfaced separately.

Headers:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1710000123
```

- `X-RateLimit-Limit`
  - Maximum number of allowed requests in the effective window (e.g., per minute) for this tenant and endpoint category.
  - Represents the **sustained** limit, not the burst capacity.
- `X-RateLimit-Remaining`
  - Number of requests remaining in the current sliding window before a 429 will be returned.
- `X-RateLimit-Reset`
  - Unix timestamp (seconds since epoch) when the window is expected to fully reset / refill, based on current state.

If a request is blocked due to a stricter user-level limit, we may additionally include:

```http
X-RateLimit-Scope: user
```

Similarly, `X-RateLimit-Scope: ip` when an IP bucket is hit.

We also support the `Retry-After` header on 429 responses:

```http
Retry-After: 5
```

- Value: seconds until the **tenant-level** bucket is expected to have capacity.

#### 5.12.5 Rate limit error response format

When a request exceeds any relevant limit, the API responds with:

- HTTP status: `429 Too Many Requests`
- Headers:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining` (typically `0` or very low)
  - `X-RateLimit-Reset`
  - `Retry-After`
  - Optionally `X-RateLimit-Scope` (which bucket was exceeded).

**Body** uses the standard error envelope:

```json
{
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded for this tenant and endpoint category.",
  "http_status": 429,
  "request_id": "req-12345",
  "details": {
    "scope": "tenant",            // or "user", "ip"
    "limit": 60,
    "remaining": 0,
    "reset_at": "2025-11-22T10:00:00Z",
    "endpoint_category": "dq_runs_create"
  }
}
```

For per-tenant daily caps or job concurrency caps, we may use more specific codes:

- `JOB_QUOTA_EXCEEDED`
- `JOB_RATE_LIMITED`

…but they inherit the same structure.

#### 5.12.6 Sliding-window behavior & consistency

Because we use a **sliding window / token bucket**:

- There is no strict alignment to wall-clock minute boundaries.
- If traffic was high in the last 60 seconds, some requests may still be throttled just after the “minute” changes.
- `X-RateLimit-Reset` is a **best-effort estimate** of when the bucket will be refilled enough to accept at least one more request.

For critical flows, clients SHOULD:

- Respect `Retry-After`.
- Consider spreading retries over the remainder of the window instead of retrying in a tight loop.

#### 5.12.7 Observability & tuning

The rate limiter emits metrics such as:

- `rate_limit_requests_total{tenant_id, endpoint_category, outcome="allowed|limited"}`
- `rate_limit_limited_total{tenant_id, endpoint_category}`
- `rate_limit_effective_limit{tenant_id, endpoint_category}`

These metrics are used to:

- Detect mis-sized limits (e.g., frequent 429s for normal usage).
- Tune plan-based defaults and enterprise overrides.
- Identify abuse patterns (spikes of 429s at specific IPs or API keys).

Together, this specification provides:

- Clear per-tenant and per-user limits by endpoint category.
- Standard headers and error bodies for clients to react to.
- A sliding-window model that avoids sharp bursts and supports smooth traffic patterns.

### 5.13 PII scrubbing in logs

The platform MUST ensure that application and infrastructure logs do not contain raw PII, except where strictly necessary and explicitly justified (e.g., limited security/audit fields). This section defines:

- Log scrubbing rules (field-based and regex-based).
- Where scrubbing happens (at source vs centralized).
- Special treatment for audit/event logs.
- Testing strategies to detect PII regressions.

#### 5.13.1 Logging principles

- **Default deny for PII in logs**:
  - Application code MUST NOT log raw dataset contents or user-submitted PII.
  - Only IDs and non-sensitive metadata should appear in routine logs.
- **Structured logging**:
  - All services use structured JSON logs, which allows:
    - field-based redaction, and
    - targeted pattern scanning.
- **Safe logging wrappers**:
  - Direct calls to `console.log`, `print`, or unstructured logging are prohibited in production code.
  - Services use a shared `logger` abstraction that handles redaction.

Examples of fields that are *safe* to log:

- `tenant_id`, `user_id`, `asset_id`, `dataset_id`, `job_id`, `request_id`
- HTTP metadata: method, path (without sensitive query string), status, latency

#### 5.13.2 Field-based scrubbing rules

We treat some fields as **always sensitive** and redact them by name before log emission.

**HTTP headers**

The following headers are **never** logged in clear form (values are replaced with `***REDACTED***` or dropped):

- `Authorization`
- `Cookie`, `Set-Cookie`
- `X-Api-Key`
- `X-Idh-Auth` (or any internal auth headers)
- Any header ending in `-Token` or `-Secret`

**JSON/body fields**

Within structured log contexts (e.g. logging request bodies, job payloads, configuration):

- Keys that match any of these (case-insensitive) are automatically redacted:

  ```text
  password
  passphrase
  secret
  api_key
  access_token
  refresh_token
  id_token
  session_id
  auth_token
  ssn
  social_security_number
  national_id
  tax_id
  card_number
  card_no
  cvv
  cvc
  security_code
  email
  phone
  mobile
  address
  ```

- Redaction behavior:
  - For strings: replace value with `***REDACTED***`.
  - For nested objects/arrays: recursively scan and redact sensitive keys.

**Configuration**

- Field lists live in a shared “redaction config” used by:
  - application loggers,
  - log forwarders (e.g., Fluent Bit / Logstash filters),
  - offline scanners.

#### 5.13.3 Regex-based scrubbing (pattern detection)

In addition to field-name rules, we run **regex-based scrubbing** on log messages to catch PII that slips through (e.g. from concatenated strings or third-party libs).

Examples of patterns (approximate; actual regex may be refined per region):

- **Email addresses**:

  ```regex
  [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}
  ```

- **Phone numbers** (E.164-ish):

  ```regex
  \+?[0-9][0-9\s().-]{7,}
  ```

- **Potential credit card numbers** (16 digits, optional separators):

  ```regex
  (?:\d[ -]*?){13,16}
  ```

- **Government IDs / SSN-like** (US-style, example):

  ```regex
  \d{3}-\d{2}-\d{4}
  ```

When these patterns are detected in non-allowlisted fields:

- The matched substring is replaced with `***REDACTED***`.
- Original value is not stored anywhere else in logging pipeline.

**Note:** actual deployed regex set will be tuned to balance false positives vs. coverage and may be region-specific.

#### 5.13.4 Scrubbing at source vs centralized

We use **defence in depth**:

1. **At source (in-service)**

   - `logger.info/debug/warn/error` automatically:
     - Applies field-based redaction to structured arguments.
     - Applies regex scrubbing to final message string.
   - Services are forbidden (code review / lint) from:
     - Logging raw HTTP request/response bodies containing dataset contents.
     - Logging entire config objects without passing through the redactor.

2. **Centralized pipeline**

   - Log forwarders / collectors (e.g., Fluent Bit, Logstash, or cloud-native log pipelines) apply a **second layer** of scrubbing:
     - Same field-based denylist (headers and JSON keys).
     - Same or simplified regex patterns.
   - This helps catch:
     - Legacy logs from components that predate safe logger adoption.
     - Logs from third-party agents.

3. **Downstream systems**

   - Indexing/search systems (e.g. log search, SIEM) receive **already-scrubbed** logs.
   - Any downstream export (e.g. S3 archive) stores **scrubbed** versions only.

#### 5.13.5 Audit logs vs application logs

Audit logs (`audit_events` table, security event streams) have **different requirements**:

- They MUST support:
  - `user_id`, `tenant_id`, `roles`, `action`, `target_type`, `target_id`, timestamps, IP, user agent.
- They MUST **not** store:
  - Raw dataset values,
  - Sensitive free-form descriptions entered by users (unless explicitly justified).

**Differences in scrubbing:**

- **Application logs**
  - Aggressively scrub PII by fields and regex.
  - Aim for “no PII” beyond stable IDs and coarse metadata (e.g., obfuscated IP if required by policy).

- **Audit logs**
  - Use **schema-based allowlists** rather than regex scrubbing:
    - Each column is typed and documented.
    - Only specific, allowed identifiers are stored (e.g., `user_email` may be allowed or hashed depending on compliance).
  - If certain audit fields contain PII (e.g., full email for security events):
    - Their retention and access are governed by stricter controls (shorter TTL, restricted access roles).
    - No regex rewriting is applied at rest to preserve forensic integrity; instead, content is controlled by schema and retention.

For both log types, PII exposure is further mitigated by:

- Encryption at rest.
- Access controls (only ops/security roles).
- Retention limits per data class.

#### 5.13.6 Testing strategy for PII detection in logs

We use multiple layers of testing and monitoring to ensure PII is not leaking into logs.

1. **Unit tests on logging utilities**

   - For the shared logger and redaction library:
     - Feed sample payloads with synthetic PII:
       - `email = "alice.secret@example.com"`
       - `phone = "+15551234567"`
       - `ssn = "123-45-6789"`
       - `card_number = "4111 1111 1111 1111"`
     - Assert that log outputs:
       - Do **not** contain the original strings.
       - Do contain `***REDACTED***` markers where expected.

2. **Integration tests**

   - End-to-end tests for high-risk flows:
     - Upload dataset with columns named like `email`, `phone`, etc.
     - Trigger DQ/compliance jobs and asset operations.
   - Capture service logs in a test environment and scan for:
     - The synthetic PII markers.
     - Known dummy PII tokens (e.g. special “canary” values).
   - Tests **fail** if any of these appear in raw form.

3. **Log scanning in non-prod environments**

   - Periodic scanners (e.g., daily jobs) run against:
     - Log indices in dev/stage.
     - Searching for PII patterns and canary tokens.
   - Findings generate alerts and block promotion if unresolved.

4. **Runtime monitoring in production**

   - Optional: deploy a “PII sentinel” that:
     - Samples logs from production.
     - Applies stricter PII regex patterns.
     - Raises an incident if suspected PII is detected (e.g., email, SSN-like strings).
   - Alerts include:
     - Service name, logger, environment.
     - Minimal surrounding context (already scrubbed) and pointers to affected log IDs.

5. **Policy & review**

   - Code review checklist includes:
     - “No logging of request/response bodies that may contain tenant data.”
     - “All new logs use the shared structured logger.”
   - Static analysis / lint rules (where feasible) flag:
     - Direct `console.log`/`print` usage in services.
     - Logging of full objects like `req.body` without redaction.

Together, these controls provide:

- Clear, enforceable redaction rules (field and regex-based).
- Defence in depth via both **source-level** and **pipeline-level** scrubbing.
- A separate, schema-controlled approach for audit logs.
- Automated testing and monitoring to catch regressions early.


---

## 6. Privacy Requirements

### 6.1 Compliance-Oriented Design

- Data intake is always accompanied by compliance scanning for personal data.
- The platform does not store data that fails compliance requirements defined by:
  - The platform defaults (e.g., GDPR/LGPD baseline).
  - Tenant-specific stricter policies (future enhancement).

### 6.2 Jurisdiction & Residency

- Each tenant has:
  - A **home region** (e.g., EU, US).
- Data residency:
  - Data files and DB records are stored in the region assigned to the tenant (when technically feasible).
  - Cross-region replication is carefully controlled and documented (future).
- Compliance evaluations:
  - For intake, at minimum: personal-data-related compliance based on the tenant’s legal environment configuration.

### 6.3 Data Minimization

- The platform only persists what is needed:
  - Metadata and contracts.
  - DQ and compliance results (derived/masked).
  - Minimal samples (if explicitly allowed).
- Deletion:
  - When assets or datasets are deleted:
    - Associated data files are removed or archived per tenant’s retention policy.
    - Audit logs remain (for 3 years minimum) but contain no raw PII.

### 6.4 User Rights (Future Extensions)

MVP notes potential future support for:

- Data subject access requests (DSAR).
- Right to erasure / rectification workflows.
- Tenant-level configurations to manage per-regulation obligations.

---

## 7. Threats & Mitigations

### 7.1 Unauthorized Cross-Tenant Data Access

**Threat:** A user from Tenant A accesses an Asset, Dataset, or DQ/Compliance report belonging to Tenant B.

**Mitigations:**

- Every resource row includes `tenant_id`.
- Every query is scoped by `tenant_id` derived from the authenticated token.
- Integration tests for:
  - “Cross-tenant access returns `NOT_FOUND` or `UNAUTHORIZED`.”
- Admin operations (if implemented) are heavily logged and restricted.

### 7.2 Leakage of PII in Logs or Audit Events

**Threat:** Raw personal data appears in logs, which may be stored outside core protections.

**Mitigations:**

- Logging policies:
  - No logging of request bodies containing data files or sample data.
  - Dedicated logic to redact sensitive fields.
- AuditEvent `details_json`:
  - Contains only IDs, counts, categories.
- Static/dynamic checks in code review to prevent direct logging of raw values.

### 7.3 Storing Non-Compliant Data

**Threat:** Data is stored even though it fails compliance checks (e.g., direct identifiers above thresholds, missing legal basis).

**Mitigations:**

- Intake pipeline order:
  - File uploaded → compliance run → only then dataset/asset is finalized.
- If compliance returns `allowed_to_store = false` OR fails:
  - Data is not persisted as a dataset.
  - Job is marked failed.
  - User is notified.
- External/scan-only mode:
  - No datasets created; only compliance results.

### 7.4 Abuse of Marketplace to Exfiltrate Data

**Threat:** Attacker uses marketplace flows to obtain sensitive datasets they are not authorized to see.

**Mitigations:**

- Public pages show only metadata & badges, not full data.
- Entitlements must exist for any download/API access.
- Provider control:
  - Assets must be explicitly flagged/listed as public products.
- Logging:
  - Audit events for:
    - Orders created.
    - Entitlements granted/revoked.
    - Downloads/API access attempts.

### 7.5 API Abuse & DoS

**Threat:** Heavy use of DQ/Compliance APIs leads to resource exhaustion.

**Mitigations:**

- Per-tenant and per-user rate limiting for:
  - `/dq-runs`
  - `/compliance-runs`
  - `/jobs` polling
- Job queue with:
  - Max concurrency per tenant.
  - Backpressure and clear error responses on overload.

### 7.6 Injection Attacks (SQL, SPARQL, CLI)

**Threat:** User-controlled input leads to injection vulnerabilities.

**Mitigations:**

- Use parameterized queries for all DB interactions.
- SPARQL:
  - Limit query complexity and permitted patterns (if possible).
  - Run in dedicated, read-only semantic store with no write capabilities.
- DataContract CLI:
  - Inputs passed as files or structured arguments; no direct shell injection.
  - CLI runs in a sandbox container with minimal privileges and no network access (where feasible).

### 7.7 Supply Chain & Third-Party Tools

**Threat:** Vulnerabilities or malicious code in:
  - DataContract CLI.
  - Great Expectations / Soda.
  - Other libraries.

**Mitigations:**

- Pin versions of critical dependencies.
- Use minimal images for CLIs with:
  - Limited network.
  - Limited filesystem access (only to required temp directories).
- Run regular dependency scanning (e.g., SCA tools).
- Implement timeouts and resource limits at process/container level.

---

## 8. Secure Development & Operations

### 8.1 Secrets Management

- Store secrets (DB passwords, API keys, KMS keys) in:
  - Cloud-native secret manager or vault.
- Avoid secrets in:
  - Code repositories.
  - Plain-text config files.

### 8.2 CI/CD Security

- CI pipelines:
  - Use least privilege tokens to access repos and artifact registries.
  - Run automated tests, linting, and security scans (static analysis, dependency scanning).
- Deployment:
  - Only signed images deployed to production (future).
  - Blue/green or rolling deployment strategy to minimize downtime.

### 8.3 Monitoring & Alerting

- Centralized logging for:
  - API requests (without sensitive payloads).
  - Authentication/authorization failures.
  - DQ/Compliance job failures.
- Metrics:
  - DQ/Compliance run status rates.
  - Rate-limit trigger counts.
- Alerts:
  - Excessive failures or suspicious patterns (e.g., scanning entire marketplace, repeated access denials).

### 8.4 Backups & Recovery

- Regular backups of:
  - Application DB.
  - Audit log store.
  - Semantic store.
- Test restore procedures periodically.
- Backups are encrypted and preserved within data residency requirements.

---

## 9. Open Issues & Future Work

- **Formal IAM Design:**  
  Detailed design of tenants, users, groups, SSO, and fine-grained permissions.

- **Advanced Data Residency / Sovereignty:**  
  Per-region strategic deployment and cross-border data transfer policies.

- **Data Subject Rights Workflows:**  
  Built-in flows to support DSAR, erasure, and portability.

- **Full KYC / Onboarding for Marketplace Participants:**  
  Clear policies and technical controls for verifying sellers and buyers.

- **Advanced Privacy Enhancements:**  
  Differential privacy for aggregated statistics, stronger de-identification methods, and privacy-preserving analytics.

---

This document should be updated as:

- New security requirements emerge.
- The product’s threat landscape changes.
- The platform moves from MVP to production-grade deployments with stronger guarantees.
