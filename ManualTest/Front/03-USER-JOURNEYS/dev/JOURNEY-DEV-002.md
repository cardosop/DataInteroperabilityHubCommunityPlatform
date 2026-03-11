# JOURNEY-DEV-002: Obtain API Credentials

**Journey ID**: JOURNEY-DEV-002  
**Title**: Obtain API Credentials  
**Persona**: External Developer  
**Priority**: High  
**Estimated Duration**: 5 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md)

---

## Prerequisites

- [ ] Logged in as **External Developer** (e2e_developer@example.com / TestPass123)

---

## What You Will Do

Create or view API keys for programmatic access.

---

## Steps

| # | Action | What to Do | Expected Result | Pass |
|---|--------|------------|-----------------|------|
| 1 | Navigate to API keys | Go to **Settings** → **API Keys** (or **Developer** → **API Keys**). | API Keys page loads | ☐ |
| 2 | Create key | Click **Create API Key**. Name it (e.g. "Manual Test"). | Key created; secret shown once | ☐ |
| 3 | Copy secret | Copy the secret immediately (it may not be shown again). | Secret saved for use | ☐ |
| 4 | Verify key in list | Key appears in list (masked). | Key listed | ☐ |

---

## Success Criteria

- API key created
- Secret obtainable
- Key usable for API calls

---

## Traceability

- **E2E Spec**: `frontend/e2e/journeys/dev/JOURNEY-DEV-002.spec.ts`
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md)
