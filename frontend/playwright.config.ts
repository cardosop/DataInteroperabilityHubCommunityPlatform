import { defineConfig, devices } from '@playwright/test';
import { resolvePlaywrightFrontend } from './src/lib/playwright-frontend-resolve';

const isVisibleRun = process.env.E2E_VISIBLE === '1';
const { baseURL: resolvedFrontendBaseURL, webPort, webServerCheckUrl } =
  resolvePlaywrightFrontend();

/**
 * Playwright E2E Test Configuration
 * Tests run against real backend (docker-compose).
 *
 * Projects:
 *   - setup-auth: one-time login to save storageState
 *   - chromium: main test run (headless, shared storageState)
 *   - visible: ONLY runs when E2E_VISIBLE=1 (headed + slowMo for interactive debugging)
 *
 * Performance: a single project runs each test once. Previous config ran 3 identical
 * projects (chromium, visible, chromium-routes) = 3× runtime for zero additional coverage.
 * This config cuts runtime from ~2h to ~35-40min for ~167 tests with 2 workers.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: !isVisibleRun,
  forbidOnly: !!process.env.CI,
  // 0 retries locally: with single-project default and loginUser fast-path, flakiness
  // is rare enough that retries waste more time than they save (~31 retries × 60s = 30 min).
  // 2 retries in CI where infra is less stable and human time is more expensive.
  retries: process.env.CI ? 2 : 0,
  // 60s default: loginUser fast-path (storageState) takes ~5-10s; simple navigate+assert
  // tests finish in 15-30s. Tests with complex flows (activation, file upload) set their own
  // higher timeout via test.setTimeout(). 120s was needed when loginUser always navigated to
  // /login first; the fast-path eliminates that overhead.
  timeout: 60000,
  // 2 workers locally: 4 workers saturate the backend login/capabilities endpoints causing
  // PostgreSQL statement timeouts and rate-limit cascades.  Batch scripts may override.
  workers: process.env.CI ? 1 : isVisibleRun ? 1 : 2,
  reporter: isVisibleRun
    ? [['list'], ['html'], ['json', { outputFile: 'test-results/results.json' }]]
    : [['html'], ['json', { outputFile: 'test-results/results.json' }]],
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: resolvedFrontendBaseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // Default navigation timeout: 30s. Without this, page.goto() inherits the test timeout
    // (60-300s), so a single stalled Vite dev server response consumes the entire test budget.
    navigationTimeout: 30000,
  },

  projects: [
    {
      name: 'setup-auth',
      testMatch: '**/setup/auth-storage.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    // Main test project — runs once per test (not 3×)
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup-auth'],
      testIgnore: [
        '**/setup/auth-storage.spec.ts',
        '**/dimensions/*.spec.ts',
        '**/personas/*.spec.ts',
      ],
    },
    // Interactive debugging project — ONLY when E2E_VISIBLE=1
    ...(isVisibleRun
      ? [
          {
            name: 'visible',
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
            testIgnore: [
              '**/setup/auth-storage.spec.ts',
              '**/dimensions/*.spec.ts',
              '**/personas/*.spec.ts',
            ],
          },
        ]
      : []),
  ],

  webServer: {
    command: (() => {
      const portArg = ` -- --port ${webPort} --strictPort`;
      // Source .env.e2e (written by global-setup) so Vite proxy targets correct API port (8000 vs 8001)
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
});
