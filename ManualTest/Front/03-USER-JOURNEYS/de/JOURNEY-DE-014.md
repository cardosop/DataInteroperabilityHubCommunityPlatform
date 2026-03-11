# JOURNEY-DE-014: Create ODPS via API

**Journey ID**: JOURNEY-DE-014  
**Title**: Create ODPS via API  
**Persona**: Data Engineer  
**Priority**: High  
**Estimated Duration**: 15 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-de-014-create-odps-via-api-new)

---

## Prerequisites

- [ ] API credentials (API key or token)
- [ ] Support material: `05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json`
- [ ] API base URL: http://localhost:8001 (test stack)

---

## What You Will Do

Create an ODPS product via REST API (`POST /api/v1/contracts/products/`). Verify response and contract creation.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Obtain token | Log in via `POST /api/v1/auth/login/` with e2e_test@example.com / TestPass123. | Access token returned | ☐ |
| 2 | Call create ODPS | `POST /api/v1/contracts/products/` with Content-Type application/json, body = content of `odps-with-embedded-odcs.json`. | 201 Created; workflow_instance_id or contract IDs returned | ☐ |
| 3 | Poll workflow (if async) | If workflow_instance_id returned, poll `GET /api/v1/workflows/{id}/` until COMPLETED. | Status = COMPLETED | ☐ |
| 4 | Verify contract | `GET /api/v1/contracts/` or retrieve by ID. | ODPS and ODCS contracts present | ☐ |

---

## Success Criteria

- API accepts ODPS payload
- Contract(s) created
- Workflow completes (if async)

---

## cURL Example

```bash
TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"e2e_test@example.com","password":"TestPass123"}' | jq -r '.access')
curl -X POST http://localhost:8001/api/v1/contracts/products/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @ManualTest/Front/05-SUPPORT-MATERIAL/contracts/odps-with-embedded-odcs.json
```

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/de/JOURNEY-DE-014.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
