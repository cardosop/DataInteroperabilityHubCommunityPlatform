/**
 * Phase 226.F1.b — pure-logic tests for the ratchet gate.
 */

'use strict';

const path = require('path');
const { evaluateRatchet, parseArgs } = require(
  path.resolve(__dirname, '..', 'check_fragile_selectors_ratchet.cjs'),
);

let passed = 0;
let failed = 0;
function eq(label, actual, expected) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    passed++;
    return;
  }
  failed++;
  console.error(`✘ ${label}\n  expected: ${JSON.stringify(expected)}\n  actual: ${JSON.stringify(actual)}`);
}
function truthy(label, actual) {
  if (actual === true) { passed++; return; }
  failed++; console.error(`✘ ${label} (got ${actual})`);
}

const baseline = {
  fragileTotal: 1000,
  fragileRatio: 0.25,
  tolerance: { fragileTotalAllowDelta: 0, fragileRatioAllowDelta: 0.005 },
};

// Identical → pass
(() => {
  const r = evaluateRatchet(baseline, { fragileTotal: 1000, fragileRatio: 0.25 });
  truthy('identical totals → passed', r.passed);
  eq('identical totals → no problems', r.problems, []);
  eq('identical totals → fragileTotalDelta', r.fragileTotalDelta, 0);
})();

// Drop → pass (good direction)
(() => {
  const r = evaluateRatchet(baseline, { fragileTotal: 800, fragileRatio: 0.20 });
  truthy('drop → passed', r.passed);
  eq('drop → fragileTotalDelta negative', r.fragileTotalDelta, -200);
})();

// Increase by 1 → fail (strict tolerance 0)
(() => {
  const r = evaluateRatchet(baseline, { fragileTotal: 1001, fragileRatio: 0.25 });
  truthy('+1 fragile → failed', r.passed === false);
  truthy('+1 fragile → fragileTotal problem reported', r.problems.some((p) => p.includes('fragileTotal')));
})();

// Increase within fragileTotal tolerance → pass
(() => {
  const lax = { ...baseline, tolerance: { fragileTotalAllowDelta: 5, fragileRatioAllowDelta: 0.005 } };
  const r = evaluateRatchet(lax, { fragileTotal: 1003, fragileRatio: 0.25 });
  truthy('+3 fragile within tolerance 5 → passed', r.passed);
})();

// Ratio bumps slightly above tolerance → fail
(() => {
  const r = evaluateRatchet(baseline, { fragileTotal: 1000, fragileRatio: 0.260 });
  truthy('ratio +1pp → failed', r.passed === false);
  truthy('ratio problem reported', r.problems.some((p) => p.includes('fragileRatio')));
})();

// Ratio within tolerance (0.005 = 0.5pp) → pass
(() => {
  const r = evaluateRatchet(baseline, { fragileTotal: 1000, fragileRatio: 0.253 });
  truthy('ratio +0.3pp within 0.5pp tolerance → passed', r.passed);
})();

// Ratio drops → pass regardless
(() => {
  const r = evaluateRatchet(baseline, { fragileTotal: 950, fragileRatio: 0.20 });
  truthy('ratio drops → passed', r.passed);
})();

// parseArgs
(() => {
  eq('default', parseArgs([]), { json: false, update: false });
  eq('--json', parseArgs(['--json']), { json: true, update: false });
  eq('--update', parseArgs(['--update']), { json: false, update: true });
  eq('both', parseArgs(['--json', '--update']), { json: true, update: true });
  let threw = false;
  try { parseArgs(['--bogus']); } catch (e) { threw = /Unknown option/.test(e.message); }
  truthy('--bogus throws', threw);
})();

console.log('');
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
process.exit(failed === 0 ? 0 : 1);
