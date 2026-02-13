# Frontend E2E Tests

End-to-end tests for the frontend application using Playwright.

## Setup

### Prerequisites

1. **Backend API running**: The tests require the backend API to be running **inside Docker** (api-service) so it can resolve `postgres` and other service hostnames. Do not run Django on the host on port 8000 when running E2E, or registration will fail with "could not translate host name postgres".

   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

   Wait for api-service to be healthy (or at least for postgres, redis-\*, and api-service to be up). For the **scheduled ingestion journey** (`e2e/journeys/scheduled-ingestion/`), also start Prefect: `prefect-integration-service`, `prefect-worker-docker`, and ensure `E2E_ENSURE_USER_ROLES=true` so the test user has `DATA_PROVIDER`.

2. **Test user**: A test user is automatically created/verified before tests run
   - Email: `e2e_test@example.com`
   - Password: `TestPass123`
   - **Role-gated routes (e.g. scheduled-ingestions)**: The test user must have the `DATA_PROVIDER` role. Either:
     - Set `E2E_ENSURE_USER_ROLES=true` in `.env.dev` and (re)start api-service so the management command runs at startup, or
     - Run once: `docker compose exec api-service python manage.py ensure_e2e_user_roles` (from repo root; api-service working_dir is `/app/hub`).

3. **MailHog (for JOURNEY-AUTH-003)**: Password reset E2E uses real email; if MailHog is not reachable or email not received, the test is skipped.
   - With **docker-compose.dev.yml**: api-service and worker-service default to `SMTP_HOST=mailhog`, `SMTP_PORT=1025`, `SMTP_USE_TLS=false`. Start mailhog and ensure api-service and worker-service are up so password reset emails reach MailHog.
   - Start: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d mailhog api-service worker-service`
   - MailHog UI/API: `http://localhost:8025` (set `MAILHOG_URL` if different)

4. **Frontend dev server**: Tests will start the dev server automatically (with `VITE_API_BASE_URL` set so the proxy targets the API), or reuse if already running. **If you start the frontend manually**, you must set the API URL so login and API calls hit the backend:
   ```bash
   VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
   ```
   Otherwise the Vite proxy defaults to port 8001 and setup-auth / login will time out waiting for the API response.

## Running Tests

```bash
# Run all E2E tests
npm run test:e2e

# Phase 1 E2E (DoD-2.2, JOURNEY-AUTH-*) against Docker API on port 8000
VITE_API_BASE_URL=http://localhost:8000/api/v1 npx playwright test e2e/login-app-shell.spec.ts e2e/auth-visitor-journeys.spec.ts

# Run specific test
npm run test:e2e -- --grep "user can login"

# Run in headed mode (see browser)
npm run test:e2e:headed

# Run with UI mode (interactive)
npm run test:e2e:ui

# Debug a test
npm run test:e2e:debug

# Run with visible browser and slow motion (for local follow-along)
# Uses E2E_VISIBLE=1 and --project=visible (headed + slowMo + video + trace)
npm run test:e2e:visible

# Run specific journey with visible browser
E2E_VISIBLE=1 npx playwright test --project=visible --reporter=list e2e/journeys/auth/
```

### Full 73 journey run (Phase 13)

1. **Backend up**: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d` (API on port 8000).
2. **Either**:
   - **Let Playwright start the frontend** (recommended): run the command below; Playwright will start `npm run dev` with `VITE_API_BASE_URL=http://localhost:8000/api/v1` and reuse it.
   - **Or** start the frontend yourself and keep it running: `VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev` (separate terminal), then run the same Playwright command; `reuseExistingServer: true` will use it.
3. **Run the full journey suite** (allow ~20–25 min, 1 worker to reduce load on the dev server):
   ```bash
   cd frontend && npx playwright test --project=chromium-routes --workers=1 --timeout=120000 e2e/journeys/ --reporter=list
   ```
4. **If the dev server drops** during the run (ERR_CONNECTION_REFUSED), run in batches: `npm run test:e2e:routes:batch1`, `batch2`, `batch3`, then `e2e/journeys/auth/` and `e2e/journeys/dpo/` separately.

## Test Structure

- `e2e/` - Test files
  - `login-app-shell.spec.ts` - DoD-2.2: Login → Load App Shell smoke test
  - `fixtures/` - Test fixtures and helpers
  - `setup/` - Test setup scripts

## Configuration

- `playwright.config.ts` - Playwright configuration
- Tests run against `http://localhost:5173` (Vite dev server)
- Backend API: set `VITE_API_BASE_URL=http://localhost:8000/api/v1` when API runs in Docker on port 8000
- MailHog expected at `http://localhost:8025` (override via `MAILHOG_URL`)

## Visible Execution (Local Development)

To run E2E tests with a visible browser and slow motion for local follow-along:

1. **Set `E2E_VISIBLE=1`** environment variable
2. **Use `--project=visible`** to enable headed mode, slow motion (400ms), video recording, and trace
3. **Use `--reporter=list`** for readable console output

**Example**:

```bash
# Run all tests with visible browser
E2E_VISIBLE=1 npx playwright test --project=visible --reporter=list

# Run specific test file
E2E_VISIBLE=1 npx playwright test --project=visible --reporter=list e2e/journeys/auth/JOURNEY-AUTH-002.spec.ts

# Using npm script (already configured)
npm run test:e2e:visible
```

**Note**: CI continues to use headless mode and parallel execution. Visible execution is for local development only.

## Notes

- Tests use real backend (no mocks/stubs)
- CORS is configured for `http://localhost:5173`
- WebSocket connection errors (404) are expected if WebSocket server is not fully configured - these don't block the smoke test
