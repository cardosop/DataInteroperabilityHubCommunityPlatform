/**
 * Playwright config for accessibility (a11y) tests only.
 * No globalSetup — a11y tests need only the frontend (webServer); no backend API required.
 * Use this config so test:a11y runs in CI without starting the backend.
 */
import { defineConfig, devices } from '@playwright/test';
import { resolvePlaywrightFrontend } from './src/lib/playwright-frontend-resolve';

const { baseURL: resolvedFrontendBaseURL, webPort, webServerCheckUrl } =
  resolvePlaywrightFrontend();

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/a11y/**/*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: 'html',
  use: {
    baseURL: resolvedFrontendBaseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `npm run dev -- --port ${webPort} --strictPort`,
    url: webServerCheckUrl.replace(/\/$/, '') || webServerCheckUrl,
    reuseExistingServer: true,
    timeout: 120 * 1000,
    env: {
      ...process.env,
      VITE_WS_ENABLED: 'false',
    },
  },
});
