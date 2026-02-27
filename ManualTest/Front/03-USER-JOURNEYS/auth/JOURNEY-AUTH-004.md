# JOURNEY-AUTH-004: Unauthenticated User Accesses Public Resources

**Journey ID**: JOURNEY-AUTH-004  
**Title**: Unauthenticated User Accesses Public Resources  
**Persona**: Visitor  
**Priority**: Medium  
**Estimated Duration**: 10 min  
**Source**: [docs/USER_JOURNEYS.md](../../../../docs/USER_JOURNEYS.md#journey-auth-004-unauthenticated-user-accesses-public-resources)

---

## Prerequisites

- [ ] User **not authenticated** (logged out or incognito)
- [ ] Backend and frontend running

---

## Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Open public URL (e.g. `/public`, health, API docs) | Resource loads without requiring authentication | ☐ |
| 2 | Browse public information | No session/token issued | ☐ |
| 3 | Navigate to login link | Login page loads (JOURNEY-AUTH-002) | ☐ |
| 4 | Navigate to register link (if available) | Registration page loads (JOURNEY-AUTH-001) | ☐ |

---

## Success Criteria

- Public resources accessible without auth
- No session/token issued unless user completes login or registration

---

## Error Scenarios

| Scenario | Expected Result | Pass |
|----------|-----------------|------|
| Resource requires auth | 401 or redirect to login | ☐ |
| No public landing | Root redirects to login (documented as intentional) | ☐ |

---

## Traceability

- **Use Case**: [UC-AUTH-004](../../02-USE-CASES/UC-AUTH-004.md)
- **Docs**: [TEST_TRACEABILITY.md](../../../../docs/TEST_TRACEABILITY.md#journey-auth-004-unauthenticated-user-accesses-public-resources)
