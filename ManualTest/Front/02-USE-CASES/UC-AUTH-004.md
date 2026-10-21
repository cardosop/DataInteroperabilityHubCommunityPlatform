# UC-AUTH-004: Unauthenticated User Accesses Public Resources

**Use Case ID**: UC-AUTH-004  
**Title**: Unauthenticated User Accesses Public Resources  
**Persona**: Visitor  
**Priority**: Medium  
**Source**: [docs/USE_CASES.md](../../docs/USE_CASES.md#uc-auth-004-unauthenticated-user-accesses-public-resources)

---

## Before You Start

1. Complete [00-PREREQUISITES.md](../00-PREREQUISITES.md)
2. Log out or use incognito. Public URLs: http://localhost:3010/health, http://localhost:3010/api/v1/openapi.json, http://localhost:3010/api-docs/

---

## Prerequisites

- [ ] User **not authenticated** (logged out or incognito)
- [ ] Backend and frontend running

---

## Main Flow Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Open public URL (e.g. `/public`, health endpoint, API docs) | Resource loads without requiring authentication | ☐ |
| 2 | Browse public information | No session/token issued | ☐ |
| 3 | Navigate to login link | Login page loads (JOURNEY-AUTH-002) | ☐ |
| 4 | Navigate to register link (if available) | Registration page loads (JOURNEY-AUTH-001) | ☐ |

---

## Alternate Flows

| Scenario | Action | Expected Result | Pass |
|----------|--------|-----------------|------|
| A1: Resource requires auth | Access protected route (e.g. `/assets`) | 401 or redirect to login | ☐ |
| A2: No public landing | Root `/` redirects to login | Documented as intentional | ☐ |

---

## Note

Many deployments restrict all application UI to authenticated users; public access is typically limited to health checks and API docs.

---

## Traceability

- **Journey**: [JOURNEY-AUTH-004](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-004.md)
- **Docs**: [TEST_TRACEABILITY.md](../../docs/TEST_TRACEABILITY.md#uc-auth-004-unauthenticated-user-accesses-public-resources)
