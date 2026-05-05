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
  // 1 worker for external targets: network latency + shared staging DB; avoid rate-limit cascades.
  // 1 worker when cookie-auth project is selected (Phase 226.F2): cookie-jar state is shared
  // across Playwright contexts on the same browser, so parallel logins race the refresh cycle.
  workers:
    process.argv.includes('--project=chromium-cookie-auth') ||
    process.env.PLAYWRIGHT_PROJECT === 'chromium-cookie-auth'
      ? 1
      : isExternalTarget
        ? 1
        : process.env.CI
          ? 1
          : isVisibleRun
            ? 1
            : 2,
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
    // Phase 226.F4 — `dimensions` project lets contract / drift / network
    // dimension specs run via the main config (`--project=dimensions`)
    // without polluting the chromium project's storageState dependency.
    // No setup-auth dependency: dimension specs hit the API directly.
    {
      name: 'dimensions',
      testMatch: '**/dimensions/*.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    // Phase 226.F2 — cookie-auth project. Forces the apiClient's
    // `_cookieAuthMode` to true at construction (via VITE_COOKIE_AUTH=true,
    // see frontend/src/shared/api/client.ts) so the auth + critical-path
    // subset exercises the cookie code path end-to-end. Workers=1 because
    // cookie-jar state is shared across Playwright contexts on the same
    // browser; parallel mutation races the refresh cycle.
    //
    // testMatch is intentionally narrow: AUTH journeys + the four
    // critical mutation paths (asset/dataset/contract/billing).
    {
      name: 'chromium-cookie-auth',
      testMatch: [
        '**/journeys/auth/**/*.spec.ts',
        '**/journeys/dpo/JOURNEY-DPO-001.spec.ts',
        '**/journeys/dpo/JOURNEY-DPO-002.spec.ts',
        '**/journeys/dpo/JOURNEY-DPO-003.spec.ts',
        '**/journeys/dc/JOURNEY-DC-001.spec.ts',
        '**/journeys/de/JOURNEY-DE-001.spec.ts',
        '**/journeys/ta/JOURNEY-TA-BILLING-UPGRADE.spec.ts',
      ],
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup-auth'],
    },
    // Phase 228.F2.27 — cross-browser Playwright projects
    // (Chromium / Firefox / WebKit).  Opt-in via env var so the
    // default chromium-only run stays fast; CI can enable for
    // nightly cross-browser validation.
    //
    //   E2E_CROSS_BROWSER=1 npx playwright test --project=firefox
    //   E2E_CROSS_BROWSER=1 npx playwright test --project=webkit
    //
    // We deliberately scope the cross-browser matrix to a curated
    // set of high-value specs (the F1 / F2 lineage surfaces) to
    // keep the matrix bounded — matrix-multiplying every spec
    // against three browsers triples runtime for marginal coverage.
    // Phase 250.6.F.5 — extended the cross-browser matrix to
    // cover the asset-creation flow (250.6.B / 250.6.D) and the
    // KYC remediation banner (250.3.A) alongside the original
    // 228.F lineage scope. The matrix is still opt-in via
    // ``E2E_CROSS_BROWSER=1`` so the default chromium-only run
    // stays fast; CI nightly + pre-release sweeps enable it.
    //
    // The ``CROSS_BROWSER_MATCH`` array below is the canonical
    // source of truth for which specs are bound to all three
    // browsers. Editing it in one place keeps Firefox + WebKit
    // aligned and avoids drift between them.
    ...(process.env.E2E_CROSS_BROWSER === '1'
      ? (() => {
          const CROSS_BROWSER_MATCH = [
            // 228.F lineage (existing — kept intact).
            '**/use-cases/marketplace/UC-MKT-LINEAGE-*.spec.ts',
            '**/use-cases/contracts/UC-LIN-FIELD-EDIT-*.spec.ts',
            // 250.6.B — asset type-picker (Phase 250.6.F.5
            // extension): keyboard + radiogroup semantics differ
            // subtly across engines (WebKit's role-tree, Firefox's
            // focus-visible behaviour); cross-browser proves the
            // WCAG 2.1 AA scaffolding actually holds.
            '**/journeys/dpo/asset-type-picker.spec.ts',
            // 250.3.A — KYC remediation banner on the marketplace
            // publish page. The banner's CTA + focus management
            // is the load-bearing UX path for the Phase 250.3
            // gating; drift here would be a customer-visible bug.
            '**/journeys/**/marketplace-kyc-remediation*.spec.ts',
            '**/journeys/**/listing-publish*.spec.ts',
          ];
          return [
            {
              name: 'firefox',
              testMatch: CROSS_BROWSER_MATCH,
              use: {
                ...devices['Desktop Firefox'],
                storageState: 'e2e/.auth/user.json',
              },
              dependencies: ['setup-auth'],
            },
            {
              name: 'webkit',
              testMatch: CROSS_BROWSER_MATCH,
              use: {
                ...devices['Desktop Safari'],
                storageState: 'e2e/.auth/user.json',
              },
              dependencies: ['setup-auth'],
            },
          ];
        })()
      : []),
  ],

  // Skip Vite webServer when targeting an external deployment (staging/production).
  // The frontend is already deployed; starting Vite would conflict with the remote URL.
  ...(isExternalTarget
    ? {}
    : {
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
            // Phase 226.F2 — propagate the cookie-auth flag into Vite so
            // the apiClient pre-seeds `_cookieAuthMode` when the
            // chromium-cookie-auth project runs. No-op when unset.
            ...(process.argv.includes('--project=chromium-cookie-auth') ||
            process.env.VITE_COOKIE_AUTH
              ? { VITE_COOKIE_AUTH: process.env.VITE_COOKIE_AUTH ?? 'true' }
              : {}),
          },
        },
      }),
});
