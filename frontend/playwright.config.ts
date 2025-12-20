/**
 * Playwright Configuration
 *
 * Comprehensive end-to-end testing configuration for the Data Interoperability Hub frontend.
 *
 * Features:
 * - Multi-browser testing (Chromium, Firefox, WebKit)
 * - Mobile device emulation
 * - CI/CD integration
 * - Comprehensive test reporting
 * - Environment-specific configuration
 * - Automatic dev server management
 *
 * See https://playwright.dev/docs/test-configuration for full documentation.
 */

import { defineConfig, devices, type PlaywrightTestConfig } from '@playwright/test'

/**
 * Determine if running in CI environment
 */
const isCI = !!process.env.CI

/**
 * Determine test environment
 */
const testEnv = process.env.TEST_ENV || 'development'

/**
 * Base URL for tests
 * Can be overridden with PLAYWRIGHT_BASE_URL environment variable
 */
const baseURL =
  process.env.PLAYWRIGHT_BASE_URL ||
  (testEnv === 'production'
    ? process.env.VITE_APP_URL || 'http://localhost:4173'
    : 'http://localhost:5173')

/**
 * Timeout configurations
 */
const timeouts = {
  // Maximum time one test can run for
  testTimeout: 60 * 1000, // 60 seconds

  // Maximum time to wait for assertion
  expectTimeout: 10 * 1000, // 10 seconds

  // Maximum time for navigation actions
  navigationTimeout: 30 * 1000, // 30 seconds

  // Maximum time for action (click, fill, etc.)
  actionTimeout: 15 * 1000, // 15 seconds
}

/**
 * Retry configuration
 * - CI: Retry failed tests 2 times for flakiness
 * - Local: No retries for faster feedback
 */
const retries = isCI ? 2 : 0

/**
 * Worker configuration
 * - CI: Run tests serially (1 worker) for stability
 * - Local: Use all available CPU cores for speed
 */
const workers = isCI ? 1 : undefined

/**
 * Test directory
 */
const testDir = './playwright/tests'

/**
 * Output directory for test artifacts
 */
const outputDir = './playwright/test-results'

/**
 * Global setup and teardown
 */
const globalSetup = './playwright/global-setup.ts'
const globalTeardown = './playwright/global-teardown.ts'

/**
 * Reporter configuration
 *
 * In CI:
 * - GitHub Actions: Use 'github' reporter for annotations
 * - JUnit: Generate XML for CI/CD integration
 * - HTML: Generate detailed HTML report with attachments
 * - JSON: Generate JSON report for programmatic access
 * - List: Console output
 *
 * Local:
 * - HTML: Detailed HTML report
 * - List: Console output
 * - Line: Compact line-by-line output
 */
const reporters: PlaywrightTestConfig['reporter'] = isCI
  ? [
      [
        'html',
        {
          outputFolder: './playwright/reports/html',
          open: 'never',
          attachments: true, // Include screenshots and videos in HTML report
        },
      ],
      ['junit', { outputFile: './playwright/reports/junit.xml' }],
      ['json', { outputFile: './playwright/reports/results.json' }],
      ['github'],
      ['list'],
    ]
  : [
      [
        'html',
        {
          outputFolder: './playwright/reports/html',
          open: 'never',
          attachments: true,
        },
      ],
      ['list'],
      ['line'],
    ]

/**
 * Shared test settings
 */
const use: PlaywrightTestConfig['use'] = {
  // Base URL for all tests
  baseURL,

  // Collect trace when retrying the failed test
  // In CI, collect traces for all tests for better debugging
  trace: isCI ? 'on' : 'on-first-retry',

  // Screenshot configuration
  // - only-on-failure: Take screenshots only when tests fail
  screenshot: 'only-on-failure',
  // Screenshot options
  // Full page screenshots on failure for better debugging
  // Screenshots are automatically attached to HTML reports

  // Video configuration
  // - retain-on-failure: Keep videos only for failed tests
  video: 'retain-on-failure',
  // Video options
  // Videos are automatically attached to HTML reports
  // Size limit: 10MB per video (Playwright default)

  // Viewport size (can be overridden per project)
  viewport: { width: 1280, height: 720 },

  // Ignore HTTPS errors (useful for local development with self-signed certs)
  ignoreHTTPSErrors: testEnv !== 'production',

  // Accept downloads automatically
  acceptDownloads: true,

  // Geolocation (if needed for tests)
  geolocation: undefined,

  // Permissions (if needed for tests)
  permissions: [],

  // Color scheme (light/dark)
  colorScheme: 'light',

  // Locale for i18n testing
  locale: 'en-US',

  // Timezone
  timezoneId: 'UTC',

  // HTTP credentials (if needed)
  httpCredentials: undefined,

  // Storage state (for authenticated tests)
  storageState: undefined,
}

/**
 * Web server configuration
 * Automatically starts the dev server before running tests
 */
const webServer: PlaywrightTestConfig['webServer'] =
  testEnv === 'development'
    ? {
        command: 'npm run dev',
        url: baseURL,
        reuseExistingServer: !isCI, // Reuse existing server in local development, don't reuse in CI
        timeout: 180 * 1000, // 3 minutes to start (allows time for dependency optimization)
        stdout: 'pipe',
        stderr: 'pipe',
        env: {
          ...process.env,
          NODE_ENV: 'test',
          VITE_DEV_SERVER_PORT: '5173', // Use port 5173 to avoid conflict with Grafana on 3000
        },
      }
    : undefined

/**
 * Browser projects configuration
 *
 * Desktop browsers:
 * - Chromium (Chrome/Edge)
 * - Firefox
 * - WebKit (Safari)
 *
 * Mobile browsers:
 * - Mobile Chrome (Android)
 * - Mobile Safari (iOS)
 */
const projects: PlaywrightTestConfig['projects'] = [
  // Desktop Chromium
  {
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      ...use,
    },
  },

  // Desktop Firefox
  {
    name: 'firefox',
    use: {
      ...devices['Desktop Firefox'],
      ...use,
    },
  },

  // Desktop WebKit (Safari)
  {
    name: 'webkit',
    use: {
      ...devices['Desktop Safari'],
      ...use,
    },
  },

  // Mobile Chrome (Android)
  {
    name: 'Mobile Chrome',
    use: {
      ...devices['Pixel 5'],
      ...use,
    },
  },

  // Mobile Safari (iOS)
  {
    name: 'Mobile Safari',
    use: {
      ...devices['iPhone 12'],
      ...use,
    },
  },

  // Tablet viewport (iPad)
  {
    name: 'Tablet',
    use: {
      ...devices['iPad Pro'],
      ...use,
    },
  },
]

/**
 * Playwright Test Configuration
 */
export default defineConfig({
  // Test directory
  testDir,

  // Output directory
  outputDir,

  // Global setup and teardown
  globalSetup,
  globalTeardown,

  // Timeout configurations
  timeout: timeouts.testTimeout,
  expect: {
    timeout: timeouts.expectTimeout,
  },

  // Test execution
  fullyParallel: true,
  forbidOnly: isCI, // Fail if test.only() is used in CI
  retries,
  workers,

  // Reporter configuration
  reporter: reporters,

  // Shared settings for all projects
  use,

  // Browser projects
  projects,

  // Web server configuration
  webServer,

  // Maximum number of test failures before stopping
  maxFailures: isCI ? 10 : undefined,

  // Global test timeout
  globalTimeout: isCI ? 60 * 60 * 1000 : undefined, // 1 hour in CI

  // Update snapshots (disabled by default, enable with --update-snapshots)
  updateSnapshots: 'missing',

  // Snapshot path template
  snapshotPathTemplate: '{testDir}/{testFileDir}/{testFileName}-snapshots/{arg}{ext}',

  // Test match pattern
  testMatch: /.*\.(spec|test)\.(js|ts|mjs)/,

  // Test ignore pattern
  testIgnore: [
    '**/node_modules/**',
    '**/dist/**',
    '**/.next/**',
    '**/coverage/**',
    '**/playwright/reports/**',
    '**/playwright/test-results/**',
  ],
})
