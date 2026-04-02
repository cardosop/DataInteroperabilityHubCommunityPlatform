/**
 * MVP E2E subset — persona + feature specs for release/mvp-v1.
 * Same webServer / globalSetup / timeouts as playwright.config.ts; only `projects` differ.
 */
import { defineConfig, devices } from '@playwright/test';
import { resolvePlaywrightFrontend } from './src/lib/playwright-frontend-resolve';

const isVisibleRun = process.env.E2E_VISIBLE === '1';
const { baseURL: resolvedFrontendBaseURL, webPort, webServerCheckUrl } =
  resolvePlaywrightFrontend();

/**
 * Explicit allowlist relative to testDir (e2e/). Playwright prepends a recursive glob prefix per pattern.
 */
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
];

export default defineConfig({
  testDir: './e2e',
  fullyParallel: !isVisibleRun,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 60000,
  workers: process.env.CI ? 1 : isVisibleRun ? 1 : 2,
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
      use: { ...devices['Desktop Chrome'] },
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
            testMatch: mvpTestMatch,
          },
        ]
      : []),
  ],

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
});
