# JOURNEY-DEV-001: Build Custom Integration

**Journey ID**: JOURNEY-DEV-001  
**Title**: Build Custom Integration  
**Persona**: External Developer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-dev-001-build-custom-integration)

---

## Prerequisites

- [ ] Logged in as **External Developer** (e2e_developer@example.com / TestPass123)
- [ ] API credentials (obtain via JOURNEY-DEV-002 first)

---

## What You Will Do

Review API documentation, test authentication, and perform a simple API call (e.g. list assets or contracts).

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Open API docs | Go to **Developer** or **API Docs** (or http://localhost:3010/api-docs/). | OpenAPI/Swagger UI loads | ☐ |
| 2 | Review endpoints | Browse assets, contracts, auth endpoints. | Endpoints documented | ☐ |
| 3 | Obtain token | Use login endpoint or Settings → API Keys. | Token or API key obtained | ☐ |
| 4 | Test API call | Call `GET /api/v1/assets/` or `GET /api/v1/contracts/` with Authorization header. | 200 OK; data returned | ☐ |
| 5 | Verify response | Check JSON structure, pagination if applicable. | Valid response | ☐ |

---

## Success Criteria

- API docs accessible
- Auth works
- API call succeeds

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dev/JOURNEY-DEV-001.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
