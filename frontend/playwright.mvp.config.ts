/**
 * MVP E2E — release/mvp-v1.
 *
 * Uses root-level `testMatch` (Playwright merges into projects that do not override it).
 * Per-project `testMatch` was ignored for the chromium project in Playwright 1.58 in this repo.
 */
import { defineConfig, devices } from '@playwright/test';
import { resolvePlaywrightFrontend } from './src/lib/playwright-frontend-resolve';

// Set VITE_E2E_TEST in the test runner process (not just the Vite webServer).
// Test specs like data-quality.spec.ts check process.env.VITE_E2E_TEST to decide
// whether to skip service-dependent tests. Without this, the env var only reaches
// the Vite dev server child process (via webServer.env below) but not the Playwright
// Node.js process that evaluates test.skip() conditions.
process.env.VITE_E2E_TEST = 'true';

const isVisibleRun = process.env.E2E_VISIBLE === '1';

// When PLAYWRIGHT_BASE_URL points to a non-localhost URL (e.g. meshant-internal.example.com),
// the frontend is already deployed — skip the local Vite webServer and run against
// the remote target directly. Local development workflow is unchanged.
const isExternalTarget = (() => {
  const url = process.env.PLAYWRIGHT_BASE_URL?.trim();
  if (!url) return false;
  try {
    const h = new URL(url).hostname;
    return h !== 'localhost' && h !== '127.0.0.1';
  } catch {
    return false;
  }
})();

const { baseURL: resolvedFrontendBaseURL, webPort, webServerCheckUrl } =
  resolvePlaywrightFrontend();

const mvpTestMatch: string[] = [
  'personas/data-product-owner.spec.ts',
  'personas/data-engineer.spec.ts',
  'personas/data-consumer.spec.ts',
  'personas/tenant-admin.spec.ts',
  'personas/platform-admin.spec.ts',
  'personas/compliance-officer.spec.ts',
  'features/auth.spec.ts',
  'features/contracts.spec.ts',
  'features/assets.spec.ts',
  'features/data-quality.spec.ts',
  'features/compliance.spec.ts',
  'features/marketplace.spec.ts',
  'features/governance.spec.ts',
  'features/files.spec.ts',
  // Phase 213.A — curated module smoke promotion (vetted: ≥2 tests, content assertions, real backend)
  'features/audit.spec.ts',
  'features/datasets.spec.ts',
  'features/webhooks.spec.ts',
  'features/jobs.spec.ts',
  'features/search.spec.ts',
  'features/semantic.spec.ts',
  // Phase 213.A.5 — resilience, security & cross-cutting promotion
  // Audited 2026-04-07: zero docker-exec/MailHog deps, only invalid-login form fills
  // (no entity creation), all use getTestUser/getConsumerTestUser (auto-registered).
  'dimensions/network-failures.spec.ts',
  'dimensions/rate-limit.spec.ts',
  'dimensions/timeout-handling.spec.ts',
  'dimensions/concurrent-operations.spec.ts',
  'cross-cutting/404-403-session.spec.ts',
  'cross-cutting/edge-cases-tests.spec.ts',
  'cross-cutting/failure-scenarios-tests.spec.ts',
  'security/csp-enforce.spec.ts',
];

export default defineConfig({
  testDir: './e2e',
  testMatch: mvpTestMatch,
  // Persona entry specs import full journey suites; keep only persona + feature tests for MVP.
  grepInvert: /JOURNEY-/,
  fullyParallel: !isVisibleRun,
  forbidOnly: !!process.env.CI,
  // External targets (staging) get 1 retry to absorb the rare worker-process
  // recycle that surfaces as "Test not found in worker process" (Playwright
  // diagnostic when a worker crashes mid-suite — usually memory pressure on
  // long suites). Local dev runs keep 0 retries to surface flakiness.
  retries: process.env.CI ? 2 : isExternalTarget ? 1 : 0,
  timeout: 60000,
  workers: isExternalTarget ? 1 : process.env.CI ? 1 : isVisibleRun ? 1 : 2,
  reporter: isVisibleRun
    ? [['list'], ['html'], ['json', { outputFile: 'test-results/results.json' }]]
    : [['html'], ['json', { outputFile: 'test-results/results.json' }]],
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: resolvedFrontendBaseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    navigationTimeout: 30000,
  },

  projects: [
    {
      name: 'setup-auth',
      testMatch: 'setup/auth-storage.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'chromium-mvp',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup-auth'],
    },
    ...(isVisibleRun
      ? [
          {
            name: 'visible-mvp',
            timeout: 180000,
            use: {
              ...devices['Desktop Chrome'],
              headless: false,
              launchOptions: { slowMo: 400 },
              video: 'retain-on-failure' as const,
              trace: 'retain-on-failure' as const,
              storageState: 'e2e/.auth/user.json',
            },
            dependencies: ['setup-auth'],
          },
        ]
      : []),
  ],

  ...(isExternalTarget
    ? {}
    : {
        webServer: {
          command: (() => {
            const portArg = ` -- --port ${webPort} --strictPort`;
            return `bash -c 'set -a; [ -f .env.e2e ] && . .env.e2e; set +a; exec npm run dev${portArg}'`;
          })(),
          url: webServerCheckUrl.replace(/\/$/, '') || webServerCheckUrl,
          reuseExistingServer: process.env.E2E_FORCE_NEW_SERVER !== '1',
          timeout: 120 * 1000,
          env: {
            ...process.env,
            VITE_API_BASE_URL: process.env.VITE_API_BASE_URL ?? '/api/v1',
            VITE_PROXY_TARGET: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
            E2E_API_BASE_URL:
              process.env.E2E_API_BASE_URL ??
              (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : undefined) ??
              'http://localhost:8000/api/v1',
            VITE_WS_ENABLED: 'false',
            VITE_E2E_TEST: 'true',
          },
        },
      }),
});
