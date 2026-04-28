/**
 * Pure-logic tests for scripts/count_fragile_selectors.cjs.
 *
 * Phase 226.F1. The detector's value is only as good as its regex
 * coverage; these tests exercise every selector pattern (testid /
 * class / has-text / getByText / getByRole(name)) and the aggregator
 * branches (empty / single-file / multi-file totals, ratio of zero).
 *
 * Run:
 *   node scripts/tests/test_count_fragile_selectors.cjs
 *
 * No test framework dependency — the runner is a tiny inline harness
 * so the test can run in any Node environment without npm install.
 */

'use strict';

const path = require('path');
const {
  countSelectors,
  aggregate,
  parseArgs,
} = require(path.resolve(__dirname, '..', 'count_fragile_selectors.cjs'));

let passed = 0;
let failed = 0;

function deepEq(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function expectEq(label, actual, expected) {
  if (deepEq(actual, expected)) {
    passed++;
    return;
  }
  failed++;
  console.error(`✘ ${label}`);
  console.error(`  expected: ${JSON.stringify(expected)}`);
  console.error(`  actual:   ${JSON.stringify(actual)}`);
}

function expectTrue(label, actual) {
  if (actual === true) {
    passed++;
    return;
  }
  failed++;
  console.error(`✘ ${label} (got ${actual}, wanted true)`);
}

// ── countSelectors ───────────────────────────────────────────────────────────

(() => {
  const out = countSelectors('');
  expectEq('empty content → all zeros', out, {
    testidLookups: 0,
    classLookups: 0,
    hasTextLookups: 0,
    byTextLookups: 0,
    byRoleWithNameLookups: 0,
    fragileTotal: 0,
    totalLookups: 0,
    fragileRatio: 0,
  });
})();

(() => {
  const out = countSelectors(`await page.getByTestId('asset-form').click();`);
  expectEq('getByTestId is counted', out.testidLookups, 1);
  expectEq('getByTestId has zero fragile', out.fragileTotal, 0);
})();

(() => {
  const out = countSelectors(`await page.locator('[data-testid="asset-row"]').click();`);
  expectEq('data-testid attribute is counted', out.testidLookups, 1);
})();

(() => {
  const out = countSelectors(`await page.locator('.app-sidebar').waitFor();`);
  expectEq('.class lookup is counted as fragile', out.classLookups, 1);
  expectEq('  fragileTotal includes class', out.fragileTotal, 1);
})();

(() => {
  const out = countSelectors(
    `await page.locator(\`button:has-text("Submit"), .submit-btn\`).click();`,
  );
  expectEq('has-text is counted', out.hasTextLookups, 1);
  // The same line ALSO matches the .submit-btn class lookup → 1 class.
  expectEq('  inline class within :has-text source line is counted', out.classLookups, 1);
})();

(() => {
  const out = countSelectors(
    `await page.locator('.error-display, .error-display-title').first();`,
  );
  // A multi-class comma-list still parses as ONE selector pattern.
  expectEq('comma-list class selectors count as 1 lookup', out.classLookups, 1);
})();

(() => {
  const out = countSelectors(
    `await page.getByText('Save').click();\nawait page.getByText('Cancel').click();`,
  );
  expectEq('two getByText → 2 byTextLookups', out.byTextLookups, 2);
  expectEq('  fragileTotal aggregated', out.fragileTotal, 2);
})();

(() => {
  const out = countSelectors(`await page.getByRole('button', { name: 'Save' }).click();`);
  expectEq('getByRole with name → 1 byRoleWithNameLookups', out.byRoleWithNameLookups, 1);
  expectEq('  also fragile', out.fragileTotal, 1);
})();

(() => {
  const src = `
    // mixed file
    await page.getByTestId('foo').click();
    await page.locator('.app-header').click();
    await page.getByText('Submit').click();
    await page.locator('button:has-text("Save")').click();
    await page.getByRole('button', { name: 'Cancel' }).click();
  `;
  const out = countSelectors(src);
  expectEq('mixed file: testid count', out.testidLookups, 1);
  expectEq('mixed file: class count', out.classLookups, 1);
  expectEq('mixed file: has-text count', out.hasTextLookups, 1);
  expectEq('mixed file: byText count', out.byTextLookups, 1);
  expectEq('mixed file: byRole(name) count', out.byRoleWithNameLookups, 1);
  expectEq('mixed file: fragileTotal = 4', out.fragileTotal, 4);
  expectEq('mixed file: totalLookups = 5', out.totalLookups, 5);
  expectTrue(
    'mixed file: ratio = 0.8 (4/5)',
    Math.abs(out.fragileRatio - 0.8) < 1e-9,
  );
})();

(() => {
  // .first() / .click() etc. method calls on a Locator should NOT match
  // the class-lookup pattern (those are method dots, not selector dots).
  const out = countSelectors(
    `await page.locator('button').first().click();\nawait el.first().textContent();`,
  );
  expectEq('Locator method dots are NOT counted as class lookups', out.classLookups, 0);
})();

(() => {
  // String containing `.scope-prefix` inside JS code (e.g. CSS class on a real element)
  // SHOULD match; we trade precision for completeness here, which is fine
  // because the ratchet is comparative across the whole suite.
  const out = countSelectors(`const SELECTOR = '.transformation-pipeline-list-page';`);
  expectEq('quoted CSS class string IS counted', out.classLookups, 1);
})();

// ── aggregate ────────────────────────────────────────────────────────────────

(() => {
  const totals = aggregate([]);
  expectEq('aggregate([]) totals.files = 0', totals.files, 0);
  expectEq('aggregate([]) ratio = 0', totals.fragileRatio, 0);
})();

(() => {
  const totals = aggregate([
    {
      file: 'a.spec.ts',
      testidLookups: 2,
      classLookups: 1,
      hasTextLookups: 0,
      byTextLookups: 0,
      byRoleWithNameLookups: 0,
      fragileTotal: 1,
      totalLookups: 3,
      fragileRatio: 1 / 3,
    },
    {
      file: 'b.spec.ts',
      testidLookups: 0,
      classLookups: 0,
      hasTextLookups: 2,
      byTextLookups: 1,
      byRoleWithNameLookups: 0,
      fragileTotal: 3,
      totalLookups: 3,
      fragileRatio: 1.0,
    },
  ]);
  expectEq('aggregate sums files', totals.files, 2);
  expectEq('aggregate sums testid', totals.testidLookups, 2);
  expectEq('aggregate sums class', totals.classLookups, 1);
  expectEq('aggregate sums fragileTotal', totals.fragileTotal, 4);
  expectEq('aggregate sums totalLookups', totals.totalLookups, 6);
  expectTrue(
    'aggregate ratio = 4/6',
    Math.abs(totals.fragileRatio - 4 / 6) < 1e-9,
  );
})();

// ── parseArgs ────────────────────────────────────────────────────────────────

(() => {
  const opts = parseArgs([]);
  expectEq('default --json is false', opts.json, false);
  expectEq('default --critical is false', opts.critical, false);
  expectEq('default --top is null', opts.top, null);
  expectEq('default explicitPaths empty', opts.explicitPaths, []);
})();

(() => {
  const opts = parseArgs(['--critical', '--json', '--top', '5']);
  expectEq('--critical sets critical', opts.critical, true);
  expectEq('--json sets json', opts.json, true);
  expectEq('--top consumes the next arg as a number', opts.top, 5);
})();

(() => {
  const opts = parseArgs(['frontend/e2e/foo.spec.ts', 'frontend/e2e/bar.spec.ts']);
  expectEq('explicit paths captured', opts.explicitPaths, [
    'frontend/e2e/foo.spec.ts',
    'frontend/e2e/bar.spec.ts',
  ]);
})();

(() => {
  let threw = false;
  try {
    parseArgs(['--top', 'not-a-number']);
  } catch (err) {
    threw = true;
    expectTrue('--top non-numeric throws', /positive integer/.test(err.message));
  }
  expectTrue('  threw at all', threw);
})();

(() => {
  let threw = false;
  try {
    parseArgs(['--unknown']);
  } catch (err) {
    threw = true;
    expectTrue('unknown option throws', /Unknown option/.test(err.message));
  }
  expectTrue('  threw at all', threw);
})();

console.log('');
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
process.exit(failed === 0 ? 0 : 1);
