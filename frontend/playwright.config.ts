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
  workers: process.env.CI ? 1 : isVisibleRun ? 1 : undefined,
  reporter: isVisibleRun ? [['list'], ['html']] : 'html',
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: process.env.FRONTEND_URL || process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'visible',
      use: {
        ...devices['Desktop Chrome'],
        headless: false,
        launchOptions: { slowMo: 400 },
        video: 'on',
        trace: 'on',
      },
    },
    {
      name: 'setup-auth',
      testMatch: '**/setup/auth-storage.spec.ts',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'chromium-routes',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'e2e/.auth/user.json',
      },
      dependencies: ['setup-auth'],
      testIgnore: ['**/setup/auth-storage.spec.ts'],
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173', // Vite default port
    reuseExistingServer: true, // Reuse if dev server is already running
    timeout: 120 * 1000,
    env: {
      ...process.env,
      VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
      VITE_WS_ENABLED: 'false', // API in Docker often HTTP-only; avoid WS 404 noise in E2E
    },
  },
});
