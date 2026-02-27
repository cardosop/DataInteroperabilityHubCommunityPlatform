# Alternate Flows: 404, 403, Session

**Version**: 1.0.0  
**Last Updated**: 2026-02-17  
**Estimated Duration**: 30 minutes  
**Traceability**: `frontend/e2e/cross-cutting/404-403-session.spec.ts`

---

## Purpose

Verify error handling and session behavior for unauthenticated access, forbidden routes, and invalid/expired sessions.

---

## Prerequisites

- [ ] Logged in as e2e_test@example.com (or any authenticated user)
- [ ] Browser DevTools open (Network tab)

---

## Steps

### 1. 404 — Not Found

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Navigate to /nonexistent-route | 404 page or "Not found" message | ☐ |
| 2 | Navigate to /assets/invalid-uuid-here | 404 or appropriate error | ☐ |

### 2. 403 — Forbidden (Role Gating)

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 3 | Log in as e2e_consumer@example.com | Success | ☐ |
| 4 | Navigate to /admin (Platform Admin only) | 403 or redirect to login/forbidden | ☐ |
| 5 | Log in as e2e_test@example.com (DPO) | Success | ☐ |
| 6 | Navigate to /admin/audit (Auditor/Admin only) | 403 or appropriate message if DPO lacks permission | ☐ |

### 3. Session — Expired/Invalid

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 7 | Log in, then clear localStorage (DevTools → Application → Local Storage → Clear) | App detects invalid session | ☐ |
| 8 | Navigate to /assets (or any protected route) | Redirect to /login | ☐ |

---

## Sign-Off

| Tester | Date | Alternate Flows Pass |
|--------|------|----------------------|
| | | ☐ |
