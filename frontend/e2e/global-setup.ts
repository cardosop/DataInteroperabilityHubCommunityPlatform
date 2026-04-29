/**
 * Global Setup for E2E Tests
 * Runs before all tests to ensure backend is available
 */

import * as fs from 'fs';
import * as path from 'path';
import { FullConfig } from '@playwright/test';

function getDefaultApiBase(): string {
  return (
    process.env.E2E_API_BASE_URL ||
    (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
    (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
    'http://localhost:8000/api/v1'
  );
}

/** Alternate port 8000 <-> 8001 for localhost */
function getAlternateApiBase(currentBase: string): string | null {
  try {
    const url = new URL(currentBase);
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
      const port = parseInt(url.port || '80', 10);
      const altPort = port === 8001 ? 8000 : port === 8000 ? 8001 : null;
      if (altPort) {
        url.port = String(altPort);
        return url.toString();
      }
    }
  } catch {
    // intentional: global-setup is best-effort: backend warmup / port-probe / seeding side effects must NOT fail the entire test run on transient errors. The first real test that needs the backend will surface any genuine outage with a clear locator/wait failure.
    // ignore
  }
  return null;
}

async function checkApiReachable(baseUrl: string): Promise<boolean> {
  try {
    const healthUrl = baseUrl.replace(/\/api\/v1\/?$/, '') + '/health/';
    const r = await fetch(healthUrl, { method: 'GET' });
    return r.status !== undefined;
  } catch {
    return false;
  }
}

/**
 * Determine whether the resolved API target is an external (deployed)
 * environment as opposed to a local docker-compose backend. External targets
 * have specific preconditions (E2E_TEST_SECRET injected, user pre-seeded via
 * kubectl) that the local Docker path doesn't share.
 */
function isExternalApiTarget(apiBaseUrl: string): boolean {
  try {
    const host = new URL(apiBaseUrl).hostname;
    return host !== 'localhost' && host !== '127.0.0.1' && host !== '0.0.0.0';
  } catch {
    return false;
  }
}

/**
 * Hard-fail the run early when running against an external target without
 * `E2E_TEST_SECRET`. Multiple specs hit `/api/v1/test/*` endpoints that are
 * gated by the `@require_e2e_token` decorator (hub/apps/api/decorators.py);
 * without the secret each request returns 404 Resource not found. The
 * symptom is several test failures with cryptic 404 bodies appearing tens
 * of minutes into the run — every developer sees the same wall of
 * confusing errors before realising the env var is missing.
 *
 * Fail-fast at setup converts that ~30 min mystery into a one-line
 * actionable error before any worker even starts.
 *
 * Affected specs (non-exhaustive):
 *   - journeys/cross-persona/multi-tenancy-isolation.spec.ts
 *     (`/api/v1/test/ensure-e2e-tenant-switch-setup/`)
 *   - journeys/auth/JOURNEY-AUTH-003.spec.ts Success
 *     (MailHog proxy at `/api/v1/test/mailhog`)
 *   - reset_e2e_auth_rate_limits warmup (already 404-warns soft)
 *
 * Override: set `E2E_ALLOW_MISSING_TEST_SECRET=1` to downgrade to a warning
 * (e.g. for the few specs that don't touch the gated endpoints — currently
 * none of the MVP set, but the override lets a developer probe behaviour
 * without hunting down the secret).
 */
function ensureE2ETestSecretForExternalTarget(apiBaseUrl: string): void {
  if (!isExternalApiTarget(apiBaseUrl)) return;
  const secret = process.env.E2E_TEST_SECRET ?? '';
  if (secret.length > 0) {
    console.log(`✅ E2E_TEST_SECRET present (length=${secret.length}) — token-gated /test/* endpoints reachable`);
    return;
  }
  if (process.env.E2E_ALLOW_MISSING_TEST_SECRET === '1') {
    console.warn(
      '⚠️  E2E_TEST_SECRET is empty AND E2E_ALLOW_MISSING_TEST_SECRET=1 — ' +
        'token-gated /test/* endpoints will return 404. Specs that depend on ' +
        '`/api/v1/test/ensure-e2e-tenant-switch-setup/`, `/api/v1/test/mailhog/*`, ' +
        'or `/api/v1/test/reset-e2e-auth-rate-limits/` will fail or skip.',
    );
    return;
  }
  throw new Error(
    [
      '',
      '❌ E2E_TEST_SECRET is required for runs against external targets but is not set.',
      '',
      `   Resolved API base:        ${apiBaseUrl}`,
      `   PLAYWRIGHT_BASE_URL:      ${process.env.PLAYWRIGHT_BASE_URL ?? '(unset)'}`,
      `   E2E_TEST_SECRET length:   0`,
      '',
      'Why this matters:',
      '   The backend gates `/api/v1/test/*` endpoints on the X-E2E-Token header',
      '   (hub/apps/api/decorators.py @require_e2e_token). Without a matching token,',
      '   every gated request returns "404 Resource not found" — and several MVP',
      '   journeys depend on those endpoints (multi-tenancy isolation setup, MailHog',
      '   proxy for password-reset, auth rate-limit reset between runs).',
      '',
      'How to fix (staging — region us-east-1, profile staging):',
      '   export E2E_TEST_SECRET="$(aws secretsmanager get-secret-value \\',
      '     --profile staging --region us-east-1 \\',
      '     --secret-id staging/hub/e2e \\',
      '     --query SecretString --output text | jq -r .E2E_TEST_SECRET)"',
      '',
      'Or — to bypass this check for a probe run — set:',
      '   E2E_ALLOW_MISSING_TEST_SECRET=1',
      '   (gated tests will fail/skip with their own diagnostics; non-gated ones still run.)',
      '',
    ].join('\n'),
  );
}

async function globalSetup(config: FullConfig) {
  // Ensure test-results exists to reduce ENOENT artifact race (Playwright trace/video writes)
  const outputDir = config.outputDir ?? path.join(process.cwd(), 'test-results');
  fs.mkdirSync(outputDir, { recursive: true });

  // Pure-unit-only runs (e.g. `_guards.spec.ts`) exercise side-effect-free helper
  // logic and do not talk to the backend. Forcing them to wait through the API
  // health-check + docker exec seeding turns a 5-second suite into a 30-second
  // failure when the stack is down. Honor a documented opt-out so those runs
  // can succeed against just the browser. Tests that DO use the network still
  // fail loudly on their own when the API is missing — this only short-circuits
  // setup work, not test-time correctness.
  if (process.env.E2E_SKIP_GLOBAL_SETUP === '1') {
    console.log('ℹ️  E2E_SKIP_GLOBAL_SETUP=1 — skipping API health check + seeding (pure-unit run)');
    return;
  }

  let API_BASE_URL = getDefaultApiBase();

  // Fail-fast precondition for external-target runs. Must run BEFORE the
  // API health-check loop so the developer sees the actionable diagnostic
  // immediately rather than after waiting for staging to respond.
  ensureE2ETestSecretForExternalTarget(API_BASE_URL);
  const maxRetries = 15;
  const retryDelay = 2000;

  // If default (8000) unreachable, try alternate port (8001) — common with docker-compose.test.yml
  if (!process.env.E2E_API_BASE_URL && !(await checkApiReachable(API_BASE_URL))) {
    const alt = getAlternateApiBase(API_BASE_URL);
    if (alt && (await checkApiReachable(alt))) {
      API_BASE_URL = alt;
      process.env.E2E_API_BASE_URL = API_BASE_URL;
      console.log(`Using alternate API port: ${API_BASE_URL}`);
    }
  }

  // Write proxy target for webServer (config loads before globalSetup; webServer needs correct port)
  try {
    const origin = new URL(API_BASE_URL).origin;
    const envPath = path.join(process.cwd(), '.env.e2e');
    fs.writeFileSync(
      envPath,
      `export VITE_PROXY_TARGET=${origin}\nexport E2E_API_BASE_URL=${API_BASE_URL}\n`,
      'utf8'
    );
  } catch {
    // intentional: global-setup is best-effort: backend warmup / port-probe / seeding side effects must NOT fail the entire test run on transient errors. The first real test that needs the backend will surface any genuine outage with a clear locator/wait failure.
    // ignore
  }

  console.log(`Checking backend API availability at ${API_BASE_URL}...`);

  for (let i = 0; i < maxRetries; i++) {
    try {
      const healthResponse = await fetch(`${API_BASE_URL.replace(/\/api\/v1\/?$/, '')}/health/`, {
        method: 'GET',
      });

      if (healthResponse.status !== undefined) {
        console.log('✅ Backend API health endpoint is available');

        const apiResponse = await fetch(`${API_BASE_URL}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: 'test', password: 'test' }),
        });

        if (apiResponse.status !== undefined) {
          console.log('✅ Backend API is available and responding');

          // Auth health gate: verify that a real login can succeed before running
          // 120+ tests that all depend on it. If the auth service is broken (DB down,
          // user doesn't exist, rate-limited), fail fast with a clear message instead
          // of letting every test fail with unclear timeout errors.
          //
          // Single source of truth for credentials: ensureTestUser() (in
          // setup/create-test-user.ts:183-184) consults E2E_ADMIN_EMAIL /
          // E2E_ADMIN_PASSWORD with defaults "e2e_test@example.com" /
          // "TestPass123" — matching hub/apps/users/management/commands/
          // ensure_e2e_user_roles.py:31. This gate MUST use the same defaults
          // so it doesn't cry wolf when local/staging credentials haven't
          // been overridden.
          //
          // E2E_TEST_USER_* aliases are retained only because the
          // `playwright-mvp-quarantine-nightly.yml` workflow sets them from
          // STAGING_E2E_USER_* secrets — honoring both names keeps that path
          // working. Drop this fallback if/when that workflow is updated.
          const E2E_EMAIL =
            process.env.E2E_ADMIN_EMAIL ||
            process.env.E2E_TEST_USER_EMAIL ||
            'e2e_test@example.com';
          const E2E_PASSWORD =
            process.env.E2E_ADMIN_PASSWORD ||
            process.env.E2E_TEST_USER_PASSWORD ||
            'TestPass123';
          try {
            const authCheck = await fetch(`${API_BASE_URL}/auth/login/`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ email: E2E_EMAIL, password: E2E_PASSWORD }),
            });
            if (authCheck.status === 200) {
              console.log('✅ Auth health gate passed — test user can log in');
            } else if (authCheck.status === 429) {
              console.log('⚠️  Auth health gate: rate-limited (429) — tests may be slow but should recover');
            } else if (authCheck.status === 400 || authCheck.status === 401) {
              console.warn(
                `⚠️  Auth health gate: login returned ${authCheck.status}. ` +
                `Test user (${E2E_EMAIL}) may not exist or password may be wrong. ` +
                `Tests that depend on authentication will fail.`
              );
            } else {
              console.warn(`⚠️  Auth health gate: unexpected status ${authCheck.status}`);
            }
          } catch (authErr) {
            console.warn(
              `⚠️  Auth health gate: login request failed — ${authErr instanceof Error ? authErr.message : String(authErr)}`
            );
          }

          process.env.E2E_API_BASE_URL = API_BASE_URL;

          // Skip docker exec seeding for remote APIs (staging/production).
          // Remote environments are seeded via kubectl exec in the CI pipeline.
          const apiHost = new URL(API_BASE_URL).hostname;
          const isRemoteApi = apiHost !== 'localhost' && apiHost !== '127.0.0.1';

          if (isRemoteApi) {
            console.log('ℹ️  Remote API detected — skipping docker exec seeding (seeded via CI pipeline)');
          } else {
            // Ensure E2E persona users (AUDITOR, TENANT_ADMIN, etc.) exist for role-gated journey tests
            try {
              const { execSync } = await import('child_process');
              const port = new URL(API_BASE_URL).port || '8000';
              const container = port === '8001' ? 'hub-test-api' : 'hub-api';
              // Seed default plans first (required for registration; ensure_e2e_user_roles may create users)
              execSync(`docker exec ${container} python hub/manage.py seed_default_plans`, {
                stdio: 'pipe',
                encoding: 'utf8',
              });
              execSync(`docker exec ${container} python hub/manage.py ensure_e2e_user_roles`, {
                stdio: 'pipe',
                encoding: 'utf8',
              });
              console.log('✅ E2E persona users ensured (ensure_e2e_user_roles)');
              try {
                execSync(`docker exec ${container} python hub/manage.py ensure_e2e_subscription`, {
                  stdio: 'pipe',
                  encoding: 'utf8',
                });
                console.log('✅ E2E subscription ensured (ensure_e2e_subscription)');
                try {
                  const authDir = path.join(process.cwd(), 'e2e', '.auth');
                  fs.mkdirSync(authDir, { recursive: true });
                  fs.writeFileSync(
                    path.join(authDir, 'subscription-primed.json'),
                    JSON.stringify({ apiBaseUrl: API_BASE_URL }),
                    'utf8'
                  );
                } catch {
                  // intentional: global-setup is best-effort: backend warmup / port-probe / seeding side effects must NOT fail the entire test run on transient errors. The first real test that needs the backend will surface any genuine outage with a clear locator/wait failure.
                  // Marker is optional; workers fall back to HTTP ensure
                }
              } catch {
                // intentional: global-setup is best-effort: backend warmup / port-probe / seeding side effects must NOT fail the entire test run on transient errors. The first real test that needs the backend will surface any genuine outage with a clear locator/wait failure.
                // Ignore - command may not exist or subscription setup may fail
              }
            } catch {
              // intentional: global-setup is best-effort: backend warmup / port-probe / seeding side effects must NOT fail the entire test run on transient errors. The first real test that needs the backend will surface any genuine outage with a clear locator/wait failure.
              // Ignore if docker/command unavailable (e.g. CI uses different container name)
            }
          }
          return;
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.log(
        `⏳ Waiting for backend API... (attempt ${i + 1}/${maxRetries}) - ${errorMessage}`
      );
      if (i < maxRetries - 1) {
        await new Promise((resolve) => setTimeout(resolve, retryDelay));
      }
    }
  }

  const apiHost = (() => {
    try { return new URL(API_BASE_URL).hostname; } catch { return 'localhost'; }
  })();
  const isRemote = apiHost !== 'localhost' && apiHost !== '127.0.0.1';

  console.error('❌ Backend API is not available after maximum retries.');
  console.error('');
  if (isRemote) {
    console.error(`Remote API at ${API_BASE_URL} is unreachable.`);
    console.error('');
    console.error('Verify that:');
    console.error('  1. The staging deployment is running (check GitHub Actions deploy workflow)');
    console.error('  2. DNS resolves correctly: nslookup ' + apiHost);
    console.error('  3. The API health endpoint responds: curl ' + API_BASE_URL.replace(/\/api\/v1\/?$/, '') + '/health/');
    console.error('  4. Your network can reach the staging environment (VPN, firewall, etc.)');
  } else {
    console.error('E2E tests require a running backend. From repo root, run one of:');
    console.error('  • docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d');
    console.error('  • docker compose up -d');
    console.error('  • docker compose -f docker-compose.test.yml up -d  (API on 8001; set E2E_API_BASE_URL=http://localhost:8001/api/v1)');
    console.error('');
    console.error('Wait for api-service to be healthy, then run: npm run test:e2e');
    console.error('Or use: npm run test:e2e:full  (starts backend automatically)');
  }
  console.error('');

  throw new Error(
    isRemote
      ? `Remote API at ${API_BASE_URL} is unreachable. Ensure the staging deployment is running.`
      : 'Backend API is not available. E2E tests require a running API service. See instructions above.'
  );
}

export default globalSetup;
