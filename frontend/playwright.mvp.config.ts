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
  // Phase 213.B — visitor persona aggregator imports JOURNEY-AUTH-002/004 (zero-mutation).
  // Other auth journeys (001/003) are imported transitively but filtered out by `grep` allowlist.
  'personas/visitor.spec.ts',
  // Phase 213.D — auditor persona (read-only RBAC). Imports JOURNEY-AUD-001..006 transitively
  // but those are filtered out by the `grep` allowlist (no AUD entries) so only the persona
  // RBAC tests in this file actually run.
  'personas/auditor.spec.ts',
  // Phase 213.D — a11y critical pages (WCAG 2 AA). No JOURNEY tags → all admitted by grep.
  'a11y/basic-a11y.spec.ts',
  'a11y/authenticated-pages-a11y.spec.ts',
  'a11y/form-a11y.spec.ts',
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
  'features/lineage.spec.ts',
  // Phase 226 — MVP feature gap closure: features available in staging but previously untested.
  // All use loginAndNavigateToRoute (event-driven auth), real backend, no mocks.
  'features/notifications.spec.ts',
  'features/home.spec.ts',
  'features/observability.spec.ts',
  'features/data-mesh.spec.ts',
  'features/virtualization.spec.ts',
  'features/integrations.spec.ts',
  'features/versioning.spec.ts',
  'features/health.spec.ts',
  // Phase 226 — use-case tests promoted to MVP CI. Only tests verified passing on staging.
  // UC-AM-001, UC-CM-001, UC-DQ-001 removed: form selectors (#key, modal interactions)
  // don't match staging UI — need individual audit before re-promotion.
  'use-cases/assets/UC-AM-002.spec.ts',
  'use-cases/contracts/UC-CM-002.spec.ts',
  'use-cases/compliance/UC-COMP-001.spec.ts',
  'use-cases/marketplace/UC-MKT-001.spec.ts',
  'use-cases/marketplace/UC-MKT-002.spec.ts',
  'use-cases/webhooks/UC-WH-001.spec.ts',
  'use-cases/ux/files-upload.spec.ts',
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
  // Phase 225.4 — meta-test: guards the @quarantine policy regex from drift.
  // Pure Node, no browser, no backend → runs in ~100 ms.
  'meta/quarantine-policy.spec.ts',
  // Phase 225.4 P0.1 — multi-tenancy isolation (security boundary). Zero
  // mutation after cleanup.track() retrofit in 225.4 P0.5.
  'journeys/cross-persona/multi-tenancy-isolation.spec.ts',
  // Phase 225.4 P0.2 — fail-closed gate specs. All three were modernised in
  // P0.5: dropped the E2E_LIFECYCLE_TESTS opt-in guard, switched to persona
  // fixtures, added cleanup.track() for the mutating spec.
  'lifecycle/failed-dq-blocks-publish.spec.ts',
  'lifecycle/rejected-compliance-blocks-order.spec.ts',
  'lifecycle/revoked-entitlement.spec.ts',
  // Phase 225.4 P0.3 — canonical end-to-end value-chain smoke. Modernised
  // in P0.5 with cleanup tracking for the asset + contract it creates.
  'lifecycle/full-value-chain.spec.ts',
  // Phase 225.4 P1.2 — PA-002 (Manage Tenant Lifecycle). The platform-admin
  // persona aggregator imports PA-001 + MPA-* + PA-010 but NOT PA-002, so
  // the grep allowlist alone would admit zero tests for it. Include the
  // spec file directly so the `JOURNEY-PA-002` grep entry has something to
  // match.
  'journeys/pa/JOURNEY-PA-002.spec.ts',
];

export default defineConfig({
  testDir: './e2e',
  testMatch: mvpTestMatch,
  // Persona entry specs import full journey suites. Use an allowlist (NOT grepInvert):
  // match titles with no JOURNEY- tag (persona/feature/dimension/cross-cutting/security)
  // OR titles tagged with one of the promoted journeys.
  // Phase 213.B (zero-mutation): AUTH-002, AUTH-004, TA-001, DE-001.
  // Phase 213.C (mutating + cleanup fixture): AUTH-001, DPO-001, DPO-002, DC-001, CPO-001.
  // Phase 225.4 P0.4 / P1.1 / P1.2 / P1.3 — grep allowlist extended to include:
  //   - AUTH-003 (password reset — aggregator visitor.spec.ts already imports it)
  //   - CPO-002 (Generate Compliance Report; read-only)
  //   - AUD-001..006 (all Auditor journeys; read-only, no cleanup needed)
  //   - PA-001, PA-002 (Platform Admin core flows; tenant + user onboarding)
  // Phase 213.B/C originals kept: AUTH-001/002/004, TA-001, DE-001,
  // DPO-001/002, DC-001, CPO-001.
  grep: /^(?!.*JOURNEY-)|JOURNEY-(AUTH-001|AUTH-002|AUTH-003|AUTH-004|TA-001|DE-001|DPO-001|DPO-002|DC-001|CPO-001|CPO-002|AUD-00[1-6]|PA-00[12])/,
  // Phase 225.4 — quarantine policy. Tests tagged `@quarantine` in their title or
  // `test.describe()` block are excluded from the default MVP run so a single flaky
  // promotion cannot break `main`. They still run (a) via `playwright.mvp.quarantine.config.ts`
  // in the nightly-staging job, and (b) locally when an engineer explicitly removes
  // the `grepInvert` to reproduce. See `e2e/README.md` → "Quarantine policy".
  grepInvert: /@quarantine\b/,
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
