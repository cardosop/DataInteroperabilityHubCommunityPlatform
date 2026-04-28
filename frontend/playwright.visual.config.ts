/**
 * Phase 226.F6 — Visual regression Playwright config.
 *
 * Standalone config so visual snapshots stay isolated from the main
 * functional test runs. Visual regression is a different gate with
 * different stability characteristics — font rendering, antialiasing,
 * and animation timing all matter for snapshot diffs but are
 * irrelevant for the functional `chromium` project.
 *
 * Why a separate config:
 *   - `expect.toHaveScreenshot` defaults are project-wide (threshold,
 *     animations) and would change behaviour for ALL functional
 *     tests if added to playwright.config.ts.
 *   - Visual specs need a stable headless Chromium pinned to one
 *     viewport; mixing into the regular run would re-record baselines
 *     for every viewport/device-mode the suite uses.
 *   - Snapshots live under
 *     `frontend/e2e/visual/__snapshots__/` so the dedicated config
 *     scopes them out of the functional snapshot lookup.
 *
 * Usage (locally):
 *   npx playwright test --config=playwright.visual.config.ts                    # run / compare
 *   npx playwright test --config=playwright.visual.config.ts --update-snapshots # bump baselines
 *
 * CI: see `.github/workflows/visual-regression.yml`.
 */

import { defineConfig, devices } from '@playwright/test';
import { resolvePlaywrightFrontend } from './src/lib/playwright-frontend-resolve';

process.env.VITE_E2E_TEST = 'true';

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

export default defineConfig({
  testDir: './e2e/visual',
  testMatch: '**/*.spec.ts',
  // Visual snapshots in e2e/visual/__snapshots__ — dedicated path so
  // the functional run's snapshot lookup never collides.
  snapshotDir: './e2e/visual/__snapshots__',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // 2 min default — enough for a full page render including async
  // capability fetches; tests can lower per-test if they want.
  timeout: 120_000,
  workers: 1, // serial: snapshot diffs are sensitive to GPU/font load
  reporter: [['list'], ['html'], ['json', { outputFile: 'test-results/visual-results.json' }]],
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: resolvedFrontendBaseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    navigationTimeout: 30_000,
    // Pin viewport so the snapshot's pixel dimensions are deterministic.
    viewport: { width: 1440, height: 900 },
    // Disable animations system-wide via prefers-reduced-motion.
    colorScheme: 'light',
    // Disable visited-link styling so anchor-tag snapshots don't
    // diff on whether the URL has been visited before.
    contextOptions: {
      reducedMotion: 'reduce',
    },
  },

  // Project-level expectation defaults.
  expect: {
    // 0.2 ratio is moderately tolerant — covers minor antialiasing
    // jitter without missing real layout regressions. Tighten per-spec
    // with `expect(...).toHaveScreenshot(name, { threshold: 0.05 })`
    // when a page is small/stable enough to warrant.
    toHaveScreenshot: {
      threshold: 0.2,
      maxDiffPixelRatio: 0.05,
      // Hide caret animation in inputs.
      animations: 'disabled',
      caret: 'hide',
      // Don't use text-mode — full-image diff catches CSS regressions.
      scale: 'css',
    },
  },

  projects: [
    {
      name: 'setup-auth',
      testMatch: '**/setup/auth-storage.spec.ts',
      testDir: './e2e',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'visual',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup-auth'],
    },
  ],

  // Skip Vite webServer when targeting an external deployment.
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
