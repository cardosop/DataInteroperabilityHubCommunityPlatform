/**
 * MVP E2E — quarantine sub-suite.
 *
 * Runs ONLY tests that are tagged `@quarantine` (in their `test.describe()` or
 * `test()` title). Scheduled by `.github/workflows/playwright-mvp-quarantine-nightly.yml`
 * against the staging environment so flaky-but-promoted specs have a path back
 * into the main MVP run:
 *
 *   @quarantine passes 5 consecutive nightly runs → strip the tag → spec re-joins
 *   the default MVP run.
 *
 * This inherits every setting from `playwright.mvp.config.ts` except the grep
 * filter (which becomes the opposite of the main run) and retries (bumped so
 * known-flaky specs get their rerun budget).
 */
import { defineConfig } from '@playwright/test';
import baseConfig from './playwright.mvp.config';

export default defineConfig({
  ...baseConfig,
  // Only quarantined tests; overrides the base `grep`/`grepInvert` pair.
  grep: /@quarantine\b/,
  grepInvert: undefined,
  // Quarantined specs are, by definition, the flaky ones — give them more retry
  // budget than the main suite (2) so nightly passes aren't noise.
  retries: 3,
});
