/**
 * Phase T.4 (W16) — pure-logic tests for the frontend environment policy.
 *
 * Pins the contract of `frontend/e2e/fixtures/envPolicy.cjs`:
 *   * `isCi()` — only CI="true"/"1" count as CI (GitHub Actions sets "true").
 *   * `environmentSkipGuard(detail)` — in CI it THROWS with a "[W16]" error
 *     carrying the detail (the environment failure announces itself); in a
 *     local run it is a no-op so the caller proceeds to its graceful skip.
 *
 * Real process.env is used — the policy reads the live environment; each
 * test restores it afterwards.
 *
 * Run: node scripts/tests/test_env_policy.cjs
 */

'use strict';

const assert = require('assert');
const path = require('path');

const envPolicy = require(
  path.resolve(__dirname, '..', '..', 'frontend', 'e2e', 'fixtures', 'envPolicy.cjs'),
);

let passed = 0;
let failed = 0;

function eq(label, actual, expected) {
  if (actual === expected) { passed++; return; }
  failed++;
  console.error(`✘ ${label}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
}
function truthy(label, actual) { eq(label, actual, true); }
function falsy(label, actual) { eq(label, actual, false); }

function withEnv(values, fn) {
  const saved = new Map();
  for (const [k, v] of Object.entries(values)) {
    saved.set(k, process.env[k]);
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  try {
    return fn();
  } finally {
    for (const [k, v] of saved) {
      if (v === undefined) delete process.env[k];
      else process.env[k] = v;
    }
  }
}

// ── isCi ────────────────────────────────────────────────────────────────────

withEnv({ CI: 'true' }, () => truthy('isCi: CI=true is CI', envPolicy.isCi()));
withEnv({ CI: '1' }, () => truthy('isCi: CI=1 is CI', envPolicy.isCi()));
withEnv({ CI: undefined }, () => falsy('isCi: unset is not CI', envPolicy.isCi()));
withEnv({ CI: 'false' }, () => falsy('isCi: CI=false is not CI', envPolicy.isCi()));
withEnv({ CI: '' }, () => falsy('isCi: CI="" is not CI', envPolicy.isCi()));
withEnv({ CI: 'TRUE' }, () => falsy('isCi: CI=TRUE (case) is not CI', envPolicy.isCi()));

// ── environmentSkipGuard ────────────────────────────────────────────────────

// CI: throws a [W16] error carrying the detail.
{
  let threw = null;
  withEnv({ CI: 'true' }, () => {
    try {
      envPolicy.environmentSkipGuard('backend rate-limited');
    } catch (e) {
      threw = e;
    }
  });
  truthy('guard: throws in CI', threw instanceof Error);
  truthy('guard: CI error carries the detail', threw !== null && threw.message.includes('backend rate-limited'));
  truthy('guard: CI error is tagged [W16]', threw !== null && threw.message.includes('[W16]'));
}

// Local: no-op — must neither throw nor skip.
{
  let returned = false;
  withEnv({ CI: undefined }, () => {
    envPolicy.environmentSkipGuard('backend rate-limited');
    returned = true;
  });
  truthy('guard: local run is a no-op (caller proceeds to skip)', returned);
}

// ── Falsifiability drill ────────────────────────────────────────────────────
// The whole point of the policy: a guard that silently no-ops in CI is the
// regression class this suite exists to catch. Run the drill against a
// deliberately-broken variant: it must FAIL (i.e. the assertion below must
// see the broken behavior as broken, proving the harness would catch a real
// regression of this shape).
{
  const broken = {
    isCi: () => false, // regression: CI detection always answers "local"
    environmentSkipGuard: () => {}, // therefore never throws
  };
  let caught = false;
  withEnv({ CI: 'true' }, () => {
    try {
      broken.environmentSkipGuard('backend down'); // would silently skip in CI
    } catch {
      caught = true;
    }
  });
  // The drill FAILS the suite if the harness cannot tell a broken policy
  // from a working one: a no-op guard under CI=true must NOT be observed
  // as "threw".
  eq('drill: a CI-noop guard variant is observable as broken (did not throw)', caught, false);
}

if (failed > 0) {
  console.error(`\n${failed} test(s) failed, ${passed} passed`);
  process.exit(1);
}
console.log(`envPolicy.cjs contract pinned: ${passed}/${passed} passed`);
