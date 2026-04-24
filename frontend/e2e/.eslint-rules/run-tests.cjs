#!/usr/bin/env node
/**
 * Unified runner for every custom ESLint rule in this directory.
 *
 * Discovery: every `*.test.cjs` file sitting alongside a `<name>.cjs`
 * rule file is executed via `require`. Each rule-test file calls
 * `RuleTester.run(...)` at load time (throws on failure) and logs
 * `'<rule>: all rule cases passed'` on success. We aggregate and
 * exit non-zero if any load threw.
 *
 * Used by CI (`npm run lint:rules`) to gate PRs on the custom-rule
 * test suite — same semantics as unit tests for any other module.
 */

'use strict';

const fs = require('node:fs');
const path = require('node:path');

const DIR = __dirname;

const testFiles = fs
  .readdirSync(DIR)
  .filter((f) => f.endsWith('.test.cjs') && !f.startsWith('run-tests.'))
  .sort();

if (testFiles.length === 0) {
  console.error('run-tests.cjs: no *.test.cjs files found in', DIR);
  process.exit(2);
}

let failures = 0;
for (const f of testFiles) {
  try {
    require(path.join(DIR, f));
  } catch (err) {
    failures += 1;
    console.error(`\n✗ ${f} FAILED:\n${err && err.stack ? err.stack : err}`);
  }
}

if (failures > 0) {
  console.error(`\n${failures} of ${testFiles.length} rule-test file(s) failed.`);
  process.exit(1);
}
console.log(`\nAll ${testFiles.length} rule-test file(s) passed.`);
