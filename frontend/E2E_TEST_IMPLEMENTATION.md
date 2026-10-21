# E2E Test Implementation - DoD-2.2

**Date**: 2026-01-26
**Status**: ✅ **COMPLETE**

## Overview

Implemented baseline smoke E2E test for "login → load app shell" as required by DoD-2.2.

## Implementation

### Test: `e2e/login-app-shell.spec.ts`

**Test Cases**:
1. ✅ `user can login and app shell loads correctly` - Main smoke test
2. ✅ `app shell persists across navigation` - Verifies shell stability
3. ✅ `unauthenticated user is redirected to login` - Security verification

### Test Flow

1. **Setup**: Get/create test user (`e2e_test@example.com`)
2. **Navigate**: Go to `/login`
3. **Login**: Fill credentials and submit
4. **Verify Redirect**: Wait for redirect to `/` (home)
5. **Verify App Shell**:
   - Header visible with title, search, user menu
   - Sidebar visible with navigation items
   - Main content area visible
6. **Verify Navigation**: Click nav items and verify shell persists

### Test Infrastructure

- **Framework**: Playwright
- **Browser**: Chromium
- **Fixtures**: `e2e/fixtures/auth.ts` - Auth helpers
- **Setup**: `e2e/setup/create-test-user.ts` - User creation
- **Global Setup**: `e2e/global-setup.ts` - Backend health check

### Configuration Fixes

1. **CORS**: Added `http://localhost:5173` to `CORS_ALLOWED_ORIGINS`
2. **CORS Headers**: Added `x-correlation-id` to allowed headers
3. **Port**: Changed Vite dev server from 3000 to 5173 (Grafana uses 3000)
4. **API Client**: Uses relative URLs (`/api/v1`) to leverage Vite proxy

### Test Results

```
✓ user can login and app shell loads correctly (27.2s)
✓ app shell persists across navigation
✓ unauthenticated user is redirected to login

3 passed (28.1s)
```

## Files Created

- `e2e/login-app-shell.spec.ts` - Main E2E test
- `e2e/fixtures/auth.ts` - Auth test helpers
- `e2e/setup/create-test-user.ts` - User setup
- `e2e/global-setup.ts` - Global test setup
- `playwright.config.ts` - Playwright configuration
- `e2e/README.md` - E2E test documentation

## Notes

- WebSocket connection errors (404) are expected if WebSocket server is not fully configured
- These don't block the smoke test - the test verifies login and app shell loading, which works correctly
- Tests use real backend (no mocks/stubs) as per requirements
