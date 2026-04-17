# Security Posture

Meshant applies defense-in-depth principles across every layer of the platform.
This page documents the key security controls for the Meshant platform.

---

## Encryption

### At Rest

All data at rest is encrypted using **AES-256**. This applies to:

- Object storage (uploaded files and dataset payloads)
- Database volumes (metadata, audit events, compliance results)
- Backups and snapshots

Encryption keys are managed through the cloud provider's key management service
with automatic rotation on a 90-day cycle.

### In Transit

All network communication uses **TLS 1.3**. Older TLS versions are rejected at
the load balancer. Internal service-to-service traffic within the cluster also
uses mTLS to prevent lateral movement in the event of a node compromise.

---

## Authentication

Meshant supports two authentication mechanisms:

- **JWT tokens** -- issued by the identity provider after user login. Tokens
  carry the user's tenant membership and role claims. Token lifetime is 15
  minutes with silent refresh.
- **API keys** -- long-lived credentials for service-to-service integrations.
  Each key is scoped to a single [tenant](../concepts/tenants.md) and a defined
  set of permissions. Keys can be rotated or revoked at any time through the
  CLI or API.

See [Users and Roles](../concepts/users-and-roles.md) for details on identity
and role management.

---

## Authorization (RBAC)

Role-based access control is enforced at the API gateway. Every request is
evaluated against the caller's role (`viewer`, `editor`, `admin`, `superadmin`)
and the target resource's tenant. Cross-tenant access is denied by default; only
`superadmin` roles can operate across tenants, and such access is logged in the
[audit trail](audit-trail.md).

---

## Rate Limiting

API endpoints are rate-limited per caller identity to protect against abuse and
denial-of-service attacks. Default limits are:

| Tier | Requests per minute |
|---|---|
| Free | 60 |
| Professional | 300 |
| Enterprise | 1000 (configurable) |

Requests exceeding the limit receive HTTP 429 with a `Retry-After` header.

---

## Input Validation

All API inputs are validated against strict JSON schemas before reaching
business logic. The validation layer rejects:

- Payloads exceeding the maximum size (10 MB for metadata endpoints, 5 GB for
  file uploads via presigned URL)
- Unexpected fields (closed schemas -- additional properties are rejected)
- SQL injection, XSS, and path traversal patterns via a sanitization middleware

---

## Dependency Scanning

The CI/CD pipeline runs **Trivy** on every container image build, scanning for
known CVEs in OS packages and application dependencies. Images with critical or
high-severity vulnerabilities that have available fixes are blocked from
deployment. Unfixable CVEs are tracked in `.trivyignore` with justification
comments.

---

## OWASP Top 10 Coverage

Meshant addresses the OWASP Top 10 (2021) as follows:

| OWASP Category | Mitigation |
|---|---|
| A01 Broken Access Control | RBAC with tenant isolation, fail-closed policy |
| A02 Cryptographic Failures | AES-256 at rest, TLS 1.3 in transit |
| A03 Injection | Input validation, parameterized queries |
| A04 Insecure Design | Threat modeling during design phase |
| A05 Security Misconfiguration | Infrastructure as Code with reviewed defaults |
| A06 Vulnerable Components | Trivy scanning in CI, automated dependency updates |
| A07 Auth Failures | JWT with short lifetime, API key scoping |
| A08 Data Integrity Failures | Signed artifacts, immutable audit trail |
| A09 Logging Failures | Comprehensive audit events, 3-year retention |
| A10 SSRF | Egress filtering, no user-controlled outbound URLs |

## Further Reading

- [Audit Trail](audit-trail.md)
- [Users and Roles concept](../concepts/users-and-roles.md)
- [Vulnerability Disclosure](vulnerability-disclosure.md)
