# Smoke Test Checklist

**Version**: 1.0.0  
**Last Updated**: 2026-02-17  
**Estimated Duration**: 15 minutes

---

## Purpose

Verify critical paths before running the full manual test suite. If smoke fails, fix environment before proceeding.

---

## Prerequisites

- [ ] Backend running (health returns 200)
- [ ] Frontend running at http://localhost:5173
- [ ] VITE_PROXY_TARGET set correctly

---

## Smoke Steps

| # | Action | Expected Result | Pass |
|---|--------|-----------------|------|
| 1 | Open http://localhost:5173 | App loads, redirects to /login if not authenticated | ☐ |
| 2 | Log in as e2e_test@example.com / TestPass123 | Redirect to home, app shell visible (.app-header, .app-sidebar) | ☐ |
| 3 | Navigate to /assets | Asset list or empty state loads | ☐ |
| 4 | Navigate to /contracts | Contract list or empty state loads | ☐ |
| 5 | Navigate to /marketplace | Marketplace or catalog loads | ☐ |
| 6 | Log out (or clear session) | Redirect to /login | ☐ |
| 7 | Access /public (unauthenticated) | Public resources page loads | ☐ |

---

## Sign-Off

| Tester | Date | Smoke Pass |
|--------|------|------------|
| | | ☐ |
