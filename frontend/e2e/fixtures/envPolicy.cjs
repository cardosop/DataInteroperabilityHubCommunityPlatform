/**
 * W16 (Phase T.4) — environment failure must announce itself.
 *
 * ONE policy for every "service unavailable / not authenticated /
 * dependency missing" branch in the E2E fixtures: in CI the branch RAISES
 * instead of skipping, so a broken environment fails the run loudly; local
 * runs keep the graceful skip so developers are not blocked by their own
 * machine state.
 *
 * Retires the per-call `failOnFallback` option and the "is the backend up?"
 * helpers that accepted any HTTP status: the answer to "can I proceed?" is
 * now binary — CI: no, and that is an error; local: yes, proceed to skip.
 *
 * Written as CommonJS so both the TS specs (esbuild resolves .cjs imports)
 * and the Node-side test harness (scripts/tests) can require it unchanged.
 */

'use strict';

/** True when the run is a CI run (GitHub Actions sets CI=true). */
function isCi() {
  const value = process.env.CI;
  return value === 'true' || value === '1';
}

/**
 * The policy: call at every environment-dependent branch BEFORE the local
 * skip/fallback. In CI this throws (the environment failure announces
 * itself); locally it is a no-op and the caller proceeds to skip.
 *
 * @param {string} detail — human-readable branch description for the CI error.
 */
function environmentSkipGuard(detail) {
  if (isCi()) {
    throw new Error(
      `[W16] environment-dependent condition in CI — failing loudly instead ` +
        `of skipping silently: ${detail}. Local runs keep the graceful skip; ` +
        `CI runs must have a working environment.`
    );
  }
}

module.exports = { isCi, environmentSkipGuard };
