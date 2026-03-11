# JOURNEY-DEV-003: Use SDK for Asset Operations

**Journey ID**: JOURNEY-DEV-003  
**Title**: Use SDK for Asset Operations  
**Persona**: External Developer  
**Priority**: High  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] API credentials (JOURNEY-DEV-002)
- [ ] Python or JavaScript SDK installed (if available)

---

## What You Will Do

Use SDK to list assets, create asset, or perform asset operations. Verify SDK works.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Install SDK | `pip install datahub-sdk` or npm equivalent. | SDK installed | ☐ |
| 2 | Authenticate | Initialize client with API key/token. | Client authenticated | ☐ |
| 3 | List assets | Call `client.assets.list()` or equivalent. | Assets returned | ☐ |
| 4 | Get asset | Retrieve single asset by ID. | Asset detail returned | ☐ |
| 5 | Create (optional) | Create asset via SDK if supported. | Asset created | ☐ |

---

## Success Criteria

- SDK works
- Asset operations succeed

---

## Note

If SDK is not available, use REST API (JOURNEY-DEV-001) and document.

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dev/JOURNEY-DEV-003.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
