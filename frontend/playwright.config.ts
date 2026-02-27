import { defineConfig, devices } from '@playwright/test';

const isVisibleRun = process.env.E2E_VISIBLE === '1';

/**
 * Playwright E2E Test Configuration
 * Tests run against real backend (docker-compose).
 * Use project "visible" for observable execution (headed + slowMo + list reporter).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: !isVisibleRun,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  timeout: 90000, // Default 90s per test; login + navigation can be slow under parallel E2E load
  // Cap workers when not in CI to reduce backend load (rate limits, postgres connections)
  workers: process.env.CI ? 1 : isVisibleRun ? 1 : 4,
  reporter: isVisibleRun ? [['list'], ['html']] : 'html',
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL:
      process.env.FRONTEND_URL ||
      process.env.PLAYWRIGHT_BASE_URL ||
      (process.env.E2E_WEB_PORT
        ? `http://localhost:${process.env.E2E_WEB_PORT}`
        : 'http://localhost:5173'),
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'setup-auth',
      testMatch: '**/setup/auth-storage.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'chromium',
      timeout: 300000, // 5 min: DPO journeys (contracts, marketplace) can be slow under parallel load
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup-auth'],
      testIgnore: [
        '**/setup/auth-storage.spec.ts',
        // Aggregators import other specs; Playwright forbids test-file imports
        '**/dimensions/*.spec.ts',
        '**/personas/*.spec.ts',
      ],
    },
    {
      name: 'visible',
      use: {
        ...devices['Desktop Chrome'],
        headless: false,
        launchOptions: { slowMo: 400 },
        video: 'retain-on-failure',
        trace: 'retain-on-failure',
        storageState: 'e2e/.auth/user.json',
        timeout: 300000, // 5 min: slowMo (400ms/action) + login; apiWait fix reduces sync-jobs/mappings latency
      },
      dependencies: ['setup-auth'],
      testIgnore: [
        '**/setup/auth-storage.spec.ts',
        '**/dimensions/*.spec.ts',
        '**/personas/*.spec.ts',
      ],
    },
    {
      name: 'chromium-routes',
      timeout: 300000, // 5 min: apiWait on tab click; DPO/marketplace tests need headroom under parallel load
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
  ],

  webServer: {
    command: (() => {
      const portArg = process.env.E2E_WEB_PORT
        ? ` -- --port ${process.env.E2E_WEB_PORT} --strictPort`
        : '';
      // Source .env.e2e (written by global-setup) so Vite proxy targets correct API port (8000 vs 8001)
      return `bash -c 'set -a; [ -f .env.e2e ] && . .env.e2e; set +a; exec npm run dev${portArg}'`;
    })(),
    url: process.env.E2E_WEB_PORT
      ? `http://localhost:${process.env.E2E_WEB_PORT}`
      : 'http://localhost:5173',
    reuseExistingServer: process.env.E2E_FORCE_NEW_SERVER !== '1',
    timeout: 120 * 1000,
    env: {
      ...process.env,
      // VITE_API_BASE_URL: relative for proxy; VITE_PROXY_TARGET from .env.e2e (global-setup)
      VITE_API_BASE_URL: process.env.VITE_API_BASE_URL ?? '/api/v1',
      VITE_PROXY_TARGET: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
      E2E_API_BASE_URL:
        process.env.E2E_API_BASE_URL ??
        (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : undefined) ??
        'http://localhost:8000/api/v1',
      VITE_WS_ENABLED: 'false', // API in Docker often HTTP-only; avoid WS 404 noise in E2E
    },
  },
});
